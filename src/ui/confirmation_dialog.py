from pathlib import Path
from typing import List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from config.settings_manager import SettingsManager
from core.case_model import CaseStatus, SimulationCase


class ConfirmationDialog(QDialog):
    """Dialogue de validation préalable et de confirmation avant le lancement des calculs."""

    def __init__(self, cases: List[SimulationCase], settings: SettingsManager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Validation & Confirmation du Lancement")
        self.resize(680, 480)
        self.cases = cases
        self.settings = settings

        self.pending_cases = [c for c in cases if c.status == CaseStatus.EN_ATTENTE]

        layout = QVBoxLayout(self)

        # 1. Vérifications préalables
        grp_check = QGroupBox("Contrôles préalables du système")
        lay_check = QVBoxLayout(grp_check)

        self.lbl_mode = QLabel()
        self.lbl_fluent = QLabel()
        self.lbl_mesh = QLabel()

        lay_check.addWidget(self.lbl_mode)
        lay_check.addWidget(self.lbl_fluent)
        lay_check.addWidget(self.lbl_mesh)

        layout.addWidget(grp_check)

        # 2. Résumé des simulations prêtes
        grp_cases = QGroupBox(f"Simulations à exécuter ({len(self.pending_cases)})")
        lay_cases = QVBoxLayout(grp_cases)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "ID", "Nom du cas", "Alpha [°]", "Vitesse [m/s]", "Itérations", "Maillage"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setRowCount(len(self.pending_cases))

        for row, c in enumerate(self.pending_cases):
            self.table.setItem(row, 0, QTableWidgetItem(c.id))
            self.table.setItem(row, 1, QTableWidgetItem(c.name))
            self.table.setItem(row, 2, QTableWidgetItem(f"{c.parameters.alpha_deg:+.2f}°"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{c.parameters.velocity:.1f}"))
            self.table.setItem(row, 4, QTableWidgetItem(str(c.parameters.iterations)))
            self.table.setItem(row, 5, QTableWidgetItem(Path(c.parameters.mesh_file).name))

        lay_cases.addWidget(self.table)
        layout.addWidget(grp_cases)

        # Boutons
        btn_box = QDialogButtonBox()
        self.btn_confirm = QPushButton("🚀 Confirmer et Lancer")
        self.btn_confirm.setObjectName("btn_primary")
        btn_cancel = QPushButton("Annuler")

        btn_box.addButton(self.btn_confirm, QDialogButtonBox.AcceptRole)
        btn_box.addButton(btn_cancel, QDialogButtonBox.RejectRole)

        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        # Exécution des contrôles
        self._run_preflight_checks()

    def _run_preflight_checks(self):
        is_mock = (self.settings.simulation_mode == "mock")

        if is_mock:
            self.lbl_mode.setText("ℹ️ <b>Mode actif :</b> Simulation Fictive (Test/Démonstration sans licence Fluent)")
            self.lbl_mode.setStyleSheet("color: #38bdf8;")
            self.lbl_fluent.setText("✅ <b>Exécutable Fluent :</b> Non requis en mode fictif.")
            self.lbl_fluent.setStyleSheet("color: #10b981;")
        else:
            self.lbl_mode.setText("⚡ <b>Mode actif :</b> Calcul Réel ANSYS Fluent")
            self.lbl_mode.setStyleSheet("color: #38bdf8;")

            if self.settings.is_fluent_valid():
                self.lbl_fluent.setText(f"✅ <b>Fluent détecté :</b> {self.settings.fluent_exe}")
                self.lbl_fluent.setStyleSheet("color: #10b981;")
            else:
                self.lbl_fluent.setText(f"❌ <b>Fluent introuvable :</b> {self.settings.fluent_exe}\n"
                                        "Vérifiez le chemin dans les Préférences ou basculez en Mode Test.")
                self.lbl_fluent.setStyleSheet("color: #ef4444;")
                self.btn_confirm.setEnabled(False)

        # Vérification des fichiers de maillage
        missing_meshes = []
        for c in self.pending_cases:
            mp = Path(c.parameters.mesh_file)
            if not mp.is_absolute():
                mp = Path.cwd() / mp
            if not mp.is_file():
                missing_meshes.append(f"{c.name} ({mp.name})")

        if missing_meshes:
            self.lbl_mesh.setText(f"❌ <b>Maillages introuvables :</b> {', '.join(missing_meshes[:3])}")
            self.lbl_mesh.setStyleSheet("color: #ef4444;")
            self.btn_confirm.setEnabled(False)
        else:
            self.lbl_mesh.setText("✅ <b>Maillages :</b> Tous les fichiers de maillage requis sont accessibles.")
            self.lbl_mesh.setStyleSheet("color: #10b981;")

        if not self.pending_cases:
            self.btn_confirm.setEnabled(False)
            self.btn_confirm.setText("Aucun cas en attente")
