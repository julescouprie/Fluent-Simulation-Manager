import unittest
from core.campaign_model import DoEStrategy
from core.design_space import DesignSpace
from doe.sampling import build_doe_campaign, detect_duplicates, generate_lhs_doe, generate_grid_doe


class TestDoESampling(unittest.TestCase):
    def setUp(self):
        self.ds = DesignSpace()
        # Activer 2 variables pour le test
        self.ds.get_variable("alpha_deg").is_active = True
        self.ds.get_variable("camber_m").is_active = True

    def test_lhs_reproducibility(self):
        active_vars = self.ds.get_active_variables()
        lhs1 = generate_lhs_doe(active_vars, n_samples=10, seed=123)
        lhs2 = generate_lhs_doe(active_vars, n_samples=10, seed=123)
        lhs3 = generate_lhs_doe(active_vars, n_samples=10, seed=456)

        self.assertEqual(len(lhs1), 10)
        # La même graine doit donner exactement les mêmes points
        for p1, p2 in zip(lhs1, lhs2):
            self.assertAlmostEqual(p1["alpha_deg"], p2["alpha_deg"])
            self.assertAlmostEqual(p1["camber_m"], p2["camber_m"])

        # Une graine différente doit donner des points différents
        diff = abs(lhs1[0]["alpha_deg"] - lhs3[0]["alpha_deg"]) + abs(lhs1[0]["camber_m"] - lhs3[0]["camber_m"])
        self.assertTrue(diff > 1e-4)

    def test_grid_sampling(self):
        active_vars = self.ds.get_active_variables()
        levels = {"alpha_deg": 4, "camber_m": 3}
        grid = generate_grid_doe(active_vars, levels)
        self.assertEqual(len(grid), 4 * 3)

    def test_duplicate_detection(self):
        active_vars = self.ds.get_active_variables()
        pts = [
            {"alpha_deg": 2.0, "camber_m": 0.02},
            {"alpha_deg": 2.0, "camber_m": 0.02},       # Doublon exact
            {"alpha_deg": 2.00001, "camber_m": 0.02},   # Doublon quasi-identique
            {"alpha_deg": 4.0, "camber_m": 0.04},       # Point distinct
        ]
        unique_pts, n_dups = detect_duplicates(pts, active_vars, tol_norm=1e-3)
        self.assertEqual(len(unique_pts), 2)
        self.assertEqual(n_dups, 2)

    def test_build_doe_campaign_workflow(self):
        strat_params = {"n_samples": 8, "seed": 42}
        points, warnings, meta = build_doe_campaign(DoEStrategy.LHS, self.ds, strat_params)

        self.assertEqual(len(points), 8)
        self.assertEqual(meta["n_valid"], 8)
        # Vérifier que les variables fixes sont présentes (ex: velocity, chord)
        self.assertIn("velocity", points[0])
        self.assertEqual(points[0]["velocity"], 30.0)


if __name__ == "__main__":
    unittest.main()
