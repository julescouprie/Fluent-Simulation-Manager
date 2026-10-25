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
    """Tableau interactif des simulations CFD avec statuts et actions."""

    case_double_clicked = Signal(str)           # case_id
    duplicate_requested = Signal(str)           # case_id
    edit_requested = Signal(str)                # case_id
    delete_requested = Signal(list)             # list of case_ids
    retry_requested = Signal(list)              # list of case_ids
    open_folder_requested = Signal(str)         # case_id
    view_logs_requested = Signal(str)           # case_id

    # Colonnes visibles par défaut (ID masqué mais accessible en col 0)
    COLUMNS = [
        "ID",
        "Nom du cas",
        "Alpha [°]",
        "CL Final",
        "CD Final",
        "Finesse",
        "Statut",
        "Durée",
        # Colonnes supplémentaires (toujours disponibles mais moins visibles)
        "Vitesse [m/s]",
        "Corde [m]",
        "Itér.",
        "Progression",
        "Maillage",
        "Message d'état",
    ]

    # Thème clair : texte coloré uniquement, fond blanc
    STATUS_COLORS = {
        CaseStatus.EN_ATTENTE: "#6B7280",           # gris neutre
        CaseStatus.PREPARATION: "#2563EB",           # bleu
        CaseStatus.EN_COURS: "#2563EB",              # bleu
        CaseStatus.POST_TRAITEMENT: "#7C3AED",       # violet
        CaseStatus.TERMINEE_CONVERGEE: "#16A34A",    # vert
        CaseStatus.TERMINEE_NON_CONVERGEE: "#D97706", # orange
        CaseStatus.INCOMPLETE: "#EA580C",            # orange foncé
        CaseStatus.ECHEC: "#DC2626",                 # rouge
        CaseStatus.ANNULEE: "#6B7280",               # gris
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
        self.resizeColumnToContents(6)  # Statut
        self.setColumnWidth(11, 100)    # Progression (progress bar)

        # Masquer la colonne ID par défaut (accessible mais invisible)
        self.setColumnHidden(0, True)

    def add_or_update_case_row(self, case: SimulationCase):
        """Ajoute ou met à jour une ligne du tableau pour un cas donné."""
        row = self._case_id_to_row.get(case.id)
        if row is None or row >= self.rowCount():
            row = self.rowCount()
            self.insertRow(row)
            self._case_id_to_row[case.id] = row

        # 0: ID (masqué mais accessible)
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

        # 3: CL Final
        cl_str = f"{case.results.cl_final:.5f}" if case.results.cl_final is not None else "—"
        item_cl = QTableWidgetItem(cl_str)
        item_cl.setTextAlignment(Qt.AlignCenter)
        item_cl.setFlags(item_cl.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 3, item_cl)

        # 4: CD Final
        cd_str = f"{case.results.cd_final:.5f}" if case.results.cd_final is not None else "—"
        item_cd = QTableWidgetItem(cd_str)
        item_cd.setTextAlignment(Qt.AlignCenter)
        item_cd.setFlags(item_cd.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 4, item_cd)

        # 5: Finesse CL/CD
        ratio_str = f"{case.results.cl_cd_ratio:.2f}" if case.results.cl_cd_ratio is not None else "—"
        item_ratio = QTableWidgetItem(ratio_str)
        item_ratio.setTextAlignment(Qt.AlignCenter)
        item_ratio.setFlags(item_ratio.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 5, item_ratio)

        # 6: Statut — texte coloré, fond blanc
        item_status = QTableWidgetItem(case.status.value)
        item_status.setTextAlignment(Qt.AlignCenter)
        fg_col = self.STATUS_COLORS.get(case.status, "#374151")
        item_status.setForeground(QColor(fg_col))
        item_status.setFont(QFont("Segoe UI", 9, QFont.Bold))
        item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 6, item_status)

        # 7: Durée
        dur_str = f"{case.duration_seconds:.1f} s" if case.duration_seconds > 0 else "—"
        item_dur = QTableWidgetItem(dur_str)
        item_dur.setTextAlignment(Qt.AlignCenter)
        item_dur.setFlags(item_dur.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 7, item_dur)

        # 8: Vitesse
        item_v = QTableWidgetItem(f"{case.parameters.velocity:.1f}")
        item_v.setTextAlignment(Qt.AlignCenter)
        item_v.setFlags(item_v.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 8, item_v)

        # 9: Corde
        item_c = QTableWidgetItem(f"{case.parameters.chord:.2f}")
        item_c.setTextAlignment(Qt.AlignCenter)
        item_c.setFlags(item_c.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 9, item_c)

        # 10: Itérations
        item_it = QTableWidgetItem(str(case.parameters.iterations))
        item_it.setTextAlignment(Qt.AlignCenter)
        item_it.setFlags(item_it.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 10, item_it)

        # 11: Progression (barre légère)
        pbar = self.cellWidget(row, 11)
        if not isinstance(pbar, QProgressBar):
            pbar = QProgressBar()
            pbar.setTextVisible(False)
            pbar.setMaximumHeight(6)
            self.setCellWidget(row, 11, pbar)

        if case.status.is_active:
            if case.progress_percent >= 0:
                pbar.setRange(0, 100)
                pbar.setValue(case.progress_percent)
            else:
                pbar.setRange(0, 0)
        elif case.status == CaseStatus.TERMINEE_CONVERGEE:
            pbar.setRange(0, 100)
            pbar.setValue(100)
        elif case.status in (CaseStatus.TERMINEE_NON_CONVERGEE, CaseStatus.INCOMPLETE,
                              CaseStatus.ECHEC, CaseStatus.ANNULEE):
            pbar.setRange(0, 100)
            pbar.setValue(case.progress_percent)
        else:
            pbar.setRange(0, 100)
            pbar.setValue(0)

        # 12: Maillage
        mesh_name = Path(case.parameters.mesh_file).name
        item_mesh = QTableWidgetItem(mesh_name)
        item_mesh.setFlags(item_mesh.flags() & ~Qt.ItemIsEditable)
        self.setItem(row, 12, item_mesh)

        # 13: Message d'état
        msg = case.error_message or ("Prêt" if case.status == CaseStatus.EN_ATTENTE else "")
        item_msg = QTableWidgetItem(msg)
        if case.status == CaseStatus.ECHEC:
            item_msg.setForeground(QColor("#DC2626"))
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
