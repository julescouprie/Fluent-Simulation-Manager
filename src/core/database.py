import json
from pathlib import Path
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple
import pandas as pd

from .case_model import CaseStatus, DataOrigin, PhysicalParameters, SimulationCase, SimulationResults
from .campaign_model import DoECampaign, DoEStrategy


class DatabaseManager:
    """Gestionnaire de persistance locale SQLite pour les campagnes DoE et les résultats CFD."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is not None:
            self.db_path = Path(db_path).resolve()
        elif Path("data/fsm_database.db").is_file():
            self.db_path = Path("data/fsm_database.db").resolve()
        elif Path("data").is_dir():
            self.db_path = Path("data/fsm_database.db").resolve()
        else:
            self.db_path = Path("fsm_database.db").resolve()
        self._init_tables()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_tables(self) -> None:
        """Initialise le schéma relationnel s'il n'existe pas."""
        with self._get_connection() as conn:
            cur = conn.cursor()

            # Table des campagnes
            cur.execute("""
                CREATE TABLE IF NOT EXISTS campaigns (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    strategy TEXT,
                    strategy_params_json TEXT,
                    active_variables_json TEXT,
                    fixed_parameters_json TEXT,
                    created_at REAL
                )
            """)

            # Table des simulations
            cur.execute("""
                CREATE TABLE IF NOT EXISTS simulations (
                    id TEXT PRIMARY KEY,
                    campaign_id TEXT,
                    name TEXT NOT NULL,
                    data_origin TEXT NOT NULL,
                    status TEXT NOT NULL,
                    quality_flag TEXT,
                    input_parameters_json TEXT NOT NULL,
                    cl_final REAL,
                    cd_final REAL,
                    cl_cd_ratio REAL,
                    cl_std_last_20 REAL,
                    cd_std_last_20 REAL,
                    quality_message TEXT,
                    duration_seconds REAL,
                    work_dir TEXT,
                    mesh_file TEXT,
                    created_at REAL,
                    FOREIGN KEY (campaign_id) REFERENCES campaigns (id)
                )
            """)
            conn.commit()

    def save_campaign(self, camp: DoECampaign) -> None:
        """Enregistre ou met à jour une campagne DoE."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO campaigns (
                    id, name, description, strategy, strategy_params_json,
                    active_variables_json, fixed_parameters_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                camp.id,
                camp.name,
                camp.description,
                camp.strategy.value if hasattr(camp.strategy, "value") else str(camp.strategy),
                json.dumps(camp.strategy_params, ensure_ascii=False),
                json.dumps(camp.active_variable_ids, ensure_ascii=False),
                json.dumps(camp.fixed_parameters, ensure_ascii=False),
                camp.created_at,
            ))
            conn.commit()

    def save_case(self, case: SimulationCase) -> None:
        """Enregistre ou met à jour un cas de simulation avec ses métriques scientifiques."""
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT OR REPLACE INTO simulations (
                    id, campaign_id, name, data_origin, status, quality_flag,
                    input_parameters_json, cl_final, cd_final, cl_cd_ratio,
                    cl_std_last_20, cd_std_last_20, quality_message,
                    duration_seconds, work_dir, mesh_file, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                case.id,
                case.campaign_id,
                case.name,
                case.data_origin.value if hasattr(case.data_origin, "value") else str(case.data_origin),
                case.status.value if hasattr(case.status, "value") else str(case.status),
                case.results.quality_flag,
                json.dumps(case.parameters.__dict__, ensure_ascii=False),
                case.results.cl_final,
                case.results.cd_final,
                case.results.cl_cd_ratio,
                case.results.cl_std_last_20,
                case.results.cd_std_last_20,
                case.results.quality_message,
                case.duration_seconds,
                case.work_dir,
                case.parameters.mesh_file,
                case.start_time or time.time(),
            ))
            conn.commit()

    def get_all_campaigns(self) -> List[DoECampaign]:
        """Récupère l'ensemble des campagnes stockées."""
        campaigns = []
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM campaigns ORDER BY created_at DESC")
            for row in cur.fetchall():
                camp = DoECampaign(
                    id=row["id"],
                    name=row["name"],
                    description=row["description"] or "",
                    strategy=DoEStrategy(row["strategy"]),
                    strategy_params=json.loads(row["strategy_params_json"] or "{}"),
                    active_variable_ids=json.loads(row["active_variables_json"] or "[]"),
                    fixed_parameters=json.loads(row["fixed_parameters_json"] or "{}"),
                    created_at=row["created_at"],
                )
                campaigns.append(camp)
        return campaigns

    def get_simulations_for_campaign(self, campaign_id: str) -> List[SimulationCase]:
        """Récupère toutes les simulations appartenant à une campagne donnée."""
        cases = []
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM simulations WHERE campaign_id = ? ORDER BY created_at ASC", (campaign_id,))
            for row in cur.fetchall():
                cases.append(self._row_to_case(row))
        return cases

    def get_all_simulations(self) -> List[SimulationCase]:
        """Récupère la totalité des simulations stockées."""
        cases = []
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM simulations ORDER BY created_at DESC")
            for row in cur.fetchall():
                cases.append(self._row_to_case(row))
        return cases

    def _row_to_case(self, row: sqlite3.Row) -> SimulationCase:
        param_dict = json.loads(row["input_parameters_json"] or "{}")
        params = PhysicalParameters(**param_dict)

        try:
            status = CaseStatus(row["status"])
        except ValueError:
            status = CaseStatus.TERMINEE_CONVERGEE if row["status"] == "Terminée" else CaseStatus.EN_ATTENTE

        try:
            origin = DataOrigin(row["data_origin"])
        except ValueError:
            origin = DataOrigin.REAL_CFD

        case = SimulationCase(
            case_id=row["id"],
            name=row["name"],
            parameters=params,
            status=status,
            campaign_id=row["campaign_id"],
            data_origin=origin,
        )
        case.duration_seconds = row["duration_seconds"] or 0.0
        case.work_dir = row["work_dir"]
        case.results = SimulationResults(
            cl_final=row["cl_final"],
            cd_final=row["cd_final"],
            cl_cd_ratio=row["cl_cd_ratio"],
            quality_flag=row["quality_flag"] or "Inconnu",
            cl_std_last_20=row["cl_std_last_20"],
            cd_std_last_20=row["cd_std_last_20"],
            quality_message=row["quality_message"] or "",
            postprocess_success=(row["cl_final"] is not None and row["cd_final"] is not None),
            is_converged=(status == CaseStatus.TERMINEE_CONVERGEE),
        )
        return case
