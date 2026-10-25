"""
Widget de Prédiction Aérodynamique par Krigeage (PySide6).

Intégration directe au sein de l'application unique :
- Sélection de la source des données (simulations CFD convergées du projet ou fichier CSV de campagne).
- Sélection des variables d'entrée (m_%, p, etc.) et cibles (Cl, Cd).
- Entraînement du métamodèle avec ou sans optimisation des theta.
- Prédiction ponctuelle instantanée avec alertes d'extrapolation hors domaine.
- Courbes d'influence 1D interactives.
- Cartes de réponse 2D (contours et surfaces).
- Diagnostic de parité (Données réelles vs Prédictions).
- Visualisation et export des données.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import numpy as np
import pandas as pd
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.case_model import CaseStatus, SimulationCase
from core.design_space import DesignSpace
from kriging.model import (
    KrigingModel,
    charger_donnees_csv,
    entrainer_modele,
)


class KrigingPredictionWidget(QWidget):
    """Écran interactif de modélisation de substitution et de prédiction par krigeage."""

    model_trained = Signal()

    def __init__(self, design_space: Optional[DesignSpace] = None, parent=None):
        super().__init__(parent)
        self.design_space = design_space
        self.cases: List[SimulationCase] = []

        # Données d'entraînement actives
        self.current_df: Optional[pd.DataFrame] = None
        self.input_columns: List[str] = []
        self.output_columns: List[str] = []
        self.trained_models: Dict[str, KrigingModel] = {}

        # Chemin du fichier CSV par défaut
        self.default_csv_path = Path("data/recapitulatif_campagne.csv")
        if not self.default_csv_path.exists():
            self.default_csv_path = Path("Krigeage Code/recapitulatif_campagne.csv")

        self._setup_ui()
        self._load_initial_data()

    # ==========================================================================
    # Construction de l'interface
    # ==========================================================================

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        splitter = QSplitter(Qt.Horizontal)

        # ── Panneau gauche : Configuration & Entraînement ────────────────────
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setFixedWidth(340)

        left_content = QWidget()
        left_layout = QVBoxLayout(left_content)
        left_layout.setContentsMargins(0, 0, 8, 0)
        left_layout.setSpacing(12)

        # 1. Source des données
        grp_source = QGroupBox("1. Source des données d'apprentissage")
        lay_source = QVBoxLayout(grp_source)

        self.radio_source_project = QRadioButton("Simulations du projet (CFD)")
        self.radio_source_csv = QRadioButton("Fichier de campagne (CSV)")
        self.radio_source_csv.setChecked(True)

        self.radio_source_project.toggled.connect(self._on_source_changed)
        lay_source.addWidget(self.radio_source_csv)
        lay_source.addWidget(self.radio_source_project)

        # Sélection CSV
        self.lay_csv_box = QHBoxLayout()
        self.lbl_csv_name = QLabel("recapitulatif_campagne.csv")
        self.lbl_csv_name.setStyleSheet("font-size: 11px; color: #4B5563;")
        self.btn_browse_csv = QPushButton("Parcourir...")
        self.btn_browse_csv.clicked.connect(self._browse_csv)
        self.lay_csv_box.addWidget(self.lbl_csv_name, stretch=1)
        self.lay_csv_box.addWidget(self.btn_browse_csv)
        lay_source.addLayout(self.lay_csv_box)

        self.lbl_data_info = QLabel("10 simulations chargées")
        self.lbl_data_info.setStyleSheet("color: #2563EB; font-weight: 600; font-size: 12px;")
        lay_source.addWidget(self.lbl_data_info)

        left_layout.addWidget(grp_source)

        # 2. Variables d'entrée (X)
        grp_inputs = QGroupBox("2. Paramètres géométriques (X)")
        self.lay_inputs = QVBoxLayout(grp_inputs)
        self.input_checkboxes: Dict[str, QCheckBox] = {}
        left_layout.addWidget(grp_inputs)

        # 3. Grandeurs cibles (Y)
        grp_targets = QGroupBox("3. Grandeurs à prédire (Y)")
        lay_targets = QVBoxLayout(grp_targets)
        self.chk_cl = QCheckBox("Coefficient de portance (Cl)")
        self.chk_cl.setChecked(True)
        self.chk_cd = QCheckBox("Coefficient de traînée (Cd)")
        self.chk_cd.setChecked(True)
        lay_targets.addWidget(self.chk_cl)
        lay_targets.addWidget(self.chk_cd)
        left_layout.addWidget(grp_targets)

        # 4. Paramètres du modèle
        grp_opt = QGroupBox("4. Optimisation des theta")
        lay_opt = QVBoxLayout(grp_opt)
        self.chk_optimize = QCheckBox("Optimisation automatique (L-BFGS-B)")
        self.chk_optimize.setChecked(True)
        lay_opt.addWidget(self.chk_optimize)
        left_layout.addWidget(grp_opt)

        # Bouton d'entraînement principal
        self.btn_train = QPushButton("⚡ Entraîner le modèle de krigeage")
        self.btn_train.setObjectName("btn_primary")
        self.btn_train.setStyleSheet("font-size: 13px; padding: 10px 16px;")
        self.btn_train.clicked.connect(self.train_models)
        left_layout.addWidget(self.btn_train)

        # État d'entraînement
        self.lbl_train_status = QLabel("Modèle non entraîné")
        self.lbl_train_status.setStyleSheet("color: #6B7280; font-size: 11px;")
        self.lbl_train_status.setWordWrap(True)
        left_layout.addWidget(self.lbl_train_status)

        left_layout.addStretch()
        left_scroll.setWidget(left_content)
        splitter.addWidget(left_scroll)

        # ── Panneau droit : Onglets d'exploitation et de prédiction ──────────
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QTabWidget()

        # Onglet 1 : Calculateur de prédiction ponctuelle
        self.tab_calc = self._build_tab_calculator()
        self.tabs.addTab(self.tab_calc, "🎯 Prédiction instantanée")

        # Onglet 2 : Courbe 1D
        self.tab_1d = self._build_tab_1d()
        self.tabs.addTab(self.tab_1d, "📈 Courbe d'influence 1D")

        # Onglet 3 : Carte 2D
        self.tab_2d = self._build_tab_2d()
        self.tabs.addTab(self.tab_2d, "🗺️ Surface de réponse 2D")

        # Onglet 4 : Diagnostic & Parité
        self.tab_parity = self._build_tab_parity()
        self.tabs.addTab(self.tab_parity, "🔬 Diagnostic & Parité")

        # Onglet 5 : Données d'apprentissage
        self.tab_data = self._build_tab_data()
        self.tabs.addTab(self.tab_data, "📋 Données d'apprentissage")

        right_layout.addWidget(self.tabs)
        splitter.addWidget(right_panel)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        main_layout.addWidget(splitter)

    # --------------------------------------------------------------------------
    # Onglet 1 : Calculateur ponctuel
    # --------------------------------------------------------------------------

    def _build_tab_calculator(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        lbl_desc = QLabel("Définissez une géométrie pour obtenir instantanément les coefficients aérodynamiques prédits par krigeage.")
        lbl_desc.setStyleSheet("color: #4B5563; font-size: 13px;")
        layout.addWidget(lbl_desc)

        # Split horizontal : Saisie à gauche, Affichage à droite
        content = QHBoxLayout()
        content.setSpacing(24)

        # Formulaire de saisie
        grp_inputs = QGroupBox("Paramètres de la géométrie")
        self.lay_calc_form = QFormLayout(grp_inputs)
        self.calc_spinboxes: Dict[str, QDoubleSpinBox] = {}
        content.addWidget(grp_inputs, stretch=1)

        # Cartes de résultats
        res_container = QVBoxLayout()
        res_container.setSpacing(12)

        # Carte Cl
        self.card_cl = QFrame()
        self.card_cl.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px;")
        lay_cl = QVBoxLayout(self.card_cl)
        lay_cl.setContentsMargins(8, 8, 8, 8)
        lbl_cl_title = QLabel("COEFFICIENT DE PORTANCE PRÉDIT (CL)")
        lbl_cl_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748B; letter-spacing: 0.5px;")
        self.lbl_cl_value = QLabel("—")
        self.lbl_cl_value.setStyleSheet("font-size: 26px; font-weight: bold; color: #111827; margin: 4px 0;")
        lbl_cl_sub = QLabel("Interpolation par processus gaussien")
        lbl_cl_sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
        lay_cl.addWidget(lbl_cl_title)
        lay_cl.addWidget(self.lbl_cl_value)
        lay_cl.addWidget(lbl_cl_sub)
        res_container.addWidget(self.card_cl)

        # Carte Cd
        self.card_cd = QFrame()
        self.card_cd.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px;")
        lay_cd = QVBoxLayout(self.card_cd)
        lay_cd.setContentsMargins(8, 8, 8, 8)
        lbl_cd_title = QLabel("COEFFICIENT DE TRAÎNÉE PRÉDIT (CD)")
        lbl_cd_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748B; letter-spacing: 0.5px;")
        self.lbl_cd_value = QLabel("—")
        self.lbl_cd_value.setStyleSheet("font-size: 26px; font-weight: bold; color: #111827; margin: 4px 0;")
        lbl_cd_sub = QLabel("Interpolation par processus gaussien")
        lbl_cd_sub.setStyleSheet("font-size: 11px; color: #94A3B8;")
        lay_cd.addWidget(lbl_cd_title)
        lay_cd.addWidget(self.lbl_cd_value)
        lay_cd.addWidget(lbl_cd_sub)
        res_container.addWidget(self.card_cd)

        # Alerte domaine
        self.lbl_domain_status = QLabel("✓ Point situé dans le domaine d'apprentissage.")
        self.lbl_domain_status.setStyleSheet("background-color: #F0FDF4; color: #166534; padding: 8px 12px; border-radius: 6px; font-size: 12px;")
        res_container.addWidget(self.lbl_domain_status)
        res_container.addStretch()

        content.addLayout(res_container, stretch=1)
        layout.addLayout(content)
        layout.addStretch()
        return widget

    # --------------------------------------------------------------------------
    # Onglet 2 : Courbe 1D
    # --------------------------------------------------------------------------

    def _build_tab_1d(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Contrôles supérieurs
        bar = QHBoxLayout()
        bar.setSpacing(12)

        bar.addWidget(QLabel("Axe horizontal (X) :"))
        self.combo_1d_x = QComboBox()
        self.combo_1d_x.currentIndexChanged.connect(self._update_plot_1d)
        bar.addWidget(self.combo_1d_x)

        bar.addWidget(QLabel("Grandeur prédite :"))
        self.combo_1d_target = QComboBox()
        self.combo_1d_target.currentIndexChanged.connect(self._update_plot_1d)
        bar.addWidget(self.combo_1d_target)

        bar.addWidget(QLabel("Paramètre fixe :"))
        self.spin_1d_fixed = QDoubleSpinBox()
        self.spin_1d_fixed.setDecimals(3)
        self.spin_1d_fixed.valueChanged.connect(self._update_plot_1d)
        bar.addWidget(self.spin_1d_fixed)

        bar.addStretch()
        layout.addLayout(bar)

        # Figure Matplotlib
        self.fig_1d = Figure(figsize=(8, 5), facecolor="#ffffff")
        self.canvas_1d = FigureCanvasQTAgg(self.fig_1d)
        self.toolbar_1d = NavigationToolbar2QT(self.canvas_1d, self)

        layout.addWidget(self.toolbar_1d)
        layout.addWidget(self.canvas_1d, stretch=1)

        lbl_caption = QLabel("ℹ️ La courbe bleue représente les prédictions continues du krigeage. Les points noirs indiquent les calculs CFD réels les plus proches.")
        lbl_caption.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(lbl_caption)

        return widget

    # --------------------------------------------------------------------------
    # Onglet 3 : Surface 2D
    # --------------------------------------------------------------------------

    def _build_tab_2d(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        bar = QHBoxLayout()
        bar.setSpacing(12)

        bar.addWidget(QLabel("Axe X :"))
        self.combo_2d_x = QComboBox()
        self.combo_2d_x.currentIndexChanged.connect(self._update_plot_2d)
        bar.addWidget(self.combo_2d_x)

        bar.addWidget(QLabel("Axe Y :"))
        self.combo_2d_y = QComboBox()
        self.combo_2d_y.currentIndexChanged.connect(self._update_plot_2d)
        bar.addWidget(self.combo_2d_y)

        bar.addWidget(QLabel("Grandeur affichée :"))
        self.combo_2d_target = QComboBox()
        self.combo_2d_target.currentIndexChanged.connect(self._update_plot_2d)
        bar.addWidget(self.combo_2d_target)

        bar.addStretch()
        layout.addLayout(bar)

        self.fig_2d = Figure(figsize=(8, 5), facecolor="#ffffff")
        self.canvas_2d = FigureCanvasQTAgg(self.fig_2d)
        self.toolbar_2d = NavigationToolbar2QT(self.canvas_2d, self)

        layout.addWidget(self.toolbar_2d)
        layout.addWidget(self.canvas_2d, stretch=1)

        lbl_caption = QLabel("⚠️ Les contours représentent la surface de réponse interpolée par krigeage. Les cercles rouges indiquent les simulations CFD d'entraînement.")
        lbl_caption.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(lbl_caption)

        return widget

    # --------------------------------------------------------------------------
    # Onglet 4 : Diagnostic & Parité
    # --------------------------------------------------------------------------

    def _build_tab_parity(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Tableau des hyperparamètres
        lbl_t_title = QLabel("Hyperparamètres du modèle de Krigeage")
        lbl_t_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #111827;")
        layout.addWidget(lbl_t_title)

        self.table_theta = QTableWidget()
        self.table_theta.setColumnCount(7)
        self.table_theta.setHorizontalHeaderLabels([
            "Cible", "Variable", "Theta (θ)", "Optimisé", "Moyenne (μ)", "Log-Vraisemblance", "Pépite (nugget)"
        ])
        self.table_theta.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_theta.setMaximumHeight(120)
        layout.addWidget(self.table_theta)

        # Figure de parité
        self.fig_parity = Figure(figsize=(8, 4.5), facecolor="#ffffff")
        self.canvas_parity = FigureCanvasQTAgg(self.fig_parity)
        self.toolbar_parity = NavigationToolbar2QT(self.canvas_parity, self)

        layout.addWidget(self.toolbar_parity)
        layout.addWidget(self.canvas_parity, stretch=1)

        lbl_note = QLabel(
            "<b>Note méthodologique :</b> Le krigeage sans bruit interpole exactement les données d'apprentissage. "
            "Ce graphique vérifie la cohérence numérique du modèle sur les points d'entraînement (et ne remplace pas une validation indépendante)."
        )
        lbl_note.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; padding: 8px 12px; border-radius: 6px; font-size: 11px; color: #4B5563;")
        lbl_note.setWordWrap(True)
        layout.addWidget(lbl_note)

        return widget

    # --------------------------------------------------------------------------
    # Onglet 5 : Données d'apprentissage
    # --------------------------------------------------------------------------

    def _build_tab_data(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        lbl_title = QLabel("Tableau des simulations CFD utilisées pour l'apprentissage")
        lbl_title.setStyleSheet("font-weight: 600; font-size: 13px; color: #111827;")
        layout.addWidget(lbl_title)

        self.table_data = QTableWidget()
        self.table_data.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table_data, stretch=1)

        # Boutons d'export
        bar_actions = QHBoxLayout()
        btn_export_csv = QPushButton("📥 Exporter le jeu d'apprentissage (CSV)")
        btn_export_csv.clicked.connect(self._export_training_csv)
        bar_actions.addWidget(btn_export_csv)
        bar_actions.addStretch()
        layout.addLayout(bar_actions)

        return widget

    # ==========================================================================
    # Gestion des données et chargement
    # ==========================================================================

    def _load_initial_data(self):
        """Charge les données initiales par défaut."""
        if self.default_csv_path.exists():
            self._load_csv_file(self.default_csv_path)
        else:
            self._refresh_from_project_cases()

    def set_cases(self, cases: List[SimulationCase]):
        """Met à jour les simulations CFD disponibles depuis le projet principal."""
        self.cases = cases
        if self.radio_source_project.isChecked():
            self._refresh_from_project_cases()

    def _on_source_changed(self):
        is_csv = self.radio_source_csv.isChecked()
        self.lbl_csv_name.setVisible(is_csv)
        self.btn_browse_csv.setVisible(is_csv)

        if is_csv:
            if self.default_csv_path.exists():
                self._load_csv_file(self.default_csv_path)
        else:
            self._refresh_from_project_cases()

    def _browse_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier CSV de campagne",
            "",
            "Fichiers CSV (*.csv);;Tous les fichiers (*.*)",
        )
        if path:
            self._load_csv_file(Path(path))

    def _load_csv_file(self, csv_path: Path):
        try:
            df, inputs, outputs, info = charger_donnees_csv(csv_path)
            self.current_df = df
            self.default_csv_path = csv_path
            self.lbl_csv_name.setText(csv_path.name)
            self.lbl_data_info.setText(f"✓ {info['nb_lignes']} simulations chargées ({len(inputs)} entrées détectées)")
            self._setup_input_checkboxes(inputs)
            self._populate_data_table(df)
            self.train_models()
        except Exception as exc:
            QMessageBox.critical(self, "Erreur de chargement", f"Impossible de charger le fichier CSV :\n{exc}")

    def _refresh_from_project_cases(self):
        """Construit un DataFrame à partir des simulations convergées du projet."""
        converged = [c for c in self.cases if c.status == CaseStatus.TERMINEE_CONVERGEE and c.results.cl_final is not None]
        if not converged:
            self.lbl_data_info.setText("⚠️ Aucune simulation convergée dans le projet.")
            return

        rows = []
        for c in converged:
            p = c.parameters
            row = {
                "Cas": c.name,
                "m_%": p.camber_m * 100.0,
                "p": p.camber_p,
                "thickness_%": p.thickness_t * 100.0,
                "alpha_deg": p.alpha_deg,
                "velocity": p.velocity,
                "Cl": c.results.cl_final,
                "Cd": c.results.cd_final,
            }
            rows.append(row)

        df = pd.DataFrame(rows)
        self.current_df = df
        self.lbl_data_info.setText(f"✓ {len(df)} simulations convergées du projet")
        inputs = ["m_%", "p", "alpha_deg"]
        self._setup_input_checkboxes([col for col in inputs if col in df.columns])
        self._populate_data_table(df)
        self.train_models()

    def _setup_input_checkboxes(self, input_cols: List[str]):
        # Nettoyage des anciennes cases à cocher
        for chk in self.input_checkboxes.values():
            self.lay_inputs.removeWidget(chk)
            chk.deleteLater()
        self.input_checkboxes.clear()

        # Recréation
        default_checked = ["m_%", "p"]
        for col in input_cols:
            chk = QCheckBox(col)
            chk.setChecked(col in default_checked or len(input_cols) <= 2)
            chk.toggled.connect(self._on_input_selection_changed)
            self.lay_inputs.addWidget(chk)
            self.input_checkboxes[col] = chk

        self._on_input_selection_changed()

    def _on_input_selection_changed(self):
        selected = [col for col, chk in self.input_checkboxes.items() if chk.isChecked()]
        self.input_columns = selected
        self._setup_calculator_form(selected)
        self._setup_plot_combos(selected)

    def _setup_calculator_form(self, input_cols: List[str]):
        # Vider le formulaire de calcul
        while self.lay_calc_form.count():
            item = self.lay_calc_form.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.calc_spinboxes.clear()

        if self.current_df is None or not input_cols:
            return

        for col in input_cols:
            spin = QDoubleSpinBox()
            spin.setDecimals(4)
            if col in self.current_df.columns:
                c_min = float(self.current_df[col].min())
                c_max = float(self.current_df[col].max())
                spin.setRange(c_min - (c_max - c_min) * 0.5, c_max + (c_max - c_min) * 0.5)
                spin.setValue(float(self.current_df[col].iloc[0]))
                span = c_max - c_min
                spin.setSingleStep(0.1 if span > 1.0 else 0.01)

            spin.valueChanged.connect(self._calculate_instant_prediction)
            self.lay_calc_form.addRow(f"{col} :", spin)
            self.calc_spinboxes[col] = spin

    def _setup_plot_combos(self, input_cols: List[str]):
        # Combo 1D
        self.combo_1d_x.blockSignals(True)
        self.combo_1d_x.clear()
        for col in input_cols:
            self.combo_1d_x.addItem(col)
        self.combo_1d_x.blockSignals(False)

        # Combo 2D
        self.combo_2d_x.blockSignals(True)
        self.combo_2d_y.blockSignals(True)
        self.combo_2d_x.clear()
        self.combo_2d_y.clear()

        for col in input_cols:
            self.combo_2d_x.addItem(col)
            self.combo_2d_y.addItem(col)

        if len(input_cols) >= 2:
            self.combo_2d_y.setCurrentIndex(1)

        self.combo_2d_x.blockSignals(False)
        self.combo_2d_y.blockSignals(False)

        # Targets
        for combo in (self.combo_1d_target, self.combo_2d_target):
            combo.blockSignals(True)
            combo.clear()
            if self.chk_cl.isChecked():
                combo.addItem("Cl")
            if self.chk_cd.isChecked():
                combo.addItem("Cd")
            combo.blockSignals(False)

    # ==========================================================================
    # Entraînement du modèle
    # ==========================================================================

    def train_models(self):
        """Entraîne les modèles de krigeage pour les cibles sélectionnées."""
        if self.current_df is None or self.current_df.empty:
            self.lbl_train_status.setText("Erreur : Aucune donnée disponible.")
            return

        selected_inputs = [col for col, chk in self.input_checkboxes.items() if chk.isChecked()]
        if not selected_inputs:
            self.lbl_train_status.setText("Sélectionnez au moins une variable d'entrée.")
            return

        selected_targets = []
        if self.chk_cl.isChecked():
            selected_targets.append("Cl")
        if self.chk_cd.isChecked():
            selected_targets.append("Cd")

        if not selected_targets:
            self.lbl_train_status.setText("Sélectionnez au moins une cible (Cl ou Cd).")
            return

        self.trained_models.clear()
        opt_theta = self.chk_optimize.isChecked()

        X = self.current_df[selected_inputs].to_numpy(dtype=float)

        try:
            for t_name in selected_targets:
                if t_name not in self.current_df.columns:
                    continue
                Y = self.current_df[t_name].to_numpy(dtype=float)
                model = entrainer_modele(
                    X=X,
                    Y=Y,
                    feature_names=selected_inputs,
                    target_name=t_name,
                    optimize_theta=opt_theta,
                )
                self.trained_models[t_name] = model

            self.lbl_train_status.setText(f"✓ Modèles {', '.join(selected_targets)} entraînés avec succès ({len(selected_inputs)} variables).")
            self.lbl_train_status.setStyleSheet("color: #16A34A; font-weight: 600; font-size: 11px;")

            # Mise à jour de toutes les vues
            self._update_theta_table()
            self._calculate_instant_prediction()
            self._update_plot_1d()
            self._update_plot_2d()
            self._update_plot_parity()
            self.model_trained.emit()

        except Exception as exc:
            self.lbl_train_status.setText(f"Échec de l'entraînement : {exc}")
            self.lbl_train_status.setStyleSheet("color: #DC2626; font-size: 11px;")

    # ==========================================================================
    # Prédiction ponctuelle instantanée
    # ==========================================================================

    def _calculate_instant_prediction(self):
        if not self.trained_models or not self.calc_spinboxes:
            return

        query_dict = {col: spin.value() for col, spin in self.calc_spinboxes.items()}

        all_inside = True
        warnings = []

        if "Cl" in self.trained_models:
            res_cl = self.trained_models["Cl"].predict(query_dict)
            self.lbl_cl_value.setText(f"{res_cl['y_pred']:.5f}")
            if not res_cl["is_inside_domain"]:
                all_inside = False
                for oob in res_cl["out_of_bounds"]:
                    warnings.append(f"{oob[0]} = {oob[1]:.2f} (domaine [{oob[2]:.2f}, {oob[3]:.2f}])")
        else:
            self.lbl_cl_value.setText("—")

        if "Cd" in self.trained_models:
            res_cd = self.trained_models["Cd"].predict(query_dict)
            self.lbl_cd_value.setText(f"{res_cd['y_pred']:.5f}")
            if not res_cd["is_inside_domain"]:
                all_inside = False
                for oob in res_cd["out_of_bounds"]:
                    warnings.append(f"{oob[0]} = {oob[1]:.2f} (domaine [{oob[2]:.2f}, {oob[3]:.2f}])")
        else:
            self.lbl_cd_value.setText("—")

        if all_inside:
            self.lbl_domain_status.setText("✓ Point situé dans le domaine d'apprentissage CFD.")
            self.lbl_domain_status.setStyleSheet("background-color: #F0FDF4; color: #166534; padding: 8px 12px; border-radius: 6px; font-size: 12px;")
        else:
            warn_str = ", ".join(set(warnings))
            self.lbl_domain_status.setText(f"⚠️ Extrapolation hors domaine : {warn_str}")
            self.lbl_domain_status.setStyleSheet("background-color: #FFFBEB; color: #92400E; padding: 8px 12px; border-radius: 6px; font-size: 12px;")

    # ==========================================================================
    # Graphique 1D (Matplotlib)
    # ==========================================================================

    def _update_plot_1d(self):
        self.fig_1d.clear()
        target = self.combo_1d_target.currentText()
        x_var = self.combo_1d_x.currentText()

        if not target or not x_var or target not in self.trained_models or self.current_df is None:
            self.canvas_1d.draw()
            return

        model = self.trained_models[target]
        idx_x = model.feature_names.index(x_var) if x_var in model.feature_names else 0

        min_x = float(model.X_min[idx_x])
        max_x = float(model.X_max[idx_x])
        x_pts = np.linspace(min_x, max_x, 120)

        # Matrice batch
        batch = np.zeros((len(x_pts), len(model.feature_names)))
        for j, col in enumerate(model.feature_names):
            if col == x_var:
                batch[:, j] = x_pts
            else:
                batch[:, j] = self.spin_1d_fixed.value()

        y_preds, _ = model.predict_batch(batch)

        ax = self.fig_1d.add_subplot(111)
        ax.set_facecolor("#FFFFFF")
        ax.plot(x_pts, y_preds, color="#2563EB", lw=2.2, label=f"{target} (Krigeage)")

        # Points CFD d'apprentissage
        ax.scatter(self.current_df[x_var], self.current_df[target], color="#0F172A", s=35, zorder=4, label="Données CFD réelles")

        ax.set_title(f"Courbe d'influence : {target} = f({x_var})", fontsize=12, fontweight="bold", color="#111827", pad=10)
        ax.set_xlabel(x_var, fontsize=11, color="#374151")
        ax.set_ylabel(f"Coefficient {target}", fontsize=11, color="#374151")
        ax.grid(True, linestyle="--", alpha=0.3, color="#94A3B8")
        ax.legend(frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0")

        self.fig_1d.tight_layout()
        self.canvas_1d.draw()

    # ==========================================================================
    # Graphique 2D (Surface de réponse)
    # ==========================================================================

    def _update_plot_2d(self):
        self.fig_2d.clear()
        target = self.combo_2d_target.currentText()
        x_var = self.combo_2d_x.currentText()
        y_var = self.combo_2d_y.currentText()

        if not target or not x_var or not y_var or x_var == y_var or target not in self.trained_models or self.current_df is None:
            self.canvas_2d.draw()
            return

        model = self.trained_models[target]
        idx_x = model.feature_names.index(x_var)
        idx_y = model.feature_names.index(y_var)

        gx = np.linspace(float(model.X_min[idx_x]), float(model.X_max[idx_x]), 40)
        gy = np.linspace(float(model.X_min[idx_y]), float(model.X_max[idx_y]), 40)
        GX, GY = np.meshgrid(gx, gy)

        mesh_batch = np.zeros((GX.size, len(model.feature_names)))
        for j, col in enumerate(model.feature_names):
            if col == x_var:
                mesh_batch[:, j] = GX.ravel()
            elif col == y_var:
                mesh_batch[:, j] = GY.ravel()
            else:
                mesh_batch[:, j] = float(self.current_df[col].iloc[0])

        Z_flat, _ = model.predict_batch(mesh_batch)
        Z_grid = Z_flat.reshape(GX.shape)

        ax = self.fig_2d.add_subplot(111)
        ax.set_facecolor("#FFFFFF")

        cnt = ax.contourf(GX, GY, Z_grid, levels=20, cmap="viridis")
        ax.contour(GX, GY, Z_grid, levels=10, colors="white", alpha=0.3, linewidths=0.7)
        self.fig_2d.colorbar(cnt, ax=ax, label=f"Coefficient {target}")

        # Points d'apprentissage réels
        ax.scatter(self.current_df[x_var], self.current_df[y_var], color="#DC2626", edgecolor="#FFFFFF", s=50, zorder=5, label="Simulations CFD réelles")

        ax.set_title(f"Surface de réponse 2D : {target} = f({x_var}, {y_var})", fontsize=12, fontweight="bold", color="#111827", pad=10)
        ax.set_xlabel(x_var, fontsize=11, color="#374151")
        ax.set_ylabel(y_var, fontsize=11, color="#374151")
        ax.legend(frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0")

        self.fig_2d.tight_layout()
        self.canvas_2d.draw()

    # ==========================================================================
    # Graphique de Parité
    # ==========================================================================

    def _update_plot_parity(self):
        self.fig_parity.clear()
        if not self.trained_models or self.current_df is None:
            self.canvas_parity.draw()
            return

        n_targets = len(self.trained_models)
        for i, (t_name, model) in enumerate(self.trained_models.items()):
            ax = self.fig_parity.add_subplot(1, n_targets, i + 1)
            ax.set_facecolor("#FFFFFF")

            y_real = model.Y_train
            X_phys = self.current_df[model.feature_names].to_numpy(dtype=float)
            y_pred, _ = model.predict_batch(X_phys)

            # Droite y = x
            min_val = min(float(y_real.min()), float(y_pred.min()))
            max_val = max(float(y_real.max()), float(y_pred.max()))
            delta = (max_val - min_val) * 0.05
            ax.plot([min_val - delta, max_val + delta], [min_val - delta, max_val + delta], "k--", lw=1.2, alpha=0.6, label="Idéal y = x")

            # Points
            ax.scatter(y_real, y_pred, color="#2563EB", edgecolor="#1E40AF", s=40, zorder=4, label="Points d'apprentissage")

            res = y_real - y_pred
            rmse = float(np.sqrt(np.mean(res ** 2)))

            ax.set_title(f"Parité {t_name} (RMSE = {rmse:.1e})", fontsize=11, fontweight="bold", color="#111827")
            ax.set_xlabel(f"{t_name} réel (CFD)", fontsize=10, color="#374151")
            ax.set_ylabel(f"{t_name} prédit (Krigeage)", fontsize=10, color="#374151")
            ax.grid(True, linestyle="--", alpha=0.3, color="#94A3B8")
            ax.legend(fontsize=9, frameon=True, facecolor="#F8FAFC", edgecolor="#E2E8F0")

        self.fig_parity.tight_layout()
        self.canvas_parity.draw()

    # ==========================================================================
    # Tableaux et données
    # ==========================================================================

    def _update_theta_table(self):
        rows = []
        for t_name, model in self.trained_models.items():
            for f_idx, f_name in enumerate(model.feature_names):
                rows.append([
                    t_name,
                    f_name,
                    f"{model.theta[f_idx]:.5f}",
                    "Oui" if model.is_optimized else "Manuel",
                    f"{model.mu:.5f}",
                    f"{model.objectif:.3f}",
                    f"{model.nugget:.1e}",
                ])

        self.table_theta.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignCenter)
                self.table_theta.setItem(r, c, item)

    def _populate_data_table(self, df: pd.DataFrame):
        self.table_data.setColumnCount(len(df.columns))
        self.table_data.setHorizontalHeaderLabels(list(df.columns))
        self.table_data.setRowCount(len(df))

        for r in range(len(df)):
            for c, col in enumerate(df.columns):
                val = df.iloc[r, c]
                val_str = f"{val:.5f}" if isinstance(val, (float, np.floating)) else str(val)
                item = QTableWidgetItem(val_str)
                item.setTextAlignment(Qt.AlignCenter)
                self.table_data.setItem(r, c, item)

    def _export_training_csv(self):
        if self.current_df is None or self.current_df.empty:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter les données d'apprentissage",
            "donnees_apprentissage_krigeage.csv",
            "Fichiers CSV (*.csv)",
        )
        if path:
            try:
                self.current_df.to_csv(path, index=False)
                QMessageBox.information(self, "Export réussi", f"Données enregistrées dans :\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Erreur d'export", f"Impossible d'exporter le fichier :\n{exc}")
