from pathlib import Path
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)

from config.settings_manager import SettingsManager


class SettingsDialog(QDialog):
    """Boîte de dialogue de configuration de l'application et d'ANSYS Fluent."""

    def __init__(self, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Préférences & Configuration ANSYS Fluent")
        self.resize(580, 480)
        self.settings = settings_manager

        main_layout = QVBoxLayout(self)

        # 1. Configuration ANSYS Fluent
        grp_fluent = QGroupBox("Environnement ANSYS Fluent")
        lay_fluent = QVBoxLayout(grp_fluent)

        lay_path = QHBoxLayout()
        self.edit_fluent_exe = QLineEdit(self.settings.fluent_exe)
        self.edit_fluent_exe.textChanged.connect(self._update_fluent_status)
        btn_browse = QPushButton("Parcourir...")
        btn_browse.clicked.connect(self._browse_fluent)
        btn_detect = QPushButton("🔍 Auto-détection")
        btn_detect.clicked.connect(self._auto_detect_fluent)

        lay_path.addWidget(self.edit_fluent_exe)
        lay_path.addWidget(btn_browse)
        lay_path.addWidget(btn_detect)

        lay_fluent.addWidget(QLabel("Chemin vers fluent.exe :"))
        lay_fluent.addLayout(lay_path)

        self.lbl_status = QLabel()
        self.lbl_status.setStyleSheet("font-weight: bold; padding: 4px;")
        lay_fluent.addWidget(self.lbl_status)
        self._update_fluent_status()

        main_layout.addWidget(grp_fluent)

        # 2. Mode d'exécution
        grp_mode = QGroupBox("Mode d'exécution")
        lay_mode = QVBoxLayout(grp_mode)

        self.radio_real = QRadioButton("Exécution réelle ANSYS Fluent (Nécessite ANSYS Fluent 2026 R1 installé)")
        self.radio_mock = QRadioButton("Mode Test / Simulation Fictive (Calcul simulé pour démonstration et validation sans licence)")

        self.btn_group_mode = QButtonGroup(self)
        self.btn_group_mode.addButton(self.radio_real)
        self.btn_group_mode.addButton(self.radio_mock)

        if self.settings.simulation_mode == "mock":
            self.radio_mock.setChecked(True)
        else:
            self.radio_real.setChecked(True)

        lay_mode.addWidget(self.radio_real)
        lay_mode.addWidget(self.radio_mock)
        main_layout.addWidget(grp_mode)

        # 3. Paramètres généraux
        grp_general = QGroupBox("Paramètres par défaut")
        lay_gen = QFormLayout(grp_general)

        self.spin_default_cores = QSpinBox()
        self.spin_default_cores.setRange(1, 128)
        self.spin_default_cores.setValue(self.settings.default_cores)
        lay_gen.addRow("Cœurs CPU par défaut :", self.spin_default_cores)

        lay_runs = QHBoxLayout()
        self.edit_runs_dir = QLineEdit(self.settings.get("runs_dir", "runs"))
        btn_browse_runs = QPushButton("Parcourir...")
        btn_browse_runs.clicked.connect(self._browse_runs_dir)
        lay_runs.addWidget(self.edit_runs_dir)
        lay_runs.addWidget(btn_browse_runs)
        lay_gen.addRow("Dossier des résultats :", lay_runs)

        main_layout.addWidget(grp_general)

        # Boutons
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

    def _update_fluent_status(self):
        path_str = self.edit_fluent_exe.text().strip()
        p = Path(path_str)
        if p.is_file() and p.name.lower().startswith("fluent"):
            self.lbl_status.setText("✅ Exécutable Fluent valide et détecté.")
            self.lbl_status.setStyleSheet("color: #10b981; font-weight: bold;")
        elif path_str:
            self.lbl_status.setText("❌ Exécutable Fluent introuvable à cet emplacement.")
            self.lbl_status.setStyleSheet("color: #ef4444; font-weight: bold;")
        else:
            self.lbl_status.setText("⚠️ Aucun chemin Fluent configuré.")
            self.lbl_status.setStyleSheet("color: #facc15; font-weight: bold;")

    def _browse_fluent(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner fluent.exe",
            r"C:\Program Files\ANSYS Inc",
            "Exécutable Fluent (fluent.exe);;Tous les fichiers (*.*)",
        )
        if file_path:
            self.edit_fluent_exe.setText(file_path)

    def _auto_detect_fluent(self):
        found = SettingsManager.detect_fluent_installations()
        if found:
            self.edit_fluent_exe.setText(found[0])
            QMessageBox.information(
                self,
                "Détection réussie",
                f"ANSYS Fluent a été trouvé automatiquement :\n{found[0]}",
            )
        else:
            QMessageBox.warning(
                self,
                "Détection infructueuse",
                "Aucune installation ANSYS Fluent n'a été détectée automatiquement dans les répertoires standards.\n"
                "Veuillez spécifier manuellement l'emplacement de fluent.exe.",
            )

    def _browse_runs_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier des runs")
        if dir_path:
            self.edit_runs_dir.setText(dir_path)

    def _on_accept(self):
        self.settings.fluent_exe = self.edit_fluent_exe.text().strip()
        self.settings.simulation_mode = "mock" if self.radio_mock.isChecked() else "real"
        self.settings.set("default_cores", self.spin_default_cores.value())
        self.settings.set("runs_dir", self.edit_runs_dir.text().strip())
        self.settings.save()
        self.accept()
