import csv
from itertools import product
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

try:
    from scipy.stats import qmc
    SCIPY_QMC_AVAILABLE = True
except ImportError:
    SCIPY_QMC_AVAILABLE = False

from core.campaign_model import DoEStrategy
from core.design_space import DesignSpace, DesignVariable


def detect_duplicates(
    points: List[Dict[str, float]],
    active_vars: List[DesignVariable],
    tol_norm: float = 1e-4,
) -> Tuple[List[Dict[str, float]], int]:
    """Détecte et élimine les points doublons dans l'espace normalisé [0, 1]^d."""
    unique_points: List[Dict[str, float]] = []
    norm_vectors: List[np.ndarray] = []
    duplicates_count = 0

    for pt in points:
        vec = np.array([var.normalize(pt.get(var.id, var.default_val)) for var in active_vars])

        # Calcul de distance par rapport aux points déjà conservés
        is_dup = False
        for existing in norm_vectors:
            dist = np.linalg.norm(vec - existing)
            if dist < tol_norm:
                is_dup = True
                duplicates_count += 1
                break

        if not is_dup:
            norm_vectors.append(vec)
            unique_points.append(pt)

    return unique_points, duplicates_count


def generate_grid_doe(
    active_vars: List[DesignVariable],
    levels_per_var: Dict[str, int],
) -> List[Dict[str, float]]:
    """Génère un plan factoriel complet (grille régulière)."""
    grid_axes = []
    for var in active_vars:
        n_levels = max(2, levels_per_var.get(var.id, 3))
        axis_vals = np.linspace(var.min_val, var.max_val, n_levels)
        grid_axes.append([(var.id, float(val)) for val in axis_vals])

    points = []
    for combination in product(*grid_axes):
        pt = dict(combination)
        points.append(pt)
    return points


def generate_lhs_doe(
    active_vars: List[DesignVariable],
    n_samples: int = 20,
    seed: int = 42,
) -> List[Dict[str, float]]:
    """Génère un plan Latin Hypercube Sampling (LHS) maximisant le remplissage de l'espace."""
    dim = len(active_vars)
    if dim == 0:
        return []

    if SCIPY_QMC_AVAILABLE:
        sampler = qmc.LatinHypercube(d=dim, seed=seed)
        sample_unit = sampler.random(n=n_samples)
    else:
        # Implémentation NumPy autonome si SciPy non disponible
        rng = np.random.default_rng(seed)
        sample_unit = np.empty((n_samples, dim))
        for j in range(dim):
            bins = rng.permutation(n_samples)
            sample_unit[:, j] = (bins + rng.uniform(0.0, 1.0, size=n_samples)) / n_samples

    points = []
    for i in range(n_samples):
        pt = {}
        for j, var in enumerate(active_vars):
            val_norm = float(sample_unit[i, j])
            val_phys = var.denormalize(val_norm)
            if var.step is not None and var.step > 0:
                val_phys = round(val_phys / var.step) * var.step
            pt[var.id] = float(np.clip(val_phys, var.min_val, var.max_val))
        points.append(pt)

    return points


def generate_random_doe(
    active_vars: List[DesignVariable],
    n_samples: int = 20,
    seed: int = 42,
) -> List[Dict[str, float]]:
    """Génère un échantillonnage aléatoire uniforme reproductible."""
    rng = np.random.default_rng(seed)
    points = []

    for _ in range(n_samples):
        pt = {}
        for var in active_vars:
            val_phys = float(rng.uniform(var.min_val, var.max_val))
            if var.step is not None and var.step > 0:
                val_phys = round(val_phys / var.step) * var.step
            pt[var.id] = float(np.clip(val_phys, var.min_val, var.max_val))
        points.append(pt)

    return points


