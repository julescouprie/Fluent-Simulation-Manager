import os
import sys
from pathlib import Path
import unittest
from PySide6.QtWidgets import QApplication

os.environ["QT_QPA_PLATFORM"] = "offscreen"


class TestGUIHeadless(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance()
        if not cls.app:
            cls.app = QApplication(sys.argv)

    def test_main_window_init(self):
        from ui.main_window import MainWindow

        window = MainWindow()
        self.assertIsNotNone(window)
        self.assertEqual(window.tabs.count(), 6)

        # Vérification des cas par défaut
        self.assertTrue(len(window.project_manager.cases) >= 5)

        # Vérification du tableau
        self.assertEqual(window.table.rowCount(), len(window.project_manager.cases))

        # Test de sélection
        window.table.selectRow(0)
        selected_ids = window.table.get_selected_case_ids()
        self.assertEqual(len(selected_ids), 1)

        window.close()


if __name__ == "__main__":
    unittest.main()
