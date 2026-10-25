import numpy as np
import pandas as pd
from scipy.optimize import minimize


# ==================================================
# 1. LECTURE DES DONNEES CFD
# ==================================================

from pathlib import Path

csv_path = Path("data/recapitulatif_campagne.csv")
if not csv_path.exists():
    csv_path = Path("recapitulatif_campagne.csv")

data = pd.read_csv(csv_path)

# Entrees : cambrure maximale m et position p
X = data[["m_%", "p"]].to_numpy(dtype=float)

# Sorties que l'on veut predire
Y_Cl = data["Cl"].to_numpy(dtype=float)
Y_Cd = data["Cd"].to_numpy(dtype=float)

# Normalisation des entrees entre 0 et 1
X_min = X.min(axis=0)
X_max = X.max(axis=0)

X_norm = (X - X_min) / (X_max - X_min)

n = len(X)


# ==================================================
# 2. FONCTION DE CORRELATION
# ==================================================

def correlation(x1, x2, theta):
    # Les puissances sont fixees a 2 : correlation gaussienne
    distance = (x1 - x2) ** 2

    return np.exp(-np.sum(theta * distance))


# ==================================================
# 3. MATRICE DE CORRELATION R
# ==================================================

def construire_R(X, theta):
    n = len(X)

    # Chaque coefficient Rij mesure la correlation
    # entre deux geometries i et j
    R = np.array([
        [correlation(X[i], X[j], theta) for j in range(n)]
        for i in range(n)
    ])

    return R


# ==================================================
# 4. FONCTION OBJECTIF : MAXIMUM DE VRAISEMBLANCE
# ==================================================

def fonction_objectif(theta, Y):
    R = construire_R(X_norm, theta)
    un = np.ones(n)

    try:
        # Estimation de la moyenne constante mu
        R_inv_un = np.linalg.solve(R, un)
        R_inv_Y = np.linalg.solve(R, Y)

        mu = np.dot(un, R_inv_Y) / np.dot(un, R_inv_un)

        # Estimation de la variance sigma^2
        residus = Y - mu * un
        R_inv_residus = np.linalg.solve(R, residus)

        sigma2 = np.dot(residus, R_inv_residus) / n

        # Logarithme du determinant de R
        signe, log_det = np.linalg.slogdet(R)

        # Rejet des calculs numeriquement invalides
        if signe <= 0 or sigma2 <= 0 or not np.isfinite(sigma2):
            return 1e100

        # Critere a minimiser (vraisemblance concentree)
        return n * np.log(sigma2) + log_det

    except np.linalg.LinAlgError:
        return 1e100


# ==================================================
# 5. APPRENTISSAGE DU MODELE DE KRIGEAGE
# ==================================================

def entrainer_modele(Y):

    # Point de depart de l'optimisation
    theta_initial = np.array([1.0, 1.0])

    # Bornes autorisees pour theta
    bornes = [(1e-3, 100), (1e-3, 100)]

    # Recherche des parametres optimaux
    resultat = minimize(
        fonction_objectif,
        theta_initial,
        args=(Y,),
        method="L-BFGS-B",
        bounds=bornes
    )

    if not resultat.success:
        raise RuntimeError(
            f"Echec de l'optimisation : {resultat.message}"
        )

    # Parametres optimaux
    theta = resultat.x

    # Reconstruction du modele avec les parametres optimaux
    R = construire_R(X_norm, theta)
    un = np.ones(n)

    R_inv_un = np.linalg.solve(R, un)
    R_inv_Y = np.linalg.solve(R, Y)

    mu = np.dot(un, R_inv_Y) / np.dot(un, R_inv_un)

    # Poids utilises pour predire de nouvelles geometries
    poids = np.linalg.solve(R, Y - mu * un)

    return {
        "theta": theta,
        "mu": mu,
        "poids": poids,
        "objectif": resultat.fun
    }


# ==================================================
# 6. ENTRAINEMENT DES DEUX MODELES
# ==================================================

modele_Cl = entrainer_modele(Y_Cl)
modele_Cd = entrainer_modele(Y_Cd)

print("\n--- Modele Cl ---")
print("Theta optimal :", modele_Cl["theta"])
print("Fonction objectif :", modele_Cl["objectif"])

print("\n--- Modele Cd ---")
print("Theta optimal :", modele_Cd["theta"])
print("Fonction objectif :", modele_Cd["objectif"])

# ==================================================
# 7. PREDICTION D'UNE NOUVELLE GEOMETRIE
# ==================================================

def predire(m, p, modele):

    # La nouvelle geometrie doit etre normalisee
    x = (np.array([m, p]) - X_min) / (X_max - X_min)

    # Correlation entre la nouvelle geometrie et les donnees CFD
    r = np.array([
        correlation(x, xi, modele["theta"])
        for xi in X_norm
    ])

    # Prediction par krigeage
    Y_pred = modele["mu"] + np.dot(r, modele["poids"])

    return Y_pred

# ==================================================
# 8. PREDICTION INTERACTIVE
# ==================================================

print("\n--- Prediction d'un profil NACA ---")

m_test = float(input("Cambrure maximale m (%) : "))
p_test = float(input("Position de cambrure p (entre 0 et 1) : "))

# Verification du domaine des simulations
if not (X_min[0] <= m_test <= X_max[0]):
    raise ValueError("Cambrure hors du domaine des simulations.")

if not (X_min[1] <= p_test <= X_max[1]):
    raise ValueError("Position de cambrure hors du domaine des simulations.")

# Prediction des coefficients aerodynamiques
Cl_pred = predire(m_test, p_test, modele_Cl)
Cd_pred = predire(m_test, p_test, modele_Cd)

print("\n--- Resultats ---")
print(f"Cambrure maximale : {m_test} %")
print(f"Position de cambrure : {p_test}")
print(f"Cl predit : {Cl_pred:.6f}")
print(f"Cd predit : {Cd_pred:.6f}")