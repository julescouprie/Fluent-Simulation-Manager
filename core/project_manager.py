import csv
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional
from .case_model import SimulationCase, PhysicalParameters, CaseStatus


class ProjectManager:
    """Gère un projet contenant une liste de cas de simulation CFD."""

    def __init__(self, project_path: Optional[Path] = None):
        self.project_path: Optional[Path] = project_path
        self.project_name: str = "Projet CFD"
        self.cases: List[SimulationCase] = []
        self.created_at: float = time.time()
        self.updated_at: float = time.time()
        self.is_modified: bool = False

        if project_path and project_path.exists():
            self.load_project(project_path)

    def add_case(self, case: SimulationCase) -> None:
        self.cases.append(case)
        self.is_modified = True
        self.updated_at = time.time()

    def remove_case(self, case_id: str) -> bool:
        initial_len = len(self.cases)
        self.cases = [c for c in self.cases if c.id != case_id]
        if len(self.cases) != initial_len:
            self.is_modified = True
            self.updated_at = time.time()
            return True
        return False

    def duplicate_case(self, case_id: str) -> Optional[SimulationCase]:
        case = self.get_case(case_id)
        if not case:
            return None
        clone = case.clone()
        # Find position of original and insert right after
        idx = self.cases.index(case)
        self.cases.insert(idx + 1, clone)
        self.is_modified = True
        self.updated_at = time.time()
        return clone

    def get_case(self, case_id: str) -> Optional[SimulationCase]:
        for c in self.cases:
            if c.id == case_id:
                return c
        return None

    def clear(self) -> None:
        self.cases.clear()
        self.is_modified = True
        self.updated_at = time.time()

    def get_summary_counts(self) -> Dict[str, int]:
        counts = {
            "total": len(self.cases),
            "en_attente": 0,
            "en_cours": 0,
            "terminee": 0,
            "echec": 0,
            "annulee": 0,
        }
        for c in self.cases:
            if c.status == CaseStatus.EN_ATTENTE:
                counts["en_attente"] += 1
            elif c.status.is_active:
                counts["en_cours"] += 1
            elif c.status == CaseStatus.TERMINEE:
                counts["terminee"] += 1
            elif c.status == CaseStatus.ECHEC:
                counts["echec"] += 1
            elif c.status == CaseStatus.ANNULEE:
                counts["annulee"] += 1
        return counts

    def save_project(self, target_path: Optional[Path] = None) -> Path:
        save_path = target_path or self.project_path
        if not save_path:
            save_path = Path("fluent_project.fsm")
        
        save_path = Path(save_path)
        self.project_path = save_path
        self.project_name = save_path.stem
        self.updated_at = time.time()

        data = {
            "version": "1.0",
            "project_name": self.project_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "cases": [c.to_dict() for c in self.cases],
        }

        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.is_modified = False
        return save_path

    def load_project(self, source_path: Path) -> None:
        source_path = Path(source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Fichier de projet introuvable : {source_path}")

        with open(source_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.project_path = source_path
        self.project_name = data.get("project_name", source_path.stem)
        self.created_at = data.get("created_at", time.time())
        self.updated_at = data.get("updated_at", time.time())
        
        cases_data = data.get("cases", [])
        self.cases = [SimulationCase.from_dict(cd) for cd in cases_data]
        self.is_modified = False

    def import_from_csv(self, csv_path: Path) -> int:
        """Importe des cas depuis un fichier CSV (colonnes : nom, alpha, vitesse, iterations, corde, maillage)."""
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"Fichier CSV introuvable : {csv_path}")

        count = 0
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # normalisation des clés
                norm = {k.strip().lower(): v for k, v in row.items() if k}
                name = norm.get("nom") or norm.get("name") or f"Import_Cas_{count + 1}"
                alpha = float(norm.get("alpha", norm.get("alpha_deg", 0.0)))
                vitesse = float(norm.get("vitesse", norm.get("velocity", 30.0)))
                iter_cnt = int(norm.get("iterations", norm.get("nb_iterations", 200)))
                corde = float(norm.get("corde", norm.get("chord", 1.0)))
                mesh = norm.get("maillage", norm.get("mesh", "profil_test.bdf"))

                params = PhysicalParameters(
                    mesh_file=mesh,
                    alpha_deg=alpha,
                    velocity=vitesse,
                    chord=corde,
                    iterations=iter_cnt,
                )
                case = SimulationCase(name=name, parameters=params)
                self.add_case(case)
                count += 1
        return count

    def export_summary_csv(self, target_path: Path) -> None:
        """Exporte un tableau récapitulatif de toutes les simulations et leurs résultats."""
        target_path = Path(target_path)
        with open(target_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "Identifiant",
                "Nom",
                "Statut",
                "Incidence [deg]",
                "Vitesse [m/s]",
                "Iterations",
                "CL Final",
                "CD Final",
                "Finesse CL/CD",
                "Durée [s]",
                "Message d'erreur",
            ])
            for c in self.cases:
                cl = f"{c.results.cl_final:.6f}" if c.results.cl_final is not None else ""
                cd = f"{c.results.cd_final:.6f}" if c.results.cd_final is not None else ""
                ratio = f"{c.results.cl_cd_ratio:.4f}" if c.results.cl_cd_ratio is not None else ""
                writer.writerow([
                    c.id,
                    c.name,
                    c.status.value,
                    f"{c.parameters.alpha_deg:.2f}",
                    f"{c.parameters.velocity:.2f}",
                    c.parameters.iterations,
                    cl,
                    cd,
                    ratio,
                    f"{c.duration_seconds:.1f}",
                    c.error_message,
                ])
