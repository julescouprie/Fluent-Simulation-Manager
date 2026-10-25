import csv
from pathlib import Path
from typing import List
import pandas as pd
from core.case_model import SimulationCase


def export_cases_to_csv(cases: List[SimulationCase], output_path: Path) -> Path:
    """Exporte les résultats des cas sélectionnés au format CSV."""
    output_path = Path(output_path)
    rows = []
    for c in cases:
        rows.append({
            "Identifiant": c.id,
            "Nom": c.name,
            "Statut": c.status.value,
            "Alpha_deg": c.parameters.alpha_deg,
            "Vitesse_m_s": c.parameters.velocity,
            "Iterations": c.parameters.iterations,
            "CL_final": c.results.cl_final if c.results.cl_final is not None else "",
            "CD_final": c.results.cd_final if c.results.cd_final is not None else "",
            "Finesse_CL_CD": c.results.cl_cd_ratio if c.results.cl_cd_ratio is not None else "",
            "Duree_s": round(c.duration_seconds, 2),
            "Dossier_calcul": c.work_dir or "",
            "Erreur": c.error_message,
        })
    df = pd.DataFrame(rows)
    df.to_csv(output_path, sep=";", index=False, encoding="utf-8-sig")
    return output_path


def export_cases_to_excel(cases: List[SimulationCase], output_path: Path) -> Path:
    """Exporte les résultats des cas sous forme de classeur Excel avec onglet récapitulatif."""
    output_path = Path(output_path)
    summary_rows = []
    for c in cases:
        summary_rows.append({
            "ID": c.id,
            "Nom": c.name,
            "Statut": c.status.value,
            "Alpha [°]": c.parameters.alpha_deg,
            "Vitesse [m/s]": c.parameters.velocity,
            "Corde [m]": c.parameters.chord,
            "Densité [kg/m³]": c.parameters.density,
            "Itérations": c.parameters.iterations,
            "CL Final": c.results.cl_final,
            "CD Final": c.results.cd_final,
            "CL / CD": c.results.cl_cd_ratio,
            "Durée [s]": round(c.duration_seconds, 1),
            "Erreur": c.error_message,
        })
    df_summary = pd.DataFrame(summary_rows)

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_summary.to_excel(writer, sheet_name="Synthese_Simulations", index=False)

    return output_path
