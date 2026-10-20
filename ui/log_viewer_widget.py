from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LogViewerWidget(QWidget):
    """Console d'affichage en direct des journaux d'exécution Fluent."""

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 5, 0, 0)
        layout.setSpacing(6)

        # Barre d'outils de la console
        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.lbl_title = QLabel("📜 Console d'exécution Fluent")
        self.lbl_title.setStyleSheet("font-weight: bold; color: #38bdf8;")
        toolbar.addWidget(self.lbl_title)

        toolbar.addStretch()

        self.edit_filter = QLineEdit()
        self.edit_filter.setPlaceholderText("Filtrer le texte...")
        self.edit_filter.setFixedWidth(200)
        self.edit_filter.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self.edit_filter)

        self.chk_autoscroll = QCheckBox("Défilement automatique")
        self.chk_autoscroll.setChecked(True)
        toolbar.addWidget(self.chk_autoscroll)

        btn_copy = QPushButton("Copier")
        btn_copy.clicked.connect(self._copy_all)
        toolbar.addWidget(btn_copy)

        btn_clear = QPushButton("Effacer")
        btn_clear.clicked.connect(self.clear)
        toolbar.addWidget(btn_clear)

        layout.addLayout(toolbar)

        # Zone de texte
        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setMaximumBlockCount(10000)  # Évite la saturation mémoire
        layout.addWidget(self.text_edit)

        self._all_lines = []

    def append_log(self, text: str):
        """Ajoute une ligne de journal."""
        self._all_lines.append(text)
        if len(self._all_lines) > 10000:
            self._all_lines.pop(0)

        # Vérification du filtre actuel
        filter_text = self.edit_filter.text().lower()
        if not filter_text or filter_text in text.lower():
            self.text_edit.appendPlainText(text)
            if self.chk_autoscroll.isChecked():
                self.text_edit.moveCursor(QTextCursor.End)

    def clear(self):
        self._all_lines.clear()
        self.text_edit.clear()

    def _copy_all(self):
        self.text_edit.selectAll()
        self.text_edit.copy()
        # Désélectionne
        cursor = self.text_edit.textCursor()
        cursor.clearSelection()
        self.text_edit.setTextCursor(cursor)

    def _apply_filter(self, text: str):
        filter_text = text.lower().strip()
        self.text_edit.clear()
        if not filter_text:
            self.text_edit.setPlainText("\n".join(self._all_lines))
        else:
            matching = [l for l in self._all_lines if filter_text in l.lower()]
            self.text_edit.setPlainText("\n".join(matching))

        if self.chk_autoscroll.isChecked():
            self.text_edit.moveCursor(QTextCursor.End)
