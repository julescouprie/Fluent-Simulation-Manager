from pathlib import Path
from typing import List, Optional
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.case_model import SimulationCase, CaseStatus
from postprocessing.exporter import export_cases_to_csv, export_cases_to_excel
from postprocessing.postprocessor import read_report, read_pressure


class ComparisonWidget(QWidget):
    """Page interactive d'analyse et de comparaison des résultats CFD."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cases: List[SimulationCase] = []

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        splitter = QSplitter(Qt.Horizontal)

        # 1. Préparation initiale du canvas Matplotlib & tableau (avant connexion des signaux)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.figure = Figure(figsize=(8, 5), dpi=100, facecolor="#FFFFFF")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)

        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas, stretch=3)

        self.table_summary = QTableWidget()
        self.table_summary.setColumnCount(7)
        self.table_summary.setHorizontalHeaderLabels([
            "ID", "Nom", "Alpha [°]", "CL Final", "CD Final", "Finesse CL/CD", "Itérations"
        ])
        self.table_summary.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_summary.setMaximumHeight(140)
        right_layout.addWidget(self.table_summary, stretch=1)

        # 2. Panneau de gauche : sélection des cas et options de tracé
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        grp_cases = QGroupBox("Sélection des cas à comparer")
        lay_cases = QVBoxLayout(grp_cases)

        lay_sel_btns = QHBoxLayout()
        btn_sel_all = QPushButton("Tout cocher")
        btn_sel_all.clicked.connect(self._select_all_cases)
        btn_desel_all = QPushButton("Tout décocher")
        btn_desel_all.clicked.connect(self._deselect_all_cases)
        lay_sel_btns.addWidget(btn_sel_all)
        lay_sel_btns.addWidget(btn_desel_all)
        lay_cases.addLayout(lay_sel_btns)

        self.list_cases = QListWidget()
        self.list_cases.itemChanged.connect(self._on_selection_changed)
        lay_cases.addWidget(self.list_cases)

        left_layout.addWidget(grp_cases)

        grp_plots = QGroupBox("Type de visualisation")
        lay_plots = QVBoxLayout(grp_plots)

        self.radio_cl_alpha = QRadioButton("Polaire : CL vs Alpha")
        self.radio_cd_alpha = QRadioButton("Traînée : CD vs Alpha")
        self.radio_cl_cd = QRadioButton("Finesse : CL / CD vs Alpha")
        self.radio_conv = QRadioButton("Courbes de convergence (CL & CD)")
        self.radio_cp = QRadioButton("Distribution de pression (Cp vs x/c)")

        self.plot_group = QButtonGroup(self)
        for r in (self.radio_cl_alpha, self.radio_cd_alpha, self.radio_cl_cd, self.radio_conv, self.radio_cp):
            self.plot_group.addButton(r)
            lay_plots.addWidget(r)
            r.toggled.connect(self.update_plot)

        self.radio_cl_alpha.setChecked(True)
        left_layout.addWidget(grp_plots)

        grp_export = QGroupBox("Exports des données")
        lay_export = QVBoxLayout(grp_export)

        btn_csv = QPushButton("📊 Exporter en CSV")
        btn_csv.clicked.connect(self._export_csv)
        btn_excel = QPushButton("📗 Exporter en Excel (.xlsx)")
        btn_excel.clicked.connect(self._export_excel)
        btn_fig = QPushButton("🖼️ Sauvegarder la figure (PNG)")
        btn_fig.clicked.connect(self._export_figure)

        lay_export.addWidget(btn_csv)
        lay_export.addWidget(btn_excel)
        lay_export.addWidget(btn_fig)

        left_layout.addWidget(grp_export)
        left_layout.addStretch()

        left_panel.setMinimumWidth(260)
        left_panel.setMaximumWidth(340)

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        main_layout.addWidget(splitter)
        self.update_plot()

    def set_cases(self, cases: List[SimulationCase]):
        self.cases = cases
        self.list_cases.blockSignals(True)
        self.list_cases.clear()

        for c in self.cases:
            if c.status in (CaseStatus.TERMINEE_CONVERGEE, CaseStatus.TERMINEE_NON_CONVERGEE) and c.results.cl_final is not None:
                item = QListWidgetItem(f"[{c.parameters.alpha_deg:+.1f}°] {c.name} ({c.id})")
                item.setData(Qt.UserRole, c.id)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked)
                self.list_cases.addItem(item)

        self.list_cases.blockSignals(False)
        self.update_plot()

    def _select_all_cases(self):
        for i in range(self.list_cases.count()):
            self.list_cases.item(i).setCheckState(Qt.Checked)

    def _deselect_all_cases(self):
        for i in range(self.list_cases.count()):
            self.list_cases.item(i).setCheckState(Qt.Unchecked)

    def _get_checked_cases(self) -> List[SimulationCase]:
        checked_ids = []
        for i in range(self.list_cases.count()):
            item = self.list_cases.item(i)
            if item.checkState() == Qt.Checked:
                checked_ids.append(item.data(Qt.UserRole))
        return [c for c in self.cases if c.id in checked_ids]

    def _on_selection_changed(self):
        self.update_plot()

    def update_plot(self):
        self.figure.clear()
        selected_cases = self._get_checked_cases()

        self._update_summary_table(selected_cases)

        if not selected_cases:
            ax = self.figure.add_subplot(111)
            ax.set_facecolor("#FFFFFF")
            ax.text(
                0.5, 0.5,
                "Aucune simulation sélectionnée ou terminée.\nCochez au moins un cas terminé pour afficher les résultats.",
                horizontalalignment="center",
                verticalalignment="center",
                transform=ax.transAxes,
                color="#6B7280",
                fontsize=13,
            )
            self._style_axis(ax)
            self.canvas.draw()
            return

        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#FFFFFF")

        colors = ["#2563EB", "#16A34A", "#DC2626", "#D97706", "#7C3AED", "#DB2777", "#0D9488", "#EA580C"]

        if self.radio_cl_alpha.isChecked():
            # CL vs Alpha
            data = sorted([(c.parameters.alpha_deg, c.results.cl_final, c.name) for c in selected_cases], key=lambda x: x[0])
            alphas = [d[0] for d in data]
            cls = [d[1] for d in data]

            ax.plot(alphas, cls, "o-", color="#2563EB", linewidth=2, markersize=7, label="CL (Portance)")
            for alpha, cl, name in data:
                ax.annotate(f"{cl:.4f}", (alpha, cl), textcoords="offset points", xytext=(0, 8),
                            ha="center", color="#374151", fontsize=9)
            ax.set_xlabel("Angle d'incidence alpha [°]", color="#374151", fontsize=11)
            ax.set_ylabel("Coefficient de portance CL [-]", color="#374151", fontsize=11)
            ax.set_title("Courbe de portance CL = f(alpha) - NACA 2212", color="#111827", fontsize=13, fontweight="bold")
            ax.legend(facecolor="#FFFFFF", edgecolor="#E5E7EB", labelcolor="#374151")

        elif self.radio_cd_alpha.isChecked():
            # CD vs Alpha
            data = sorted([(c.parameters.alpha_deg, c.results.cd_final, c.name) for c in selected_cases], key=lambda x: x[0])
            alphas = [d[0] for d in data]
            cds = [d[1] for d in data]

            ax.plot(alphas, cds, "s-", color="#DC2626", linewidth=2, markersize=7, label="CD (Traînée)")
            for alpha, cd, name in data:
                ax.annotate(f"{cd:.5f}", (alpha, cd), textcoords="offset points", xytext=(0, 8),
                            ha="center", color="#374151", fontsize=9)
            ax.set_xlabel("Angle d'incidence alpha [°]", color="#374151", fontsize=11)
            ax.set_ylabel("Coefficient de traînée CD [-]", color="#374151", fontsize=11)
            ax.set_title("Courbe de traînée CD = f(alpha) - NACA 2212", color="#DC2626", fontsize=13, fontweight="bold")
            ax.legend(facecolor="#FFFFFF", edgecolor="#E5E7EB", labelcolor="#374151")

        elif self.radio_cl_cd.isChecked():
            # Finesse CL/CD vs Alpha
            data = sorted([
                (c.parameters.alpha_deg, c.results.cl_cd_ratio)
                for c in selected_cases
                if c.results.cl_cd_ratio is not None
            ], key=lambda x: x[0])

            if data:
                alphas = [d[0] for d in data]
                ratios = [d[1] for d in data]
                ax.plot(alphas, ratios, "^-", color="#16A34A", linewidth=2, markersize=7, label="Finesse CL/CD")
                for alpha, r in data:
                    ax.annotate(f"{r:.2f}", (alpha, r), textcoords="offset points", xytext=(0, 8),
                                ha="center", color="#374151", fontsize=9)
            ax.set_xlabel("Angle d'incidence alpha [°]", color="#374151", fontsize=11)
            ax.set_ylabel("Finesse aérodynamique CL / CD [-]", color="#374151", fontsize=11)
            ax.set_title("Finesse aérodynamique = f(alpha)", color="#16A34A", fontsize=13, fontweight="bold")
            ax.legend(facecolor="#FFFFFF", edgecolor="#E5E7EB", labelcolor="#374151")

        elif self.radio_conv.isChecked():
            # Convergence
            for i, c in enumerate(selected_cases):
                color = colors[i % len(colors)]
                work_p = Path(c.work_dir) if c.work_dir else None
                if work_p and work_p.exists():
                    cl_df = read_report(work_p / "cl_test.txt")
                    if not cl_df.empty:
                        ax.plot(cl_df.iteration, cl_df.value, "-", color=color, linewidth=1.5,
                                label=f"{c.name} (alpha={c.parameters.alpha_deg:.1f}°)")
            ax.set_xlabel("Itération", color="#374151", fontsize=11)
            ax.set_ylabel("Coefficient CL [-]", color="#374151", fontsize=11)
            ax.set_title("Historique de convergence de la portance CL", color="#111827", fontsize=13, fontweight="bold")
            ax.legend(facecolor="#FFFFFF", edgecolor="#E5E7EB", labelcolor="#374151", fontsize=9)

        elif self.radio_cp.isChecked():
            # Distribution Cp
            for i, c in enumerate(selected_cases):
                color = colors[i % len(colors)]
                work_p = Path(c.work_dir) if c.work_dir else None
                if work_p and work_p.exists():
                    p_file = work_p / "post" / "pressure_distribution.csv"
                    if not p_file.exists():
                        p_file = work_p / "airfoil_pressure.csv"
                    if p_file.exists():
                        try:
                            df = pd.read_csv(p_file)
                            if "x_sur_c" in df.columns and "Cp" in df.columns:
                                ax.plot(df.x_sur_c, df.Cp, "o-", markersize=2, color=color, linewidth=1.2,
                                        label=f"{c.name} ({c.parameters.alpha_deg:+.1f}°)")
                        except Exception:
                            pass
            ax.invert_yaxis()  # Convention aérodynamique : succion vers le haut
            ax.set_xlabel("Position normalisée x / c [-]", color="#374151", fontsize=11)
            ax.set_ylabel("Coefficient de pression Cp [-]", color="#374151", fontsize=11)
            ax.set_title("Distribution du coefficient de pression Cp sur le profil", color="#111827", fontsize=13, fontweight="bold")
            ax.legend(facecolor="#FFFFFF", edgecolor="#E5E7EB", labelcolor="#374151", fontsize=9)

        self._style_axis(ax)
        self.figure.tight_layout()
        self.canvas.draw()

    def _style_axis(self, ax):
        ax.set_facecolor("#FFFFFF")
        ax.grid(True, linestyle="--", alpha=0.4, color="#E5E7EB")
        ax.tick_params(colors="#6B7280", which="both")
        for spine in ax.spines.values():
            spine.set_color("#E5E7EB")

    def _update_summary_table(self, selected_cases: List[SimulationCase]):
        self.table_summary.setRowCount(len(selected_cases))
        for r, c in enumerate(selected_cases):
            self.table_summary.setItem(r, 0, QTableWidgetItem(c.id))
            self.table_summary.setItem(r, 1, QTableWidgetItem(c.name))
            self.table_summary.setItem(r, 2, QTableWidgetItem(f"{c.parameters.alpha_deg:+.2f}°"))
            cl_s = f"{c.results.cl_final:.5f}" if c.results.cl_final is not None else "-"
            cd_s = f"{c.results.cd_final:.5f}" if c.results.cd_final is not None else "-"
            ratio_s = f"{c.results.cl_cd_ratio:.2f}" if c.results.cl_cd_ratio is not None else "-"
            self.table_summary.setItem(r, 3, QTableWidgetItem(cl_s))
            self.table_summary.setItem(r, 4, QTableWidgetItem(cd_s))
            self.table_summary.setItem(r, 5, QTableWidgetItem(ratio_s))
            self.table_summary.setItem(r, 6, QTableWidgetItem(str(c.parameters.iterations)))

    def _export_csv(self):
        cases = self._get_checked_cases() or self.cases
        if not cases:
            QMessageBox.warning(self, "Export", "Aucun cas à exporter.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter en CSV", "comparaison_simulations.csv", "Fichier CSV (*.csv)")
        if path:
            export_cases_to_csv(cases, Path(path))
            QMessageBox.information(self, "Export réussi", f"Données exportées avec succès dans :\n{path}")

    def _export_excel(self):
        cases = self._get_checked_cases() or self.cases
        if not cases:
            QMessageBox.warning(self, "Export", "Aucun cas à exporter.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Exporter en Excel", "comparaison_simulations.xlsx", "Classeur Excel (*.xlsx)")
        if path:
            export_cases_to_excel(cases, Path(path))
            QMessageBox.information(self, "Export réussi", f"Données exportées avec succès dans :\n{path}")

    def _export_figure(self):
        path, _ = QFileDialog.getSaveFileName(self, "Enregistrer la figure", "graphique_aerodynamique.png", "Image PNG (*.png);;Fichier PDF (*.pdf)")
        if path:
            self.figure.savefig(path, dpi=200, facecolor=self.figure.get_facecolor(), edgecolor="none")
            QMessageBox.information(self, "Enregistrement réussi", f"Graphique enregistré dans :\n{path}")
