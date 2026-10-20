DARK_TECH_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #0f172a;
    color: #f8fafc;
    font-family: "Segoe UI", "Segoe UI Variable Text", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QGroupBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: bold;
    color: #38bdf8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    background-color: #1e293b;
    border-radius: 4px;
}

QTabWidget::pane {
    border: 1px solid #334155;
    background-color: #0f172a;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #1e293b;
    color: #94a3b8;
    padding: 10px 20px;
    font-weight: 600;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 3px;
    border: 1px solid #334155;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #0284c7;
    color: #ffffff;
    border-color: #38bdf8;
}

QTabBar::tab:hover:!selected {
    background-color: #334155;
    color: #f1f5f9;
}

QPushButton {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #334155;
    border-color: #64748b;
}

QPushButton:pressed {
    background-color: #0f172a;
}

QPushButton:disabled {
    background-color: #1e293b;
    color: #64748b;
    border-color: #334155;
}

QPushButton#btn_primary, QPushButton[class="primary"] {
    background-color: #0284c7;
    border: 1px solid #38bdf8;
    color: #ffffff;
    font-size: 14px;
    font-weight: bold;
    padding: 10px 24px;
}

QPushButton#btn_primary:hover {
    background-color: #0369a1;
}

QPushButton#btn_success {
    background-color: #059669;
    border: 1px solid #34d399;
    color: #ffffff;
}

QPushButton#btn_success:hover {
    background-color: #047857;
}

QPushButton#btn_danger {
    background-color: #dc2626;
    border: 1px solid #f87171;
    color: #ffffff;
}

QPushButton#btn_danger:hover {
    background-color: #b91c1c;
}

QPushButton#btn_warning {
    background-color: #d97706;
    border: 1px solid #fbbf24;
    color: #ffffff;
}

QPushButton#btn_warning:hover {
    background-color: #b45309;
}

QTableWidget {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    gridline-color: #334155;
    selection-background-color: #0369a1;
    selection-color: #ffffff;
    color: #e2e8f0;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #1e293b;
}

QTableWidget::item:selected {
    background-color: #0284c7;
    color: #ffffff;
}

QHeaderView::section {
    background-color: #0f172a;
    color: #94a3b8;
    font-weight: bold;
    padding: 8px 6px;
    border: none;
    border-right: 1px solid #334155;
    border-bottom: 2px solid #0284c7;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #1e293b;
    color: #f8fafc;
    border: 1px solid #475569;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #0284c7;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #38bdf8;
    background-color: #0f172a;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QProgressBar {
    background-color: #1e293b;
    border: 1px solid #475569;
    border-radius: 5px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
    height: 18px;
}

QProgressBar::chunk {
    background-color: #0284c7;
    border-radius: 4px;
}

QTextEdit, QPlainTextEdit {
    background-color: #020617;
    color: #cbd5e1;
    border: 1px solid #334155;
    border-radius: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}

QScrollBar:vertical {
    background: #0f172a;
    width: 12px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #475569;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QStatusBar {
    background-color: #020617;
    color: #94a3b8;
    border-top: 1px solid #1e293b;
}

QLabel {
    color: #cbd5e1;
}

QLabel#lbl_title {
    font-size: 18px;
    font-weight: bold;
    color: #38bdf8;
}

QLabel#lbl_stat_value {
    font-size: 24px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#lbl_stat_name {
    font-size: 11px;
    text-transform: uppercase;
    font-weight: 600;
    color: #94a3b8;
}
"""
