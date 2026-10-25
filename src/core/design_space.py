from dataclasses import dataclass, field, asdict
from enum import Enum
import math
from typing import Any, Dict, List, Optional, Tuple


class VariableType(str, Enum):
    CONTINUOUS = "Continue"
    DISCRETE = "Discrète"
    CATEGORICAL = "Catégorielle"


class VariableCategory(str, Enum):
    GEOMETRY_2D = "Géométrie Profil 2D"
    FLOW_PHYSICS = "Physique de l'écoulement"
    NUMERICAL = "Résolution numérique"
    GROUND_EFFECT = "Effet de sol (Étape 2)"
    ENDPLATE_3D = "Endplates 3D (Étape 3)"
    USER_CUSTOM = "Personnalisée"


@dataclass
class DesignVariable:
    """Représente une variable d'entrée de l'espace de conception."""

    id: str                         # Identifiant technique unique (ex: "camber_m")
    name: str                       # Nom complet (ex: "Cambrure maximale")
    symbol: str                     # Symbole mathématique (ex: "m")
    unit: str                       # Unité (ex: "-", "°", "m/s", "m")
    min_val: float                  # Valeur minimale autorisée
    max_val: float                  # Valeur maximale autorisée
    default_val: float              # Valeur nominale / de référence
    var_type: VariableType = VariableType.CONTINUOUS
    step: Optional[float] = None    # Pas pour les variables discrètes
    allowed_values: Optional[List[Any]] = None
    is_active: bool = False         # True = variable explorée dans le DoE ; False = fixée à default_val
    category: VariableCategory = VariableCategory.GEOMETRY_2D
    is_operational: bool = True     # True si reliée à la chaîne de calcul actuelle
    description: str = ""           # Description physique / aérodynamique

    def validate_value(self, val: float) -> Tuple[bool, str]:
        """Vérifie si une valeur respecte les bornes et contraintes de la variable."""
        if val < self.min_val - 1e-9:
            return False, f"La valeur {val} est inférieure au minimum autorisé ({self.min_val} {self.unit})."
        if val > self.max_val + 1e-9:
            return False, f"La valeur {val} dépasse le maximum autorisé ({self.max_val} {self.unit})."
        if self.allowed_values and val not in self.allowed_values:
            return False, f"La valeur {val} ne fait pas partie des valeurs discrètes autorisées."
        return True, ""

    def normalize(self, val: float) -> float:
        """Normalise la valeur dans l'intervalle [0, 1] pour les DoE et le krigeage."""
        if abs(self.max_val - self.min_val) < 1e-12:
            return 0.0
        return (val - self.min_val) / (self.max_val - self.min_val)

    def denormalize(self, norm_val: float) -> float:
        """Reprojette une valeur normalisée [0, 1] dans l'espace physique [min, max]."""
        return self.min_val + norm_val * (self.max_val - self.min_val)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["var_type"] = self.var_type.value
        d["category"] = self.category.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DesignVariable":
        d = dict(data)
        if "var_type" in d:
            d["var_type"] = VariableType(d["var_type"])
        if "category" in d:
            d["category"] = VariableCategory(d["category"])
        return cls(**d)


