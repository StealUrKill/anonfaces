import sys
import os
import sqlite3

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QInputDialog,
    QScrollArea, QGridLayout, QDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap

try:
    from anonfaces.gui.gui import apply_dark_theme
except (ModuleNotFoundError, ImportError):
    _pkg_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _pkg_dir not in sys.path:
        sys.path.insert(0, _pkg_dir)
    from gui.gui import apply_dark_theme


def initialize_database():
    database_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'database',
        'face_db.sqlite'
    )
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS persons (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS images (
        id INTEGER PRIMARY KEY,
        person_id INTEGER,
        image BLOB,
        FOREIGN KEY (person_id) REFERENCES persons(id)
    )
    ''')
    conn.commit()
    return conn, cursor


class FaceDatabaseApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Face Database Manager")
        self.setMinimumSize(600, 400)
        self.conn, self.cursor = initialize_database()

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Top buttons
        btn_frame = QWidget()
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(0, 0, 0, 0)

        single_btn = QPushButton("Single Image Enroll")
        single_btn.clicked.connect(self._open_file_dialog)
        btn_layout.addWidget(single_btn)

        batch_btn = QPushButton("Batch Image Enroll")
        batch_btn.clicked.connect(self._batch_enroll_dialog)
        btn_layout.addWidget(batch_btn)

        btn_layout.addStretch()

        clear_btn = QPushButton("Clear Database")
        clear_btn.clicked.connect(self._delete_all_dialog)
        btn_layout.addWidget(clear_btn)

        main_layout.addWidget(btn_frame)

        # Scrollable image area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.images_widget = QWidget()
        self.images_layout = QVBoxLayout(self.images_widget)
        self.images_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.images_widget)
        main_layout.addWidget(self.scroll_area, stretch=1)

        self._load_images()
        self._fit_to_content()

    def _fit_to_content(self):
        screen = QApplication.primaryScreen().geometry()
        max_w = int(screen.width() * 0.98)
        max_h = int(screen.height() * 0.8)
        self.adjustSize()
        w = min(self.sizeHint().width() + 50, max_w)
        h = min(self.sizeHint().height() + 60, max_h)
        w = max(w, 600)
        h = max(h, 400)
        self.resize(w, h)
        self.move((screen.width() - w) // 2, (screen.height() - h) // 2)

    def _pixmap_from_blob(self, blob_data, max_w=100, max_h=200):
        pixmap = QPixmap()
        pixmap.loadFromData(blob_data)
        if not pixmap.isNull():
            pixmap = pixmap.scaled(max_w, max_h,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
        return pixmap

    # ── enroll ───────────────────────────────────────────────────────

    def _open_file_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select an Image",
            filter="Image files (*.jpg *.jpeg *.png)")
        if path:
            self._process_image(path)

    def _batch_enroll_dialog(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Images",
            filter="Image files (*.jpg *.jpeg *.png)")
        if paths:
            name, ok = QInputDialog.getText(self, "Input", "Enter the name for these faces:")
            if ok and name:
                for path in paths:
                    self._process_image(path, name)
            elif ok:
                QMessageBox.warning(self, "No Name", "No name provided, skipping batch enroll.")

    def _process_image(self, file_path, name=None):
        if name is None:
            name, ok = QInputDialog.getText(self, "Input", "Enter the name for this face:")
            if not ok or not name:
                QMessageBox.warning(self, "No Name", "No name provided, skipping.")
                return

        self.cursor.execute('SELECT id FROM persons WHERE name = ?', (name,))
        person_row = self.cursor.fetchone()
        if person_row:
            person_id = person_row[0]
            self.cursor.execute('SELECT COUNT(*) FROM images WHERE person_id = ?', (person_id,))
            if self.cursor.fetchone()[0] >= 5:
                QMessageBox.warning(self, "Limit Reached",
                    "This person already has 5 images. No more can be added.")
                return
        else:
            self.cursor.execute('INSERT OR IGNORE INTO persons (name) VALUES (?)', (name,))
            self.cursor.execute('SELECT id FROM persons WHERE name = ?', (name,))
            person_id = self.cursor.fetchone()[0]

        with open(file_path, 'rb') as f:
            image_data = f.read()

        self.cursor.execute('INSERT INTO images (person_id, image) VALUES (?, ?)',
            (person_id, image_data))
        self.conn.commit()
        self._load_images()

    # ── delete all ───────────────────────────────────────────────────

    def _delete_all_dialog(self):
        reply = QMessageBox.question(self, "Confirm Delete All",
            "Are you sure you want to delete all users and images?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.cursor.execute('DELETE FROM images')
                self.cursor.execute('DELETE FROM persons')
                self.conn.commit()
                QMessageBox.information(self, "Success", "All users and images have been deleted.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {e}")
            self._load_images()

    # ── load and display images ──────────────────────────────────────

    def _load_images(self):
        # Clear existing widgets
        while self.images_layout.count():
            child = self.images_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        self.cursor.execute('''
            SELECT persons.id, persons.name, images.id, images.image
            FROM persons
            JOIN images ON persons.id = images.person_id
            ORDER BY persons.name, images.id
        ''')

        current_name = None
        row_widget = None
        images_layout = None

        for person_id, name, image_id, image_data in self.cursor.fetchall():
            if name != current_name:
                current_name = name

                row_widget = QWidget()
                row_layout = QHBoxLayout(row_widget)
                row_layout.setContentsMargins(5, 5, 5, 5)

                # Images container
                img_container = QWidget()
                images_layout = QHBoxLayout(img_container)
                images_layout.setContentsMargins(0, 0, 0, 0)
                row_layout.addWidget(img_container)

                # Name label
                name_label = QLabel(name)
                name_label.setFixedWidth(150)
                row_layout.addWidget(name_label)

                # Action buttons
                btn_container = QWidget()
                btn_lay = QHBoxLayout(btn_container)
                btn_lay.setContentsMargins(0, 0, 0, 0)

                rename_btn = QPushButton("Rename")
                rename_btn.clicked.connect(lambda checked, iid=image_id: self._rename_person(iid))
                btn_lay.addWidget(rename_btn)

                export_btn = QPushButton("Export")
                export_btn.clicked.connect(lambda checked, pid=person_id: self._export_image(pid))
                btn_lay.addWidget(export_btn)

                del_img_btn = QPushButton("Delete Image")
                del_img_btn.clicked.connect(lambda checked, pid=person_id: self._delete_single_image(pid))
                btn_lay.addWidget(del_img_btn)

                del_btn = QPushButton("Delete")
                del_btn.clicked.connect(lambda checked, iid=image_id: self._delete_all(iid))
                btn_lay.addWidget(del_btn)

                row_layout.addWidget(btn_container)
                self.images_layout.addWidget(row_widget)

            # Add image thumbnail
            pixmap = self._pixmap_from_blob(image_data)
            if not pixmap.isNull() and images_layout is not None:
                img_label = QLabel()
                img_label.setPixmap(pixmap)
                images_layout.addWidget(img_label)

    # ── rename ───────────────────────────────────────────────────────

    def _rename_person(self, image_id):
        new_name, ok = QInputDialog.getText(self, "Input", "Enter the new name for this face:")
        if not ok or not new_name:
            QMessageBox.warning(self, "No Name", "No new name provided, modification skipped.")
            return

        self.cursor.execute('SELECT person_id FROM images WHERE id = ?', (image_id,))
        row = self.cursor.fetchone()
        if not row:
            return
        current_person_id = row[0]

        self.cursor.execute('SELECT name FROM persons WHERE id = ?', (current_person_id,))
        old_name = self.cursor.fetchone()[0]

        self.cursor.execute('SELECT id FROM persons WHERE name = ?', (new_name,))
        existing = self.cursor.fetchone()

        if existing:
            new_person_id = existing[0]
            self.cursor.execute('SELECT COUNT(*) FROM images WHERE person_id = ?', (new_person_id,))
            if self.cursor.fetchone()[0] >= 5:
                QMessageBox.critical(self, "Error",
                    "Cannot add more than 5 images to the same person.")
                return

            self.cursor.execute('UPDATE images SET person_id = ? WHERE id = ?',
                (new_person_id, image_id))
            self.conn.commit()
            QMessageBox.information(self, "Success",
                f"Image added to existing person '{new_name}'.")

            self.cursor.execute('SELECT COUNT(*) FROM images WHERE person_id = ?',
                (current_person_id,))
            if self.cursor.fetchone()[0] == 0:
                self.cursor.execute('DELETE FROM persons WHERE id = ?', (current_person_id,))
                self.conn.commit()
        else:
            self.cursor.execute('UPDATE persons SET name = ? WHERE id = ?',
                (new_name, current_person_id))
            self.conn.commit()
            QMessageBox.information(self, "Success", "Name updated.")

        self._load_images()

    # ── export ───────────────────────────────────────────────────────

    def _export_image(self, person_id):
        self.cursor.execute('SELECT name FROM persons WHERE id = ?', (person_id,))
        row = self.cursor.fetchone()
        if not row:
            QMessageBox.warning(self, "Not Found", "No person found with the specified ID.")
            return
        name = row[0].replace(" ", "_")

        self.cursor.execute('SELECT id, image FROM images WHERE person_id = ?', (person_id,))
        images = self.cursor.fetchall()
        if not images:
            QMessageBox.warning(self, "No Images", "No images found for this person.")
            return

        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Save Images")
        if directory:
            for image_id, image_data in images:
                file_path = os.path.join(directory, f"{name}_{image_id}.jpg")
                with open(file_path, 'wb') as f:
                    f.write(image_data)
            QMessageBox.information(self, "Success",
                f"All images exported successfully to {directory}.")

    # ── delete person and all images ─────────────────────────────────

    def _delete_all(self, image_id):
        self.cursor.execute('SELECT person_id FROM images WHERE id = ?', (image_id,))
        row = self.cursor.fetchone()
        if not row:
            return
        person_id = row[0]

        self.cursor.execute('SELECT name FROM persons WHERE id = ?', (person_id,))
        person_name = self.cursor.fetchone()[0]

        reply = QMessageBox.question(self, f"Confirm Deletion of {person_name}",
            f"Are you sure you want to delete {person_name} and all associated images?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.cursor.execute('DELETE FROM images WHERE person_id = ?', (person_id,))
            self.cursor.execute('DELETE FROM persons WHERE id = ?', (person_id,))
            self.conn.commit()
            QMessageBox.information(self, "Success",
                f"{person_name} and all associated images were deleted.")
            self._load_images()

    # ── delete single image (picker dialog) ──────────────────────────

    def _delete_single_image(self, person_id):
        self.cursor.execute('SELECT id, image FROM images WHERE person_id = ?', (person_id,))
        images = self.cursor.fetchall()
        if not images:
            QMessageBox.warning(self, "No Images", "No images found for this person.")
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Select Image to Delete")
        layout = QVBoxLayout(dlg)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(5)

        columns = 5
        for index, (image_id, image_data) in enumerate(images):
            pixmap = self._pixmap_from_blob(image_data)
            if pixmap.isNull():
                continue

            img_label = QLabel()
            img_label.setPixmap(pixmap)

            container = QPushButton()
            container.setFixedSize(pixmap.width() + 10, pixmap.height() + 10)
            container.setStyleSheet("QPushButton { border: 1px solid #3a3a3a; }")
            container_layout = QVBoxLayout(container)
            container_layout.setContentsMargins(2, 2, 2, 2)
            container_layout.addWidget(img_label, alignment=Qt.AlignmentFlag.AlignCenter)
            container.clicked.connect(
                lambda checked, iid=image_id, d=dlg: self._confirm_delete_image(iid, d))

            grid.addWidget(container, index // columns, index % columns)

        scroll.setWidget(grid_widget)
        layout.addWidget(scroll)

        # Size dialog to content
        screen = QApplication.primaryScreen().geometry()
        dlg.resize(
            min(grid_widget.sizeHint().width() + 40, int(screen.width() * 0.98)),
            min(grid_widget.sizeHint().height() + 40, int(screen.height() * 0.8)))
        dlg.move((screen.width() - dlg.width()) // 2,
                 (screen.height() - dlg.height()) // 2)
        dlg.exec()

    def _confirm_delete_image(self, image_id, dialog):
        self.cursor.execute('SELECT person_id FROM images WHERE id = ?', (image_id,))
        row = self.cursor.fetchone()
        if not row:
            return
        person_id = row[0]

        self.cursor.execute('SELECT name FROM persons WHERE id = ?', (person_id,))
        person_name = self.cursor.fetchone()[0]

        reply = QMessageBox.question(dialog, "Confirm Delete",
            f"Are you sure you want to delete this image from '{person_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            self.cursor.execute('DELETE FROM images WHERE id = ?', (image_id,))
            self.conn.commit()

            self.cursor.execute('SELECT COUNT(*) FROM images WHERE person_id = ?', (person_id,))
            remaining = self.cursor.fetchone()[0]

            if remaining == 0:
                self.cursor.execute('DELETE FROM persons WHERE id = ?', (person_id,))
                self.conn.commit()
                QMessageBox.information(dialog, "Person Deleted",
                    f"'{person_name}' has been deleted (no remaining images).")
            else:
                QMessageBox.information(dialog, "Success",
                    f"Image deleted from '{person_name}'.")

            dialog.close()
            self._load_images()

    # ── cleanup ──────────────────────────────────────────────────────

    def close_app(self):
        if self.conn:
            self.conn.close()
            self.conn = None
        self.close()

    def closeEvent(self, event):
        if self.conn:
            self.conn.close()
            self.conn = None
        event.accept()


if __name__ == "__main__":
    app = QApplication.instance() or QApplication(sys.argv)
    apply_dark_theme(app)
    window = FaceDatabaseApp()
    window.show()
    sys.exit(app.exec())
