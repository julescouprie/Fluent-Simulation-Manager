"""
Module Krigeage - Moteur mathématique et modèle de substitution.

Implémente :
- Corrélation gaussienne : R(x1, x2, theta) = exp(-sum(theta * (x1 - x2)^2))
- Matrice de corrélation R(n, n)
- Vraisemblance concentrée pour krigeage ordinaire (tendance constante mu)
- Optimisation des hyperparamètres theta par L-BFGS-B
- Normalisation Min-Max [0, 1] cohérente apprentissage / prédiction
- Prédiction ponctuelle et vectorisée (batch / grille 1D/2D)
- Détection des sorties de domaine d'apprentissage
- Gestion des variations de dimension (d=1, d=2, etc.) et régularisation numérique (nugget)
- Entraînement direct depuis un DataFrame CSV ou depuis une liste de simulations CFD
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from scipy.optimize import minimize


# ==============================================================================
# 1. FONCTIONS FONDAMENTALES DE CORRELATION ET MATRICE R
# ==============================================================================

def correlation(x1: np.ndarray, x2: np.ndarray, theta: np.ndarray) -> float:
    """Calcule la corrélation gaussienne entre deux points normalisés x1 et x2.
    
    Puissances fixées à 2 (corrélation gaussienne) :
        R(x1, x2, theta) = exp(-sum_k(theta_k * (x1_k - x2_k)^2))
    """
    distance = (x1 - x2) ** 2
    return float(np.exp(-np.sum(theta * distance)))


def construire_R(X_norm: np.ndarray, theta: np.ndarray, nugget: float = 0.0) -> np.ndarray:
    """Construit la matrice de corrélation R de taille (n, n).
    
    Chaque coefficient R_ij mesure la corrélation entre les géométries i et j.
    Si nugget > 0, ajoute un effet de pépite sur la diagonale pour le conditionnement numérique.
    """
    n = len(X_norm)
    # Construction vectorisée optimisée
    diff = X_norm[:, np.newaxis, :] - X_norm[np.newaxis, :, :]  # (n, n, d)
    dist_sq = diff ** 2                                         # (n, n, d)
    R = np.exp(-np.sum(theta * dist_sq, axis=-1))              # (n, n)

    if nugget > 0.0:
        R += nugget * np.eye(n)

    return R


# ==============================================================================
# 2. VRAISEMBLANCE CONCENTREE ET ESTIMATION DE MU ET SIGMA^2
# ==============================================================================

def estimer_mu_sigma2(
    R: np.ndarray, Y: np.ndarray
) -> Tuple[Optional[float], Optional[float], Optional[np.ndarray]]:
    """Estime la moyenne constante mu, la variance sigma^2 et les poids R^(-1)*(Y - mu*1)."""
    n = len(Y)
    un = np.ones(n)

    try:
        R_inv_un = np.linalg.solve(R, un)
        R_inv_Y = np.linalg.solve(R, Y)

        denom = np.dot(un, R_inv_un)
        if abs(denom) < 1e-15:
            return None, None, None

        mu = float(np.dot(un, R_inv_Y) / denom)
        residus = Y - mu * un
        R_inv_residus = np.linalg.solve(R, residus)
        sigma2 = float(np.dot(residus, R_inv_residus) / n)

        poids = R_inv_residus
        return mu, sigma2, poids

    except np.linalg.LinAlgError:
        return None, None, None


def fonction_objectif(
    theta: np.ndarray, X_norm: np.ndarray, Y: np.ndarray, nugget: float = 0.0
) -> float:
    """Fonction objectif de vraisemblance concentrée à minimiser.
    
    Critère = n * ln(sigma^2) + ln(det(R))
    Rejette les configurations numériquement invalides en renvoyant 1e100.
    """
    n = len(X_norm)
    R = construire_R(X_norm, theta, nugget=nugget)

    mu, sigma2, _ = estimer_mu_sigma2(R, Y)
    if mu is None or sigma2 is None or sigma2 <= 0.0 or not np.isfinite(sigma2):
        return 1e100

    signe, log_det = np.linalg.slogdet(R)
    if signe <= 0 or not np.isfinite(log_det):
        return 1e100

    valeur = n * np.log(sigma2) + log_det
    return float(valeur) if np.isfinite(valeur) else 1e100


# ==============================================================================
# 3. STRUCTURE DE DONNEES ET ENTRAINEMENT DU MODELE
# ==============================================================================

@dataclass
class KrigingModel:
    """Encapsulation d'un modèle de krigeage entraîné pour une grandeur cible."""
    target_name: str
    feature_names: List[str]
    theta: np.ndarray
    mu: float
    sigma2: float
    poids: np.ndarray
    objectif: float
    X_min: np.ndarray
    X_max: np.ndarray
    X_norm: np.ndarray
    Y_train: np.ndarray
    is_optimized: bool
    optimization_success: bool
    optimization_message: str
    nugget: float = 0.0
    warning: str = ""

    def predict(self, x_phys: Union[List[float], np.ndarray, Dict[str, float]]) -> Dict[str, Any]:
        """Prédit la réponse pour une géométrie unique spécifiée par un vecteur ou dictionnaire."""
        if isinstance(x_phys, dict):
            x_arr = np.array([float(x_phys[col]) for col in self.feature_names], dtype=float)
        else:
            x_arr = np.asarray(x_phys, dtype=float)

        if len(x_arr) != len(self.feature_names):
            raise ValueError(
                f"Dimension d'entrée incompatible : attendu {len(self.feature_names)} variables, reçu {len(x_arr)}."
            )

        # Normalisation Min-Max
        denom = self.X_max - self.X_min
        denom = np.where(denom == 0.0, 1.0, denom)
        x_norm = (x_arr - self.X_min) / denom

        # Vérification des bornes du domaine
        out_of_bounds = []
        for i, col in enumerate(self.feature_names):
            val = x_arr[i]
            if val < self.X_min[i] or val > self.X_max[i]:
                out_of_bounds.append((col, float(val), float(self.X_min[i]), float(self.X_max[i])))

        is_inside = (len(out_of_bounds) == 0)

        # Corrélation avec les points d'apprentissage
        r = np.array([
            correlation(x_norm, xi, self.theta)
            for xi in self.X_norm
        ])

        y_pred = float(self.mu + np.dot(r, self.poids))

        return {
            "y_pred": y_pred,
            "is_inside_domain": is_inside,
            "out_of_bounds": out_of_bounds,
            "target_name": self.target_name,
        }

    def predict_batch(self, X_phys_batch: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Prédit pour un lot de points physiques de taille (M, d).
        
        Retourne :
            y_preds : np.ndarray de taille (M,)
            inside_mask : np.ndarray booléen de taille (M,) indiquant les points dans le domaine
        """
        X_arr = np.asarray(X_phys_batch, dtype=float)
        if X_arr.ndim == 1:
            X_arr = X_arr.reshape(-1, len(self.feature_names))

        denom = self.X_max - self.X_min
        denom = np.where(denom == 0.0, 1.0, denom)
        X_norm_batch = (X_arr - self.X_min) / denom

        # Vérification du domaine
        inside_mask = np.all((X_arr >= self.X_min) & (X_arr <= self.X_max), axis=1)

        # Calcul vectorisé de la matrice de corrélation croisée r_batch (M, n)
        diff = X_norm_batch[:, np.newaxis, :] - self.X_norm[np.newaxis, :, :]
        dist_sq = diff ** 2
        r_batch = np.exp(-np.sum(self.theta * dist_sq, axis=-1))

        y_preds = self.mu + np.dot(r_batch, self.poids)
        return y_preds, inside_mask


def detecter_doublons_coordonnees(X_norm: np.ndarray) -> bool:
    """Détecte si deux points d'apprentissage possèdent exactement les mêmes coordonnées d'entrée."""
    n = len(X_norm)
    for i in range(n):
        for j in range(i + 1, n):
            if np.allclose(X_norm[i], X_norm[j], atol=1e-12):
                return True
    return False


def entrainer_modele(
    X: np.ndarray,
    Y: np.ndarray,
    feature_names: List[str],
    target_name: str,
    optimize_theta: bool = True,
    custom_theta: Optional[Union[List[float], np.ndarray]] = None,
    nugget: Optional[float] = None,
) -> KrigingModel:
    """Entraîne un modèle de krigeage pour une variable cible Y à partir de la matrice d'entrée X.
    
    Conserve rigoureusement les hypothèses et équations de la V1 :
    - Normalisation Min-Max entre 0 et 1
    - Optimisation L-BFGS-B des theta sur [(1e-3, 100)]^d avec theta_initial = 1.0
    - En cas de dimension réduite créant des coordonnées identiques (ex : seule m_% choisie alors
      que plusieurs cas ont le même m_% avec des p différents), un nugget minimal (1e-6) est
      appliqué pour garantir l'inversibilité de la matrice R sans altérer les autres cas.
    """
    X_arr = np.asarray(X, dtype=float)
    Y_arr = np.asarray(Y, dtype=float)

    if X_arr.ndim == 1:
        X_arr = X_arr.reshape(-1, 1)

    n, d = X_arr.shape
    if len(Y_arr) != n:
        raise ValueError(f"Incohérence de taille : X a {n} lignes et Y a {len(Y_arr)} éléments.")

    X_min = X_arr.min(axis=0)
    X_max = X_arr.max(axis=0)
    denom = X_max - X_min
    denom = np.where(denom == 0.0, 1.0, denom)
    X_norm = (X_arr - X_min) / denom

    # Gestion de la régularisation numérique (nugget)
    has_duplicates = detecter_doublons_coordonnees(X_norm)
    warning_msg = ""
    effective_nugget = 0.0

    if nugget is not None:
        effective_nugget = max(0.0, float(nugget))
    elif has_duplicates:
        effective_nugget = 1e-6
        warning_msg = (
            f"Plusieurs simulations partagent les mêmes valeurs pour les entrées sélectionnées "
            f"({', '.join(feature_names)}). Un effet de pépite numérique minimal (nugget = 1e-6) "
            f"a été activé pour garantir l'inversibilité de la matrice de corrélation."
        )

    # Initialisation de theta
    theta_opt = np.ones(d, dtype=float)
    obj_val = 0.0
    opt_success = True
    opt_msg = "Valeurs manuelles / non optimisées"

    if optimize_theta:
        theta_initial = np.ones(d, dtype=float)
        bornes = [(1e-3, 100.0)] * d

        resultat = minimize(
            fonction_objectif,
            theta_initial,
            args=(X_norm, Y_arr, effective_nugget),
            method="L-BFGS-B",
            bounds=bornes,
        )

        opt_success = bool(resultat.success)
        opt_msg = str(resultat.message)

        if not opt_success and effective_nugget == 0.0:
            effective_nugget = 1e-6
            resultat = minimize(
                fonction_objectif,
                theta_initial,
                args=(X_norm, Y_arr, effective_nugget),
                method="L-BFGS-B",
                bounds=bornes,
            )
            opt_success = bool(resultat.success)
            opt_msg = f"{resultat.message} (avec nugget de conditionnement 1e-6)"

        theta_opt = np.asarray(resultat.x, dtype=float)
        obj_val = float(resultat.fun)
    else:
        if custom_theta is not None:
            c_theta = np.asarray(custom_theta, dtype=float)
            if len(c_theta) == d:
                theta_opt = c_theta
            else:
                theta_opt = np.ones(d, dtype=float)
        else:
            theta_opt = np.ones(d, dtype=float)

        obj_val = fonction_objectif(theta_opt, X_norm, Y_arr, effective_nugget)

    # Reconstruction finale du modèle
    R = construire_R(X_norm, theta_opt, nugget=effective_nugget)
    mu, sigma2, poids = estimer_mu_sigma2(R, Y_arr)

    if mu is None or sigma2 is None or poids is None:
        raise RuntimeError(
            f"Impossible de construire le modèle de krigeage pour '{target_name}'. "
            f"La matrice de corrélation reste singulière. Vérifiez les entrées sélectionnées."
        )

    return KrigingModel(
        target_name=target_name,
        feature_names=list(feature_names),
        theta=theta_opt,
        mu=mu,
        sigma2=sigma2,
        poids=poids,
        objectif=obj_val,
        X_min=X_min,
        X_max=X_max,
        X_norm=X_norm,
        Y_train=Y_arr,
        is_optimized=optimize_theta,
        optimization_success=opt_success,
        optimization_message=opt_msg,
        nugget=effective_nugget,
        warning=warning_msg,
    )


# ==============================================================================
# 4. CHARGEMENT ET VALIDATION DU JEU DE DONNEES
# ==============================================================================

def charger_donnees_csv(
    chemin_csv: Union[str, Path]
) -> Tuple[pd.DataFrame, List[str], List[str], Dict[str, Any]]:
    """Charge le fichier CSV de simulations et détecte les variables disponibles.
    
    Retourne :
        df : DataFrame pandas
        input_candidates : colonnes d'entrées potentielles (numériques hors sorties et statut)
        output_candidates : colonnes de sorties potentielles (Cl, Cd)
        info_dict : informations sur le jeu de données
    """
    path = Path(chemin_csv)
    if not path.exists():
        raise FileNotFoundError(f"Le fichier de données '{path}' est introuvable.")

    df = pd.read_csv(path)
    if df.empty:
        raise ValueError(f"Le fichier '{path}' est vide.")

    cols = list(df.columns)
    
    # Sorties prioritaires spécifiées par le projet
    sorties_recherchees = ["Cl", "Cd"]
    sorties_trouvees = [c for c in cols if c in sorties_recherchees]

    # Autres colonnes exclues des entrées
    exclusions = set(sorties_trouvees + ["Cas", "Statut", "Finesse", "Unnamed: 0"])

    entrees_candidates = []
    for c in cols:
        if c not in exclusions:
            try:
                pd.to_numeric(df[c])
                entrees_candidates.append(c)
            except (ValueError, TypeError):
                pass

    info = {
        "nb_lignes": len(df),
        "nb_colonnes": len(cols),
        "colonnes": cols,
        "entrees_detectees": entrees_candidates,
        "sorties_detectees": sorties_trouvees,
        "statut_present": "Statut" in cols,
    }

    return df, entrees_candidates, sorties_trouvees, info
