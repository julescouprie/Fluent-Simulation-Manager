import csv
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from .case_model import CaseStatus, PhysicalParameters, SimulationCase
from .campaign_model import DoECampaign
from .design_space import DesignSpace
from .database import DatabaseManager


class ProjectManager:
    """Gère un projet unifié combinant l'espace de conception, les campagnes DoE, la base de données et les simulations."""

    def __init__(self, project_path: Optional[Path] = None, db_path: Path = Path("fsm_database.db")):
        self.project_path: Optional[Path] = project_path
        self.project_name: str = "Projet CFD & Krigeage"
        self.cases: List[SimulationCase] = []
        self.campaigns: List[DoECampaign] = []
        self.design_space = DesignSpace()
        self.database = DatabaseManager(db_path=db_path)
        self.created_at: float = time.time()
        self.updated_at: float = time.time()
        self.is_modified: bool = False

        if project_path and project_path.exists():
            self.load_project(project_path)

    def add_case(self, case: SimulationCase) -> None:
        self.cases.append(case)
        self.database.save_case(case)
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
        idx = self.cases.index(case)
        self.cases.insert(idx + 1, clone)
        self.database.save_case(clone)
        self.is_modified = True
        self.updated_at = time.time()
        return clone

    def get_case(self, case_id: str) -> Optional[SimulationCase]:
        for c in self.cases:
            if c.id == case_id:
                return c
        return None

    def add_campaign(self, campaign: DoECampaign) -> None:
        self.campaigns.append(campaign)
        self.database.save_campaign(campaign)
        self.is_modified = True
        self.updated_at = time.time()

    def get_campaign(self, campaign_id: str) -> Optional[DoECampaign]:
        for camp in self.campaigns:
            if camp.id == campaign_id:
                return camp
        return None

    def clear(self) -> None:
        self.cases.clear()
        self.campaigns.clear()
        self.is_modified = True
        self.updated_at = time.time()

    def get_summary_counts(self) -> Dict[str, int]:
        counts = {
            "total": len(self.cases),
            "en_attente": 0,
            "en_cours": 0,
            "terminee_convergee": 0,
            "terminee_non_convergee": 0,
            "incomplete": 0,
            "echec": 0,
            "annulee": 0,
        }
        for c in self.cases:
            if c.status == CaseStatus.EN_ATTENTE:
                counts["en_attente"] += 1
            elif c.status.is_active:
                counts["en_cours"] += 1
            elif c.status == CaseStatus.TERMINEE_CONVERGEE:
                counts["terminee_convergee"] += 1
            elif c.status == CaseStatus.TERMINEE_NON_CONVERGEE:
                counts["terminee_non_convergee"] += 1
            elif c.status == CaseStatus.INCOMPLETE:
                counts["incomplete"] += 1
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

        # Enregistrement dans la base SQLite locale
        for camp in self.campaigns:
            self.database.save_campaign(camp)
        for c in self.cases:
            self.database.save_case(c)

        # Enregistrement dans le fichier portable JSON .fsm
        data = {
            "version": "2.0",
            "project_name": self.project_name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "design_space": self.design_space.to_dict(),
            "campaigns": [camp.to_dict() for camp in self.campaigns],
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

        # Restauration du Design Space
        if "design_space" in data:
            self.design_space = DesignSpace.from_dict(data["design_space"])

        # Restauration des campagnes
        camp_data = data.get("campaigns", [])
        self.campaigns = [DoECampaign.from_dict(cd) for cd in camp_data]

        # Restauration des cas
        cases_data = data.get("cases", [])
        self.cases = [SimulationCase.from_dict(cd) for cd in cases_data]

        # Synchronisation dans SQLite
        for camp in self.campaigns:
            self.database.save_campaign(camp)
        for c in self.cases:
            self.database.save_case(c)

        self.is_modified = False

    def import_from_csv(self, csv_path: Path) -> int:
        """Importe des cas depuis un fichier CSV."""
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f"Fichier CSV introuvable : {csv_path}")

        count = 0
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=";")
            if not reader.fieldnames or len(reader.fieldnames) == 1:
                f.seek(0)
                reader = csv.DictReader(f, delimiter=",")

            for row in reader:
                norm = {k.strip().lower(): v for k, v in row.items() if k}
                name = norm.get("nom") or norm.get("name") or f"Import_Cas_{count + 1}"
                alpha = float(norm.get("alpha", norm.get("alpha_deg", 0.0)))
                vitesse = float(norm.get("vitesse", norm.get("velocity", 30.0)))
                iter_cnt = int(norm.get("iterations", norm.get("nb_iterations", 200)))
                corde = float(norm.get("corde", norm.get("chord", 1.0)))
                camber_m = float(norm.get("camber_m", norm.get("m", 0.02)))
                camber_p = float(norm.get("camber_p", norm.get("p", 0.20)))
                thickness_t = float(norm.get("thickness_t", norm.get("t", 0.12)))
                mesh = norm.get("maillage", norm.get("mesh", "profil_test.bdf"))

                params = PhysicalParameters(
                    camber_m=camber_m,
                    camber_p=camber_p,
                    thickness_t=thickness_t,
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
        """Exporte un tableau récapitulatif détaillé avec indicateurs de convergence."""
        target_path = Path(target_path)
        with open(target_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f, delimiter=";")
            writer.writerow([
                "Identifiant",
                "Nom",
                "Campagne",
                "Origine_Donnees",
                "Statut",
                "Qualite_Convergence",
                "Cambrure_m",
                "Pos_Cambrure_p",
                "Epaisseur_t",
                "Incidence_alpha_deg",
                "Vitesse_m_s",
                "Iterations",
                "CL_Final",
                "CD_Final",
                "Finesse_CL_CD",
                "Ecart_Type_CL_20iter",
                "Duree_s",
                "Dossier_Calcul",
                "Message_Qualite",
            ])
            for c in self.cases:
                cl = f"{c.results.cl_final:.6f}" if c.results.cl_final is not None else ""
                cd = f"{c.results.cd_final:.6f}" if c.results.cd_final is not None else ""
                ratio = f"{c.results.cl_cd_ratio:.4f}" if c.results.cl_cd_ratio is not None else ""
                cl_std = f"{c.results.cl_std_last_20:.2e}" if c.results.cl_std_last_20 is not None else ""
                writer.writerow([
                    c.id,
                    c.name,
                    c.campaign_id or "",
                    c.data_origin.value,
                    c.status.value,
                    c.results.quality_flag,
                    f"{c.parameters.camber_m:.4f}",
                    f"{c.parameters.camber_p:.4f}",
                    f"{c.parameters.thickness_t:.4f}",
                    f"{c.parameters.alpha_deg:.2f}",
                    f"{c.parameters.velocity:.2f}",
                    c.parameters.iterations,
                    cl,
                    cd,
                    ratio,
                    cl_std,
                    f"{c.duration_seconds:.1f}",
                    c.work_dir or "",
                    c.results.quality_message,
                ])
