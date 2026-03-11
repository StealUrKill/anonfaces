import sys
import os
import shutil
import threading
import subprocess
import json as _json
from datetime import datetime

# Import onnxruntime before PyQt6 to avoid DLL conflicts on Windows.
# When launched via anonfaces.py, providers are cached there before PyQt6 loads.
_cached_providers = None
try:
    import onnxruntime as _ort
    _cached_providers = _ort.get_available_providers() or []
except Exception:
    # Check if anonfaces.py already cached them before PyQt6 loaded
    try:
        import anonfaces.anonfaces as _entry
        _cached_providers = getattr(_entry, '_cached_providers', None)
    except Exception:
        pass

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QLineEdit, QPushButton, QCheckBox,
    QComboBox, QTextEdit, QProgressBar, QFileDialog, QMessageBox,
    QDialog, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPalette, QColor, QFont, QTextCursor

try:
    import anonfaces
    from anonfaces import __version__
except (ModuleNotFoundError, ImportError):
    _pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _pkg_dir not in sys.path:
        sys.path.insert(0, _pkg_dir)
    import __init__ as anonfaces
    from __init__ import __version__


def apply_dark_theme(app):
    """Apply a dark color palette to the QApplication."""
    palette = QPalette()
    dark = QColor(30, 30, 30)
    darker = QColor(20, 20, 20)
    mid = QColor(45, 45, 45)
    white = QColor(210, 210, 210)
    accent = QColor(42, 130, 218)

    palette.setColor(QPalette.ColorRole.Window, dark)
    palette.setColor(QPalette.ColorRole.WindowText, white)
    palette.setColor(QPalette.ColorRole.Base, darker)
    palette.setColor(QPalette.ColorRole.AlternateBase, mid)
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(50, 50, 50))
    palette.setColor(QPalette.ColorRole.ToolTipText, white)
    palette.setColor(QPalette.ColorRole.Text, white)
    palette.setColor(QPalette.ColorRole.Button, mid)
    palette.setColor(QPalette.ColorRole.ButtonText, white)
    palette.setColor(QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
    palette.setColor(QPalette.ColorRole.Link, accent)
    palette.setColor(QPalette.ColorRole.Highlight, accent)
    palette.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(127, 127, 127))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(127, 127, 127))

    app.setPalette(palette)
    app.setStyleSheet("""
        QToolTip {
            color: #d2d2d2; background-color: #3a3a3a;
            border: 1px solid #5a5a5a; padding: 4px;
        }
        QProgressBar {
            border: 1px solid #3a3a3a; border-radius: 3px;
            text-align: center; background-color: #1e1e1e;
        }
        QProgressBar::chunk { background-color: #2a82da; border-radius: 2px; }
        QComboBox { padding: 3px 8px; }
        QComboBox QAbstractItemView {
            background-color: #2d2d2d; selection-background-color: #2a82da;
        }
        QPushButton {
            padding: 5px 12px; border: 1px solid #3a3a3a;
            border-radius: 3px; background-color: #3a3a3a;
        }
        QPushButton:hover { background-color: #4a4a4a; }
        QPushButton:pressed { background-color: #2a82da; }
        QLineEdit {
            padding: 4px; border: 1px solid #3a3a3a; border-radius: 3px;
        }
        QCheckBox::indicator { width: 16px; height: 16px; }
        QTextEdit { border: 1px solid #3a3a3a; border-radius: 3px; }
        QMenu { background-color: #2d2d2d; border: 1px solid #3a3a3a; }
        QMenu::item:selected { background-color: #2a82da; }
    """)


