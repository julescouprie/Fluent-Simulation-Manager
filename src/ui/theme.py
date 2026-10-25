LIGHT_PRO_STYLESHEET = """
QMainWindow, QDialog, QWidget {
    background-color: #FFFFFF;
    color: #111827;
    font-family: "Segoe UI Variable", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QGroupBox {
    background-color: transparent;
    border: 1px solid #E5E7EB;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 12px;
    font-weight: bold;
    font-size: 12px;
    color: #374151;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #374151;
    font-weight: bold;
    font-size: 12px;
}

QTabWidget::pane {
    border: 1px solid #E5E7EB;
    background-color: #FFFFFF;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #F9FAFB;
    color: #6B7280;
    padding: 8px 18px;
    font-weight: 600;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 2px;
    border: 1px solid #E5E7EB;
    border-bottom: none;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #2563EB;
    border-color: #E5E7EB;
    border-bottom: 2px solid #2563EB;
}

QTabBar::tab:hover:!selected {
    background-color: #F3F4F6;
    color: #374151;
}

QPushButton {
    background-color: #F3F4F6;
    color: #374151;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 7px 16px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #E5E7EB;
    border-color: #9CA3AF;
}

QPushButton:pressed {
    background-color: #D1D5DB;
}

QPushButton:disabled {
    background-color: #F9FAFB;
    color: #9CA3AF;
    border-color: #E5E7EB;
}

QPushButton#btn_primary, QPushButton[class="primary"] {
    background-color: #2563EB;
    border: none;
    color: #FFFFFF;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 20px;
}

QPushButton#btn_primary:hover {
    background-color: #1D4ED8;
}

QPushButton#btn_primary:disabled {
    background-color: #93C5FD;
    color: #FFFFFF;
}

QPushButton#btn_success {
    background-color: #2563EB;
    border: none;
    color: #FFFFFF;
}

QPushButton#btn_success:hover {
    background-color: #1D4ED8;
}

QPushButton#btn_danger {
    background-color: #FFFFFF;
    border: 1px solid #DC2626;
    color: #DC2626;
}

QPushButton#btn_danger:hover {
    background-color: #FEF2F2;
}

QPushButton#btn_warning {
    background-color: #F3F4F6;
    border: 1px solid #D1D5DB;
    color: #374151;
}

QPushButton#btn_warning:hover {
    background-color: #E5E7EB;
}

/* Sidebar navigation buttons */
QPushButton#nav_btn {
    background-color: transparent;
    color: #6B7280;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    font-weight: 500;
    font-size: 13px;
}

QPushButton#nav_btn:hover {
    background-color: #F3F4F6;
    color: #374151;
}

QPushButton#nav_btn_active {
    background-color: #EFF6FF;
    color: #2563EB;
    border: none;
    border-radius: 8px;
    padding: 10px 16px;
    text-align: left;
    font-weight: 600;
    font-size: 13px;
}

QPushButton#nav_btn_active:hover {
    background-color: #DBEAFE;
}

QTableWidget {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    gridline-color: #F3F4F6;
    selection-background-color: #EFF6FF;
    selection-color: #1E40AF;
    color: #111827;
    alternate-background-color: #F9FAFB;
}

QTableWidget::item {
    padding: 6px 8px;
    border-bottom: 1px solid #F3F4F6;
}

QTableWidget::item:selected {
    background-color: #EFF6FF;
    color: #1E40AF;
}

QHeaderView::section {
    background-color: #F9FAFB;
    color: #6B7280;
    font-weight: 600;
    padding: 8px 6px;
    border: none;
    border-right: 1px solid #E5E7EB;
    border-bottom: 1px solid #E5E7EB;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #FFFFFF;
    color: #111827;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 6px 10px;
    selection-background-color: #DBEAFE;
}

QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
    border: 1px solid #2563EB;
    background-color: #FFFFFF;
}

QComboBox::drop-down {
    border: none;
    padding-right: 8px;
}

QComboBox QAbstractItemView {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    color: #111827;
    selection-background-color: #EFF6FF;
    selection-color: #2563EB;
}

QProgressBar {
    background-color: #F3F4F6;
    border: none;
    border-radius: 3px;
    text-align: center;
    color: transparent;
    height: 6px;
    max-height: 6px;
}

QProgressBar::chunk {
    background-color: #2563EB;
    border-radius: 3px;
}

QTextEdit, QPlainTextEdit {
    background-color: #F8F9FA;
    color: #374151;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 12px;
}

QScrollBar:vertical {
    background: #F9FAFB;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #D1D5DB;
    min-height: 20px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #9CA3AF;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background: #F9FAFB;
    height: 8px;
    margin: 0px;
}

QScrollBar::handle:horizontal {
    background: #D1D5DB;
    min-width: 20px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal:hover {
    background: #9CA3AF;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

QStatusBar {
    background-color: #F9FAFB;
    color: #6B7280;
    border-top: 1px solid #E5E7EB;
}

QLabel {
    color: #374151;
}

QLabel#lbl_page_title {
    font-size: 20px;
    font-weight: bold;
    color: #111827;
}

QLabel#lbl_section_title {
    font-size: 13px;
    font-weight: bold;
    color: #374151;
    letter-spacing: 0.5px;
}

QLabel#lbl_stat_value {
    font-size: 28px;
    font-weight: bold;
    color: #111827;
}

QLabel#lbl_stat_label {
    font-size: 11px;
    color: #6B7280;
    text-transform: uppercase;
}

QLabel#lbl_stat_name {
    font-size: 11px;
    color: #6B7280;
}

QLabel#lbl_metric {
    font-size: 14px;
    color: #374151;
}

QLabel#lbl_title {
    font-size: 18px;
    font-weight: bold;
    color: #111827;
}

QCheckBox, QRadioButton {
    color: #374151;
    spacing: 6px;
}

QCheckBox::indicator, QRadioButton::indicator {
    border: 1px solid #D1D5DB;
    background-color: #FFFFFF;
}

QCheckBox::indicator:checked {
    background-color: #2563EB;
    border-color: #2563EB;
}

QMenu {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    color: #111827;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item {
    padding: 6px 20px;
    border-radius: 4px;
}

QMenu::item:selected {
    background-color: #EFF6FF;
    color: #2563EB;
}

QMenu::separator {
    height: 1px;
    background-color: #E5E7EB;
    margin: 4px 8px;
}

QMenuBar {
    background-color: #FFFFFF;
    color: #374151;
    border-bottom: 1px solid #E5E7EB;
}

QMenuBar::item:selected {
    background-color: #EFF6FF;
    color: #2563EB;
    border-radius: 4px;
}

QMessageBox {
    background-color: #FFFFFF;
    color: #111827;
}

/* Sidebar */
QWidget#sidebar {
    background-color: #F8F9FA;
    border-right: 1px solid #E5E7EB;
}

QSplitter::handle {
    background-color: #E5E7EB;
}

QSplitter::handle:horizontal {
    width: 1px;
}

QSplitter::handle:vertical {
    height: 1px;
}

QListWidget {
    background-color: #FFFFFF;
    border: 1px solid #E5E7EB;
    border-radius: 6px;
    color: #374151;
}

QListWidget::item:selected {
    background-color: #EFF6FF;
    color: #2563EB;
}

QListWidget::item:hover {
    background-color: #F9FAFB;
}

QToolBar {
    background-color: #F9FAFB;
    border-bottom: 1px solid #E5E7EB;
    spacing: 4px;
}
"""
