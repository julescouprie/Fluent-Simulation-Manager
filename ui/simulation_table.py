from pathlib import Path
from typing import Dict, List, Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QColor, QFont
from PySide6.QtWidgets import (
    QHeaderView,
    QMenu,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from core.case_model import CaseStatus, SimulationCase


class SimulationTableWidget(QTableWidget):
    """Tableau interactif des simulations CFD avec statuts, jauges et actions."""

    case_double_clicked = Signal(str)           # case_id
    duplicate_requested = Signal(str)           # case_id
    edit_requested = Signal(str)                # case_id
    delete_requested = Signal(list)             # list of case_ids
    retry_requested = Signal(list)              # list of case_ids
    open_folder_requested = Signal(str)         # case_id
    view_logs_requested = Signal(str)           # case_id

    COLUMNS = [
        "ID",
        "Nom du cas",
        "Alpha [°]",
        "Vitesse [m/s]",
        "Corde [m]",
        "Itér.",
        "Statut",
        "Progression",
        "CL Final",
        "CD Final",
        "CL / CD",
        "Durée",
        "Maillage",
        "Message d'état",
    ]

    STATUS_COLORS = {
        CaseStatus.EN_ATTENTE: ("#facc15", "#422006"),
        CaseStatus.PREPARATION: ("#38bdf8", "#082f49"),
        CaseStatus.EN_COURS: ("#0284c7", "#0c4a6e"),
        CaseStatus.POST_TRAITEMENT: ("#818cf8", "#1e1b4b"),
        CaseStatus.TERMINEE_CONVERGEE: ("#10b981", "#064e3b"),
        CaseStatus.TERMINEE_NON_CONVERGEE: ("#f59e0b", "#451a03"),
        CaseStatus.INCOMPLETE: ("#ea580c", "#431407"),
        CaseStatus.ECHEC: ("#ef4444", "#450a0a"),
        CaseStatus.ANNULEE: ("#94a3b8", "#1e293b"),
    }

    def __init__(self):
        super().__init__()
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setSelectionMode(QTableWidget.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.horizontalHeader().setStretchLastSection(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)

        self.customContextMenuRequested.connect(self._show_context_menu)
        self.cellDoubleClicked.connect(self._on_cell_double_clicked)

        # Mapping case_id -> ligne
        self._case_id_to_row: Dict[str, int] = {}

    def populate(self, cases: List[SimulationCase]):
        """Recharge l'intégralité du tableau avec la liste de cas."""
        self.setRowCount(0)
        self._case_id_to_row.clear()

        for case in cases:
            self.add_or_update_case_row(case)

        # Ajustement des largeurs de colonnes
        self.resizeColumnToContents(0)  # ID
        self.resizeColumnToContents(1)  # Nom
        self.resizeColumnToContents(2)  # Alpha
        self.resizeColumnToContents(3)  # Vitesse
        self.resizeColumnToContents(6)  # Statut
        self.setColumnWidth(7, 130)     # Barre de progression

    def add_or_update_case_row(self, case: SimulationCase):
        """Ajoute ou met à jour une ligne du tableau pour un cas donné."""
        row = self._case_id_to_row.get(case.id)
        if row is None or row >= self.rowCount():
            row = self.rowCount()
            self.insertRow(row)
            self._case_id_to_row[case.id] = row

        # 0: ID
        item_id = QTableWidgetItem(case.id)
        item_id.setTextAlignment(Qt.AlignCenter)
        item_id.setFlags(item_id.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 0, item_id)

        # 1: Nom
        item_name = QTableWidgetItem(case.name)
        item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 1, item_name)

        # 2: Alpha
        item_alpha = QTableWidgetItem(f"{case.parameters.alpha_deg:.2f}°")
        item_alpha.setTextAlignment(Qt.AlignCenter)
        item_alpha.setFlags(item_alpha.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 2, item_alpha)

        # 3: Vitesse
        item_v = QTableWidgetItem(f"{case.parameters.velocity:.1f}")
        item_v.setTextAlignment(Qt.AlignCenter)
        item_v.setFlags(item_v.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 3, item_v)

        # 4: Corde
        item_c = QTableWidgetItem(f"{case.parameters.chord:.2f}")
        item_c.setTextAlignment(Qt.AlignCenter)
        item_c.setFlags(item_c.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 4, item_c)

        # 5: Itérations
        item_it = QTableWidgetItem(str(case.parameters.iterations))
        item_it.setTextAlignment(Qt.AlignCenter)
        item_it.setFlags(item_it.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 5, item_it)

        # 6: Statut
        item_status = QTableWidgetItem(case.status.value)
        item_status.setTextAlignment(Qt.AlignCenter)
        fg_col, bg_col = self.STATUS_COLORS.get(case.status, ("#ffffff", "#334155"))
        item_status.setForeground(QColor(fg_col))
        item_status.setFont(QFont("Segoe UI", 9, QFont.Bold))
        item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 6, item_status)

        # 7: Progression
        pbar = self.cellWidget(row, 7)
        if not isinstance(pbar, QProgressBar):
            pbar = QProgressBar()
            pbar.setTextVisible(True)
            self.setCellWidget(row, 7, pbar)

        if case.status.is_active:
            if case.progress_percent >= 0:
                pbar.setRange(0, 100)
                pbar.setValue(case.progress_percent)
                pbar.setFormat(f"{case.current_iteration}/{case.total_iterations} ({case.progress_percent}%)")
            else:
                pbar.setRange(0, 0)
                pbar.setFormat("Calcul en cours...")
        elif case.status == CaseStatus.TERMINEE_CONVERGEE:
            pbar.setRange(0, 100)
            pbar.setValue(100)
            pbar.setFormat("100% Convergé")
        elif case.status == CaseStatus.TERMINEE_NON_CONVERGEE:
            pbar.setRange(0, 100)
            pbar.setValue(100)
            pbar.setFormat("100% Non-stabilisé")
        elif case.status == CaseStatus.INCOMPLETE:
            pbar.setRange(0, 100)
            pbar.setValue(case.progress_percent)
            pbar.setFormat("Incomplet")
        elif case.status == CaseStatus.ECHEC:
            pbar.setRange(0, 100)
            pbar.setValue(case.progress_percent)
            pbar.setFormat("Échec")
        elif case.status == CaseStatus.ANNULEE:
            pbar.setRange(0, 100)
            pbar.setValue(case.progress_percent)
            pbar.setFormat("Annulée")
        else:  # EN_ATTENTE
            pbar.setRange(0, 100)
            pbar.setValue(0)
            pbar.setFormat("En attente")

        # 8: CL Final
        cl_str = f"{case.results.cl_final:.5f}" if case.results.cl_final is not None else "-"
        item_cl = QTableWidgetItem(cl_str)
        item_cl.setTextAlignment(Qt.AlignCenter)
        item_cl.setFlags(item_cl.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 8, item_cl)

        # 9: CD Final
        cd_str = f"{case.results.cd_final:.5f}" if case.results.cd_final is not None else "-"
        item_cd = QTableWidgetItem(cd_str)
        item_cd.setTextAlignment(Qt.AlignCenter)
        item_cd.setFlags(item_cd.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 9, item_cd)

        # 10: CL/CD
        ratio_str = f"{case.results.cl_cd_ratio:.2f}" if case.results.cl_cd_ratio is not None else "-"
        item_ratio = QTableWidgetItem(ratio_str)
        item_ratio.setTextAlignment(Qt.AlignCenter)
        item_ratio.setFlags(item_ratio.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 10, item_ratio)

        # 11: Durée
        dur_str = f"{case.duration_seconds:.1f} s" if case.duration_seconds > 0 else "-"
        item_dur = QTableWidgetItem(dur_str)
        item_dur.setTextAlignment(Qt.AlignCenter)
        item_dur.setFlags(item_dur.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 11, item_dur)

        # 12: Maillage
        mesh_name = Path(case.parameters.mesh_file).name
        item_mesh = QTableWidgetItem(mesh_name)
        item_mesh.setFlags(item_mesh.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 12, item_mesh)

        # 13: Message d'état
        msg = case.error_message or ("Prêt" if case.status == CaseStatus.EN_ATTENTE else "")
        item_msg = QTableWidgetItem(msg)
        if case.status == CaseStatus.ECHEC:
            item_msg.setForeground(QColor("#ef4444"))
        item_msg.setFlags(item_msg.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 13, item_msg)

    def get_selected_case_ids(self) -> List[str]:
        selected_rows = set(index.row() for index in self.selectedIndexes())
        ids = []
        for r in selected_rows:
            item = self.item(r, 0)
            if item:
                ids.append(item.text())
        return ids

    def _on_cell_double_clicked(self, row: int, col: int):
        item = self.item(row, 0)
        if item:
            self.case_double_clicked.emit(item.text())

    def _show_context_menu(self, pos):
        selected_ids = self.get_selected_case_ids()
        if not selected_ids:
            return

        menu = QMenu(self)
        first_id = selected_ids[0]

        act_edit = QAction("✏️ Modifier le cas", self)
        act_edit.triggered.connect(lambda: self.edit_requested.emit(first_id))
        menu.addAction(act_edit)

        act_dup = QAction("📑 Dupliquer", self)
        act_dup.triggered.connect(lambda: self.duplicate_requested.emit(first_id))
        menu.addAction(act_dup)

        act_retry = QAction("🔄 Réinitialiser / Relancer", self)
        act_retry.triggered.connect(lambda: self.retry_requested.emit(selected_ids))
        menu.addAction(act_retry)

        act_folder = QAction("📁 Ouvrir le dossier de calcul", self)
        act_folder.triggered.connect(lambda: self.open_folder_requested.emit(first_id))
        menu.addAction(act_folder)

        act_logs = QAction("📜 Voir le journal Fluent", self)
        act_logs.triggered.connect(lambda: self.view_logs_requested.emit(first_id))
        menu.addAction(act_logs)

        menu.addSeparator()

        act_del = QAction("❌ Supprimer de la file", self)
        act_del.triggered.connect(lambda: self.delete_requested.emit(selected_ids))
        menu.addAction(act_del)

        menu.exec(self.viewport().mapToGlobal(pos))
