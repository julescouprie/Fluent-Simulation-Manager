from pathlib import Path
import unittest
from core.case_model import PhysicalParameters, SimulationCase, CaseStatus
from core.project_manager import ProjectManager


class TestProjectManager(unittest.TestCase):
    def setUp(self):
        self.pm = ProjectManager()

    def test_add_duplicate_remove(self):
        case1 = SimulationCase(name="Cas 1", parameters=PhysicalParameters(alpha_deg=0.0))
        self.pm.add_case(case1)
        self.assertEqual(len(self.pm.cases), 1)

        clone = self.pm.duplicate_case(case1.id)
        self.assertIsNotNone(clone)
        self.assertEqual(len(self.pm.cases), 2)

        removed = self.pm.remove_case(case1.id)
        self.assertTrue(removed)
        self.assertEqual(len(self.pm.cases), 1)

    def test_save_and_reload_project(self):
        save_file = Path("tests/output/test_project.fsm")
        save_file.parent.mkdir(parents=True, exist_ok=True)

        case1 = SimulationCase(name="Alpha 0", parameters=PhysicalParameters(alpha_deg=0.0, iterations=100))
        case2 = SimulationCase(name="Alpha 5", parameters=PhysicalParameters(alpha_deg=5.0, iterations=120))
        self.pm.add_case(case1)
        self.pm.add_case(case2)

        self.pm.save_project(save_file)
        self.assertTrue(save_file.is_file())

        pm_reloaded = ProjectManager(project_path=save_file)
        self.assertEqual(len(pm_reloaded.cases), 2)
        self.assertEqual(pm_reloaded.cases[0].name, "Alpha 0")
        self.assertEqual(pm_reloaded.cases[1].parameters.alpha_deg, 5.0)

    def test_import_csv(self):
        csv_file = Path("tests/output/test_cases.csv")
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        csv_file.write_text(
            "nom,alpha,vitesse,iterations,corde,maillage\n"
            "Test_Import_1,2.0,30.0,150,1.0,profil_test.bdf\n"
            "Test_Import_2,4.0,35.0,200,1.0,profil_test.bdf\n",
            encoding="utf-8",
        )

        nb = self.pm.import_from_csv(csv_file)
        self.assertEqual(nb, 2)
        self.assertEqual(self.pm.cases[-2].parameters.alpha_deg, 2.0)
        self.assertEqual(self.pm.cases[-1].parameters.velocity, 35.0)


if __name__ == "__main__":
    unittest.main()
