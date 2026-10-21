from dataclasses import dataclass, field, asdict
from enum import Enum
import math
import time
from typing import Any, Dict, List, Optional
import uuid


class CaseStatus(str, Enum):
    EN_ATTENTE = "En attente"
    PREPARATION = "Préparation"
    EN_COURS = "En cours"
    POST_TRAITEMENT = "Post-traitement"
    TERMINEE_CONVERGEE = "Terminée (Convergée)"
    TERMINEE_NON_CONVERGEE = "Terminée (Non convergée)"
    INCOMPLETE = "Incomplète"
    ECHEC = "Échec"
    ANNULEE = "Annulée"

    @property
    def is_finished(self) -> bool:
        return self in (
            CaseStatus.TERMINEE_CONVERGEE,
            CaseStatus.TERMINEE_NON_CONVERGEE,
            CaseStatus.INCOMPLETE,
            CaseStatus.ECHEC,
            CaseStatus.ANNULEE,
        )

    @property
    def is_active(self) -> bool:
        return self in (CaseStatus.PREPARATION, CaseStatus.EN_COURS, CaseStatus.POST_TRAITEMENT)

    @property
    def is_valid_for_kriging(self) -> bool:
        """Seules les simulations ayant atteint une convergence asymptotique stricte sont fiables pour le krigeage."""
        return self == CaseStatus.TERMINEE_CONVERGEE


class DataOrigin(str, Enum):
    REAL_CFD = "CFD Réelle (ANSYS Fluent)"
    SYNTHETIC_MOCK = "Simulation Fictive (Test)"
    SURROGATE_PRED = "Prédiction Krigeage"


@dataclass
class PhysicalParameters:
    # Géométrie du profil NACA 4-chiffres (reliée dynamiquement à Gmsh)
    camber_m: float = 0.02          # Cambrure relative max m (0 à 0.08)
    camber_p: float = 0.20          # Position de cambrure max p (0.1 à 0.8)
    thickness_t: float = 0.12       # Épaisseur relative max t (0.04 à 0.25)
    chord: float = 1.0              # Corde du profil (m)

    # Écoulement et conditions limites (reliées à Fluent)
    alpha_deg: float = 0.0          # Angle d'incidence en degrés
    velocity: float = 30.0          # Vitesse de l'écoulement en m/s
    density: float = 1.225          # Masse volumique (kg/m3)
    pressure_ref: float = 0.0       # Pression de référence (Pa)

    # Paramètres solveur
    iterations: int = 200           # Nombre maximal d'itérations Fluent
    cores: int = 4                  # Cœurs CPU alloués
    turbulence_model: str = "kw-sst" # k-omega SST (validé 2026 R1)
    mesh_file: str = "profil_test.bdf"

    @property
    def naca_digits(self) -> str:
        """Génère la désignation NACA standard à 4 chiffres (ex: NACA 2212, NACA 0012, NACA 4415)."""
        m_digit = int(round(self.camber_m * 100))
        p_digit = int(round(self.camber_p * 10)) if self.camber_m > 1e-4 else 0
        t_digits = int(round(self.thickness_t * 100))
        return f"{m_digit:01d}{p_digit:01d}{t_digits:02d}"

    @property
    def alpha_rad(self) -> float:
        return math.radians(self.alpha_deg)

    @property
    def vx(self) -> float:
        return self.velocity * math.cos(self.alpha_rad)

    @property
    def vy(self) -> float:
        return self.velocity * math.sin(self.alpha_rad)

    @property
    def lift_force_vector(self) -> tuple[float, float]:
        # Lift is perpendicular to freestream velocity: (-sin(alpha), cos(alpha))
        return (-math.sin(self.alpha_rad), math.cos(self.alpha_rad))

    @property
    def drag_force_vector(self) -> tuple[float, float]:
        # Drag is aligned with freestream velocity: (cos(alpha), sin(alpha))
        return (math.cos(self.alpha_rad), math.sin(self.alpha_rad))

    @property
    def dynamic_pressure(self) -> float:
        return 0.5 * self.density * (self.velocity ** 2)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not (0.0 <= self.camber_m <= 0.10):
            errors.append("La cambrure maximale m doit être comprise entre 0.00 et 0.10.")
        if not (0.05 <= self.camber_p <= 0.90):
            errors.append("La position de cambrure p doit être comprise entre 0.05 et 0.90.")
        if not (0.03 <= self.thickness_t <= 0.35):
            errors.append("L'épaisseur t/c doit être comprise entre 0.03 et 0.35.")
        if self.chord <= 0:
            errors.append("La corde doit être strictement positive.")
        if self.velocity <= 0:
            errors.append("La vitesse doit être strictement positive.")
        if self.density <= 0:
            errors.append("La masse volumique doit être strictement positive.")
        if self.iterations <= 0:
            errors.append("Le nombre d'itérations doit être supérieur à zéro.")
        if self.cores <= 0:
            errors.append("Le nombre de cœurs CPU doit être au moins 1.")
        if not (-90.0 <= self.alpha_deg <= 90.0):
            errors.append("L'angle d'incidence doit être compris entre -90° et +90°.")
        return errors


