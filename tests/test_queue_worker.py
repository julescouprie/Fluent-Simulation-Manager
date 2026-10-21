import sys
import time
import unittest
from pathlib import Path
from PySide6.QtCore import QCoreApplication

from core.case_model import PhysicalParameters, SimulationCase, CaseStatus
from core.project_manager import ProjectManager
from core.queue_worker import QueueWorker


class TestQueueWorker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QCoreApplication.instance()
        if not cls.app:
            cls.app = QCoreApplication(sys.argv)

    def test_queue_execution_end_to_end(self):
        pm = ProjectManager()
        c1 = SimulationCase(name="Case Alpha 0", parameters=PhysicalParameters(alpha_deg=0.0, iterations=30))
        c2 = SimulationCase(name="Case Alpha 4", parameters=PhysicalParameters(alpha_deg=4.0, iterations=30))
        c3_fail = SimulationCase(name="Case Simulated Fail", parameters=PhysicalParameters(alpha_deg=8.0, iterations=30))
        pm.add_case(c1)
        pm.add_case(c2)
        pm.add_case(c3_fail)

        started = []
        progresses = []
        finished = []

        worker = QueueWorker(
            cases_getter=lambda: pm.cases,
            fluent_exe_getter=lambda: "",
            mode_getter=lambda: "mock",
            base_runs_dir=Path("tests/output/worker_runs"),
            mock_speed_factor=100.0,
        )
        worker.case_started.connect(lambda cid: started.append(cid))
        worker.case_progress.connect(lambda cid, cur, tot: progresses.append((cid, cur, tot)))
        worker.case_finished.connect(lambda cid, ok, err: finished.append((cid, ok, err)))

        worker.start_queue()

        # Attente de la fin de la file (avec timeout de 10s)
        timeout = 10.0
        start = time.time()
        while worker.is_running and (time.time() - start) < timeout:
            QCoreApplication.processEvents()
            time.sleep(0.02)

        # Attente que les signaux inter-threads restants soient délivrés
        for _ in range(10):
            QCoreApplication.processEvents()
            time.sleep(0.01)

        self.assertFalse(worker.is_running)
        self.assertEqual(len(started), 3)
        self.assertEqual(len(finished), 3)

        # c1 et c2 doivent être terminées avec succès (et convergence validée)
        self.assertEqual(c1.status, CaseStatus.TERMINEE_CONVERGEE)
        self.assertIsNotNone(c1.results.cl_final)
        self.assertEqual(c2.status, CaseStatus.TERMINEE_CONVERGEE)
        self.assertIsNotNone(c2.results.cl_final)

        # c3 doit être en échec car son nom contient "fail"
        self.assertEqual(c3_fail.status, CaseStatus.ECHEC)
        self.assertIn("Divergence", c3_fail.error_message)


if __name__ == "__main__":
    unittest.main()
