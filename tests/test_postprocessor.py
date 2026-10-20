from pathlib import Path
import unittest
from core.case_model import PhysicalParameters, SimulationCase
from simulation.mock_runner import MockFluentRunner
from postprocessing.postprocessor import process_case_results, read_report


class TestPostprocessor(unittest.TestCase):
    def test_postprocessing_on_mock_results(self):
        runner = MockFluentRunner(
            base_runs_dir=Path("tests/output/post_runs"),
            speed_factor=100.0,
        )
        case = SimulationCase(
            name="Cas NACA 2212 Post Test",
            parameters=PhysicalParameters(alpha_deg=4.0, velocity=30.0, iterations=40),
        )
        runner.run(case)

        # Lancement du post-traitement
        results = process_case_results(Path(case.work_dir), case.parameters)

        self.assertTrue(results.postprocess_success)
        self.assertIsNotNone(results.cl_final)
        self.assertIsNotNone(results.cd_final)
        self.assertIsNotNone(results.cl_cd_ratio)
        self.assertTrue(results.cl_cd_ratio > 0)

        # Vérification des fichiers post-traités
        post_dir = Path(case.work_dir) / "post"
        self.assertTrue((post_dir / "coefficients.csv").is_file())
        self.assertTrue((post_dir / "pressure_distribution.csv").is_file())
        self.assertTrue((post_dir / "cl_convergence.png").is_file())
        self.assertTrue((post_dir / "cd_convergence.png").is_file())
        self.assertTrue((post_dir / "cp_distribution.png").is_file())

    def test_postprocessing_missing_files(self):
        empty_dir = Path("tests/output/empty_run")
        empty_dir.mkdir(parents=True, exist_ok=True)

        params = PhysicalParameters()
        results = process_case_results(empty_dir, params)
        self.assertFalse(results.postprocess_success)
        self.assertIsNone(results.cl_final)
        self.assertIsNone(results.cd_final)


if __name__ == "__main__":
    unittest.main()
