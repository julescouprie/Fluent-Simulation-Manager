import unittest
from pathlib import Path
import numpy as np
import pandas as pd

import sys
BASE_DIR = Path(__file__).resolve().parent.parent
KRIGEAGE_DIR = BASE_DIR / "Krigeage Code"
if str(KRIGEAGE_DIR) not in sys.path:
    sys.path.insert(0, str(KRIGEAGE_DIR))

from kriging_model import (
    correlation,
    construire_R,
    fonction_objectif,
    entrainer_modele,
    charger_donnees_csv,
    KrigingModel,
)


class TestKrigingV2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.csv_path = KRIGEAGE_DIR / "recapitulatif_campagne.csv"
        cls.df, cls.inputs, cls.outputs, cls.info = charger_donnees_csv(cls.csv_path)

    def test_data_loading(self):
        self.assertEqual(len(self.df), 10)
        self.assertIn("m_%", self.inputs)
        self.assertIn("p", self.inputs)
        self.assertIn("Cl", self.outputs)
        self.assertIn("Cd", self.outputs)
        self.assertNotIn("Finesse", self.outputs)  # Ne pas inclure Finesse comme sortie souhaitée

    def test_v1_exact_reproduction_cl(self):
        """Vérifie que pour m_% et p, le modèle Cl donne exactement les theta et prédictions de la V1."""
        X = self.df[["m_%", "p"]].to_numpy(dtype=float)
        Y_Cl = self.df["Cl"].to_numpy(dtype=float)

        model_cl = entrainer_modele(X, Y_Cl, ["m_%", "p"], "Cl", optimize_theta=True)

        # Theta de référence V1 : [1.17667114, 0.11086027]
        np.testing.assert_allclose(model_cl.theta, [1.17667114, 0.11086027], rtol=1e-4)
        self.assertAlmostEqual(model_cl.objectif, -58.710372765, places=3)

        # Prédiction pour le point de test V1 : m=2.0%, p=0.2 -> Cl = 0.188292
        pred = model_cl.predict({"m_%": 2.0, "p": 0.2})
        self.assertAlmostEqual(pred["y_pred"], 0.188292, places=5)
        self.assertTrue(pred["is_inside_domain"])

    def test_v1_exact_reproduction_cd(self):
        """Vérifie que pour m_% et p, le modèle Cd donne exactement les theta et prédictions de la V1."""
        X = self.df[["m_%", "p"]].to_numpy(dtype=float)
        Y_Cd = self.df["Cd"].to_numpy(dtype=float)

        model_cd = entrainer_modele(X, Y_Cd, ["m_%", "p"], "Cd", optimize_theta=True)

        # Theta de référence V1 : [3.83004458, 1.72016532]
        np.testing.assert_allclose(model_cd.theta, [3.83004458, 1.72016532], rtol=1e-4)
        self.assertAlmostEqual(model_cd.objectif, -111.040717, places=3)

        # Prédiction pour le point de test V1 : m=2.0%, p=0.2 -> Cd = 0.010572
        pred = model_cd.predict({"m_%": 2.0, "p": 0.2})
        self.assertAlmostEqual(pred["y_pred"], 0.0105722, places=5)
        self.assertTrue(pred["is_inside_domain"])

    def test_single_variable_selection_m(self):
        """Vérifie que la sélection d'une seule variable (m_%) modifie réellement la matrice X et s'exécute."""
        X_m = self.df[["m_%"]].to_numpy(dtype=float)
        Y_Cl = self.df["Cl"].to_numpy(dtype=float)

        model_m = entrainer_modele(X_m, Y_Cl, ["m_%"], "Cl", optimize_theta=True)
        self.assertEqual(len(model_m.theta), 1)
        self.assertEqual(model_m.X_norm.shape, (10, 1))

        # Prédiction 1D
        pred = model_m.predict([5.0])
        self.assertIsInstance(pred["y_pred"], float)
        self.assertTrue(pred["is_inside_domain"])

    def test_single_variable_selection_p(self):
        """Vérifie que la sélection d'une seule variable (p) modifie la matrice X et s'exécute."""
        X_p = self.df[["p"]].to_numpy(dtype=float)
        Y_Cd = self.df["Cd"].to_numpy(dtype=float)

        model_p = entrainer_modele(X_p, Y_Cd, ["p"], "Cd", optimize_theta=True)
        self.assertEqual(len(model_p.theta), 1)
        self.assertEqual(model_p.X_norm.shape, (10, 1))

    def test_manual_theta_without_optimization(self):
        """Vérifie le fonctionnement lorsque l'optimisation des theta est désactivée."""
        X = self.df[["m_%", "p"]].to_numpy(dtype=float)
        Y_Cl = self.df["Cl"].to_numpy(dtype=float)

        custom = np.array([2.5, 0.5])
        model_manual = entrainer_modele(
            X, Y_Cl, ["m_%", "p"], "Cl", optimize_theta=False, custom_theta=custom
        )
        self.assertFalse(model_manual.is_optimized)
        np.testing.assert_allclose(model_manual.theta, custom)

    def test_out_of_bounds_detection(self):
        """Vérifie que les points hors du domaine d'apprentissage sont correctement détectés."""
        X = self.df[["m_%", "p"]].to_numpy(dtype=float)
        Y_Cl = self.df["Cl"].to_numpy(dtype=float)
        model = entrainer_modele(X, Y_Cl, ["m_%", "p"], "Cl")

        # m = 15.0 est hors domaine [2.0, 10.0]
        pred = model.predict({"m_%": 15.0, "p": 0.4})
        self.assertFalse(pred["is_inside_domain"])
        self.assertEqual(len(pred["out_of_bounds"]), 1)
        self.assertEqual(pred["out_of_bounds"][0][0], "m_%")

    def test_batch_prediction_for_curves_and_maps(self):
        """Vérifie le calcul par lot (batch) pour la génération de graphiques 1D et 2D."""
        X = self.df[["m_%", "p"]].to_numpy(dtype=float)
        Y_Cl = self.df["Cl"].to_numpy(dtype=float)
        model = entrainer_modele(X, Y_Cl, ["m_%", "p"], "Cl")

        # 50 points d'évaluation
        m_vals = np.linspace(2.0, 10.0, 50)
        p_vals = np.full(50, 0.4)
        batch = np.column_stack([m_vals, p_vals])

        preds, inside = model.predict_batch(batch)
        self.assertEqual(len(preds), 50)
        self.assertTrue(np.all(inside))
        self.assertTrue(np.all(np.isfinite(preds)))


if __name__ == "__main__":
    unittest.main()
