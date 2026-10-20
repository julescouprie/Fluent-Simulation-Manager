from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt


class StatCard(QFrame):
    """Carte individuelle d'indicateur numérique avec couleur d'accent."""

    def __init__(self, title: str, initial_value: str = "0", accent_color: str = "#0284c7"):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet(f"""
            QFrame {{
                background-color: #1e293b;
                border: 1px solid #334155;
                border-left: 4px solid {accent_color};
                border-radius: 8px;
                padding: 6px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(2)

        self.lbl_title = QLabel(title)
        self.lbl_title.setObjectName("lbl_stat_name")
        self.lbl_title.setAlignment(Qt.AlignLeft)

        self.lbl_value = QLabel(initial_value)
        self.lbl_value.setObjectName("lbl_stat_value")
        self.lbl_value.setAlignment(Qt.AlignLeft)

        layout.addWidget(self.lbl_title)
        layout.addWidget(self.lbl_value)

    def set_value(self, value: str):
        self.lbl_value.setText(str(value))


class DashboardWidget(QWidget):
    """Tableau de bord affichant le statut de l'ensemble des simulations."""

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 10)
        layout.setSpacing(10)

        self.card_total = StatCard("Total Simulations", "0", "#38bdf8")
        self.card_pending = StatCard("En attente", "0", "#facc15")
        self.card_running = StatCard("En cours", "0", "#0284c7")
        self.card_done = StatCard("Terminées", "0", "#10b981")
        self.card_failed = StatCard("Échecs", "0", "#ef4444")
        self.card_time = StatCard("Temps de calcul", "00:00", "#a855f7")

        layout.addWidget(self.card_total)
        layout.addWidget(self.card_pending)
        layout.addWidget(self.card_running)
        layout.addWidget(self.card_done)
        layout.addWidget(self.card_failed)
        layout.addWidget(self.card_time)

    def update_stats(self, counts: dict, elapsed_seconds: float = 0.0):
        self.card_total.set_value(str(counts.get("total", 0)))
        self.card_pending.set_value(str(counts.get("en_attente", 0)))
        self.card_running.set_value(str(counts.get("en_cours", 0)))
        self.card_done.set_value(str(counts.get("terminee", 0)))
        self.card_failed.set_value(str(counts.get("echec", 0)))

        mins = int(elapsed_seconds // 60)
        secs = int(elapsed_seconds % 60)
        self.card_time.set_value(f"{mins:02d}:{secs:02d}")
