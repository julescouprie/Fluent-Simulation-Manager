import math
import unittest
from core.case_model import PhysicalParameters, SimulationCase, CaseStatus


class TestCaseModel(unittest.TestCase):
    def test_physical_parameters_calculations(self):
        p = PhysicalParameters(alpha_deg=0.0, velocity=30.0, chord=1.0)
        self.assertAlmostEqual(p.vx, 30.0)
        self.assertAlmostEqual(p.vy, 0.0)
        
        # At alpha = 0, lift vector is (0, 1) and drag vector is (1, 0)
        fx_l, fy_l = p.lift_force_vector
        fx_d, fy_d = p.drag_force_vector
        self.assertAlmostEqual(fx_l, 0.0)
        self.assertAlmostEqual(fy_l, 1.0)
        self.assertAlmostEqual(fx_d, 1.0)
        self.assertAlmostEqual(fy_d, 0.0)

        # At alpha = 30 deg
        p30 = PhysicalParameters(alpha_deg=30.0, velocity=30.0)
        self.assertAlmostEqual(p30.vx, 30.0 * math.cos(math.radians(30)))
        self.assertAlmostEqual(p30.vy, 30.0 * math.sin(math.radians(30)))
        fx_l, fy_l = p30.lift_force_vector
        fx_d, fy_d = p30.drag_force_vector
        self.assertAlmostEqual(fx_l, -math.sin(math.radians(30)))
        self.assertAlmostEqual(fy_l, math.cos(math.radians(30)))
        self.assertAlmostEqual(fx_d, math.cos(math.radians(30)))
        self.assertAlmostEqual(fy_d, math.sin(math.radians(30)))

    def test_validation(self):
        p_ok = PhysicalParameters(velocity=25.0, iterations=100)
        self.assertEqual(len(p_ok.validate()), 0)

        p_err = PhysicalParameters(velocity=-5.0, iterations=-10, alpha_deg=120.0)
        errors = p_err.validate()
        self.assertTrue(len(errors) >= 3)

    def test_case_serialization(self):
        case = SimulationCase(name="Cas Test NACA", parameters=PhysicalParameters(alpha_deg=5.0))
        d = case.to_dict()
        restored = SimulationCase.from_dict(d)
        self.assertEqual(restored.name, case.name)
        self.assertEqual(restored.parameters.alpha_deg, 5.0)
        self.assertEqual(restored.status, CaseStatus.EN_ATTENTE)

    def test_case_clone(self):
        case = SimulationCase(name="Original", parameters=PhysicalParameters(alpha_deg=2.0))
        cloned = case.clone()
        self.assertEqual(cloned.parameters.alpha_deg, 2.0)
        self.assertIn("copie", cloned.name)
        self.assertNotEqual(cloned.id, case.id)


if __name__ == "__main__":
    unittest.main()
