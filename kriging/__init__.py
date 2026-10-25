"""
Package Kriging - Modélisation de substitution et prédiction aérodynamique.
"""

from kriging.model import (
    KrigingModel,
    charger_donnees_csv,
    construire_R,
    correlation,
    entrainer_modele,
    estimer_mu_sigma2,
    fonction_objectif,
)

__all__ = [
    "KrigingModel",
    "correlation",
    "construire_R",
    "estimer_mu_sigma2",
    "fonction_objectif",
    "entrainer_modele",
    "charger_donnees_csv",
]
