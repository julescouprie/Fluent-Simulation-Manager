from pathlib import Path
from typing import List
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.case_model import SimulationCase
from core.design_space import DesignSpace
from postprocessing.kriging_exporter import extract_kriging_matrices, save_kriging_files


class KrigingExportWidget(QWidget):
    """Écran de préparation et d'exportation des données pour l'apprentissage d'un modèle de Krigeage."""

    def __init__(self, design_space: DesignSpace, parent=None):
        super().__init__(parent)
        self.design_space = design_space
        self.cases: List[SimulationCase] = []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)

        splitter = QSplitter(Qt.Horizontal)

        # 1. Panneau de gauche : Réglages d'exportation pour le métamodèle
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        grp_filters = QGroupBox("Conditionnement & Filtrage Qualité Krigeage")
        lay_filt = QVBoxLayout(grp_filters)

        self.chk_only_conv = QCheckBox("Exclure impérativement les non-convergés / instables")
        self.chk_only_conv.setChecked(True)
        self.chk_only_conv.toggled.connect(self.update_preview)
        lay_filt.addWidget(self.chk_only_conv)

        self.chk_real_only = QCheckBox("Exclure les simulations fictives (CFD Réelle uniquement)")
        self.chk_real_only.setChecked(False)
        self.chk_real_only.toggled.connect(self.update_preview)
        lay_filt.addWidget(self.chk_real_only)

        self.chk_normalize = QCheckBox("Normaliser l'espace d'entrée X dans [0, 1]")
        self.chk_normalize.setChecked(True)
        self.chk_normalize.toggled.connect(self.update_preview)
        lay_filt.addWidget(self.chk_normalize)

        lay_split = QHBoxLayout()
        self.chk_split = QCheckBox("Partition de test indépendante :")
        self.chk_split.toggled.connect(self._on_split_toggled)
        self.spin_split = QSpinBox()
        self.spin_split.setRange(5, 50)
        self.spin_split.setValue(20)
        self.spin_split.setSuffix(" %")
        self.spin_split.setEnabled(False)
        self.spin_split.valueChanged.connect(self.update_preview)
        lay_split.addWidget(self.chk_split)
        lay_split.addWidget(self.spin_split)
        lay_filt.addLayout(lay_split)

        left_layout.addWidget(grp_filters)

        # Résumé des dimensions
        grp_summary = QGroupBox("Résumé du Jeu de Données")
        lay_sum = QFormLayout(grp_summary)
        self.lbl_n_total = QLabel("0")
        self.lbl_n_valid = QLabel("0")
        self.lbl_n_features = QLabel("0")
        lay_sum.addRow("Points totaux en base :", self.lbl_n_total)
        lay_sum.addRow("Points qualifiés pour Krigeage :", self.lbl_n_valid)
        lay_sum.addRow("Nombre de variables X (dim) :", self.lbl_n_features)
        left_layout.addWidget(grp_summary)

        # Boutons d'exportation
        grp_btn = QGroupBox("Génération des Fichiers")
        lay_btn = QVBoxLayout(grp_btn)

        btn_export_separate = QPushButton("📊 Exporter Matrices Séparées (X_train, Y_train)")
        btn_export_separate.setObjectName("btn_primary")
        btn_export_separate.clicked.connect(lambda: self._do_export(split_xy=True))

        btn_export_unified = QPushButton("📄 Exporter Tableau Unique Combiné (CSV)")
        btn_export_unified.clicked.connect(lambda: self._do_export(split_xy=False))

        lay_btn.addWidget(btn_export_separate)
        lay_btn.addWidget(btn_export_unified)
        left_layout.addWidget(grp_btn)

        left_layout.addStretch()
        left_panel.setMinimumWidth(320)
        left_panel.setMaximumWidth(420)
        splitter.addWidget(left_panel)

        # 2. Panneau de droite : Prévisualisation tabulaire du dataset
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.lbl_table_header = QLabel("Aperçu de la table des données de krigeage (X et Y)")
        self.lbl_table_header.setStyleSheet("font-weight: bold; color: #38bdf8;")
        right_layout.addWidget(self.lbl_table_header)

        self.table_preview = QTableWidget()
        self.table_preview.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table_preview.setAlternatingRowColors(True)
        right_layout.addWidget(self.table_preview)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

    def _on_split_toggled(self, checked: bool):
        self.spin_split.setEnabled(checked)
        self.update_preview()

    def set_cases(self, cases: List[SimulationCase]):
        self.cases = cases
        self.update_preview()

    def update_preview(self):
        active_ids = [v.id for v in self.design_space.get_operational_variables()]
        split_ratio = (self.spin_split.value() / 100.0) if self.chk_split.isChecked() else 0.0

        dataset = extract_kriging_matrices(
            cases=self.cases,
            active_var_ids=active_ids,
            only_converged=self.chk_only_conv.isChecked(),
            include_mock=not self.chk_real_only.isChecked(),
            normalize_X=self.chk_normalize.isChecked(),
            design_space=self.design_space,
            test_split_ratio=split_ratio,
        )

        self.lbl_n_total.setText(str(len(self.cases)))

        if not dataset["success"] or dataset["n_samples"] == 0:
            self.lbl_n_valid.setText("0 (Aucun calcul qualifié)")
            self.lbl_n_features.setText("0")
            self.table_preview.setRowCount(0)
            self.table_preview.setColumnCount(0)
            return

        n_valid = dataset["n_samples"]
        self.lbl_n_valid.setText(f"{n_valid} points fiables")
        self.lbl_n_features.setText(str(len(active_ids)))

        df_X = dataset.get("X_train", dataset.get("X"))
        df_Y = dataset.get("Y_train", dataset.get("Y"))
        df_meta = dataset.get("meta_train", dataset.get("meta"))

        df_view = pd.concat([df_meta[["simulation_id", "data_origin", "quality_flag"]], df_X, df_Y], axis=1)

        self.table_preview.setRowCount(len(df_view))
        self.table_preview.setColumnCount(len(df_view.columns))
        self.table_preview.setHorizontalHeaderLabels(list(df_view.columns))

        for r in range(len(df_view)):
            for c, col_name in enumerate(df_view.columns):
                val = df_view.iloc[r, c]
                val_str = f"{val:.4f}" if isinstance(val, (float, np.floating)) else str(val)
                item = QTableWidgetItem(val_str)
                item.setTextAlignment(Qt.AlignCenter)
                self.table_preview.setItem(r, c, item)

    def _do_export(self, split_xy: bool):
        active_ids = [v.id for v in self.design_space.get_operational_variables()]
        split_ratio = (self.spin_split.value() / 100.0) if self.chk_split.isChecked() else 0.0

        dataset = extract_kriging_matrices(
            cases=self.cases,
            active_var_ids=active_ids,
            only_converged=self.chk_only_conv.isChecked(),
            include_mock=not self.chk_real_only.isChecked(),
            normalize_X=self.chk_normalize.isChecked(),
            design_space=self.design_space,
            test_split_ratio=split_ratio,
        )

        if not dataset["success"]:
            QMessageBox.warning(self, "Export impossible", dataset["message"])
            return

        out_dir = QFileDialog.getExistingDirectory(self, "Choisir le dossier de destination pour les données de Krigeage")
        if out_dir:
            files = save_kriging_files(dataset, Path(out_dir))
            file_names = "\n".join([f"• {f.name}" for f in files])
            QMessageBox.information(
                self,
                "Export Krigeage réussi",
                f"Les fichiers de données d'apprentissage ont été générés avec succès :\n\n{file_names}\n\n"
                f"Dossier : {out_dir}",
            )