@dataclass
class SimulationResults:
    cl_final: Optional[float] = None
    cd_final: Optional[float] = None
    cl_cd_ratio: Optional[float] = None
    iteration_final: Optional[int] = None
    cl_history: List[Dict[str, float]] = field(default_factory=list)
    cd_history: List[Dict[str, float]] = field(default_factory=list)
    pressure_file: Optional[str] = None
    postprocess_success: bool = False
    
    # Indicateurs de qualité et convergence scientifique
    is_converged: bool = False
    quality_flag: str = "Inconnu"
    cl_std_last_20: Optional[float] = None
    cd_std_last_20: Optional[float] = None
    cl_relative_change_pct: Optional[float] = None
    quality_message: str = ""

    def compute_ratio(self) -> None:
        if self.cl_final is not None and self.cd_final is not None and abs(self.cd_final) > 1e-9:
            self.cl_cd_ratio = self.cl_final / self.cd_final
        else:
            self.cl_cd_ratio = None


class SimulationCase:
    def __init__(
        self,
        case_id: Optional[str] = None,
        name: str = "Cas NACA",
        parameters: Optional[PhysicalParameters] = None,
        status: CaseStatus = CaseStatus.EN_ATTENTE,
        campaign_id: Optional[str] = None,
        data_origin: DataOrigin = DataOrigin.REAL_CFD,
    ):
        self.id = case_id or f"SIM_{uuid.uuid4().hex[:6].upper()}"
        self.name = name
        self.parameters = parameters or PhysicalParameters()
        self.status = status
        self.campaign_id = campaign_id
        self.data_origin = data_origin
        self.current_iteration = 0
        self.total_iterations = self.parameters.iterations
        self.progress_percent = 0
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.duration_seconds: float = 0.0
        self.error_message: str = ""
        self.work_dir: Optional[str] = None
        self.log_file: Optional[str] = None
        self.results = SimulationResults()

    def reset_status(self) -> None:
        self.status = CaseStatus.EN_ATTENTE
        self.current_iteration = 0
        self.progress_percent = 0
        self.start_time = None
        self.end_time = None
        self.duration_seconds = 0.0
        self.error_message = ""
        self.results = SimulationResults()

    def clone(self, new_id: Optional[str] = None) -> "SimulationCase":
        new_params = PhysicalParameters(**asdict(self.parameters))
        cloned = SimulationCase(
            case_id=new_id,
            name=f"{self.name} (copie)",
            parameters=new_params,
            status=CaseStatus.EN_ATTENTE,
            campaign_id=self.campaign_id,
            data_origin=self.data_origin,
        )
        return cloned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "campaign_id": self.campaign_id,
            "data_origin": self.data_origin.value,
            "parameters": asdict(self.parameters),
            "status": self.status.value,
            "current_iteration": self.current_iteration,
            "total_iterations": self.total_iterations,
            "progress_percent": self.progress_percent,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "work_dir": self.work_dir,
            "log_file": self.log_file,
            "results": asdict(self.results),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SimulationCase":
        param_data = data.get("parameters", {})
        parameters = PhysicalParameters(**param_data)
        
        status_val = data.get("status", CaseStatus.EN_ATTENTE.value)
        # Gestion de la compatibilité ascendante avec l'ancien statut "Terminée"
        if status_val == "Terminée":
            status_val = CaseStatus.TERMINEE_CONVERGEE.value

        try:
            status = CaseStatus(status_val)
        except ValueError:
            status = CaseStatus.EN_ATTENTE

        origin_val = data.get("data_origin", DataOrigin.REAL_CFD.value)
        try:
            origin = DataOrigin(origin_val)
        except ValueError:
            origin = DataOrigin.REAL_CFD

        case = cls(
            case_id=data.get("id"),
            name=data.get("name", "Cas sans nom"),
            parameters=parameters,
            status=status,
            campaign_id=data.get("campaign_id"),
            data_origin=origin,
        )
        case.current_iteration = data.get("current_iteration", 0)
        case.total_iterations = data.get("total_iterations", parameters.iterations)
        case.progress_percent = data.get("progress_percent", 0)
        case.start_time = data.get("start_time")
        case.end_time = data.get("end_time")
        case.duration_seconds = data.get("duration_seconds", 0.0)
        case.error_message = data.get("error_message", "")
        case.work_dir = data.get("work_dir")
        case.log_file = data.get("log_file")

        res_data = data.get("results")
        if res_data:
            case.results = SimulationResults(**res_data)
        return case
