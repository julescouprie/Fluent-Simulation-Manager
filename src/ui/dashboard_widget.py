from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel,
    QFrame,
)
from PySide6.QtCore import Qt


class StatCard(QFrame):
    """Carte individuelle d'indicateur numérique sobre (thème clair)."""

    def __init__(self, title: str, initial_value: str = "0"):
        super().__init__()
        self.setFrameShape(QFrame.StyledPanel)
        self.setMaximumHeight(80)
        self.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)

        self.lbl_title = QLabel(title.upper())
        self.lbl_title.setObjectName("lbl_stat_label")
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
        layout.setContentsMargins(0, 0, 0, 12)
        layout.setSpacing(10)

        self.card_total = StatCard("Total")
        self.card_pending = StatCard("En attente")
        self.card_running = StatCard("En cours")
        self.card_converged = StatCard("Convergées")
        self.card_unconverged = StatCard("Non convergées")
        self.card_failed = StatCard("Échecs")
        self.card_time = StatCard("Temps", "00:00")

        layout.addWidget(self.card_total)
        layout.addWidget(self.card_pending)
        layout.addWidget(self.card_running)
        layout.addWidget(self.card_converged)
        layout.addWidget(self.card_unconverged)
        layout.addWidget(self.card_failed)
        layout.addWidget(self.card_time)

    def update_stats(self, counts: dict, elapsed_seconds: float = 0.0):
        self.card_total.set_value(str(counts.get("total", 0)))
        self.card_pending.set_value(str(counts.get("en_attente", 0)))
        self.card_running.set_value(str(counts.get("en_cours", 0)))
        self.card_converged.set_value(str(counts.get("terminee_convergee", 0)))
        self.card_unconverged.set_value(str(counts.get("terminee_non_convergee", 0)))
        self.card_failed.set_value(str(counts.get("echec", 0)))

        mins = int(elapsed_seconds // 60)
        secs = int(elapsed_seconds % 60)
        self.card_time.set_value(f"{mins:02d}:{secs:02d}")
