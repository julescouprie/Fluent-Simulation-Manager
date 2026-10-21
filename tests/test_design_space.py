import unittest
from core.design_space import DesignSpace, DesignVariable, VariableCategory, VariableType


class TestDesignSpace(unittest.TestCase):
    def setUp(self):
        self.ds = DesignSpace()

    def test_catalog_initialization(self):
        # Vérification des variables clés
        camber = self.ds.get_variable("camber_m")
        self.assertIsNotNone(camber)
        self.assertEqual(camber.symbol, "m")
        self.assertTrue(camber.is_operational)

        ground = self.ds.get_variable("ground_height_h")
        self.assertIsNotNone(ground)
        # La garde au sol doit être marquée comme non opérationnelle pour la phase 2D
        self.assertFalse(ground.is_operational)

    def test_normalization_denormalization(self):
        var = self.ds.get_variable("alpha_deg")
        # alpha in [-10, 20]
        norm_0 = var.normalize(5.0)  # (5 - (-10)) / 30 = 15/30 = 0.5
        self.assertAlmostEqual(norm_0, 0.5)
        denorm = var.denormalize(0.5)
        self.assertAlmostEqual(denorm, 5.0)

    def test_point_validation_valid(self):
        pt = {
            "camber_m": 0.04,
            "camber_p": 0.40,
            "thickness_t": 0.15,
            "alpha_deg": 4.0,
            "velocity": 30.0,
        }
        ok, errors = self.ds.validate_point(pt)
        self.assertTrue(ok)
        self.assertEqual(len(errors), 0)

    def test_point_validation_invalid(self):
        pt_bad = {
            "camber_m": 0.25,      # Hors bornes max (max = 0.08 / 0.10)
            "thickness_t": 0.01,   # Trop fin (< 2%)
            "alpha_deg": 45.0,     # Hors bornes max (max = 20°)
        }
        ok, errors = self.ds.validate_point(pt_bad)
        self.assertFalse(ok)
        self.assertTrue(len(errors) >= 2)


if __name__ == "__main__":
    unittest.main()
