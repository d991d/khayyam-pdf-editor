"""
main.py — Entry point for Khayyam PDF Editor (Windows Edition).

Run:
    python main.py [optional_file.pdf]

Package as .exe (Windows):
    pip install pyinstaller
    pyinstaller --onefile --windowed --name "Khayyam PDF Editor" main.py
"""

import sys
import os

# When running as a PyInstaller bundle, add the bundle dir to path
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPalette, QColor


def _light_palette() -> QPalette:
    """Explicit light palette — overrides Windows dark mode."""
    p = QPalette()
    white     = QColor(255, 255, 255)
    light     = QColor(245, 245, 245)
    mid       = QColor(235, 235, 235)
    btn       = QColor(240, 240, 240)
    text      = QColor(20, 20, 20)
    disabled  = QColor(160, 160, 160)
    accent    = QColor(0, 120, 212)

    p.setColor(QPalette.ColorRole.Window,           light)
    p.setColor(QPalette.ColorRole.WindowText,       text)
    p.setColor(QPalette.ColorRole.Base,             white)
    p.setColor(QPalette.ColorRole.AlternateBase,    mid)
    p.setColor(QPalette.ColorRole.ToolTipBase,      QColor(255, 255, 220))
    p.setColor(QPalette.ColorRole.ToolTipText,      text)
    p.setColor(QPalette.ColorRole.Text,             text)
    p.setColor(QPalette.ColorRole.Button,           btn)
    p.setColor(QPalette.ColorRole.ButtonText,       text)
    p.setColor(QPalette.ColorRole.BrightText,       QColor(255, 0, 0))
    p.setColor(QPalette.ColorRole.Link,             accent)
    p.setColor(QPalette.ColorRole.Highlight,        accent)
    p.setColor(QPalette.ColorRole.HighlightedText,  white)
    p.setColor(QPalette.ColorRole.Mid,              QColor(200, 200, 200))
    p.setColor(QPalette.ColorRole.Dark,             QColor(180, 180, 180))
    p.setColor(QPalette.ColorRole.Shadow,           QColor(100, 100, 100))

    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled)

    return p


def main() -> None:
    # High-DPI policy must be set before QApplication
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Khayyam PDF Editor")
    app.setOrganizationName("d991d")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")

    # Force light mode regardless of Windows dark mode setting
    app.setPalette(_light_palette())

    # Segoe UI is Windows' native UI font; fall back gracefully on other platforms
    font = QFont("Segoe UI", 9)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # Import after QApplication is created (avoids import-time Qt warnings)
    from src.main_window import MainWindow

    window = MainWindow()
    window.show()

    # Open a file passed on the command line
    if len(sys.argv) > 1:
        path = sys.argv[1]
        if os.path.isfile(path) and path.lower().endswith(".pdf"):
            window.open_pdf(path)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
