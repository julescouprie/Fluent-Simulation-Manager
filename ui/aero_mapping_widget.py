from pathlib import Path
from typing import List, Optional
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from scipy.interpolate import griddata
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.case_model import CaseStatus, DataOrigin, SimulationCase
from core.design_space import DesignSpace


class AeroMappingWidget(QWidget):
    """Plateforme d'Aéro Mapping : Cartographie de sensibilité 2D, courbes d'influence 1D et comparaison."""

    def __init__(self, design_space: DesignSpace, parent=None):
        super().__init__(parent)
        self.design_space = design_space
        self.cases: List[SimulationCase] = []

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Horizontal)

        # 1. Panneau de contrôle gauche
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # Mode d'affichage
        grp_mode = QGroupBox("Mode d'exploration Aéro")
        lay_mode = QVBoxLayout(grp_mode)
        self.radio_map2d = QRadioButton("🗺️ Carte de sensibilité 2D")
        self.radio_inf1d = QRadioButton("📈 Courbe d'influence 1D")
        self.radio_comp = QRadioButton("📋 Comparaison de configurations")

        self.btn_group_mode = QButtonGroup(self)
        for r in (self.radio_map2d, self.radio_inf1d, self.radio_comp):
            self.btn_group_mode.addButton(r)
            lay_mode.addWidget(r)
        left_layout.addWidget(grp_mode)

        # Sélecteurs de variables
        grp_vars = QGroupBox("Variables et Grandeurs")
        lay_vars = QVBoxLayout(grp_vars)

        lay_vars.addWidget(QLabel("Axe Horizontal (X) :"))
        self.combo_x = QComboBox()
        lay_vars.addWidget(self.combo_x)

        self.lbl_y = QLabel("Axe Vertical (Y) :")
        self.combo_y = QComboBox()
        lay_vars.addWidget(self.lbl_y)
        lay_vars.addWidget(self.combo_y)

        lay_vars.addWidget(QLabel("Grandeur aérodynamique (Z / Sortie) :"))
        self.combo_z = QComboBox()
        self.combo_z.addItem("Portance CL [-]", "cl_final")
        self.combo_z.addItem("Traînée CD [-]", "cd_final")
        self.combo_z.addItem("Finesse CL / CD [-]", "cl_cd_ratio")
        lay_vars.addWidget(self.combo_z)

        self.chk_interpolate = QCheckBox("Afficher la surface continue (Interpolation)")
        self.chk_interpolate.setChecked(True)
        lay_vars.addWidget(self.chk_interpolate)

        left_layout.addWidget(grp_vars)

        # Filtres
        grp_filt = QGroupBox("Filtres scientifiques")
        lay_filt = QVBoxLayout(grp_filt)

        self.chk_only_converged = QCheckBox("Exclure les calculs non convergés")
        self.chk_only_converged.setChecked(True)
        lay_filt.addWidget(self.chk_only_converged)

        self.chk_include_mock = QCheckBox("Inclure les simulations fictives (Test)")
        self.chk_include_mock.setChecked(True)
        lay_filt.addWidget(self.chk_include_mock)

        left_layout.addWidget(grp_filt)

        # Panneau des paramètres fixes
        grp_fixed = QGroupBox("Paramètres maintenus fixes")
        lay_fixed = QVBoxLayout(grp_fixed)
        self.lbl_fixed_info = QLabel("Aucun")
        self.lbl_fixed_info.setWordWrap(True)
        self.lbl_fixed_info.setStyleSheet("color: #94a3b8; font-size: 11px;")
        lay_fixed.addWidget(self.lbl_fixed_info)
        left_layout.addWidget(grp_fixed)

        # Export image
        btn_save_plot = QPushButton("🖼️ Exporter le graphique (PNG)")
        btn_save_plot.clicked.connect(self._save_plot)
        left_layout.addWidget(btn_save_plot)

        left_layout.addStretch()
        left_panel.setMinimumWidth(280)
        left_panel.setMaximumWidth(360)
        splitter.addWidget(left_panel)

        # 2. Panneau de droite : Matplotlib + Tableau
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self.figure = Figure(figsize=(8, 6), dpi=100, facecolor="#0f172a")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.toolbar.setStyleSheet("background-color: #1e293b; color: white;")

        right_layout.addWidget(self.toolbar)
        right_layout.addWidget(self.canvas, stretch=3)

        self.table_details = QTableWidget()
        self.table_details.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_details.setMaximumHeight(160)
        right_layout.addWidget(self.table_details, stretch=1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)

        main_layout.addWidget(splitter)

        self._populate_variable_combos()

        # Connecter tous les signaux une fois l'interface complètement assemblée
        for r in (self.radio_map2d, self.radio_inf1d, self.radio_comp):
            r.toggled.connect(self._on_controls_changed)
        self.radio_map2d.setChecked(True)
        self.combo_x.currentIndexChanged.connect(self._on_controls_changed)
        self.combo_y.currentIndexChanged.connect(self._on_controls_changed)
        self.combo_z.currentIndexChanged.connect(self._on_controls_changed)
        self.chk_interpolate.toggled.connect(self._on_controls_changed)
        self.chk_only_converged.toggled.connect(self._on_controls_changed)
        self.chk_include_mock.toggled.connect(self._on_controls_changed)

    def _populate_variable_combos(self):
        self.combo_x.blockSignals(True)
        self.combo_y.blockSignals(True)
        self.combo_x.clear()
        self.combo_y.clear()

        # Ne proposer que les variables opérationnelles
        for v in self.design_space.get_operational_variables():
            self.combo_x.addItem(f"{v.name} ({v.symbol})", v.id)
            self.combo_y.addItem(f"{v.name} ({v.symbol})", v.id)

        # Choix par défaut : X = Incidence, Y = Cambrure
        idx_alpha = self.combo_x.findData("alpha_deg")
        if idx_alpha >= 0:
            self.combo_x.setCurrentIndex(idx_alpha)

        idx_camber = self.combo_y.findData("camber_m")
        if idx_camber >= 0:
            self.combo_y.setCurrentIndex(idx_camber)

        self.combo_x.blockSignals(False)
        self.combo_y.blockSignals(False)

    def set_cases(self, cases: List[SimulationCase]):
        self.cases = cases
        self.update_view()

    def _on_controls_changed(self):
        is_2d = self.radio_map2d.isChecked()
        self.lbl_y.setVisible(is_2d)
        self.combo_y.setVisible(is_2d)
        self.chk_interpolate.setVisible(is_2d)
        self.update_view()

    def _get_filtered_cases(self) -> List[SimulationCase]:
        only_conv = self.chk_only_converged.isChecked()
        inc_mock = self.chk_include_mock.isChecked()

        filtered = []
        for c in self.cases:
            if c.results.cl_final is None or c.results.cd_final is None:
                continue
            if only_conv and c.status != CaseStatus.TERMINEE_CONVERGEE:
                continue
            if not inc_mock and c.data_origin == DataOrigin.SYNTHETIC_MOCK:
                continue
            filtered.append(c)
        return filtered

    def update_view(self):
        self.figure.clear()
        cases = self._get_filtered_cases()

        var_x_id = self.combo_x.currentData() or "alpha_deg"
        var_y_id = self.combo_y.currentData() or "camber_m"
        metric_key = self.combo_z.currentData() or "cl_final"

        var_x = self.design_space.get_variable(var_x_id)
        var_y = self.design_space.get_variable(var_y_id)

        # Mise à jour du texte des paramètres fixes
        fixed_text = []
        for v in self.design_space.get_operational_variables():
            if v.id not in (var_x_id, var_y_id if self.radio_map2d.isChecked() else ""):
                fixed_text.append(f"• <b>{v.name} ({v.symbol})</b> : {v.default_val} {v.unit}")
        self.lbl_fixed_info.setText("<br>".join(fixed_text) if fixed_text else "Tous les paramètres sont sur les axes.")

        if not cases:
            ax = self.figure.add_subplot(111)
            ax.set_facecolor("#1e293b")
            ax.text(
                0.5, 0.5,
                "Aucune donnée CFD disponible répondant aux filtres.\n"
                "Lancez une campagne de calcul ou cochez 'Inclure les simulations fictives'.",
                ha="center", va="center", transform=ax.transAxes, color="#94a3b8", fontsize=12
            )
            self._style_axis(ax)
            self.canvas.draw()
            self._update_table(cases)
            return

        if self.radio_map2d.isChecked():
            self._plot_map2d(cases, var_x, var_y, metric_key)
        elif self.radio_inf1d.isChecked():
            self._plot_influence1d(cases, var_x, metric_key)
        else:
            self._plot_comparison_bars(cases, metric_key)

        self.figure.tight_layout()
        self.canvas.draw()
        self._update_table(cases)

    def _plot_map2d(self, cases: List[SimulationCase], var_x, var_y, metric_key: str):
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#1e293b")

        x_vals = np.array([c.parameters.__dict__.get(var_x.id, var_x.default_val) for c in cases])
        y_vals = np.array([c.parameters.__dict__.get(var_y.id, var_y.default_val) for c in cases])
        z_vals = np.array([getattr(c.results, metric_key) for c in cases])

        # 1. Surface continue interpolée (si demandée et si >= 4 points distincts)
        has_mesh = False
        if self.chk_interpolate.isChecked() and len(set(zip(x_vals, y_vals))) >= 4:
            try:
                xi = np.linspace(x_vals.min(), x_vals.max(), 100)
                yi = np.linspace(y_vals.min(), y_vals.max(), 100)
                XI, YI = np.meshgrid(xi, yi)
                ZI = griddata((x_vals, y_vals), z_vals, (XI, YI), method="linear")

                cp = ax.contourf(XI, YI, ZI, levels=20, cmap="viridis", alpha=0.85)
                cbar = self.figure.colorbar(cp, ax=ax)
                cbar.set_label(f"{self.combo_z.currentText()}", color="#f8fafc")
                cbar.ax.yaxis.set_tick_params(color="#94a3b8")
                plt_ticks = cbar.ax.get_yticks()
                cbar.ax.set_yticklabels([f"{t:.3f}" for t in plt_ticks], color="#94a3b8")
                has_mesh = True
            except Exception:
                pass

        # 2. Superposition des points CFD réels calculés
        # Distinction visuelle : Disque = CFD Réelle | Triangle = Simulation Fictive | Étoile = Krigeage
        for c, x, y, z in zip(cases, x_vals, y_vals, z_vals):
            if c.data_origin == DataOrigin.REAL_CFD:
                marker, color, label_marker = "o", "#38bdf8", "Point CFD réel"
            elif c.data_origin == DataOrigin.SYNTHETIC_MOCK:
                marker, color, label_marker = "^", "#facc15", "Simulation test/DoE"
            else:
                marker, color, label_marker = "*", "#a855f7", "Prédiction Krigeage"

            edge = "white" if c.status == CaseStatus.TERMINEE_CONVERGEE else "red"
            ax.scatter(x, y, c=color, edgecolors=edge, s=80, marker=marker, zorder=5, linewidth=1.5)
            ax.annotate(f"{z:.3f}", (x, y), textcoords="offset points", xytext=(0, 7), ha="center", color="#ffffff", fontsize=8)

        ax.set_xlabel(f"{var_x.name} ({var_x.symbol}) [{var_x.unit}]", color="#f8fafc", fontsize=11)
        ax.set_ylabel(f"{var_y.name} ({var_y.symbol}) [{var_y.unit}]", color="#f8fafc", fontsize=11)
        ax.set_title(f"Aéro Mapping 2D : {self.combo_z.currentText()} = f({var_x.symbol}, {var_y.symbol})", color="#38bdf8", fontweight="bold", fontsize=12)

        self._style_axis(ax)

    def _plot_influence1d(self, cases: List[SimulationCase], var_x, metric_key: str):
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#1e293b")

        data = sorted([
            (c.parameters.__dict__.get(var_x.id, var_x.default_val), getattr(c.results, metric_key), c.name, c.data_origin)
            for c in cases
        ], key=lambda d: d[0])

        x_vals = [d[0] for d in data]
        y_vals = [d[1] for d in data]

        ax.plot(x_vals, y_vals, "o-", color="#38bdf8", linewidth=2, markersize=7, label="Données CFD simulées")
        for x, y, name, origin in data:
            ax.annotate(f"{y:.4f}", (x, y), textcoords="offset points", xytext=(0, 8), ha="center", color="#ffffff", fontsize=9)

        ax.set_xlabel(f"{var_x.name} ({var_x.symbol}) [{var_x.unit}]", color="#f8fafc", fontsize=11)
        ax.set_ylabel(f"{self.combo_z.currentText()}", color="#f8fafc", fontsize=11)
        ax.set_title(f"Influence de {var_x.name} sur {self.combo_z.currentText()}", color="#38bdf8", fontweight="bold", fontsize=12)
        ax.legend(facecolor="#1e293b", edgecolor="#334155", labelcolor="#f8fafc")

        self._style_axis(ax)

    def _plot_comparison_bars(self, cases: List[SimulationCase], metric_key: str):
        ax = self.figure.add_subplot(111)
        ax.set_facecolor("#1e293b")

        top_cases = cases[:12]  # Max 12 pour lisibilité
        names = [c.name for c in top_cases]
        vals = [getattr(c.results, metric_key) for c in top_cases]

        bars = ax.bar(range(len(names)), vals, color="#0284c7", edgecolor="#38bdf8", width=0.6)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.01 * (max(vals) - min(vals)), f"{v:.4f}", ha="center", va="bottom", color="#f8fafc", fontsize=9)

        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=25, ha="right", color="#94a3b8")
        ax.set_ylabel(self.combo_z.currentText(), color="#f8fafc")
        ax.set_title("Comparaison des configurations simulées", color="#38bdf8", fontweight="bold")

        self._style_axis(ax)

    def _style_axis(self, ax):
        ax.grid(True, linestyle="--", alpha=0.3, color="#64748b")
        ax.tick_params(colors="#94a3b8", which="both")
        for spine in ax.spines.values():
            spine.set_color("#334155")

    def _update_table(self, cases: List[SimulationCase]):
        self.table_details.setRowCount(len(cases))
        self.table_details.setColumnCount(8)
        self.table_details.setHorizontalHeaderLabels([
            "ID", "Nom du cas", "Origine", "Alpha [°]", "Cambrure m", "Epaisseur t", "CL", "CD"
        ])
        for r, c in enumerate(cases):
            self.table_details.setItem(r, 0, QTableWidgetItem(c.id))
            self.table_details.setItem(r, 1, QTableWidgetItem(c.name))
            self.table_details.setItem(r, 2, QTableWidgetItem(c.data_origin.value))
            self.table_details.setItem(r, 3, QTableWidgetItem(f"{c.parameters.alpha_deg:+.2f}°"))
            self.table_details.setItem(r, 4, QTableWidgetItem(f"{c.parameters.camber_m:.3f}"))
            self.table_details.setItem(r, 5, QTableWidgetItem(f"{c.parameters.thickness_t:.3f}"))
            cl_s = f"{c.results.cl_final:.5f}" if c.results.cl_final is not None else "-"
            cd_s = f"{c.results.cd_final:.5f}" if c.results.cd_final is not None else "-"
            self.table_details.setItem(r, 6, QTableWidgetItem(cl_s))
            self.table_details.setItem(r, 7, QTableWidgetItem(cd_s))

    def _save_plot(self):
        p, _ = QFileDialog.getSaveFileName(self, "Enregistrer la carte Aéro Mapping", "aero_mapping.png", "Image PNG (*.png);;PDF (*.pdf)")
        if p:
            self.figure.savefig(p, dpi=200, facecolor=self.figure.get_facecolor())
            QMessageBox.information(self, "Succès", f"Graphique sauvegardé dans :\n{p}")
