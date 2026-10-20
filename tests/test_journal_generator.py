from pathlib import Path
import unittest
from core.case_model import PhysicalParameters, SimulationCase
from simulation.journal_generator import generate_fluent_journal


class TestJournalGenerator(unittest.TestCase):
    def test_journal_generation(self):
        tmp_jou = Path("tests/output/test_solve.jou")
        case = SimulationCase(
            name="Cas Alpha 4deg",
            parameters=PhysicalParameters(alpha_deg=4.0, velocity=35.0, iterations=150),
        )
        out = generate_fluent_journal(case, tmp_jou, mesh_filename="profil_test.bdf")
        self.assertTrue(out.is_file())

        content = out.read_text(encoding="utf-8")

        # Vérifications des instructions clés
        self.assertIn('/file/import/nastran/bulkdata "profil_test.bdf"', content)
        self.assertIn("/define/models/viscous/kw-sst? yes", content)
        self.assertIn("/solve/iterate 150", content)
        self.assertIn("/file/export/ascii airfoil_pressure.csv", content)
        self.assertIn("cl-rep", content)
        self.assertIn("cd-rep", content)

        # Vérification vitesse projetée (vx = 35 * cos(4 deg), vy = 35 * sin(4 deg))
        self.assertIn("34.9147", content)  # 35 * cos(4 deg) ~ 34.9147
        self.assertIn("2.4415", content)   # 35 * sin(4 deg) ~ 2.4415


if __name__ == "__main__":
    unittest.main()
