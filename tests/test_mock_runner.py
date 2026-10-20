from pathlib import Path
import unittest
from core.case_model import PhysicalParameters, SimulationCase, CaseStatus
from simulation.mock_runner import MockFluentRunner


class TestMockRunner(unittest.TestCase):
    def test_mock_simulation_success(self):
        progress_events = []
        log_events = []

        runner = MockFluentRunner(
            base_runs_dir=Path("tests/output/mock_runs"),
            on_log=lambda l: log_events.append(l),
            on_progress=lambda c, t: progress_events.append((c, t)),
            speed_factor=100.0,  # Très rapide pour les tests unitaires
        )

        case = SimulationCase(
            name="Cas Test Réussi",
            parameters=PhysicalParameters(alpha_deg=2.0, velocity=30.0, iterations=50),
        )

        success = runner.run(case)
        self.assertTrue(success)
        self.assertEqual(case.status, CaseStatus.POST_TRAITEMENT)
        self.assertEqual(case.current_iteration, 50)
        self.assertTrue(len(progress_events) > 0)
        self.assertTrue(len(log_events) > 0)

        # Vérification des fichiers produits
        work_dir = Path(case.work_dir)
        self.assertTrue((work_dir / "cl_test.txt").is_file())
        self.assertTrue((work_dir / "cd_test.txt").is_file())
        self.assertTrue((work_dir / "airfoil_pressure.csv").is_file())
        self.assertTrue((work_dir / "fluent_execution.log").is_file())

    def test_mock_simulation_failure_handling(self):
        runner = MockFluentRunner(
            base_runs_dir=Path("tests/output/mock_runs"),
            speed_factor=100.0,
        )

        case = SimulationCase(
            name="Cas Test Echec Simule",
            parameters=PhysicalParameters(alpha_deg=10.0, iterations=60),
        )

        success = runner.run(case)
        self.assertFalse(success)
        self.assertEqual(case.status, CaseStatus.ECHEC)
        self.assertIn("Divergence numérique", case.error_message)


if __name__ == "__main__":
    unittest.main()
