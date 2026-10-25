from pathlib import Path
import re
import sys
from typing import Optional, Tuple
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg
import numpy as np
import pandas as pd

from core.case_model import PhysicalParameters, SimulationResults
from .quality_checker import assess_convergence_quality, QualityFlag


def read_report(path: Path) -> pd.DataFrame:
    """Lit un fichier de rapport d'itérations Fluent (cl_test.txt, cd_test.txt)."""
    if not path.exists():
        return pd.DataFrame(columns=["iteration", "value"])
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith(("#", ";", "((")):
            continue
        nums = re.findall(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?", s)
        if len(nums) >= 2:
            try:
                rows.append((float(nums[0]), float(nums[-1])))
            except ValueError:
                pass
    if not rows:
        raise ValueError(f"Aucune donnée d'itération trouvée dans {path.name}")
    df = (
        pd.DataFrame(rows, columns=["iteration", "value"])
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
        .drop_duplicates("iteration", keep="last")
        .sort_values("iteration")
    )
    return df


def read_pressure(path: Path) -> Optional[pd.DataFrame]:
    """Lit et normalise le fichier airfoil_pressure.csv exporté par Fluent."""
    if not path.exists():
        return None

    df = None
    for sep in [",", ";", r"\s+", r"\t"]:
        try:
            temp = pd.read_csv(path, sep=sep, engine="python", comment="#")
            if temp.shape[1] >= 3:
                df = temp
                break
        except Exception:
            pass

    if df is None:
        raise ValueError(f"Fichier de pression illisible : {path.name}")

    norm = {re.sub(r"[^a-z0-9]", "", str(c).lower()): c for c in df.columns}

    def col(*names):
        for n in names:
            k = re.sub(r"[^a-z0-9]", "", n.lower())
            if k in norm:
                return norm[k]
        return None

    x = col("x-coordinate", "x coordinate", "x")
    y = col("y-coordinate", "y coordinate", "y")
    p = col("pressure", "static-pressure")
    pt = col("total-pressure", "total pressure", "absolute-total-pressure")

    if x is None or p is None:
        raise ValueError("Colonnes x-coordinate et pressure introuvables dans airfoil_pressure.csv")

    out = pd.DataFrame({
        "x_m": pd.to_numeric(df[x], errors="coerce"),
        "pressure_Pa": pd.to_numeric(df[p], errors="coerce"),
    })
    if y:
        out["y_m"] = pd.to_numeric(df[y], errors="coerce")
    if pt:
        out["total_pressure_Pa"] = pd.to_numeric(df[pt], errors="coerce")

    return out.replace([np.inf, -np.inf], np.nan).dropna(subset=["x_m", "pressure_Pa"]).sort_values("x_m")


def plot_convergence(df: pd.DataFrame, label: str, output_path: Path) -> None:
    if df.empty:
        return
    fig = Figure(figsize=(7, 4))
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot(df.iteration, df.value, linewidth=1.5, color="#1f77b4")
    ax.set(xlabel="Itération", ylabel=label, title=f"Convergence de {label}")
    ax.grid(True, linestyle="--", alpha=0.5)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)


def plot_distribution(x: pd.Series, y: pd.Series, label: str, output_path: Path, invert: bool = False) -> None:
    fig = Figure(figsize=(7, 4.2))
    canvas = FigureCanvasAgg(fig)
    ax = fig.add_subplot(111)
    ax.plot(x, y, "o-", markersize=2, linewidth=1.2, color="#0055aa")
    ax.set(xlabel="x / c", ylabel=label, title=f"Distribution de {label} sur le profil")
    ax.grid(True, linestyle="--", alpha=0.5)
    if invert:
        ax.invert_yaxis()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)


def process_case_results(case_dir: Path, params: PhysicalParameters) -> SimulationResults:
    """Traite les résultats générés dans le dossier de calcul d'un cas."""
    case_dir = Path(case_dir)
    out_dir = case_dir / "post"
    out_dir.mkdir(parents=True, exist_ok=True)

    rho_ref = params.density
    u_ref = params.velocity
    p_ref = params.pressure_ref
    chord = params.chord
    q_ref = 0.5 * rho_ref * (u_ref ** 2)

    cl_path = case_dir / "cl_test.txt"
    cd_path = case_dir / "cd_test.txt"
    press_path = case_dir / "airfoil_pressure.csv"

    cl_df = read_report(cl_path)
    cd_df = read_report(cd_path)

    results = SimulationResults()

    if not cl_df.empty:
        results.cl_final = float(cl_df.iloc[-1].value)
        results.iteration_final = int(cl_df.iloc[-1].iteration)
        results.cl_history = cl_df.to_dict(orient="records")
        plot_convergence(cl_df, "CL", out_dir / "cl_convergence.png")

    if not cd_df.empty:
        results.cd_final = float(cd_df.iloc[-1].value)
        results.cd_history = cd_df.to_dict(orient="records")
        plot_convergence(cd_df, "CD", out_dir / "cd_convergence.png")

    results.compute_ratio()

    # Enregistrement coefficients.csv
    summary = []
    if results.cl_final is not None:
        summary.append({
            "coefficient": "CL",
            "iteration_finale": results.iteration_final,
            "valeur_finale": results.cl_final,
        })
    if results.cd_final is not None:
        summary.append({
            "coefficient": "CD",
            "iteration_finale": results.iteration_final,
            "valeur_finale": results.cd_final,
        })
    if summary:
        pd.DataFrame(summary).to_csv(out_dir / "coefficients.csv", index=False)

    # Traitement pression
    press_df = read_pressure(press_path)
    if press_df is not None and not press_df.empty:
        press_df["x_sur_c"] = press_df.x_m / chord
        press_df["Cp"] = (press_df.pressure_Pa - p_ref) / q_ref
        plot_distribution(press_df.x_sur_c, press_df.Cp, "Cp", out_dir / "cp_distribution.png", invert=True)

        if "total_pressure_Pa" in press_df.columns:
            press_df["Cpt"] = (press_df.total_pressure_Pa - p_ref) / q_ref
            plot_distribution(press_df.x_sur_c, press_df.Cpt, "Cpt", out_dir / "cpt_distribution.png", invert=True)

        csv_out = out_dir / "pressure_distribution.csv"
        press_df.to_csv(csv_out, index=False)
        results.pressure_file = str(csv_out)

    # Évaluation scientifique de la convergence et de la qualité
    quality = assess_convergence_quality(cl_df, cd_df)
    results.is_converged = quality.is_converged
    results.quality_flag = quality.quality_flag.value
    results.cl_std_last_20 = quality.cl_std_last_20
    results.cd_std_last_20 = quality.cd_std_last_20
    results.cl_relative_change_pct = quality.cl_relative_change_pct
    results.quality_message = quality.message

    results.postprocess_success = (results.cl_final is not None and results.cd_final is not None)
    return results