class AnonymizationApp(QMainWindow):
    _log_signal = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Anonfaces Anonymization Tool - v{__version__}")
        self.setFixedSize(950, 830)
        self._center_on_screen()

        self.process = None
        self.process_stopped = False
        self.tooltips_enabled = True
        self._tooltip_store = {}

        central = QWidget()
        self.setCentralWidget(central)
        self.main_layout = QVBoxLayout(central)
        self.main_layout.setSpacing(6)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        self._create_file_selection()
        self._create_options()
        self._create_control_buttons()
        self._create_progress_bar()
        self._create_log_output()

        self._log_signal.connect(self._append_log)

        # Long press timer for input button
        self._select_type = "file"
        self._long_press_timer = QTimer()
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.timeout.connect(self._switch_to_directory)

    # ── helpers ──────────────────────────────────────────────────────

    def _center_on_screen(self):
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)

    def _register_tooltip(self, widget, text):
        widget.setToolTip(text)
        self._tooltip_store[widget] = text

    @staticmethod
    def _get_execution_providers():
        if _cached_providers:
            return _cached_providers
        return ["onnxruntime not available"]

    # ── file selection area ──────────────────────────────────────────

    def _create_file_selection(self):
        file_frame = QWidget()
        layout = QGridLayout(file_frame)
        layout.setContentsMargins(0, 0, 0, 0)

        # Input row
        self.select_button = QPushButton("Input")
        self.select_button.setFixedWidth(90)
        self.select_button.pressed.connect(self._start_long_press)
        self.select_button.released.connect(self._end_long_press)
        self._register_tooltip(self.select_button,
            "Short press to open file, long press to open directory.\n"
            "Automatically clears output if output extension is present.")

        self.input_entry = QLineEdit()
        self.input_entry.setPlaceholderText("File path or 'cam' for webcam...")
        self._register_tooltip(self.input_entry, "To use cam, input cam here.")

        # Output row
        self.output_button = QPushButton("Output")
        self.output_button.setFixedWidth(90)
        self.output_button.clicked.connect(self._browse_output)
        self._register_tooltip(self.output_button,
            "Automatically switches between file and directory from input.\n"
            "If file is selected, only the name is needed as the output\n"
            "will automatically match the extension from the input.")

        self.output_entry = QLineEdit()
        self.output_entry.setPlaceholderText("Output path (defaults to input + _anonymized)...")

        # Help / Toggle buttons
        self.help_button = QPushButton("Help")
        self.help_button.setFixedWidth(80)
        self.help_button.clicked.connect(self._show_help)

        self.toggle_button = QPushButton("Toggle Tooltips")
        self.toggle_button.setFixedWidth(115)
        self.toggle_button.clicked.connect(self._toggle_tooltips)

        layout.addWidget(self.select_button, 0, 0)
        layout.addWidget(self.input_entry, 0, 1)
        layout.addWidget(self.help_button, 0, 2)
        layout.addWidget(self.output_button, 1, 0)
        layout.addWidget(self.output_entry, 1, 1)
        layout.addWidget(self.toggle_button, 1, 2)

        self.main_layout.addWidget(file_frame)

    # ── options grid ─────────────────────────────────────────────────

    def _create_options(self):
        options_frame = QWidget()
        grid = QGridLayout(options_frame)
        grid.setSpacing(6)
        grid.setContentsMargins(5, 5, 5, 5)

        # -- left column: labels + entries/combos (cols 0-1) --
        row = 0

        lbl = QLabel("Detection Threshold:")
        self._register_tooltip(lbl, "Detection threshold (tune this to trade off between\nfalse positive and false negative rate). Default: 0.2")
        grid.addWidget(lbl, row, 0)
        self.thresh_entry = QLineEdit()
        self.thresh_entry.setFixedWidth(140)
        self._register_tooltip(self.thresh_entry, "Detection threshold. Default: 0.2")
        grid.addWidget(self.thresh_entry, row, 1)
        row += 1

        lbl = QLabel("Scale (WxH):")
        self._register_tooltip(lbl, "Downscale images for network inference\n(format: WxH, example: 1280x720).\nClick to set default, double-click to clear.")
        lbl.mousePressEvent = lambda e: self.scale_entry.setText("1280x720") if e.button() == Qt.MouseButton.LeftButton else None
        lbl.mouseDoubleClickEvent = lambda e: self.scale_entry.clear()
        grid.addWidget(lbl, row, 0)
        self.scale_entry = QLineEdit()
        self.scale_entry.setFixedWidth(140)
        self._register_tooltip(self.scale_entry, "Downscale images for network inference (format: WxH).")
        grid.addWidget(self.scale_entry, row, 1)
        row += 1

        lbl = QLabel("Replace With:")
        self._register_tooltip(lbl, 'Anonymization filter mode.\n"blur", "solid", "none", "img", "mosaic". Default: "blur".')
        grid.addWidget(lbl, row, 0)
        self.replacewith_combo = QComboBox()
        self.replacewith_combo.addItems(["", "blur", "solid", "none", "img", "mosaic"])
        self.replacewith_combo.setFixedWidth(140)
        self._register_tooltip(self.replacewith_combo, 'Anonymization filter mode. Default: "blur".')
        grid.addWidget(self.replacewith_combo, row, 1)
        row += 1

        self.replaceimg_button = QPushButton("Replace Image")
        self.replaceimg_button.clicked.connect(self._browse_replaceimg)
        self._register_tooltip(self.replaceimg_button, "Anonymization image for face regions.\nRequires replacewith img option.")
        grid.addWidget(self.replaceimg_button, row, 0)
        self.replaceimg_entry = QLineEdit()
        self._register_tooltip(self.replaceimg_entry, "Anonymization image for face regions.\nRequires replacewith img option.")
        grid.addWidget(self.replaceimg_entry, row, 1)
        row += 1

        lbl = QLabel("Mosaic Size:")
        self._register_tooltip(lbl, "Setting the mosaic size.\nRequires replacewith mosaic. Default: 20")
        grid.addWidget(lbl, row, 0)
        self.mosaicsize_entry = QLineEdit()
        self.mosaicsize_entry.setFixedWidth(140)
        self._register_tooltip(self.mosaicsize_entry, "Mosaic size. Default: 20")
        grid.addWidget(self.mosaicsize_entry, row, 1)
        row += 1

        lbl = QLabel("Mask Scale:")
        self._register_tooltip(lbl, "Scale factor for face masks.\nDefault: 1.3.")
        grid.addWidget(lbl, row, 0)
        self.maskscale_entry = QLineEdit()
        self.maskscale_entry.setFixedWidth(140)
        self._register_tooltip(self.maskscale_entry, "Mask scale factor. Default: 1.3.")
        grid.addWidget(self.maskscale_entry, row, 1)
        row += 1

        lbl = QLabel("Face Recog. Threshold:")
        self._register_tooltip(lbl, "Face recognition cosine similarity threshold\n(higher = stricter). Default: 0.45")
        grid.addWidget(lbl, row, 0)
        self.fr_thresh_entry = QLineEdit()
        self.fr_thresh_entry.setFixedWidth(140)
        self._register_tooltip(self.fr_thresh_entry, "Face recognition threshold. Default: 0.45")
        grid.addWidget(self.fr_thresh_entry, row, 1)
        row += 1

        lbl = QLabel("Backend:")
        self._register_tooltip(lbl, "Backend for ONNX model execution.\nDefault: auto (prefer onnxrt if available)")
        grid.addWidget(lbl, row, 0)
        self.backend_combo = QComboBox()
        self.backend_combo.addItems(["", "auto", "onnxrt", "opencv"])
        self.backend_combo.setFixedWidth(140)
        self._register_tooltip(self.backend_combo, "Backend for ONNX model execution. Default: auto")
        grid.addWidget(self.backend_combo, row, 1)
        row += 1

        lbl = QLabel("Execution Provider:")
        self._register_tooltip(lbl, "Override onnxrt execution provider.\nSee https://onnxruntime.ai/docs/execution-providers/")
        grid.addWidget(lbl, row, 0)
        self.ep_combo = QComboBox()
        self.ep_combo.addItem("")
        self.ep_combo.addItems(self._get_execution_providers())
        self.ep_combo.setMinimumWidth(220)
        self._register_tooltip(self.ep_combo, "Override onnxrt execution provider.\nOnly used if backend is onnxrt.")
        grid.addWidget(self.ep_combo, row, 1)
        row += 1

        lbl = QLabel("Video Codec:")
        self._register_tooltip(lbl, "Video encoder.\nmpeg4 (MPEG-4 Part 2) — fast, widely compatible (default).\n"
            "libx264 (H.264) — better compression.\nlibsvtav1 (AV1) — royalty-free, best compression, slower.\n"
            "libvpx-vp9 (VP9) — royalty-free, broadly supported.")
        grid.addWidget(lbl, row, 0)
        self.vcodec_combo = QComboBox()
        self.vcodec_combo.addItems(["mpeg4", "libx264", "libsvtav1", "libvpx-vp9"])
        self.vcodec_combo.setFixedWidth(140)
        self._register_tooltip(self.vcodec_combo, "Video encoder. Default: mpeg4")
        grid.addWidget(self.vcodec_combo, row, 1)
        row += 1

        lbl = QLabel("Audio Codec:")
        self._register_tooltip(lbl, "Audio encoder.\naac (default), libmp3lame (MP3),\nlibopus (royalty-free, excellent quality).")
        grid.addWidget(lbl, row, 0)
        self.acodec_combo = QComboBox()
        self.acodec_combo.addItems(["aac", "libmp3lame", "libopus"])
        self.acodec_combo.setFixedWidth(140)
        self._register_tooltip(self.acodec_combo, "Audio encoder. Default: aac")
        grid.addWidget(self.acodec_combo, row, 1)
        row += 1

        lbl = QLabel("FFmpeg Config (JSON):")
        self._register_tooltip(lbl, 'Additional FFMPEG config in JSON notation.\nExample: {"fps": 10, "bitrate": "1000k"}\nVideo/audio codecs are set by the dropdowns above.')
        grid.addWidget(lbl, row, 0)
        self.ffmpeg_config_entry = QLineEdit()
        self._register_tooltip(self.ffmpeg_config_entry, 'Additional FFMPEG config in JSON.\nExample: {"fps": 10, "bitrate": "1000k"}')
        grid.addWidget(self.ffmpeg_config_entry, row, 1)

        # -- right column: checkboxes (col 3) --
        chk_row = 0

        self.preview_check = QCheckBox("Enable Preview")
        self._register_tooltip(self.preview_check, "Enable live preview GUI (can decrease performance).")
        grid.addWidget(self.preview_check, chk_row, 3)
        chk_row += 1

        self.boxes_check = QCheckBox("Use Boxes Instead of Ellipse")
        self._register_tooltip(self.boxes_check, "Use boxes instead of ellipse masks.")
        grid.addWidget(self.boxes_check, chk_row, 3)
        chk_row += 1

        self.draw_scores_check = QCheckBox("Draw Detection Scores")
        self._register_tooltip(self.draw_scores_check, "Draw detection scores onto outputs and previews.")
        grid.addWidget(self.draw_scores_check, chk_row, 3)
        chk_row += 1

        self.face_recog_check = QCheckBox("Enable Face Recognition")
        self._register_tooltip(self.face_recog_check, "Enable face recognition to not blur\nfaces in Face GUI Database.")
        grid.addWidget(self.face_recog_check, chk_row, 3)
        chk_row += 1

        self.fr_name_check = QCheckBox("Enable Face Recog. With Names")
        self._register_tooltip(self.fr_name_check, "Enable face recognition names from\nimage name in Face GUI Database.")
        grid.addWidget(self.fr_name_check, chk_row, 3)
        chk_row += 1

        self.distort_audio_check = QCheckBox("Distort Audio")
        self._register_tooltip(self.distort_audio_check, "Enable audio distortion for the output video.\nApplies pitch shift and gain effects.")
        grid.addWidget(self.distort_audio_check, chk_row, 3)
        chk_row += 1

        self.keep_audio_check = QCheckBox("Keep Audio")
        self._register_tooltip(self.keep_audio_check, "Keep audio from video source file\n(only applies to videos).")
        grid.addWidget(self.keep_audio_check, chk_row, 3)
        chk_row += 1

        self.copy_acodec_check = QCheckBox("Copy Audio Codec")
        self._register_tooltip(self.copy_acodec_check, "Keep the audio codec from video source file.")
        grid.addWidget(self.copy_acodec_check, chk_row, 3)
        chk_row += 1

        self.info_check = QCheckBox("Show Info")
        self._register_tooltip(self.info_check, "Shows file input/output location and ffmpeg command.")
        grid.addWidget(self.info_check, chk_row, 3)
        chk_row += 1

        self.keep_metadata_check = QCheckBox("Keep Metadata")
        self._register_tooltip(self.keep_metadata_check, "Keep metadata of the original image. Default: False.")
        grid.addWidget(self.keep_metadata_check, chk_row, 3)

        # spacer column between left and right sides
        grid.setColumnStretch(2, 1)

        self.main_layout.addWidget(options_frame)

    # ── control buttons ──────────────────────────────────────────────

    def _create_control_buttons(self):
        btn_frame = QWidget()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        self.start_button = QPushButton("Start Anonymization")
        self.start_button.clicked.connect(self._start_anonymization)
        btn_layout.addWidget(self.start_button)

        self.stop_button = QPushButton("Stop Anonymization")
        self.stop_button.clicked.connect(self._stop_anonymization)
        btn_layout.addWidget(self.stop_button)

        self.facedb_button = QPushButton("Face Database GUI")
        self.facedb_button.clicked.connect(self._facedbgui_launch)
        btn_layout.addWidget(self.facedb_button)

        self.clear_button = QPushButton("Clear All Options")
        self.clear_button.clicked.connect(self._clear_options)
        btn_layout.addWidget(self.clear_button)

        self.convert_button = QPushButton("Convert Audio")
        self.convert_button.clicked.connect(self._convert_audio_launch)
        self._register_tooltip(self.convert_button, "Convert video using the selected video and audio codecs.")
        btn_layout.addWidget(self.convert_button)

        self.main_layout.addWidget(btn_frame)

    # ── progress bar ─────────────────────────────────────────────────

    def _create_progress_bar(self):
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        self.main_layout.addWidget(self.progress)

    # ── log output ───────────────────────────────────────────────────

    def _create_log_output(self):
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMinimumHeight(200)

        self.log_text.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.log_text.customContextMenuRequested.connect(self._show_log_menu)

        self.main_layout.addWidget(self.log_text, stretch=1)

    # ── log helpers ──────────────────────────────────────────────────

    def log_message(self, message):
        self._log_signal.emit(message)

    def _append_log(self, message):
        self.log_text.append(message)
        self.log_text.moveCursor(QTextCursor.MoveOperation.End)

    def _clear_log(self):
        self.log_text.clear()

    def _show_log_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Copy All", self._copy_log)
        menu.addAction("Save Log...", self._save_log)
        menu.exec(self.log_text.mapToGlobal(pos))

    def _copy_log(self):
        QApplication.clipboard().setText(self.log_text.toPlainText())

    def _save_log(self):
        app_name = "Anonfaces"
        current_date = datetime.now().strftime("%Y-%m-%d")
        default_name = f"{app_name}_v{__version__}_{current_date}.txt"

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Log", default_name, "Text files (*.txt)")
        if path:
            with open(path, 'w') as f:
                f.write(self.log_text.toPlainText())

    # ── progress helpers ─────────────────────────────────────────────

    def _start_progress(self):
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)

    def _stop_progress(self):
        self.progress.setVisible(False)

    # ── tooltip toggle ───────────────────────────────────────────────

    def _toggle_tooltips(self):
        self.tooltips_enabled = not self.tooltips_enabled
        for widget, text in self._tooltip_store.items():
            widget.setToolTip(text if self.tooltips_enabled else "")
        self.toggle_button.setText(
            "Disable Tooltips" if self.tooltips_enabled else "Enable Tooltips")

    # ── long press input button ──────────────────────────────────────

    def _start_long_press(self):
        self._long_press_timer.start(300)

    def _end_long_press(self):
        if self._long_press_timer.isActive():
            self._long_press_timer.stop()
        self._select_path()

    def _switch_to_directory(self):
        self._select_type = "directory"
        self.select_button.setText("Directory")

    # ── file/directory selection ─────────────────────────────────────

    def _select_path(self):
        output_path = self.output_entry.text()
        if self._select_type == "file":
            input_path, _ = QFileDialog.getOpenFileName(self, "Select Input File")
            if input_path:
                self.input_entry.setText(input_path)
                if os.path.isdir(output_path):
                    QMessageBox.information(self, "File Selected",
                        "Input file detected!\n\nClearing output due to output directory set.")
                    self.output_entry.clear()
        else:
            input_path = QFileDialog.getExistingDirectory(self, "Select Input Directory")
            if input_path:
                self.input_entry.setText(input_path)
                output_path = self.output_entry.text()
                if output_path and os.path.splitext(output_path)[1]:
                    QMessageBox.information(self, "Directory Selected",
                        "Output extension detected!\n\nClearing output due to input directory set.")
                    self.output_entry.clear()

        self._select_type = "file"
        self.select_button.setText("Input")

    def _browse_output(self):
        input_path = self.input_entry.text()
        if not input_path:
            return
        if os.path.isdir(input_path):
            QMessageBox.information(self, "Directory Selected",
                "Input directory detected!\n\nPlease choose an output directory.")
            output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
            if output_dir:
                self.output_entry.setText(output_dir)
        else:
            input_ext = os.path.splitext(input_path)[1]
            output_path, _ = QFileDialog.getSaveFileName(self, "Select Output File")
            if output_path:
                if not output_path.endswith(input_ext):
                    output_path += input_ext
                self.output_entry.setText(output_path)

    def _browse_replaceimg(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Replace Image",
            filter="Image files (*.jpg *.jpeg *.png *.bmp)")
        if path:
            self.replaceimg_entry.setText(path)

    # ── face database GUI launch ─────────────────────────────────────

    def _facedbgui_launch(self):
        cmd = [sys.executable, "-m", "anonfaces", "dbgui"]
        subprocess.run(cmd)

    # ── help window ──────────────────────────────────────────────────

    def _show_help(self):
        help_text = """
    Anonfaces Anonymization Tool - Info:

    1. Input:
       File path(s) or camera device name. It is possible to pass multiple paths by separating them
       by spaces or by using shell expansion (e.g. `$ anonfaces vids/*.mp4`). Alternatively, you
       can pass a directory as input, and all files in the directory will be used. If a camera is
       installed, start a live demo with `$ anonfaces cam` (shortcut for `$ anonfaces -p '<video0>'`).

       INFO:
       Short press to open file, long press to open directory.
       Automatically clears output if an output extension is present when input directory is set.
       Automatically clears output if an output directory is present when input file is set.

    2. Output:
       Output file name. Defaults to input path + postfix "_anonymized".

       INFO:
       Automatically switches between file and directory from input.
       If a file is selected from the input, only the name of the file is needed as the output will
       automatically match the extension from the input file.

    3. Threshold:
       Detection threshold. Default is 0.2.

    4. Scale:
       Downscale images for inference. Format WxH (e.g., scale 1280x720).

    5. Preview:
       Enable live preview GUI (may reduce performance).

    6. Boxes:
       Use boxes instead of ellipse masks.

    7. Detection Scores:
       Draw detection scores onto outputs.

    8. Mask Scale:
       Scale factor for face masks. Default: 1.3.

    9. Replace With:
       Face anonymization filter mode. Options: 'blur', 'solid', 'none', 'img', 'mosaic'. Default: 'blur'.

    10. Replace Image:
        Custom image for face replacement (requires replacewith img).

    11. Mosaic Size:
        Mosaic size for face replacement. Default: 20.

    12. Face Recognition:
        Face Recognition: Enable face recognition to not blur faces in Face GUI Database.
        Face Recognition Name: Enable face recognition names from image name in Face GUI Database.
        Face Recognition GUI: Launch face database GUI.
        Face Recognition Threshold: Set face recognition cosine similarity threshold
        (higher = stricter). Default: 0.45.

    13. Audio:
        Distort Audio: Enable audio distortion in output video.
            This applies --keep-audio but will not work with --copy-acodec.
        Keep Audio: Keep audio from the video source.
        Copy Audio Codec: Keep the audio codec from the source.

    14. Video Codec:
        Select video encoder. mpeg4 (MPEG-4 Part 2, fast, widely compatible, default),
        libx264 (H.264, better compression), libsvtav1 (AV1, royalty-free, best compression, slower),
        libvpx-vp9 (VP9, royalty-free, broadly supported). Default: mpeg4.

    15. Audio Codec:
        Select audio encoder for --keep-audio. aac (default, widely compatible),
        libmp3lame (MP3), libopus (royalty-free, excellent quality). Default: aac.

    16. FFmpeg Config:
        Additional FFmpeg encoding options in JSON notation.
        Example: {"fps": 10, "bitrate": "1000k"}
        See https://ffmpeg.org/ffmpeg-codecs.html for more options

    17. Backend:
        Select ONNX model execution backend. Options: 'auto', 'onnxrt', 'opencv'. Default: 'auto'.

    18. Execution Provider:
        Override the ONNX runtime execution provider. Only used if backend is onnxrt.
        If not specified, the presumably fastest available one will be automatically selected.
        See - https://onnxruntime.ai/docs/execution-providers/

    19. Additional Options:
        Show Info: Show file input/output locations and ffmpeg command.
        Keep Metadata: Keep metadata from the original image. Default: False.
        """

        dlg = QDialog(self)
        dlg.setWindowTitle("Help")
        dlg.setFixedSize(950, 750)

        layout = QVBoxLayout(dlg)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(QFont("Consolas", 10))
        text_edit.setPlainText(help_text)
        layout.addWidget(text_edit)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dlg.close)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Center on screen
        screen = QApplication.primaryScreen().geometry()
        dlg.move((screen.width() - dlg.width()) // 2,
                 (screen.height() - dlg.height()) // 2)
        dlg.exec()

    # ── clear all options ────────────────────────────────────────────

    def _clear_options(self):
        self.input_entry.clear()
        self.output_entry.clear()
        self.replaceimg_entry.clear()
        self.thresh_entry.clear()
        self.scale_entry.clear()
        self.mosaicsize_entry.clear()
        self.maskscale_entry.clear()
        self.fr_thresh_entry.clear()
        self.ffmpeg_config_entry.clear()

        self.preview_check.setChecked(False)
        self.boxes_check.setChecked(False)
        self.draw_scores_check.setChecked(False)
        self.face_recog_check.setChecked(False)
        self.fr_name_check.setChecked(False)
        self.distort_audio_check.setChecked(False)
        self.keep_audio_check.setChecked(False)
        self.copy_acodec_check.setChecked(False)
        self.info_check.setChecked(False)
        self.keep_metadata_check.setChecked(False)

        self.replacewith_combo.setCurrentIndex(0)
        self.backend_combo.setCurrentIndex(0)
        self.ep_combo.setCurrentIndex(0)
        self.vcodec_combo.setCurrentText("mpeg4")
        self.acodec_combo.setCurrentText("aac")

    # ── convert audio ────────────────────────────────────────────────

    def _convert_audio_launch(self):
        self._clear_log()
        ffmpeg_path = shutil.which('ffmpeg')
        if not ffmpeg_path:
            self.log_message("FFmpeg executable not found. Ensure ffmpeg is installed and on your system PATH.")
            return

        input_path = self.input_entry.text()
        if not input_path:
            self.log_message("Please select an input file before converting audio.")
            return

        input_dir, input_filename = os.path.split(input_path)
        input_name, input_ext = os.path.splitext(input_filename)
        output_path = os.path.join(input_dir, f"{input_name}_converted{input_ext}")

        self._start_progress()
        vcodec = self.vcodec_combo.currentText() or "mpeg4"
        acodec = self.acodec_combo.currentText() or "aac"
        cmd = [
            ffmpeg_path, "-y", "-i", input_path,
            "-c:v", vcodec, "-crf", "23",
            "-c:a", acodec, "-q:a", "100",
            "-sn", "-vf", "yadif", output_path
        ]
        self.log_message(f"Running FFmpeg command: {' '.join(cmd)}")

        def run_ffmpeg():
            try:
                self.process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                for line in iter(self.process.stderr.readline, ""):
                    self.log_message(line.strip())
                self.process.wait()
                if self.process.returncode == 0:
                    self.log_message(f"Audio conversion completed successfully. Output file: {output_path}")
                else:
                    self.log_message(f"Error in audio conversion: {self.process.stderr.read()}")
            except Exception as e:
                self.log_message(f"An error occurred while running FFmpeg: {e}")
            finally:
                self._stop_progress()
                self.process = None

        threading.Thread(target=run_ffmpeg, daemon=True).start()

    # ── start/stop anonymization ─────────────────────────────────────

    def _start_anonymization(self):
        self._clear_log()
        options = self._collect_options()
        threading.Thread(target=self._run_anonymization, args=(options,)).start()

    def _stop_anonymization(self):
        if self.process is not None and self.process.poll() is None:
            try:
                self.log_message("Attempting to stop the process...")
                self.process_stopped = True
                self.process.terminate()
                self.process.wait()
            except Exception as e:
                self.log_message(f"Error stopping the process: {e}")
            finally:
                self.process = None
                self._stop_progress()
                self.log_message("Anonymization stopped.")

    # ── collect options ──────────────────────────────────────────────

    def _collect_options(self):
        return {
            "input": self.input_entry.text(),
            "output": self.output_entry.text(),
            "thresh": self.thresh_entry.text(),
            "scale": self.scale_entry.text(),
            "replacewith": self.replacewith_combo.currentText(),
            "replaceimg": self.replaceimg_entry.text(),
            "mosaicsize": self.mosaicsize_entry.text(),
            "mask_scale": self.maskscale_entry.text(),
            "face_recog": self.face_recog_check.isChecked(),
            "fr_name": self.fr_name_check.isChecked(),
            "distort_audio": self.distort_audio_check.isChecked(),
            "keep_audio": self.keep_audio_check.isChecked(),
            "copy_acodec": self.copy_acodec_check.isChecked(),
            "fr_thresh": self.fr_thresh_entry.text(),
            "backend": self.backend_combo.currentText(),
            "execution_provider": self.ep_combo.currentText(),
            "vcodec": self.vcodec_combo.currentText(),
            "acodec": self.acodec_combo.currentText(),
            "ffmpeg_config": self.ffmpeg_config_entry.text(),
            "info": self.info_check.isChecked(),
            "keep_metadata": self.keep_metadata_check.isChecked(),
            "preview": self.preview_check.isChecked(),
            "boxes": self.boxes_check.isChecked(),
            "draw_scores": self.draw_scores_check.isChecked(),
        }

    # ── run anonymization subprocess ─────────────────────────────────

    def _run_anonymization(self, options):
        self.log_message("Starting anonymization...")
        self._start_progress()
        self.process_stopped = False

        args = []
        if options["input"]:
            args.append(options["input"])
        if options["output"]:
            args.extend(["--output", options["output"]])
        if options["thresh"]:
            args.extend(["--thresh", options["thresh"]])
        if options["scale"]:
            args.extend(["--scale", options["scale"]])
        if options["replacewith"]:
            args.extend(["--replacewith", options["replacewith"]])
        if options["replaceimg"]:
            args.extend(["--replaceimg", options["replaceimg"]])
        if options["mosaicsize"]:
            args.extend(["--mosaicsize", options["mosaicsize"]])
        if options["mask_scale"]:
            args.extend(["--mask-scale", options["mask_scale"]])
        if options["face_recog"]:
            args.append("--face-recog")
        if options["fr_name"]:
            args.append("--frn")
        if options["distort_audio"]:
            args.append("--distort-audio")
        if options["keep_audio"]:
            args.append("--keep-audio")
        if options["copy_acodec"]:
            args.append("--copy-acodec")
        if options["fr_thresh"]:
            args.extend(["--fr-thresh", options["fr_thresh"]])
        if options["backend"]:
            args.extend(["--backend", options["backend"]])
        if options["execution_provider"]:
            args.extend(["--execution-provider", options["execution_provider"]])

        # Build ffmpeg-config JSON merging codec dropdowns + manual entry
        ffmpeg_cfg = {}
        if options["ffmpeg_config"]:
            try:
                ffmpeg_cfg = _json.loads(options["ffmpeg_config"])
            except _json.JSONDecodeError:
                pass
        if options.get("vcodec"):
            ffmpeg_cfg["codec"] = options["vcodec"]
        if options.get("acodec"):
            ffmpeg_cfg["acodec"] = options["acodec"]
        if ffmpeg_cfg:
            args.extend(["--ffmpeg-config", _json.dumps(ffmpeg_cfg)])

        if options["info"]:
            args.append("--info")
        if options["keep_metadata"]:
            args.append("--keep-metadata")
        if options["preview"]:
            args.append("--preview")
        if options["boxes"]:
            args.append("--boxes")
        if options["draw_scores"]:
            args.append("--draw-scores")

        pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cmd = [sys.executable, "-m", "anonfaces"] + args

        try:
            self.process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, cwd=os.path.dirname(pkg_dir))

            def read_stdout():
                for line in iter(self.process.stdout.readline, ''):
                    self.log_message(line.strip())

            def read_stderr():
                for line in iter(self.process.stderr.readline, ''):
                    self.log_message(line.strip())

            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()

            self.process.wait()

            if not self.process_stopped:
                self.log_message("Anonymization completed successfully.")
        except Exception as e:
            self.log_message(f"An error occurred: {e}")
        finally:
            self._stop_progress()
            self.process = None


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    apply_dark_theme(app)
    window = AnonymizationApp()
    window.show()
    sys.exit(app.exec())
