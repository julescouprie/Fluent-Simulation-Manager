from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from core.case_model import PhysicalParameters, SimulationCase


class CaseDialog(QDialog):
    """Boîte de dialogue de création ou de modification d'une simulation CFD."""

    def __init__(self, parent=None, case: Optional[SimulationCase] = None):
        super().__init__(parent)
        self.setWindowTitle("Configuration de la Simulation" if case else "Ajouter une Simulation")
        self.resize(520, 560)
        self.case = case

        main_layout = QVBoxLayout(self)

        # 1. Informations générales
        grp_general = QGroupBox("Identification du cas")
        lay_gen = QFormLayout(grp_general)

        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("Ex: NACA 2212 - Alpha 4°")
        lay_gen.addRow("Nom de la simulation :", self.edit_name)

        # Fichier de maillage
        lay_mesh = QHBoxLayout()
        self.edit_mesh = QLineEdit("profil_test.bdf")
        btn_browse_mesh = QPushButton("Parcourir...")
        btn_browse_mesh.clicked.connect(self._browse_mesh)
        lay_mesh.addWidget(self.edit_mesh)
        lay_mesh.addWidget(btn_browse_mesh)
        lay_gen.addRow("Fichier de maillage :", lay_mesh)

        main_layout.addWidget(grp_general)

        # 2. Paramètres aérodynamiques
        grp_aero = QGroupBox("Paramètres d'écoulement et géométrie")
        lay_aero = QFormLayout(grp_aero)

        self.spin_alpha = QDoubleSpinBox()
        self.spin_alpha.setRange(-90.0, 90.0)
        self.spin_alpha.setDecimals(2)
        self.spin_alpha.setSingleStep(0.5)
        self.spin_alpha.setSuffix(" °")
        self.spin_alpha.setValue(0.0)
        lay_aero.addRow("Angle d'incidence (alpha) :", self.spin_alpha)

        self.spin_velocity = QDoubleSpinBox()
        self.spin_velocity.setRange(0.1, 1000.0)
        self.spin_velocity.setDecimals(2)
        self.spin_velocity.setSingleStep(1.0)
        self.spin_velocity.setSuffix(" m/s")
        self.spin_velocity.setValue(30.0)
        lay_aero.addRow("Vitesse de l'écoulement (U) :", self.spin_velocity)

        self.spin_chord = QDoubleSpinBox()
        self.spin_chord.setRange(0.01, 100.0)
        self.spin_chord.setDecimals(3)
        self.spin_chord.setSingleStep(0.1)
        self.spin_chord.setSuffix(" m")
        self.spin_chord.setValue(1.0)
        lay_aero.addRow("Longueur de corde (c) :", self.spin_chord)

        self.spin_density = QDoubleSpinBox()
        self.spin_density.setRange(0.01, 100.0)
        self.spin_density.setDecimals(4)
        self.spin_density.setSingleStep(0.01)
        self.spin_density.setSuffix(" kg/m³")
        self.spin_density.setValue(1.225)
        lay_aero.addRow("Masse volumique (rho) :", self.spin_density)

        self.spin_pref = QDoubleSpinBox()
        self.spin_pref.setRange(-1e6, 1e6)
        self.spin_pref.setDecimals(1)
        self.spin_pref.setSuffix(" Pa")
        self.spin_pref.setValue(0.0)
        lay_aero.addRow("Pression de référence :", self.spin_pref)

        main_layout.addWidget(grp_aero)

        # 3. Paramètres numériques et solveur
        grp_solver = QGroupBox("Résolution numérique Fluent")
        lay_solver = QFormLayout(grp_solver)

        self.spin_iters = QSpinBox()
        self.spin_iters.setRange(1, 100000)
        self.spin_iters.setSingleStep(50)
        self.spin_iters.setValue(200)
        lay_solver.addRow("Nombre d'itérations :", self.spin_iters)

        self.spin_cores = QSpinBox()
        self.spin_cores.setRange(1, 128)
        self.spin_cores.setValue(4)
        lay_solver.addRow("Cœurs CPU alloués :", self.spin_cores)

        self.combo_turb = QComboBox()
        self.combo_turb.addItem("k-omega SST (Validé ANSYS 2026 R1)", "kw-sst")
        self.combo_turb.setEnabled(False)  # Fixé au modèle validé pour ce journal
        lay_solver.addRow("Modèle de turbulence :", self.combo_turb)

        lbl_turb_note = QLabel("<i>Note : Le modèle k-omega SST est le seul automatisé et validé pour ce cas.</i>")
        lbl_turb_note.setStyleSheet("color: #94a3b8; font-size: 11px;")
        lay_solver.addRow("", lbl_turb_note)

        main_layout.addWidget(grp_solver)

        # Boutons OK / Annuler
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        # Si édition d'un cas existant
        if self.case:
            self._load_case_data(self.case)
        else:
            self.edit_name.setText("Cas NACA 2212 - Alpha 0°")

    def _load_case_data(self, case: SimulationCase):
        self.edit_name.setText(case.name)
        p = case.parameters
        self.edit_mesh.setText(p.mesh_file)
        self.spin_alpha.setValue(p.alpha_deg)
        self.spin_velocity.setValue(p.velocity)
        self.spin_chord.setValue(p.chord)
        self.spin_density.setValue(p.density)
        self.spin_pref.setValue(p.pressure_ref)
        self.spin_iters.setValue(p.iterations)
        self.spin_cores.setValue(p.cores)

    def _browse_mesh(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner le maillage",
            "",
            "Maillages Nastran / Fluent (*.bdf *.dat *.nas *.msh *.cas *.cas.h5);;Tous les fichiers (*.*)",
        )
        if file_path:
            self.edit_mesh.setText(file_path)

    def _on_accept(self):
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Champ manquant", "Veuillez attribuer un nom à la simulation.")
            return

        mesh_file = self.edit_mesh.text().strip()
        if not mesh_file:
            QMessageBox.warning(self, "Champ manquant", "Veuillez renseigner un fichier de maillage.")
            return

        self.accept()

    def get_parameters(self) -> PhysicalParameters:
        return PhysicalParameters(
            mesh_file=self.edit_mesh.text().strip(),
            alpha_deg=self.spin_alpha.value(),
            velocity=self.spin_velocity.value(),
            density=self.spin_density.value(),
            pressure_ref=self.spin_pref.value(),
            chord=self.spin_chord.value(),
            iterations=self.spin_iters.value(),
            cores=self.spin_cores.value(),
            turbulence_model="kw-sst",
        )

    def get_case_name(self) -> str:
        return self.edit_name.text().strip()
