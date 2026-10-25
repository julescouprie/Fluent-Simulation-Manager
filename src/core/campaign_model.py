from dataclasses import dataclass, field, asdict
from enum import Enum
import time
from typing import Any, Dict, List, Optional
import uuid


class DoEStrategy(str, Enum):
    MANUAL = "Saisie manuelle"
    GRID = "Grille factorielle complète"
    LHS = "Latin Hypercube Sampling (LHS)"
    RANDOM = "Échantillonnage aléatoire uniforme"
    CSV_IMPORT = "Import de configurations CSV"
    ADAPTIVE = "Échantillonnage adaptatif (Krigeage)"


@dataclass
class DoECampaign:
    """Représente une campagne d'exploration de l'espace de conception réunissant plusieurs simulations."""

    id: str = field(default_factory=lambda: f"CAMP_{uuid.uuid4().hex[:6].upper()}")
    name: str = "Campagne sans nom"
    description: str = ""
    created_at: float = field(default_factory=time.time)
    strategy: DoEStrategy = DoEStrategy.MANUAL
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    active_variable_ids: List[str] = field(default_factory=list)
    fixed_parameters: Dict[str, float] = field(default_factory=dict)
    case_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["strategy"] = self.strategy.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DoECampaign":
        d = dict(data)
        if "strategy" in d:
            try:
                d["strategy"] = DoEStrategy(d["strategy"])
            except ValueError:
                d["strategy"] = DoEStrategy.MANUAL
        return cls(**d)
