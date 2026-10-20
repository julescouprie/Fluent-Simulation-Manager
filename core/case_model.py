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
    TERMINEE = "Terminée"
    ECHEC = "Échec"
    ANNULEE = "Annulée"

    @property
    def is_finished(self) -> bool:
        return self in (CaseStatus.TERMINEE, CaseStatus.ECHEC, CaseStatus.ANNULEE)

    @property
    def is_active(self) -> bool:
        return self in (CaseStatus.PREPARATION, CaseStatus.EN_COURS, CaseStatus.POST_TRAITEMENT)


@dataclass
class PhysicalParameters:
    mesh_file: str = "profil_test.bdf"
    alpha_deg: float = 0.0          # Angle d'incidence en degrés
    velocity: float = 30.0          # Vitesse de l'écoulement en m/s
    density: float = 1.225          # Masse volumique (kg/m3)
    pressure_ref: float = 0.0       # Pression de référence (Pa)
    chord: float = 1.0              # Corde du profil (m)
    iterations: int = 200           # Nombre d'itérations
    cores: int = 4                  # Cœurs CPU alloués
    turbulence_model: str = "kw-sst" # k-omega SST (validé 2026 R1)

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
        # q = 0.5 * rho * U^2
        return 0.5 * self.density * (self.velocity ** 2)

    def validate(self) -> List[str]:
        errors: List[str] = []
        if self.velocity <= 0:
            errors.append("La vitesse doit être strictement positive.")
        if self.density <= 0:
            errors.append("La masse volumique doit être strictement positive.")
        if self.chord <= 0:
            errors.append("La corde doit être strictement positive.")
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

    def compute_ratio(self) -> None:
        if self.cl_final is not None and self.cd_final is not None and abs(self.cd_final) > 1e-9:
            self.cl_cd_ratio = self.cl_final / self.cd_final
        else:
            self.cl_cd_ratio = None


class SimulationCase:
    def __init__(
        self,
        case_id: Optional[str] = None,
        name: str = "Cas NACA 2212",
        parameters: Optional[PhysicalParameters] = None,
        status: CaseStatus = CaseStatus.EN_ATTENTE,
    ):
        self.id = case_id or f"SIM_{uuid.uuid4().hex[:6].upper()}"
        self.name = name
        self.parameters = parameters or PhysicalParameters()
        self.status = status
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
        )
        return cloned

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
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
        try:
            status = CaseStatus(status_val)
        except ValueError:
            status = CaseStatus.EN_ATTENTE

        case = cls(
            case_id=data.get("id"),
            name=data.get("name", "Cas sans nom"),
            parameters=parameters,
            status=status,
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
