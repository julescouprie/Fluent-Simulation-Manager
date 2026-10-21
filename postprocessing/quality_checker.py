from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


class QualityFlag(str, Enum):
    VALID = "Validé (Convergé & Stable)"
    WARNING_OSCILLATING = "Avertissement (Oscillations en fin de calcul)"
    WARNING_DRIFTING = "Avertissement (Dérive continue / Non stabilisé)"
    DIVERGED = "Échec (Divergence numérique)"
    INCOMPLETE = "Incomplet (Données manquantes)"


@dataclass
class ConvergenceMetrics:
    """Métriques scientifiques évaluant la convergence asymptotique et la stabilité CFD."""

    is_converged: bool = False
    quality_flag: QualityFlag = QualityFlag.INCOMPLETE
    cl_final: Optional[float] = None
    cd_final: Optional[float] = None
    cl_cd_ratio: Optional[float] = None
    cl_std_last_20: Optional[float] = None
    cd_std_last_20: Optional[float] = None
    cl_relative_change_pct: Optional[float] = None
    evaluation_window: int = 20
    message: str = ""

    def to_dict(self) -> Dict[str, any]:
        return {
            "is_converged": self.is_converged,
            "quality_flag": self.quality_flag.value,
            "cl_final": self.cl_final,
            "cd_final": self.cd_final,
            "cl_cd_ratio": self.cl_cd_ratio,
            "cl_std_last_20": self.cl_std_last_20,
            "cd_std_last_20": self.cd_std_last_20,
            "cl_relative_change_pct": self.cl_relative_change_pct,
            "message": self.message,
        }


def assess_convergence_quality(
    cl_df: pd.DataFrame,
    cd_df: pd.DataFrame,
    window: int = 20,
    tol_std: float = 1.5e-3,          # Écart-type maximal sur les 20 dernières itérations
    tol_rel_change_pct: float = 0.5,   # Variation relative maximale autorisée sur la fin de calcul (%)
) -> ConvergenceMetrics:
    """Analyse rigoureusement l'historique des itérations pour attester de la convergence physique."""
    if cl_df.empty or cd_df.empty:
        return ConvergenceMetrics(
            is_converged=False,
            quality_flag=QualityFlag.INCOMPLETE,
            message="Fichiers de rapport CL ou CD vides ou absents.",
        )

    cl_vals = cl_df["value"].values
    cd_vals = cd_df["value"].values
    n_iters = len(cl_vals)

    cl_final = float(cl_vals[-1])
    cd_final = float(cd_vals[-1])

    # Vérification de non-divergence (NaN, Inf ou valeurs physiquement absurdes)
    if np.isnan(cl_final) or np.isnan(cd_final) or np.isinf(cl_final) or np.isinf(cd_final):
        return ConvergenceMetrics(
            is_converged=False,
            quality_flag=QualityFlag.DIVERGED,
            message="Valeurs NaN ou infinies détectées (Divergence du solveur).",
        )

    if abs(cl_final) > 10.0 or cd_final < -0.1 or cd_final > 5.0:
        return ConvergenceMetrics(
            is_converged=False,
            quality_flag=QualityFlag.DIVERGED,
            cl_final=cl_final,
            cd_final=cd_final,
            message=f"Valeurs aérodynamiques aberrantes (CL={cl_final:.2f}, CD={cd_final:.2f}).",
        )

    ratio = (cl_final / cd_final) if abs(cd_final) > 1e-9 else None

    # Si le nombre d'itérations est inférieur à la fenêtre d'évaluation
    actual_window = min(window, n_iters)
    if actual_window < 5:
        return ConvergenceMetrics(
            is_converged=False,
            quality_flag=QualityFlag.INCOMPLETE,
            cl_final=cl_final,
            cd_final=cd_final,
            cl_cd_ratio=ratio,
            message="Nombre d'itérations insuffisant pour attester de la stabilité.",
        )

    # Analyse statistique sur la fin du calcul
    cl_tail = cl_vals[-actual_window:]
    cd_tail = cd_vals[-actual_window:]

    cl_std = float(np.std(cl_tail))
    cd_std = float(np.std(cd_tail))

    # Variation relative entre le début et la fin de la fenêtre
    cl_start_window = cl_tail[0]
    denom = abs(cl_final) if abs(cl_final) > 1e-4 else 1.0
    rel_change_pct = float(abs(cl_final - cl_start_window) / denom * 100.0)

    # Détection des oscillations et de la dérive
    is_oscillating = (cl_std > tol_std) or (cd_std > tol_std)
    is_drifting = (rel_change_pct > tol_rel_change_pct)

    if is_oscillating:
        flag = QualityFlag.WARNING_OSCILLATING
        msg = f"Oscillations détectées en fin de calcul (std={cl_std:.2e} > tol {tol_std:.2e})."
        is_conv = False
    elif is_drifting:
        flag = QualityFlag.WARNING_DRIFTING
        msg = f"Dérive continue du coefficient CL ({rel_change_pct:.2f}% de variation sur {actual_window} iters)."
        is_conv = False
    else:
        flag = QualityFlag.VALID
        msg = "Convergence asymptotique satisfaite avec stabilité stricte."
        is_conv = True

    return ConvergenceMetrics(
        is_converged=is_conv,
        quality_flag=flag,
        cl_final=cl_final,
        cd_final=cd_final,
        cl_cd_ratio=ratio,
        cl_std_last_20=cl_std,
        cd_std_last_20=cd_std,
        cl_relative_change_pct=rel_change_pct,
        evaluation_window=actual_window,
        message=msg,
    )
