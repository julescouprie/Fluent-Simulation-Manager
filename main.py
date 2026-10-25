import os
import sys
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

# Assurer que les répertoires racine et src sont dans sys.path
BASE_DIR = Path(__file__).resolve().parent
SRC_DIR = BASE_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from ui.main_window import MainWindow


def main():
    # Adaptation haute résolution d'écran sous Windows
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Fluent Simulation Manager")
    app.setOrganizationName("AeroCFD")
    app.setApplicationVersion("1.0.0")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