class DesignSpace:
    """Gestionnaire de l'espace de conception réunissant l'ensemble des variables et contraintes."""

    def __init__(self):
        self.variables: Dict[str, DesignVariable] = {}
        self._load_standard_catalog()

    def _load_standard_catalog(self):
        """Catalogue standard initialisé pour le cas profil aérodynamique 2D et préparé pour l'effet de sol."""
        # 1. Variables Géométriques Profil 2D (Opérationnelles via Gmsh)
        self.add_variable(DesignVariable(
            id="camber_m",
            name="Cambrure maximale",
            symbol="m",
            unit="-",
            min_val=0.00,
            max_val=0.08,
            default_val=0.02,
            step=0.01,
            category=VariableCategory.GEOMETRY_2D,
            is_active=False,
            is_operational=True,
            description="Cambrure relative maximale du profil (ex: 0.02 pour NACA 2212).",
        ))
        self.add_variable(DesignVariable(
            id="camber_p",
            name="Position de la cambrure maximale",
            symbol="p",
            unit="-",
            min_val=0.10,
            max_val=0.80,
            default_val=0.20,
            step=0.05,
            category=VariableCategory.GEOMETRY_2D,
            is_active=False,
            is_operational=True,
            description="Position longitudinale du maximum de cambrure en fraction de corde.",
        ))
        self.add_variable(DesignVariable(
            id="thickness_t",
            name="Épaisseur relative maximale",
            symbol="t/c",
            unit="-",
            min_val=0.04,
            max_val=0.25,
            default_val=0.12,
            step=0.01,
            category=VariableCategory.GEOMETRY_2D,
            is_active=False,
            is_operational=True,
            description="Épaisseur maximale relative du profil (ex: 0.12 pour 12%).",
        ))
        self.add_variable(DesignVariable(
            id="chord",
            name="Longueur de corde",
            symbol="c",
            unit="m",
            min_val=0.1,
            max_val=5.0,
            default_val=1.0,
            step=0.1,
            category=VariableCategory.GEOMETRY_2D,
            is_active=False,
            is_operational=True,
            description="Corde géométrique du profil d'aile.",
        ))

        # 2. Variables de l'Écoulement Aérodynamique (Opérationnelles dans Fluent)
        self.add_variable(DesignVariable(
            id="alpha_deg",
            name="Angle d'incidence",
            symbol="alpha",
            unit="°",
            min_val=-10.0,
            max_val=20.0,
            default_val=0.0,
            step=0.5,
            category=VariableCategory.FLOW_PHYSICS,
            is_active=True,
            is_operational=True,
            description="Incidence aérodynamique du profil par rapport à la vitesse de l'infini amont.",
        ))
        self.add_variable(DesignVariable(
            id="velocity",
            name="Vitesse de l'écoulement",
            symbol="U_inf",
            unit="m/s",
            min_val=5.0,
            max_val=120.0,
            default_val=30.0,
            step=5.0,
            category=VariableCategory.FLOW_PHYSICS,
            is_active=False,
            is_operational=True,
            description="Vitesse de l'écoulement non perturbé.",
        ))
        self.add_variable(DesignVariable(
            id="density",
            name="Masse volumique de l'air",
            symbol="rho",
            unit="kg/m³",
            min_val=0.5,
            max_val=2.0,
            default_val=1.225,
            step=0.025,
            category=VariableCategory.FLOW_PHYSICS,
            is_active=False,
            is_operational=True,
            description="Densité de l'air de référence.",
        ))

        # 3. Paramètres Numériques Fluent (Opérationnels)
        self.add_variable(DesignVariable(
            id="iterations",
            name="Nombre d'itérations solveur",
            symbol="N_iter",
            unit="-",
            min_val=50,
            max_val=5000,
            default_val=200,
            var_type=VariableType.DISCRETE,
            step=50,
            category=VariableCategory.NUMERICAL,
            is_active=False,
            is_operational=True,
            description="Nombre maximal d'itérations Fluent avant contrôle de convergence.",
        ))
        self.add_variable(DesignVariable(
            id="cores",
            name="Cœurs CPU alloués",
            symbol="N_cpu",
            unit="-",
            min_val=1,
            max_val=128,
            default_val=4,
            var_type=VariableType.DISCRETE,
            step=1,
            category=VariableCategory.NUMERICAL,
            is_active=False,
            is_operational=True,
            description="Nombre de cœurs de processeur pour l'exécution parallèle.",
        ))

        # 4. Variables Futures Déclarées (Explicitement NON opérationnelles en Étape 1)
        self.add_variable(DesignVariable(
            id="ground_height_h",
            name="Garde au sol relative",
            symbol="h/c",
            unit="-",
            min_val=0.05,
            max_val=2.0,
            default_val=0.3,
            category=VariableCategory.GROUND_EFFECT,
            is_active=False,
            is_operational=False,
            description="Distance du bord d'attaque au sol (Prévu Étape 2 - Effet de sol).",
        ))
        self.add_variable(DesignVariable(
            id="endplate_span",
            name="Envergure de plaque d'extrémité",
            symbol="b_ep",
            unit="m",
            min_val=0.05,
            max_val=0.8,
            default_val=0.2,
            category=VariableCategory.ENDPLATE_3D,
            is_active=False,
            is_operational=False,
            description="Hauteur d'endplate 3D (Prévu Étape 3 - 3D).",
        ))

    def add_variable(self, var: DesignVariable) -> None:
        self.variables[var.id] = var

    def get_variable(self, var_id: str) -> Optional[DesignVariable]:
        return self.variables.get(var_id)

    def get_active_variables(self) -> List[DesignVariable]:
        """Retourne les variables marquées comme actives pour le DoE (uniquement parmi celles opérationnelles)."""
        return [v for v in self.variables.values() if v.is_active and v.is_operational]

    def get_fixed_variables(self) -> List[DesignVariable]:
        """Retourne les variables opérationnelles non explorées (fixées à leur valeur de référence)."""
        return [v for v in self.variables.values() if not v.is_active and v.is_operational]

    def get_operational_variables(self) -> List[DesignVariable]:
        return [v for v in self.variables.values() if v.is_operational]

    def validate_point(self, point: Dict[str, float]) -> Tuple[bool, List[str]]:
        """Valide un point de simulation par rapport aux bornes et contraintes physiques/géométriques."""
        errors: List[str] = []

        # 1. Vérification des bornes individuelles
        for var_id, val in point.items():
            var = self.get_variable(var_id)
            if var:
                ok, err = var.validate_value(val)
                if not ok:
                    errors.append(f"[{var.name}] {err}")

        # 2. Contraintes d'intégrité géométrique (ex: NACA 4-chiffres)
        m = point.get("camber_m", self.variables["camber_m"].default_val)
        p = point.get("camber_p", self.variables["camber_p"].default_val)
        t = point.get("thickness_t", self.variables["thickness_t"].default_val)

        if m == 0.0 and p != 0.0:
            # Profil symétrique : p doit être ramené à 0 conventionnellement
            pass

        if t <= 0.02:
            errors.append("Épaisseur trop faible (< 2%) : risque d'auto-intersection du maillage.")

        if m > 0.12:
            errors.append("Cambrure excessive (> 12%) : courbure incompatible avec le maillage structuré C-grid.")

        return len(errors) == 0, errors

    def to_dict(self) -> Dict[str, Any]:
        return {"variables": {k: v.to_dict() for k, v in self.variables.items()}}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DesignSpace":
        ds = cls()
        ds.variables.clear()
        vars_dict = data.get("variables", {})
        for k, v in vars_dict.items():
            ds.variables[k] = DesignVariable.from_dict(v)
        return ds
