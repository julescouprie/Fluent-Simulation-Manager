import os
from pathlib import Path
import subprocess
import sys
import time
from typing import List, Optional

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from config.settings_manager import SettingsManager
from core.case_model import CaseStatus, PhysicalParameters, SimulationCase
from core.project_manager import ProjectManager
from core.queue_worker import QueueWorker
from ui.case_dialog import CaseDialog
from ui.comparison_widget import ComparisonWidget
from ui.confirmation_dialog import ConfirmationDialog
from ui.dashboard_widget import DashboardWidget
from ui.log_viewer_widget import LogViewerWidget
from ui.settings_dialog import SettingsDialog
from ui.simulation_table import SimulationTableWidget
from ui.design_space_widget import DesignSpaceWidget
from ui.campaign_widget import CampaignWidget
from ui.aero_mapping_widget import AeroMappingWidget
from ui.kriging_export_widget import KrigingExportWidget
from ui.kriging_prediction_widget import KrigingPredictionWidget
from ui.theme import LIGHT_PRO_STYLESHEET


class MainWindow(QMainWindow):
    """Fenêtre principale de l'application Fluent Simulation Manager."""

    # Indices des pages du QStackedWidget
    PAGE_OVERVIEW = 0
    PAGE_CAMPAIGNS = 1
    PAGE_AERO_MAPPING = 2
    PAGE_DATA = 3

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Fluent Simulation Manager - ANSYS Fluent 2026 R1")
        self.resize(1380, 900)
        self.setStyleSheet(LIGHT_PRO_STYLESHEET)

        self.settings = SettingsManager()
        self.project_manager = ProjectManager()

        # Horloge de suivi du temps
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer_tick)
        self.start_timestamp: Optional[float] = None
        self.accumulated_seconds: float = 0.0

        # Travailleur de file d'attente
        self.queue_worker = QueueWorker(
            cases_getter=lambda: self.project_manager.cases,
            fluent_exe_getter=lambda: self.settings.fluent_exe,
            mode_getter=lambda: self.settings.simulation_mode,
            base_runs_dir=Path(self.settings.get("runs_dir", "runs")),
        )

        self._setup_ui()
        self._setup_menus()
        self._connect_signals()

        # Initialisation avec quelques cas par défaut si le projet est vide
        if not self.project_manager.cases:
            self._init_default_cases()

        self._update_all_views()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------

    def _setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Sidebar ────────────────────────────────────────────────────
        self.sidebar = QWidget()
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(12, 16, 12, 16)
        sidebar_layout.setSpacing(4)

        # Titre de l'application dans la sidebar
        app_title = QLabel("FSM")
        app_title.setStyleSheet(
            "font-size: 18px; font-weight: bold; color: #111827; padding: 4px 4px 16px 4px;"
        )
        sidebar_layout.addWidget(app_title)

        # Boutons de navigation
        self._nav_buttons: List[QPushButton] = []

        nav_items = [
            ("🏠  Vue d'ensemble", self.PAGE_OVERVIEW),
            ("🎯  Campagnes & DoE", self.PAGE_CAMPAIGNS),
            ("🗺️  Aéro Mapping", self.PAGE_AERO_MAPPING),
            ("🧠  Prédiction (Krigeage)", self.PAGE_DATA),
        ]

        for label, page_idx in nav_items:
            btn = QPushButton(label)
            btn.setObjectName("nav_btn")
            btn.setCheckable(False)
            btn.clicked.connect(lambda checked=False, idx=page_idx: self._navigate_to(idx))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        sidebar_layout.addStretch()

        # Séparateur
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E5E7EB;")
        sidebar_layout.addWidget(sep)

        # Bouton Réglages
        btn_settings = QPushButton("⚙️  Réglages")
        btn_settings.setObjectName("nav_btn")
        btn_settings.clicked.connect(self._open_settings)
        sidebar_layout.addWidget(btn_settings)

        root_layout.addWidget(self.sidebar)

        # ── Contenu principal : QStackedWidget ─────────────────────────
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, stretch=1)

        # Alias pour compatibilité (les tests/méthodes qui référencent self.tabs)
        self.tabs = self.stack

        # ── Page 0 : Vue d'ensemble ────────────────────────────────────
        page_overview = self._build_page_overview()
        self.stack.addWidget(page_overview)

        # ── Page 1 : Campagnes ─────────────────────────────────────────
        page_campaigns = self._build_page_campaigns()
        self.stack.addWidget(page_campaigns)

        # ── Page 2 : Aéro Mapping ──────────────────────────────────────
        page_aero = self._build_page_aero_mapping()
        self.stack.addWidget(page_aero)

        # ── Page 3 : Données ───────────────────────────────────────────
        page_data = self._build_page_data()
        self.stack.addWidget(page_data)

        # Activer la première page
        self._navigate_to(self.PAGE_OVERVIEW)

        # Barre d'état
        self.status_bar = self.statusBar()
        self.lbl_status_mode = QLabel()
        self.lbl_status_fluent = QLabel()
        self.status_bar.addPermanentWidget(self.lbl_status_mode)
        self.status_bar.addPermanentWidget(self.lbl_status_fluent)
        self._update_status_bar()

    def _build_page_overview(self) -> QWidget:
        """Page 0 — Vue d'ensemble : Dashboard + File de simulation + Log."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 12)
        lay.setSpacing(12)

        # Titre de la page
        lbl_title = QLabel("Vue d'ensemble")
        lbl_title.setObjectName("lbl_page_title")
        lay.addWidget(lbl_title)

        # Dashboard intégré
        self.dashboard = DashboardWidget()
        lay.addWidget(self.dashboard)

        # Barre d'actions
        action_bar = QHBoxLayout()
        action_bar.setSpacing(8)

        btn_add = QPushButton("➕ Nouveau cas")
        btn_add.clicked.connect(self._add_case)
        btn_dup = QPushButton("📑 Dupliquer")
        btn_dup.clicked.connect(self._duplicate_selected)
        btn_edit = QPushButton("✏️ Modifier")
        btn_edit.clicked.connect(self._edit_selected)
        btn_del = QPushButton("❌ Supprimer")
        btn_del.clicked.connect(self._delete_selected)
        btn_import = QPushButton("📥 Importer CSV")
        btn_import.clicked.connect(self._import_csv)

        action_bar.addWidget(btn_add)
        action_bar.addWidget(btn_dup)
        action_bar.addWidget(btn_edit)
        action_bar.addWidget(btn_del)
        action_bar.addWidget(btn_import)
        action_bar.addStretch()

        # Boutons de contrôle de la file
        self.btn_run = QPushButton("🚀 Lancer les simulations")
        self.btn_run.setObjectName("btn_primary")
        self.btn_run.clicked.connect(self._on_launch_clicked)

        self.btn_pause = QPushButton("⏸️ Pause")
        self.btn_pause.setObjectName("btn_warning")
        self.btn_pause.setEnabled(False)
        self.btn_pause.clicked.connect(self._on_pause_clicked)

        self.btn_cancel = QPushButton("⏹️ Arrêter")
        self.btn_cancel.setObjectName("btn_danger")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._on_cancel_clicked)

        action_bar.addWidget(self.btn_run)
        action_bar.addWidget(self.btn_pause)
        action_bar.addWidget(self.btn_cancel)

        lay.addLayout(action_bar)

        # Splitter vertical : Tableau + Panneau bas (Log / Détails)
        v_splitter = QSplitter(Qt.Vertical)

        self.table = SimulationTableWidget()
        v_splitter.addWidget(self.table)

        # Panneau inférieur avec sous-onglets
        sub_tabs = QTabWidget()

        self.log_viewer = LogViewerWidget()
        sub_tabs.addTab(self.log_viewer, "📜 Journal Fluent (En direct)")

        self.details_widget = QTextBrowser()
        sub_tabs.addTab(self.details_widget, "🔍 Détails du cas")

        v_splitter.addWidget(sub_tabs)
        v_splitter.setStretchFactor(0, 3)
        v_splitter.setStretchFactor(1, 2)

        lay.addWidget(v_splitter)
        return page

    def _build_page_campaigns(self) -> QWidget:
        """Page 1 — Campagnes : Design Space + Campagnes DoE."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 12)
        lay.setSpacing(12)

        lbl_title = QLabel("Campagnes & Plans d'Expériences")
        lbl_title.setObjectName("lbl_page_title")
        lay.addWidget(lbl_title)

        inner_tabs = QTabWidget()

        # Sous-onglet : Espace de Conception
        self.design_space_widget = DesignSpaceWidget(self.project_manager.design_space)
        self.design_space_widget.design_space_changed.connect(self._on_design_space_changed)
        inner_tabs.addTab(self.design_space_widget, "📐 Espace de Conception")

        # Sous-onglet : Campagnes DoE
        self.campaign_widget = CampaignWidget(self.project_manager.design_space)
        self.campaign_widget.campaign_created.connect(self._on_campaign_created)
        inner_tabs.addTab(self.campaign_widget, "🎯 Campagnes DoE")

        lay.addWidget(inner_tabs)
        return page

    def _build_page_aero_mapping(self) -> QWidget:
        """Page 2 — Aéro Mapping : Mapping + Comparaison polaires."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 12)
        lay.setSpacing(12)

        lbl_title = QLabel("Aéro Mapping & Analyse Polaires")
        lbl_title.setObjectName("lbl_page_title")
        lay.addWidget(lbl_title)

        inner_tabs = QTabWidget()

        self.aero_mapping_widget = AeroMappingWidget(self.project_manager.design_space)
        inner_tabs.addTab(self.aero_mapping_widget, "🗺️ Aéro Mapping")

        self.comparison_widget = ComparisonWidget()
        inner_tabs.addTab(self.comparison_widget, "📊 Analyse Polaires & Cp")

        lay.addWidget(inner_tabs)
        return page

    def _build_page_data(self) -> QWidget:
        """Page 3 — Prédiction & Krigeage : Métamodèle, prédictions interactives et exports."""
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(20, 16, 20, 12)
        lay.setSpacing(12)

        lbl_title = QLabel("Prédiction Aérodynamique & Krigeage")
        lbl_title.setObjectName("lbl_page_title")
        lay.addWidget(lbl_title)

        inner_tabs = QTabWidget()

        # Widget de prédiction interactif par Krigeage
        self.kriging_prediction_widget = KrigingPredictionWidget(self.project_manager.design_space)
        self.kriging_widget = self.kriging_prediction_widget
        inner_tabs.addTab(self.kriging_prediction_widget, "🧠 Modèle & Prédiction interactive")

        # Widget d'exportation standardisée des matrices (conservé pour compatibilité)
        self.kriging_export_widget = KrigingExportWidget(self.project_manager.design_space)
        inner_tabs.addTab(self.kriging_export_widget, "📦 Export standardisé des matrices")

        lay.addWidget(inner_tabs)
        return page

    # ------------------------------------------------------------------
    # Navigation sidebar
    # ------------------------------------------------------------------

    def _navigate_to(self, page_idx: int):
        """Bascule vers la page demandée et met à jour les boutons de la sidebar."""
        self.stack.setCurrentIndex(page_idx)
        for i, btn in enumerate(self._nav_buttons):
            if i == page_idx:
                btn.setObjectName("nav_btn_active")
            else:
                btn.setObjectName("nav_btn")
            # Forcer le re-rendu du style
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ------------------------------------------------------------------
    # Menus
    # ------------------------------------------------------------------

    def _setup_menus(self):
        menubar = self.menuBar()

        # Menu Fichier
        menu_file = menubar.addMenu("&Fichier")

        act_new = QAction("&Nouveau projet", self)
        act_new.setShortcut(QKeySequence.New)
        act_new.triggered.connect(self._new_project)
        menu_file.addAction(act_new)

        act_open = QAction("&Ouvrir un projet...", self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._open_project)
        menu_file.addAction(act_open)

        act_save = QAction("&Enregistrer le projet", self)
        act_save.setShortcut(QKeySequence.Save)
        act_save.triggered.connect(self._save_project)
        menu_file.addAction(act_save)

        act_save_as = QAction("Enregistrer &sous...", self)
        act_save_as.triggered.connect(self._save_project_as)
        menu_file.addAction(act_save_as)

        menu_file.addSeparator()

        act_import = QAction("&Importer une liste de cas (CSV)...", self)
        act_import.triggered.connect(self._import_csv)
        menu_file.addAction(act_import)

        act_export_summary = QAction("&Exporter le récapitulatif (CSV)...", self)
        act_export_summary.triggered.connect(self._export_summary_csv)
        menu_file.addAction(act_export_summary)

        menu_file.addSeparator()

        act_quit = QAction("&Quitter", self)
        act_quit.setShortcut(QKeySequence.Quit)
        act_quit.triggered.connect(self.close)
        menu_file.addAction(act_quit)

        # Menu Édition
        menu_edit = menubar.addMenu("&Édition")

        act_add_case = QAction("&Ajouter un cas...", self)
        act_add_case.triggered.connect(self._add_case)
        menu_edit.addAction(act_add_case)

        act_dup_case = QAction("&Dupliquer le cas sélectionné", self)
        act_dup_case.triggered.connect(self._duplicate_selected)
        menu_edit.addAction(act_dup_case)

        act_edit_case = QAction("&Modifier le cas sélectionné", self)
        act_edit_case.triggered.connect(self._edit_selected)
        menu_edit.addAction(act_edit_case)

        act_del_case = QAction("&Supprimer les cas sélectionnés", self)
        act_del_case.triggered.connect(self._delete_selected)
        menu_edit.addAction(act_del_case)

        menu_edit.addSeparator()

        act_reset_failed = QAction("&Réinitialiser les cas en échec / annulés", self)
        act_reset_failed.triggered.connect(self._reset_failed_cases)
        menu_edit.addAction(act_reset_failed)

        # Menu Simulations
        menu_sim = menubar.addMenu("&Simulations")

        act_launch = QAction("&Lancer les simulations en attente", self)
        act_launch.setShortcut("F5")
        act_launch.triggered.connect(self._on_launch_clicked)
        menu_sim.addAction(act_launch)

        act_pause = QAction("&Mettre en pause la file", self)
        act_pause.triggered.connect(self._on_pause_clicked)
        menu_sim.addAction(act_pause)

        act_stop = QAction("&Arrêter la simulation active", self)
        act_stop.triggered.connect(self._on_cancel_clicked)
        menu_sim.addAction(act_stop)

        # Menu Outils
        menu_tools = menubar.addMenu("&Outils")

        act_generate_mesh = QAction("📐 &Générer le maillage NACA 2212 (Gmsh)", self)
        act_generate_mesh.triggered.connect(self._generate_naca_mesh)
        menu_tools.addAction(act_generate_mesh)

        act_settings = QAction("⚙️ &Préférences & Configuration Fluent...", self)
        act_settings.triggered.connect(self._open_settings)
        menu_tools.addAction(act_settings)

        # Menu Aide
        menu_help = menubar.addMenu("&Aide")

        act_about = QAction("À propos de &Fluent Simulation Manager", self)
        act_about.triggered.connect(self._show_about)
        menu_help.addAction(act_about)

    # ------------------------------------------------------------------
    # Connexions des signaux
    # ------------------------------------------------------------------

    def _connect_signals(self):
        # Table
        self.table.itemSelectionChanged.connect(self._on_table_selection_changed)
        self.table.case_double_clicked.connect(self._edit_case_by_id)
        self.table.edit_requested.connect(self._edit_case_by_id)
        self.table.duplicate_requested.connect(self._duplicate_case_by_id)
        self.table.delete_requested.connect(self._delete_cases_by_ids)
        self.table.retry_requested.connect(self._retry_cases_by_ids)
        self.table.open_folder_requested.connect(self._open_case_folder)
        self.table.view_logs_requested.connect(self._view_case_logs)

        # Worker
        self.queue_worker.case_started.connect(self._on_case_started)
        self.queue_worker.case_progress.connect(self._on_case_progress)
        self.queue_worker.case_log.connect(self._on_case_log)
        self.queue_worker.case_finished.connect(self._on_case_finished)
        self.queue_worker.queue_state_changed.connect(self._on_queue_state_changed)
        self.queue_worker.queue_finished.connect(self._on_queue_finished)

    # ------------------------------------------------------------------
    # Initialisation des cas par défaut
    # ------------------------------------------------------------------

    def _init_default_cases(self):
        """Initialise une série d'angles d'incidence typiques pour l'étude aérodynamique."""
        angles = [0.0, 2.0, 4.0, 6.0, 8.0]
        for a in angles:
            p = PhysicalParameters(
                mesh_file="profil_test.bdf",
                alpha_deg=a,
                velocity=30.0,
                iterations=200,
                cores=self.settings.default_cores,
            )
            case = SimulationCase(name=f"NACA 2212 - Alpha {a:+.1f}°", parameters=p)
            self.project_manager.add_case(case)

    # ------------------------------------------------------------------
    # Mise à jour globale des vues
    # ------------------------------------------------------------------

    def _update_all_views(self):
        self.table.populate(self.project_manager.cases)
        counts = self.project_manager.get_summary_counts()
        self.dashboard.update_stats(counts, self.accumulated_seconds)
        self.comparison_widget.set_cases(self.project_manager.cases)
        if hasattr(self, "aero_mapping_widget"):
            self.aero_mapping_widget.set_cases(self.project_manager.cases)
        if hasattr(self, "kriging_export_widget"):
            self.kriging_export_widget.set_cases(self.project_manager.cases)
        if hasattr(self, "kriging_prediction_widget"):
            self.kriging_prediction_widget.set_cases(self.project_manager.cases)
        if hasattr(self, "campaign_widget"):
            self.campaign_widget.update_active_variables_display()
        self._update_status_bar()

    def _on_design_space_changed(self):
        if hasattr(self, "campaign_widget"):
            self.campaign_widget.update_active_variables_display()
        if hasattr(self, "aero_mapping_widget"):
            self.aero_mapping_widget._populate_variable_combos()
            self.aero_mapping_widget.update_view()
        if hasattr(self, "kriging_export_widget"):
            self.kriging_export_widget.update_preview()

    def _on_campaign_created(self, campaign, cases):
        self.project_manager.add_campaign(campaign)
        for c in cases:
            self.project_manager.add_case(c)
        self._update_all_views()
        # Naviguer vers la vue d'ensemble après création d'une campagne
        self._navigate_to(self.PAGE_OVERVIEW)

    def _update_status_bar(self):
        mode = self.settings.simulation_mode
        if mode == "mock":
            self.lbl_status_mode.setText("🟡 Mode Test Fictif (Sans licence) | ")
            self.lbl_status_mode.setStyleSheet("color: #D97706; font-weight: bold;")
            self.lbl_status_fluent.setText("Calculs de démonstration")
            self.lbl_status_fluent.setStyleSheet("color: #6B7280;")
        else:
            self.lbl_status_mode.setText("🟢 Mode Réel ANSYS Fluent | ")
            self.lbl_status_mode.setStyleSheet("color: #16A34A; font-weight: bold;")
            if self.settings.is_fluent_valid():
                self.lbl_status_fluent.setText(f"Fluent : {Path(self.settings.fluent_exe).name}")
                self.lbl_status_fluent.setStyleSheet("color: #16A34A;")
            else:
                self.lbl_status_fluent.setText("Fluent : Introuvable (Configurer dans Préférences)")
                self.lbl_status_fluent.setStyleSheet("color: #DC2626;")

    def _on_timer_tick(self):
        if self.start_timestamp:
            self.accumulated_seconds = time.time() - self.start_timestamp
            counts = self.project_manager.get_summary_counts()
            self.dashboard.update_stats(counts, self.accumulated_seconds)

    # ------------------------------------------------------------------
    # Actions sur les simulations
    # ------------------------------------------------------------------

    def _add_case(self):
        dlg = CaseDialog(self)
        if dlg.exec():
            params = dlg.get_parameters()
            name = dlg.get_case_name()
            case = SimulationCase(name=name, parameters=params)
            self.project_manager.add_case(case)
            self._update_all_views()

    def _edit_case_by_id(self, case_id: str):
        case = self.project_manager.get_case(case_id)
        if not case:
            return
        if case.status.is_active:
            QMessageBox.warning(self, "Action impossible", "Impossible de modifier une simulation en cours d'exécution.")
            return

        dlg = CaseDialog(self, case=case)
        if dlg.exec():
            case.name = dlg.get_case_name()
            case.parameters = dlg.get_parameters()
            case.reset_status()
            self.project_manager.is_modified = True
            self._update_all_views()

    def _edit_selected(self):
        selected = self.table.get_selected_case_ids()
        if selected:
            self._edit_case_by_id(selected[0])

    def _duplicate_case_by_id(self, case_id: str):
        clone = self.project_manager.duplicate_case(case_id)
        if clone:
            self._update_all_views()

    def _duplicate_selected(self):
        selected = self.table.get_selected_case_ids()
        for cid in selected:
            self.project_manager.duplicate_case(cid)
        self._update_all_views()

    def _delete_cases_by_ids(self, case_ids: List[str]):
        if not case_ids:
            return
        ret = QMessageBox.question(
            self,
            "Confirmer la suppression",
            f"Voulez-vous supprimer {len(case_ids)} cas de simulation de la file ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            for cid in case_ids:
                self.project_manager.remove_case(cid)
            self._update_all_views()

    def _delete_selected(self):
        selected = self.table.get_selected_case_ids()
        self._delete_cases_by_ids(selected)

    def _retry_cases_by_ids(self, case_ids: List[str]):
        for cid in case_ids:
            case = self.project_manager.get_case(cid)
            if case and not case.status.is_active:
                case.reset_status()
        self._update_all_views()

    def _reset_failed_cases(self):
        for c in self.project_manager.cases:
            if c.status in (CaseStatus.ECHEC, CaseStatus.ANNULEE):
                c.reset_status()
        self._update_all_views()

    def _open_case_folder(self, case_id: str):
        case = self.project_manager.get_case(case_id)
        if case and case.work_dir and Path(case.work_dir).exists():
            if sys.platform == "win32":
                os.startfile(case.work_dir)
            else:
                subprocess.run(["xdg-open", case.work_dir])
        else:
            QMessageBox.information(self, "Dossier absent", "Aucun dossier de calcul n'a encore été créé pour ce cas.")

    def _view_case_logs(self, case_id: str):
        case = self.project_manager.get_case(case_id)
        if case and case.log_file and Path(case.log_file).exists():
            content = Path(case.log_file).read_text(encoding="utf-8", errors="ignore")
            self.log_viewer.clear()
            for line in content.splitlines():
                self.log_viewer.append_log(line)
            # Naviguer vers Vue d'ensemble pour voir le log
            self._navigate_to(self.PAGE_OVERVIEW)
        else:
            QMessageBox.information(self, "Logs absents", "Aucun fichier journal disponible pour ce cas.")

    def _on_table_selection_changed(self):
        selected = self.table.get_selected_case_ids()
        if not selected:
            self.details_widget.setHtml("<i>Aucune simulation sélectionnée.</i>")
            return

        case = self.project_manager.get_case(selected[0])
        if not case:
            return

        p = case.parameters
        html = f"""
        <h3>Cas : {case.name} <span style='color:#2563EB;'>[{case.id}]</span></h3>
        <p><b>Statut :</b> {case.status.value}</p>
        <hr>
        <h4>Paramètres physiques &amp; géométriques</h4>
        <ul>
            <li><b>Angle d'incidence (&alpha;) :</b> {p.alpha_deg:+.2f}°</li>
            <li><b>Vitesse de l'écoulement (U) :</b> {p.velocity:.2f} m/s</li>
            <li><b>Longueur de corde (c) :</b> {p.chord:.3f} m</li>
            <li><b>Masse volumique (&rho;) :</b> {p.density:.4f} kg/m³</li>
            <li><b>Pression dynamique (q) :</b> {p.dynamic_pressure:.2f} Pa</li>
            <li><b>Fichier maillage :</b> {p.mesh_file}</li>
            <li><b>Modèle de turbulence :</b> {p.turbulence_model} (k-omega SST)</li>
        </ul>
        <h4>Résolution numérique</h4>
        <ul>
            <li><b>Itérations configurées :</b> {p.iterations}</li>
            <li><b>Cœurs CPU :</b> {p.cores}</li>
            <li><b>Dossier d'exécution :</b> {case.work_dir or 'Non généré'}</li>
            <li><b>Fichier journal :</b> {case.log_file or 'Non généré'}</li>
        </ul>
        """
        if case.results.cl_final is not None:
            html += f"""
            <h4>Résultats aérodynamiques finaux</h4>
            <ul>
                <li><b>Portance CL :</b> <span style='color:#16A34A; font-weight:bold;'>{case.results.cl_final:.5f}</span></li>
                <li><b>Traînée CD :</b> <span style='color:#DC2626; font-weight:bold;'>{case.results.cd_final:.5f}</span></li>
                <li><b>Finesse CL/CD :</b> <span style='color:#2563EB; font-weight:bold;'>{case.results.cl_cd_ratio:.2f}</span></li>
                <li><b>Durée du calcul :</b> {case.duration_seconds:.1f} secondes</li>
            </ul>
            """
        if case.error_message:
            html += f"<p style='color:#DC2626;'><b>Erreur :</b> {case.error_message}</p>"

        self.details_widget.setHtml(html)

    # ------------------------------------------------------------------
    # Lancement et Gestion de la file
    # ------------------------------------------------------------------

    def _on_launch_clicked(self):
        pending = [c for c in self.project_manager.cases if c.status == CaseStatus.EN_ATTENTE]
        if not pending:
            QMessageBox.information(
                self,
                "File vide",
                "Aucune simulation n'est en attente d'exécution.\n"
                "Ajoutez un nouveau cas ou réinitialisez les simulations échouées.",
            )
            return

        dlg = ConfirmationDialog(self.project_manager.cases, self.settings, self)
        if dlg.exec():
            self.start_timestamp = time.time()
            self.accumulated_seconds = 0.0
            self.timer.start(1000)
            self.queue_worker.start_queue()

    def _on_pause_clicked(self):
        if self.queue_worker.is_paused:
            self.queue_worker.resume_queue()
        else:
            self.queue_worker.pause_queue()

    def _on_cancel_clicked(self):
        ret = QMessageBox.question(
            self,
            "Arrêter la simulation",
            "Voulez-vous interrompre le calcul en cours et arrêter la file ?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            self.queue_worker.stop_all()

    # ------------------------------------------------------------------
    # Événements du Worker
    # ------------------------------------------------------------------

    def _on_case_started(self, case_id: str):
        case = self.project_manager.get_case(case_id)
        if case:
            self.table.add_or_update_case_row(case)
            self.dashboard.update_stats(self.project_manager.get_summary_counts(), self.accumulated_seconds)
            self.statusBar().showMessage(f"Simulation en cours : {case.name} [{case.id}]")

    def _on_case_progress(self, case_id: str, current: int, total: int):
        case = self.project_manager.get_case(case_id)
        if case:
            self.table.add_or_update_case_row(case)

    def _on_case_log(self, case_id: str, line: str):
        self.log_viewer.append_log(line)

    def _on_case_finished(self, case_id: str, success: bool, error: str):
        case = self.project_manager.get_case(case_id)
        if case:
            self.table.add_or_update_case_row(case)
            self.dashboard.update_stats(self.project_manager.get_summary_counts(), self.accumulated_seconds)
            self.comparison_widget.set_cases(self.project_manager.cases)

    def _on_queue_state_changed(self, is_running: bool, is_paused: bool):
        self.btn_run.setEnabled(not is_running)
        self.btn_pause.setEnabled(is_running)
        self.btn_cancel.setEnabled(is_running)

        if is_paused:
            self.btn_pause.setText("▶️ Reprendre")
            self.btn_pause.setObjectName("btn_success")
            self.statusBar().showMessage("File d'attente en pause.")
        else:
            self.btn_pause.setText("⏸️ Pause")
            self.btn_pause.setObjectName("btn_warning")

    def _on_queue_finished(self):
        self.timer.stop()
        self.btn_run.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.statusBar().showMessage("Toutes les simulations sont terminées.", 5000)
        self._update_all_views()

    # ------------------------------------------------------------------
    # Gestion de projets & Fichiers
    # ------------------------------------------------------------------

    def _new_project(self):
        if self.project_manager.is_modified:
            ret = QMessageBox.question(
                self,
                "Enregistrer les modifications ?",
                "Le projet actuel comporte des modifications non enregistrées. Voulez-vous le sauvegarder ?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            )
            if ret == QMessageBox.Save:
                self._save_project()
            elif ret == QMessageBox.Cancel:
                return

        self.project_manager.clear()
        self._init_default_cases()
        self._update_all_views()
        self.statusBar().showMessage("Nouveau projet initialisé.")

    def _open_project(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Ouvrir un projet FSM",
            "",
            "Projet Fluent Simulation Manager (*.fsm *.json);;Tous les fichiers (*.*)",
        )
        if path:
            try:
                self.project_manager.load_project(Path(path))
                self._update_all_views()
                self.statusBar().showMessage(f"Projet chargé : {path}")
            except Exception as exc:
                QMessageBox.critical(self, "Erreur de chargement", f"Impossible d'ouvrir le projet :\n{exc}")

    def _save_project(self):
        if not self.project_manager.project_path:
            self._save_project_as()
        else:
            try:
                self.project_manager.save_project()
                self.statusBar().showMessage(f"Projet enregistré : {self.project_manager.project_path}")
            except Exception as exc:
                QMessageBox.critical(self, "Erreur d'enregistrement", f"Impossible d'enregistrer le projet :\n{exc}")

    def _save_project_as(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer le projet sous...",
            f"{self.project_manager.project_name}.fsm",
            "Projet Fluent Simulation Manager (*.fsm);;Tous les fichiers (*.*)",
        )
        if path:
            try:
                self.project_manager.save_project(Path(path))
                self.statusBar().showMessage(f"Projet enregistré sous : {path}")
            except Exception as exc:
                QMessageBox.critical(self, "Erreur d'enregistrement", f"Impossible d'enregistrer le projet :\n{exc}")

    def _import_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Importer des cas depuis un fichier CSV",
            "",
            "Fichier CSV (*.csv);;Tous les fichiers (*.*)",
        )
        if path:
            try:
                nb = self.project_manager.import_from_csv(Path(path))
                self._update_all_views()
                QMessageBox.information(self, "Import réussi", f"{nb} cas de simulation importés avec succès.")
            except Exception as exc:
                QMessageBox.critical(self, "Erreur d'import", f"Impossible d'importer le fichier CSV :\n{exc}")

    def _export_summary_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter le récapitulatif en CSV",
            "recapitulatif_simulations.csv",
            "Fichier CSV (*.csv)",
        )
        if path:
            try:
                self.project_manager.export_summary_csv(Path(path))
                QMessageBox.information(self, "Export réussi", f"Récapitulatif enregistré dans :\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Erreur d'export", f"Impossible d'exporter le récapitulatif :\n{exc}")

    def _open_settings(self):
        dlg = SettingsDialog(self.settings, self)
        if dlg.exec():
            self._update_status_bar()

    def _generate_naca_mesh(self):
        """Lance la génération du maillage profil_test.bdf à l'aide de mgsh_naca2212.py."""
        script = Path("mgsh_naca2212.py")
        if not script.exists():
            QMessageBox.critical(self, "Fichier manquant", "Le script mgsh_naca2212.py est introuvable.")
            return

        try:
            self.statusBar().showMessage("Génération du maillage NACA 2212 avec Gmsh...")
            subprocess.run([sys.executable, str(script)], check=True)
            QMessageBox.information(
                self,
                "Maillage généré",
                "Le maillage profil_test.bdf a été généré avec succès par Gmsh !",
            )
            self.statusBar().showMessage("Maillage prêt.")
        except Exception as exc:
            QMessageBox.critical(self, "Erreur Gmsh", f"Impossible de générer le maillage :\n{exc}")

    def _show_about(self):
        QMessageBox.about(
            self,
            "À propos de Fluent Simulation Manager",
            "<h2>Fluent Simulation Manager</h2>"
            "<p><b>Version :</b> 1.0.0 (Windows)</p>"
            "<p><b>Cible :</b> ANSYS Fluent 2026 R1 &amp; Aérodynamique de profils d'ailes (NACA 2212 2D)</p>"
            "<p>Application d'automatisation, de file d'attente séquentielle, de surveillance en temps réel "
            "et de post-traitement aérodynamique (CL, CD, Finesse, Cp, convergence).</p>"
            "<p>Conçu pour une utilisation ingénieur robuste et intuitive.</p>",
        )
