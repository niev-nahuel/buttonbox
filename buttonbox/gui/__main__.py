import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPalette, QColor
from .window import MainWindow


def _dark_palette(app: QApplication) -> None:
    p = QPalette()
    c = {
        "Window":          "#2b2b2b",
        "WindowText":      "#bbbbbb",
        "Base":            "#1e1e1e",
        "AlternateBase":   "#353535",
        "Text":            "#bbbbbb",
        "Button":          "#353535",
        "ButtonText":      "#bbbbbb",
        "Highlight":       "#2a82da",
        "HighlightedText": "#000000",
        "ToolTipBase":     "#2b2b2b",
        "ToolTipText":     "#bbbbbb",
    }
    for role_name, hex_color in c.items():
        p.setColor(getattr(QPalette.ColorRole, role_name), QColor(hex_color))
    app.setPalette(p)


def main() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setStyle("Fusion")
    _dark_palette(app)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