def import_csv_doe(
    csv_path: Path,
    active_vars: List[DesignVariable],
) -> List[Dict[str, float]]:
    """Importe et filtre des points depuis un fichier CSV externe."""
    points = []
    active_dict = {v.id.lower(): v for v in active_vars}
    name_dict = {v.name.lower(): v for v in active_vars}
    symb_dict = {v.symbol.lower(): v for v in active_vars}

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        if not reader.fieldnames or len(reader.fieldnames) == 1:
            f.seek(0)
            reader = csv.DictReader(f, delimiter=",")

        for row in reader:
            pt = {}
            for col_name, raw_val in row.items():
                if not col_name or raw_val is None or str(raw_val).strip() == "":
                    continue
                k = col_name.strip().lower()
                target_var = active_dict.get(k) or name_dict.get(k) or symb_dict.get(k)
                if target_var:
                    try:
                        pt[target_var.id] = float(raw_val)
                    except ValueError:
                        pass
            if pt:
                points.append(pt)

    return points


def build_doe_campaign(
    strategy: DoEStrategy,
    design_space: DesignSpace,
    strategy_params: Dict[str, Any],
) -> Tuple[List[Dict[str, float]], List[str], Dict[str, Any]]:
    """Point d'entrée unique construisant l'ensemble des points d'une campagne DoE.
    
    Retourne : (points_validés, avertissements_ou_erreurs, métadonnées)
    """
    active_vars = design_space.get_active_variables()
    fixed_vars = design_space.get_fixed_variables()

    if not active_vars and strategy != DoEStrategy.MANUAL:
        return [], ["Aucune variable d'entrée n'est activée pour l'exploration dans le Design Space."], {}

    raw_points: List[Dict[str, float]] = []
    warnings: List[str] = []

    if strategy == DoEStrategy.GRID:
        levels_map = strategy_params.get("levels", {})
        # Calcul prédictif du nombre de points
        total_comb = 1
        for v in active_vars:
            total_comb *= max(2, levels_map.get(v.id, 3))
        if total_comb > 50:
            warnings.append(f"Attention : La grille factorielle demande {total_comb} simulations CFD.")
        raw_points = generate_grid_doe(active_vars, levels_map)

    elif strategy == DoEStrategy.LHS:
        n_samples = int(strategy_params.get("n_samples", 15))
        seed = int(strategy_params.get("seed", 42))
        raw_points = generate_lhs_doe(active_vars, n_samples=n_samples, seed=seed)

    elif strategy == DoEStrategy.RANDOM:
        n_samples = int(strategy_params.get("n_samples", 15))
        seed = int(strategy_params.get("seed", 42))
        raw_points = generate_random_doe(active_vars, n_samples=n_samples, seed=seed)

    elif strategy == DoEStrategy.CSV_IMPORT:
        csv_file = Path(strategy_params.get("csv_path", ""))
        if not csv_file.is_file():
            return [], [f"Fichier CSV introuvable : {csv_file}"], {}
        raw_points = import_csv_doe(csv_file, active_vars)

    elif strategy == DoEStrategy.MANUAL:
        raw_points = strategy_params.get("manual_points", [])

    # Compléter chaque point avec les variables fixes à leur valeur de référence
    complete_points = []
    for pt in raw_points:
        full_pt = dict(pt)
        for fv in fixed_vars:
            if fv.id not in full_pt:
                full_pt[fv.id] = fv.default_val
        complete_points.append(full_pt)

    # Détection et élimination des doublons
    unique_points, n_dups = detect_duplicates(complete_points, active_vars)
    if n_dups > 0:
        warnings.append(f"{n_dups} configuration(s) doublon(s) ont été automatiquement détectées et fusionnées.")

    # Validation géométrique et contraintes physiques
    valid_points = []
    for i, pt in enumerate(unique_points):
        ok, errs = design_space.validate_point(pt)
        if ok:
            valid_points.append(pt)
        else:
            warnings.append(f"Point #{i+1} rejeté : {'; '.join(errs)}")

    metadata = {
        "strategy": strategy.value,
        "n_generated": len(raw_points),
        "n_unique": len(unique_points),
        "n_valid": len(valid_points),
        "n_duplicates": n_dups,
        "seed": strategy_params.get("seed"),
    }

    return valid_points, warnings, metadata
