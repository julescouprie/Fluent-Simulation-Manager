from pathlib import Path
import unittest
from core.case_model import CaseStatus, DataOrigin, PhysicalParameters, SimulationCase, SimulationResults
from core.design_space import DesignSpace
from postprocessing.kriging_exporter import extract_kriging_matrices, save_kriging_files


class TestKrigingExporter(unittest.TestCase):
    def setUp(self):
        self.ds = DesignSpace()
        self.cases = []

        # 3 cas convergés
        for i, a in enumerate([0.0, 2.0, 4.0]):
            c = SimulationCase(
                case_id=f"SIM_00{i+1}",
                name=f"NACA Alpha {a}",
                parameters=PhysicalParameters(alpha_deg=a, camber_m=0.02, thickness_t=0.12),
                status=CaseStatus.TERMINEE_CONVERGEE,
                data_origin=DataOrigin.REAL_CFD,
            )
            c.results = SimulationResults(
                cl_final=0.22 + 0.1 * a,
                cd_final=0.01 + 0.001 * a,
                cl_cd_ratio=20.0,
                is_converged=True,
                quality_flag="Validé (Convergé & Stable)",
            )
            self.cases.append(c)

        # 1 cas non convergé (qui doit être exclu par défaut)
        c_bad = SimulationCase(
            case_id="SIM_BAD",
            name="NACA Bad",
            parameters=PhysicalParameters(alpha_deg=10.0),
            status=CaseStatus.TERMINEE_NON_CONVERGEE,
        )
        c_bad.results = SimulationResults(cl_final=1.1, cd_final=0.05, is_converged=False)
        self.cases.append(c_bad)

    def test_extract_and_exclude_unconverged(self):
        active_vars = ["alpha_deg", "camber_m", "thickness_t"]
        dataset = extract_kriging_matrices(
            cases=self.cases,
            active_var_ids=active_vars,
            only_converged=True,
            normalize_X=True,
            design_space=self.ds,
        )

        self.assertTrue(dataset["success"])
        # Doit contenir exactement les 3 cas convergés et exclure SIM_BAD
        self.assertEqual(dataset["n_samples"], 3)
        self.assertIn("X", dataset)
        self.assertIn("Y", dataset)
        self.assertEqual(len(dataset["X"].columns), 3)

        # Vérification normalisation [0, 1]
        for val in dataset["X"]["alpha_deg"].values:
            self.assertTrue(0.0 <= val <= 1.0)

    def test_save_kriging_files_on_disk(self):
        active_vars = ["alpha_deg", "camber_m"]
        dataset = extract_kriging_matrices(
            cases=self.cases,
            active_var_ids=active_vars,
            only_converged=True,
        )
        out_dir = Path("tests/output/kriging_export")
        files = save_kriging_files(dataset, out_dir, prefix="test_dataset")

        self.assertTrue(len(files) >= 3)
        self.assertTrue((out_dir / "test_dataset_X.csv").is_file())
        self.assertTrue((out_dir / "test_dataset_Y.csv").is_file())
        self.assertTrue((out_dir / "test_dataset_metadata.json").is_file())


if __name__ == "__main__":
    unittest.main()
