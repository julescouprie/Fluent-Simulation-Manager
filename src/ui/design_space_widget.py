from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.design_space import DesignSpace, DesignVariable, VariableCategory


class DesignSpaceWidget(QWidget):
    """Écran de configuration de l'espace de conception (Design Space) et des variables."""

    design_space_changed = Signal()

    COLUMNS = [
        "Explorer (DoE)",
        "Nom de la variable",
        "Symbole",
        "Unité",
        "Valeur nominale",
        "Borne Min",
        "Borne Max",
        "Statut chaîne CFD",
        "Catégorie",
    ]

    def __init__(self, design_space: DesignSpace, parent=None):
        super().__init__(parent)
        self.design_space = design_space

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 1. Bannière explicative
        banner = QGroupBox("Définition de l'Espace de Conception")
        lay_banner = QVBoxLayout(banner)
        lbl_info = QLabel(
            "<b>Espace de Conception :</b> Définissez les variables explorées par les plans d'expériences "
            "pour alimenter le modèle de krigeage.<br>"
            "<i>Note : Les variables marquées 'Prévu Étape 2/3' (Effet de sol, Endplates 3D) sont déjà structurées dans l'architecture "
            "mais ne sont pas modifiables dans cette première étape 2D.</i>"
        )
        lbl_info.setWordWrap(True)
        lay_banner.addWidget(lbl_info)
        layout.addWidget(banner)

        # 2. Tableau des variables
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        layout.addWidget(self.table)

        # 3. Actions
        lay_actions = QHBoxLayout()
        btn_reset = QPushButton("🔄 Réinitialiser aux valeurs par défaut")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_apply = QPushButton("💾 Valider et Enregistrer l'Espace de Conception")
        btn_apply.setObjectName("btn_primary")
        btn_apply.clicked.connect(self._save_changes)

        lay_actions.addWidget(btn_reset)
        lay_actions.addStretch()
        lay_actions.addWidget(btn_apply)
        layout.addLayout(lay_actions)

        self.populate()

    def populate(self):
        """Remplit le tableau à partir des variables actuelles."""
        self.table.setRowCount(0)
        row = 0

        for var_id, var in self.design_space.variables.items():
            self.table.insertRow(row)

            # 0: Checkbox Active DoE
            chk_widget = QWidget()
            chk_lay = QHBoxLayout(chk_widget)
            chk_lay.setContentsMargins(0, 0, 0, 0)
            chk_lay.setAlignment(Qt.AlignCenter)
            chk = QCheckBox()
            chk.setChecked(var.is_active and var.is_operational)
            chk.setEnabled(var.is_operational)
            chk_lay.addWidget(chk)
            self.table.setCellWidget(row, 0, chk_widget)

            # 1: Nom
            item_name = QTableWidgetItem(var.name)
            item_name.setData(Qt.UserRole, var.id)
            item_name.setFlags(item_name.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 1, item_name)

            # 2: Symbole
            item_sym = QTableWidgetItem(var.symbol)
            item_sym.setTextAlignment(Qt.AlignCenter)
            item_sym.setFlags(item_sym.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 2, item_sym)

            # 3: Unité
            item_unit = QTableWidgetItem(var.unit)
            item_unit.setTextAlignment(Qt.AlignCenter)
            item_unit.setFlags(item_unit.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 3, item_unit)

            # 4: Valeur nominale
            spin_def = QDoubleSpinBox()
            spin_def.setRange(-1e6, 1e6)
            spin_def.setDecimals(4 if var.step and var.step < 0.01 else 2)
            spin_def.setValue(var.default_val)
            spin_def.setEnabled(var.is_operational)
            self.table.setCellWidget(row, 4, spin_def)

            # 5: Min
            spin_min = QDoubleSpinBox()
            spin_min.setRange(-1e6, 1e6)
            spin_min.setDecimals(4 if var.step and var.step < 0.01 else 2)
            spin_min.setValue(var.min_val)
            spin_min.setEnabled(var.is_operational)
            self.table.setCellWidget(row, 5, spin_min)

            # 6: Max
            spin_max = QDoubleSpinBox()
            spin_max.setRange(-1e6, 1e6)
            spin_max.setDecimals(4 if var.step and var.step < 0.01 else 2)
            spin_max.setValue(var.max_val)
            spin_max.setEnabled(var.is_operational)
            self.table.setCellWidget(row, 6, spin_max)

            # 7: Statut opérationnel
            if var.is_operational:
                status_text = "✅ Opérationnel (Relié CFD)"
                status_color = "#16A34A"
            else:
                status_text = "⏳ Non relié (Étapes futures)"
                status_color = "#D97706"

            item_status = QTableWidgetItem(status_text)
            item_status.setForeground(QColor(status_color))
            item_status.setFont(QFont("Segoe UI", 9, QFont.Bold))
            item_status.setFlags(item_status.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 7, item_status)

            # 8: Catégorie
            item_cat = QTableWidgetItem(var.category.value)
            item_cat.setFlags(item_cat.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 8, item_cat)

            row += 1

        self.table.resizeColumnsToContents()
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(1, 230)

    def _save_changes(self):
        for r in range(self.table.rowCount()):
            item_name = self.table.item(r, 1)
            if not item_name:
                continue
            var_id = item_name.data(Qt.UserRole)
            var = self.design_space.get_variable(var_id)
            if not var:
                continue

            chk_widget = self.table.cellWidget(r, 0)
            chk = chk_widget.findChild(QCheckBox) if chk_widget else None
            spin_def = self.table.cellWidget(r, 4)
            spin_min = self.table.cellWidget(r, 5)
            spin_max = self.table.cellWidget(r, 6)

            if chk:
                var.is_active = chk.isChecked()
            if spin_def:
                var.default_val = spin_def.value()
            if spin_min:
                var.min_val = spin_min.value()
            if spin_max:
                var.max_val = spin_max.value()

            # Validation min < max
            if var.min_val >= var.max_val:
                QMessageBox.warning(
                    self,
                    "Incohérence de bornes",
                    f"Pour la variable '{var.name}', la borne minimale ({var.min_val}) "
                    f"doit être strictement inférieure à la borne maximale ({var.max_val}).",
                )
                return

        QMessageBox.information(self, "Sauvegarde", "Espace de conception mis à jour avec succès.")
        self.design_space_changed.emit()

    def _reset_defaults(self):
        self.design_space._load_standard_catalog()
        self.populate()
        self.design_space_changed.emit()
