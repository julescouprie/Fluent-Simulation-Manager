from pathlib import Path
import unittest
from config.settings_manager import SettingsManager
from core.case_model import PhysicalParameters, SimulationCase, CaseStatus
from simulation.fluent_runner import FluentRunner


class TestFluentPathValidation(unittest.TestCase):
    def test_invalid_path_detection(self):
        sm = SettingsManager()
        sm.fluent_exe = r"C:\Faux\Chemin\Inexistant\fluent.exe"
        self.assertFalse(sm.is_fluent_valid())

        runner = FluentRunner(
            fluent_exe=Path(sm.fluent_exe),
            base_runs_dir=Path("tests/output/runs"),
        )
        case = SimulationCase(
            name="Cas Test Chemin Invalide",
            parameters=PhysicalParameters(alpha_deg=0.0),
        )

        dummy_mesh = Path("tests/output/dummy.bdf")
        dummy_mesh.parent.mkdir(parents=True, exist_ok=True)
        dummy_mesh.write_text("DUMMY MESH", encoding="utf-8")

        success = runner.run(case, dummy_mesh)
        self.assertFalse(success)
        self.assertEqual(case.status, CaseStatus.ECHEC)
        self.assertIn("Exécutable Fluent introuvable", case.error_message)


if __name__ == "__main__":
    unittest.main()
