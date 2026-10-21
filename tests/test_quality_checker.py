import unittest
import numpy as np
import pandas as pd
from postprocessing.quality_checker import assess_convergence_quality, QualityFlag


class TestQualityChecker(unittest.TestCase):
    def test_converged_case(self):
        # Simulation d'un historique stabilisé
        iters = list(range(1, 101))
        # Décroissance exponentielle vers CL = 0.45 avec bruit décroissant
        cl_vals = [0.45 * (1.0 - np.exp(-i / 15.0)) + np.random.normal(0, 1e-4) for i in iters]
        cd_vals = [0.015 * (1.0 + np.exp(-i / 15.0)) + np.random.normal(0, 1e-5) for i in iters]

        cl_df = pd.DataFrame({"iteration": iters, "value": cl_vals})
        cd_df = pd.DataFrame({"iteration": iters, "value": cd_vals})

        res = assess_convergence_quality(cl_df, cd_df)
        self.assertTrue(res.is_converged)
        self.assertEqual(res.quality_flag, QualityFlag.VALID)
        self.assertAlmostEqual(res.cl_final, cl_vals[-1], places=3)
        self.assertTrue(res.cl_std_last_20 < 1.5e-3)

    def test_oscillating_case(self):
        iters = list(range(1, 101))
        # Fortes oscillations non amorties en fin de calcul
        cl_vals = [0.45 + 0.05 * np.sin(i) for i in iters]
        cd_vals = [0.02 + 0.005 * np.cos(i) for i in iters]

        cl_df = pd.DataFrame({"iteration": iters, "value": cl_vals})
        cd_df = pd.DataFrame({"iteration": iters, "value": cd_vals})

        res = assess_convergence_quality(cl_df, cd_df)
        self.assertFalse(res.is_converged)
        self.assertEqual(res.quality_flag, QualityFlag.WARNING_OSCILLATING)

    def test_diverged_nan_case(self):
        iters = [1, 2, 3]
        cl_df = pd.DataFrame({"iteration": iters, "value": [0.2, 0.4, np.nan]})
        cd_df = pd.DataFrame({"iteration": iters, "value": [0.01, 0.02, 0.03]})

        res = assess_convergence_quality(cl_df, cd_df)
        self.assertFalse(res.is_converged)
        self.assertEqual(res.quality_flag, QualityFlag.DIVERGED)


if __name__ == "__main__":
    unittest.main()
