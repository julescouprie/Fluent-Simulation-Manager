import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from core.case_model import CaseStatus, SimulationCase
from core.design_space import DesignSpace


def extract_kriging_matrices(
    cases: List[SimulationCase],
    active_var_ids: Optional[List[str]] = None,
    only_converged: bool = True,
    include_mock: bool = True,
    normalize_X: bool = False,
    design_space: Optional[DesignSpace] = None,
    test_split_ratio: float = 0.0,
    random_seed: int = 42,
) -> Dict[str, Any]:
    """Extrait et prépare les matrices d'apprentissage X et de cibles Y pour le krigeage.
    
    Effectue :
    - Le filtrage strict des simulations non convergées ou incomplètes (évite d'empoisonner le métamodèle).
    - La séparation X (entrées physiques ou normalisées) et Y (CL, CD, Finesse).
    - L'exportation des métadonnées de mise à l'échelle (scalers).
    - La partition optionnelle Train / Validation indépendante.
    """
    if active_var_ids is None:
        active_var_ids = ["alpha_deg", "camber_m", "camber_p", "thickness_t", "velocity", "chord"]

    # 1. Filtrage rigoureux des données fiables
    filtered_cases: List[SimulationCase] = []
    for c in cases:
        if only_converged and c.status != CaseStatus.TERMINEE_CONVERGEE:
            continue
        if not include_mock and "mock" in c.data_origin.value.lower():
            continue
        if c.results.cl_final is None or c.results.cd_final is None:
            continue
        if np.isnan(c.results.cl_final) or np.isnan(c.results.cd_final):
            continue
        filtered_cases.append(c)

    if not filtered_cases:
        return {
            "success": False,
            "message": "Aucune simulation valide et convergée ne correspond aux filtres d'exportation.",
            "n_samples": 0,
        }

    # 2. Construction de la table brute
    x_rows = []
    y_rows = []
    meta_rows = []

    for c in filtered_cases:
        p_dict = c.parameters.__dict__
        x_row = {v_id: float(p_dict.get(v_id, 0.0)) for v_id in active_var_ids}
        x_rows.append(x_row)

        y_row = {
            "CL": float(c.results.cl_final),
            "CD": float(c.results.cd_final),
            "CL_CD": float(c.results.cl_cd_ratio) if c.results.cl_cd_ratio is not None else 0.0,
        }
        y_rows.append(y_row)

        meta_rows.append({
            "simulation_id": c.id,
            "case_name": c.name,
            "campaign_id": c.campaign_id or "",
            "data_origin": c.data_origin.value,
            "quality_flag": c.results.quality_flag,
            "status": c.status.value,
        })

    df_X = pd.DataFrame(x_rows)
    df_Y = pd.DataFrame(y_rows)
    df_meta = pd.DataFrame(meta_rows)

    scaler_dict: Dict[str, Dict[str, float]] = {}

    # 3. Normalisation min-max [0, 1] optionnelle pour conditionnement optimal du krigeage
    if normalize_X:
        df_X_norm = pd.DataFrame(index=df_X.index)
        for col in df_X.columns:
            if design_space and design_space.get_variable(col):
                v = design_space.get_variable(col)
                min_v, max_v = v.min_val, v.max_val
            else:
                min_v, max_v = float(df_X[col].min()), float(df_X[col].max())

            scaler_dict[col] = {"min": min_v, "max": max_v}
            denom = (max_v - min_v) if abs(max_v - min_v) > 1e-9 else 1.0
            df_X_norm[col] = (df_X[col] - min_v) / denom
        df_X_export = df_X_norm
    else:
        df_X_export = df_X

    # 4. Partitionnement optionnel Train / Test
    n_samples = len(df_X)
    if test_split_ratio > 0.0 and n_samples >= 5:
        rng = np.random.default_rng(random_seed)
        shuffled_indices = rng.permutation(n_samples)
        test_size = max(1, int(round(n_samples * test_split_ratio)))
        test_idx = shuffled_indices[:test_size]
        train_idx = shuffled_indices[test_size:]

        dataset = {
            "success": True,
            "n_samples": n_samples,
            "n_train": len(train_idx),
            "n_test": len(test_idx),
            "X_train": df_X_export.iloc[train_idx],
            "Y_train": df_Y.iloc[train_idx],
            "X_test": df_X_export.iloc[test_idx],
            "Y_test": df_Y.iloc[test_idx],
            "meta_train": df_meta.iloc[train_idx],
            "meta_test": df_meta.iloc[test_idx],
            "is_normalized": normalize_X,
            "scalers": scaler_dict,
        }
    else:
        dataset = {
            "success": True,
            "n_samples": n_samples,
            "X": df_X_export,
            "Y": df_Y,
            "meta": df_meta,
            "is_normalized": normalize_X,
            "scalers": scaler_dict,
        }

    return dataset


def save_kriging_files(dataset: Dict[str, Any], output_dir: Path, prefix: str = "kriging_data") -> List[Path]:
    """Sauvegarde sur disque les fichiers d'entrée/sortie prêts à l'entraînement d'un modèle de krigeage."""
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_files = []

    if "X_train" in dataset:
        p_xtrain = output_dir / f"{prefix}_X_train.csv"
        p_ytrain = output_dir / f"{prefix}_Y_train.csv"
        p_xtest = output_dir / f"{prefix}_X_test.csv"
        p_ytest = output_dir / f"{prefix}_Y_test.csv"

        dataset["X_train"].to_csv(p_xtrain, sep=";", index=False, encoding="utf-8-sig")
        dataset["Y_train"].to_csv(p_ytrain, sep=";", index=False, encoding="utf-8-sig")
        dataset["X_test"].to_csv(p_xtest, sep=";", index=False, encoding="utf-8-sig")
        dataset["Y_test"].to_csv(p_ytest, sep=";", index=False, encoding="utf-8-sig")
        generated_files.extend([p_xtrain, p_ytrain, p_xtest, p_ytest])
    else:
        p_x = output_dir / f"{prefix}_X.csv"
        p_y = output_dir / f"{prefix}_Y.csv"
        p_unified = output_dir / f"{prefix}_unified.csv"

        dataset["X"].to_csv(p_x, sep=";", index=False, encoding="utf-8-sig")
        dataset["Y"].to_csv(p_y, sep=";", index=False, encoding="utf-8-sig")

        # Table combinée (X + Y + Métadonnées)
        df_all = pd.concat([dataset["meta"], dataset["X"], dataset["Y"]], axis=1)
        df_all.to_csv(p_unified, sep=";", index=False, encoding="utf-8-sig")
        generated_files.extend([p_x, p_y, p_unified])

    # Fichier de métadonnées et paramètres de mise à l'échelle
    p_meta = output_dir / f"{prefix}_metadata.json"
    meta_content = {
        "n_samples": dataset.get("n_samples", 0),
        "is_normalized": dataset.get("is_normalized", False),
        "scalers": dataset.get("scalers", {}),
    }
    with open(p_meta, "w", encoding="utf-8") as f:
        json.dump(meta_content, f, indent=2, ensure_ascii=False)
    generated_files.append(p_meta)

    return generated_files
