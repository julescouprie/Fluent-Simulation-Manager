from pathlib import Path
import unittest
from core.campaign_model import DoECampaign, DoEStrategy
from core.case_model import CaseStatus, DataOrigin, PhysicalParameters, SimulationCase, SimulationResults
from core.database import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    def setUp(self):
        self.db_path = Path("tests/output/test_fsm_db.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if self.db_path.exists():
            self.db_path.unlink()
        self.db = DatabaseManager(db_path=self.db_path)

    def test_save_and_retrieve_campaign_and_cases(self):
        camp = DoECampaign(
            id="CAMP_TEST_01",
            name="Campagne Test",
            description="Test DoE",
            strategy=DoEStrategy.LHS,
            active_variable_ids=["alpha_deg", "camber_m"],
        )
        self.db.save_campaign(camp)

        case1 = SimulationCase(
            case_id="SIM_DB_01",
            name="NACA 2212 Alpha 0",
            parameters=PhysicalParameters(alpha_deg=0.0, camber_m=0.02),
            status=CaseStatus.TERMINEE_CONVERGEE,
            campaign_id=camp.id,
            data_origin=DataOrigin.REAL_CFD,
        )
        case1.results = SimulationResults(
            cl_final=0.245,
            cd_final=0.0125,
            cl_cd_ratio=19.6,
            is_converged=True,
            quality_flag="Validé (Convergé & Stable)",
            cl_std_last_20=1.2e-4,
        )
        self.db.save_case(case1)

        # Relecture
        campaigns = self.db.get_all_campaigns()
        self.assertEqual(len(campaigns), 1)
        self.assertEqual(campaigns[0].name, "Campagne Test")

        cases = self.db.get_simulations_for_campaign(camp.id)
        self.assertEqual(len(cases), 1)
        c = cases[0]
        self.assertEqual(c.name, "NACA 2212 Alpha 0")
        self.assertEqual(c.status, CaseStatus.TERMINEE_CONVERGEE)
        self.assertAlmostEqual(c.results.cl_final, 0.245)
        self.assertTrue(c.results.is_converged)


if __name__ == "__main__":
    unittest.main()
