#CREATING FOR NEW ADDITIONS/GUI
import argparse
import sys

# Import onnxruntime before PyQt6 to avoid DLL conflicts on Windows
_cached_providers = None
try:
    import onnxruntime as _ort
    _cached_providers = _ort.get_available_providers() or []
except Exception:
    pass

from PyQt6.QtWidgets import QApplication

try:
    from anonfaces.gui.dbfacegui import FaceDatabaseApp
    from anonfaces.gui.gui import AnonymizationApp, apply_dark_theme
    from anonfaces.main.main import main as main_script
    from anonfaces.helper.cleanup import remove_database
except (ModuleNotFoundError, ImportError):
    # Standalone mode - running directly from the package directory
    from gui.dbfacegui import FaceDatabaseApp
    from gui.gui import AnonymizationApp, apply_dark_theme
    from main.main import main as main_script
    from helper.cleanup import remove_database

def run_anonfaces_gui():
    app = QApplication.instance() or QApplication(sys.argv)
    apply_dark_theme(app)
    window = AnonymizationApp()
    window.show()
    app.exec()

def run_face_database_gui():
    app = QApplication.instance() or QApplication(sys.argv)
    apply_dark_theme(app)
    window = FaceDatabaseApp()
    window.show()
    app.exec()


def run_face_dbcleanup():
    remove_database()


def main():
    if len(sys.argv) == 1:
        main_script()  # no args so run the main script
        return

    # check args for anything listed
    mode = sys.argv[1]
    if mode == 'gui':
        run_anonfaces_gui()
    elif mode == 'dbgui':
        run_face_database_gui()
    elif mode == 'cleanup':
        run_face_dbcleanup()
    else:
        # pass anything else not from above
        main_script()


if __name__ == '__main__':
    main()
