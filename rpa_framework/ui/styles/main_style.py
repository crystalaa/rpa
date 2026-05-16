ROOT_STYLE = """
    QMainWindow, QWidget {
        font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
        font-size: 10pt
    }
"""

SEARCH_STYLE = """
QLineEdit {
    font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
    border: 1px solid #e0e0e0;
    border-radius: 2px;
    background: #fcf8f6;
    padding-left: 10px;
    padding-right: 40px;
    margin-left:2px;
    margin-right:2px;
    height: 28px;
    outline: none;
}
QLineEdit:focus {
    border: none;
    border-bottom: 2px solid #1a76c6;
    outline: none;
}
"""

SEARCH_BTN_STYLE = """
    QToolButton {
        border: none;
        background: #fcf8f6;
        border-radius: 5px;
        width: 28px;
        height: 22px;
    }
    QToolButton:hover {
        background: #e0e0e0;
    }
"""

SIDEBAR_STYLE = """

    QListWidget {
        background-color: #f3f3f3;
        color: black;
        border: none;
        border-right: 1px solid white;
        padding: 10px;
        outline: none;
    }
    QListWidget::item {
        height: 50px;
        padding: 0px 10px;
        margin: 0px;
        border-radius: 0px;
        color: black;
    }
    QListWidget::item:selected {
        background-color: #e8e8e8;
        color: black;
        border: none;
        outline: none;
    }
    QListWidget::item:hover {
        background-color: #e8e8e8;
        border-radius: 0px;
        margin: 0px;
        color: black;
    }
    QListWidget:focus {
        outline: none;
    }
"""

CONTENT_STYLE = """
    QWidget {
        background-color: #f3f3f3;
        border: none;
        border-radius: 5px;
    }
"""

TOP_PANEL_STYLE = """
    QWidget {
    }
"""

TAB_WIDGET_STYLE = """
QTabWidget::pane {
padding:0
margin:0
}
QTabBar::tab {
}
"""

START_BUTTON_STYLE = """
    QPushButton {
        background-color: #27ae60;
        color: white;
        border-radius: 5px;
        font-weight: bold;
        padding:10px 20px;
    }
    QPushButton:disabled {
        background-color: #e0e0e0;
        color: #888888;
    }
    QPushButton:hover {
        background-color: #2ecc71;
    }
"""

STOP_BUTTON_STYLE = """
    QPushButton {
        background-color: #e74c3c;
        color: white;
        border-radius: 5px;
        font-weight: bold;
        padding:10px 20px;
    }
    QPushButton:hover {
        background-color: #c0392b;
    }
"""

OPEN_BUTTON_STYLE = """
    QPushButton {
        background-color: #3498db;
        color: white;
        border-radius: 2px;
        padding: 5px
    }
    QPushButton:hover {
        background-color: #2980b9;
    }
"""

TEXT_EDIT_STYLE = """
    QTextEdit {
        border: none;
        background-color: white;
        font-size: 10pt;
    }
"""

TOGGLE_SWITCH_STYLE = """
    ToggleSwitch {
        border-radius: 10px;
        background-color: #bdc3c7;
    }
    ToggleSwitch::checked {
        background-color: #27ae60;
    }
    ToggleSwitch::handle {
        background-color: white;
        border-radius: 8px;
        width: 16px;
        height: 16px;
        margin: 2px;
    }
    ToggleSwitch::checked {
        background-color: #27ae60;
    }
"""

INSTRUCTION_STYLE = """
    QTextEdit {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0px;
        padding: 8px;
        font-size: 12pt;
    }
"""

LOG_EDIT_STYLE = """
    QTextEdit {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0px;
        padding: 8px;
        font-size: 12pt;
    }
"""