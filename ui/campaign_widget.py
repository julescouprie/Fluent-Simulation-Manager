import random
from pathlib import Path
from typing import Any, Dict, List
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.campaign_model import DoECampaign, DoEStrategy
from core.case_model import PhysicalParameters, SimulationCase
from core.design_space import DesignSpace
from doe.sampling import build_doe_campaign


class CampaignWidget(QWidget):
    """Écran de conception de campagnes de calcul par Plans d'Expériences (DoE)."""

    campaign_created = Signal(object, list)  # (DoECampaign, List[SimulationCase])

    def __init__(self, design_space: DesignSpace, parent=None):
        super().__init__(parent)
        self.design_space = design_space
        self.previewed_points: List[Dict[str, float]] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Horizontal)

        # Panneau de gauche : Paramétrage du DoE
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 1. Identification
        grp_id = QGroupBox("Identification de la Campagne")
        lay_id = QFormLayout(grp_id)

        self.edit_name = QLineEdit("Campagne_Sensibilite_01")
        self.edit_desc = QLineEdit("Exploration de l'espace pour entraînement du métamodèle Krigeage")
        lay_id.addRow("Nom :", self.edit_name)
        lay_id.addRow("Description :", self.edit_desc)

        left_layout.addWidget(grp_id)

        # 2. Stratégie de génération
        grp_strat = QGroupBox("Stratégie de Plan d'Expériences (DoE)")
        lay_strat = QFormLayout(grp_strat)

        self.combo_strat = QComboBox()
        self.combo_strat.addItem("Latin Hypercube Sampling (LHS)", DoEStrategy.LHS)
        self.combo_strat.addItem("Grille factorielle complète", DoEStrategy.GRID)
        self.combo_strat.addItem("Échantillonnage aléatoire uniforme", DoEStrategy.RANDOM)
        self.combo_strat.addItem("Importation depuis un fichier CSV", DoEStrategy.CSV_IMPORT)
        self.combo_strat.currentIndexChanged.connect(self._on_strategy_changed)

        lay_strat.addRow("Méthode :", self.combo_strat)

        # Paramètres LHS / Random
        self.spin_nsamples = QSpinBox()
        self.spin_nsamples.setRange(2, 500)
        self.spin_nsamples.setValue(15)
        lay_strat.addRow("Nombre de simulations :", self.spin_nsamples)

        lay_seed = QHBoxLayout()
        self.spin_seed = QSpinBox()
        self.spin_seed.setRange(0, 999999)
        self.spin_seed.setValue(42)
        btn_rnd_seed = QPushButton("🎲 Aléatoire")
        btn_rnd_seed.clicked.connect(lambda: self.spin_seed.setValue(random.randint(1, 99999)))
        lay_seed.addWidget(self.spin_seed)
        lay_seed.addWidget(btn_rnd_seed)
        lay_strat.addRow("Graine reproductible (Seed) :", lay_seed)

        # Paramètre CSV
        self.lay_csv = QHBoxLayout()
        self.edit_csv_path = QLineEdit()
        self.btn_browse_csv = QPushButton("Parcourir...")
        self.btn_browse_csv.clicked.connect(self._browse_csv)
        self.lay_csv.addWidget(self.edit_csv_path)
        self.lay_csv.addWidget(self.btn_browse_csv)
        self.lbl_csv = QLabel("Fichier CSV :")
        lay_strat.addRow(self.lbl_csv, self.lay_csv)

        left_layout.addWidget(grp_strat)

        # Résumé des variables actives
        self.lbl_active_vars = QLabel()
        self.lbl_active_vars.setWordWrap(True)
        self.lbl_active_vars.setObjectName("lbl_metric")
        left_layout.addWidget(self.lbl_active_vars)

        # Boutons d'action
        btn_preview = QPushButton("🔍 Prévisualiser les configurations")
        btn_preview.clicked.connect(self._preview_doe)
        left_layout.addWidget(btn_preview)

        self.btn_add_queue = QPushButton("🚀 Ajouter la campagne à la file d'attente")
        self.btn_add_queue.setObjectName("btn_primary")
        self.btn_add_queue.setEnabled(False)
        self.btn_add_queue.clicked.connect(self._commit_campaign)
        left_layout.addWidget(self.btn_add_queue)

        left_layout.addStretch()
        left_panel.setMinimumWidth(320)
        left_panel.setMaximumWidth(420)
        splitter.addWidget(left_panel)

        # Panneau de droite : Prévisualisation du tableau DoE
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_table_header = QLabel("Tableau des configurations de la campagne (0 point)")
        self.lbl_table_header.setObjectName("lbl_section_title")
        right_layout.addWidget(self.lbl_table_header)

        self.table_preview = QTableWidget()
        self.table_preview.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        right_layout.addWidget(self.table_preview)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        self._on_strategy_changed()
        self.update_active_variables_display()

    def update_active_variables_display(self):
        actives = self.design_space.get_active_variables()
        if actives:
            names = [f"<b>{v.name}</b> ({v.symbol})" for v in actives]
            self.lbl_active_vars.setText(f"Variables explorées ({len(actives)}) :<br>" + ", ".join(names))
        else:
            self.lbl_active_vars.setText("⚠️ <i>Aucune variable activée dans l'Espace de Conception ! Allez dans l'onglet 'Espace de Conception' pour en cocher.</i>")

    def _on_strategy_changed(self):
        strat = self.combo_strat.currentData()
        is_csv = (strat == DoEStrategy.CSV_IMPORT)
        is_samples = (strat in (DoEStrategy.LHS, DoEStrategy.RANDOM))

        self.spin_nsamples.setEnabled(is_samples)
        self.spin_seed.setEnabled(is_samples)

        self.lbl_csv.setVisible(is_csv)
        self.edit_csv_path.setVisible(is_csv)
        self.btn_browse_csv.setVisible(is_csv)

    def _browse_csv(self):
        f, _ = QFileDialog.getOpenFileName(self, "Sélectionner le fichier CSV de DoE", "", "Fichiers CSV (*.csv);;Tous les fichiers (*.*)")
        if f:
            self.edit_csv_path.setText(f)

    def _preview_doe(self):
        strat = self.combo_strat.currentData()
        strat_params = {
            "n_samples": self.spin_nsamples.value(),
            "seed": self.spin_seed.value(),
            "csv_path": self.edit_csv_path.text().strip(),
            "levels": {v.id: 3 for v in self.design_space.get_active_variables()},
        }

        points, warnings, meta = build_doe_campaign(strat, self.design_space, strat_params)

        if warnings:
            msg = "\n".join(warnings[:5])
            if len(warnings) > 5:
                msg += f"\n... et {len(warnings) - 5} autre(s) avertissement(s)."
            QMessageBox.information(self, "Avertissements DoE", msg)

        if not points:
            QMessageBox.warning(self, "Erreur", "Aucune configuration valide n'a pu être générée.")
            self.btn_add_queue.setEnabled(False)
            return

        self.previewed_points = points
        self._populate_preview_table(points)
        self.btn_add_queue.setEnabled(True)
        self.lbl_table_header.setText(f"Tableau des configurations de la campagne ({len(points)} simulations valides)")

    def _populate_preview_table(self, points: List[Dict[str, float]]):
        if not points:
            self.table_preview.setRowCount(0)
            return

        all_keys = list(points[0].keys())
        self.table_preview.setColumnCount(len(all_keys) + 1)
        headers = ["#"] + [self.design_space.get_variable(k).symbol if self.design_space.get_variable(k) else k for k in all_keys]
        self.table_preview.setHorizontalHeaderLabels(headers)
        self.table_preview.setRowCount(len(points))

        for r, pt in enumerate(points):
            self.table_preview.setItem(r, 0, QTableWidgetItem(f"Cas #{r+1}"))
            for c, k in enumerate(all_keys):
                val = pt[k]
                item = QTableWidgetItem(f"{val:.3f}" if isinstance(val, float) else str(val))
                item.setTextAlignment(Qt.AlignCenter)
                self.table_preview.setItem(r, c + 1, item)

    def _commit_campaign(self):
        if not self.previewed_points:
            return

        name = self.edit_name.text().strip() or "Campagne_DoE"
        strat = self.combo_strat.currentData()
        active_ids = [v.id for v in self.design_space.get_active_variables()]
        fixed_dict = {v.id: v.default_val for v in self.design_space.get_fixed_variables()}

        campaign = DoECampaign(
            name=name,
            description=self.edit_desc.text().strip(),
            strategy=strat,
            strategy_params={"n_samples": len(self.previewed_points), "seed": self.spin_seed.value()},
            active_variable_ids=active_ids,
            fixed_parameters=fixed_dict,
        )

        cases: List[SimulationCase] = []
        for i, pt in enumerate(self.previewed_points):
            params = PhysicalParameters(
                camber_m=float(pt.get("camber_m", 0.02)),
                camber_p=float(pt.get("camber_p", 0.20)),
                thickness_t=float(pt.get("thickness_t", 0.12)),
                chord=float(pt.get("chord", 1.0)),
                alpha_deg=float(pt.get("alpha_deg", 0.0)),
                velocity=float(pt.get("velocity", 30.0)),
                density=float(pt.get("density", 1.225)),
                iterations=int(pt.get("iterations", 200)),
                cores=int(pt.get("cores", 4)),
            )
            case_name = f"{name}_NACA{params.naca_digits}_a{params.alpha_deg:+.1f}deg"
            case = SimulationCase(
                name=case_name,
                parameters=params,
                campaign_id=campaign.id,
            )
            cases.append(case)
            campaign.case_ids.append(case.id)

        self.campaign_created.emit(campaign, cases)
        QMessageBox.information(
            self,
            "Campagne injectée",
            f"La campagne '{name}' ({len(cases)} simulations) a été créée et ajoutée à la file d'attente !",
        )
        self.btn_add_queue.setEnabled(False)
