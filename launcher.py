#!/usr/bin/env python3
"""
Calico Launcher
A GUI application to manage and monitor the Calico Voice Assistant services.
This version uses a robust, non-blocking threading model for stability.
"""
import sys
import subprocess
import time
import json
import requests
import os
from pathlib import Path

# This requires PyQt6. Install with: pip install PyQt6
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QTextEdit, QLabel,
                             QMessageBox, QDialog, QGridLayout, QComboBox,
                             QLineEdit, QFrame, QGroupBox)
from PyQt6.QtCore import QObject, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QMovie, QIcon

# --- Configuration ---
APP_NAME = "Calico"
APP_DIR = Path.home() / ".local" / "share" / APP_NAME.lower()
CONFIG_DIR = Path.home() / ".config" / APP_NAME.lower()
SERVICES_DIR = APP_DIR / "services"
SKILL_SERVICE_SCRIPT = SERVICES_DIR / "calico_skill_service.py"
RHASSPY_CONTAINER_NAME = "calico-rhasspy"
ICON_PATH = APP_DIR / "icon.png"
SPINNER_URL = "https://i.gifer.com/ZKZg.gif" # A simple, public domain white spinner
SPINNER_PATH = APP_DIR / "spinner.gif"
LOCK_FILE = Path.home() / ".local" / "share" / "calico.lock"

# --- Single Instance Lock ---
class SingleInstance:
    """Ensures only one instance of the application can run at a time."""
    def __init__(self):
        self.lock_file_path = str(LOCK_FILE)
        self.lock_file = None

    def __enter__(self):
        try:
            self.lock_file = os.open(self.lock_file_path, os.O_WRONLY | os.O_CREAT)
            import fcntl
            fcntl.lockf(self.lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (IOError, BlockingIOError):
            QMessageBox.critical(None, "Already Running",
                                 "Another instance of Calico Launcher is already running.")
            sys.exit(1)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file:
            import fcntl
            fcntl.lockf(self.lock_file, fcntl.LOCK_UN)
            os.close(self.lock_file)
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()

# --- Service Management (The "Worker") ---
class ServiceManager(QObject):
    """Manages the lifecycle of Rhasspy and the Calico skill service."""
    log_updated = pyqtSignal(str)
    services_started = pyqtSignal()
    services_stopped = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.skill_service_process = None

    def _start_rhasspy(self):
        """Stops any existing Rhasspy container and starts a new one."""
        self.log_updated.emit("[INFO] Ensuring old Rhasspy container is removed...")
        subprocess.run(["docker", "rm", "-f", RHASSPY_CONTAINER_NAME], capture_output=True, text=True)

        self.log_updated.emit("[INFO] Starting new Rhasspy container...")
        rhasspy_profile_dir = CONFIG_DIR / "rhasspy"
        rhasspy_profile_dir.mkdir(parents=True, exist_ok=True)

        docker_command = [
            "docker", "run", "-d", "-p", "12101:12101",
            "--name", RHASSPY_CONTAINER_NAME, "--network", "host",
            "--restart", "unless-stopped",
            "-v", f"{rhasspy_profile_dir}:/profiles",
            "-v", "/etc/localtime:/etc/localtime:ro",
            "--device", "/dev/snd:/dev/snd",
            "rhasspy/rhasspy:2.5.11", "--user-profiles", "/profiles", "--profile", "en"
        ]
        result = subprocess.run(docker_command, capture_output=True, text=True)
        if result.returncode != 0:
            self.log_updated.emit(f"[ERROR] Docker failed to start. Is the Docker daemon running?")
            self.log_updated.emit(f"[ERROR] {result.stderr}")
            return False
        self.log_updated.emit("[OK] Rhasspy container started.")
        return True

    def _start_skill_service(self):
        """Starts the Calico skill service as a background subprocess."""
        self.log_updated.emit("[INFO] Starting Calico skill service...")
        python_executable = APP_DIR / ".venv" / "bin" / "python3"
        if not python_executable.exists():
            self.log_updated.emit(f"[ERROR] Python executable not found at {python_executable}")
            return False

        # Run the skill service as a detached background process.
        # We are no longer capturing its output.
        self.skill_service_process = subprocess.Popen(
            [str(python_executable), str(SKILL_SERVICE_SCRIPT)],
            stdout=subprocess.DEVNULL, # Discard stdout
            stderr=subprocess.DEVNULL  # Discard stderr
        )

        self.log_updated.emit("[OK] Calico skill service is running.")
        return True

    def handle_start(self):
        """Public slot to start all services."""
        if not self._start_rhasspy():
            self.services_stopped.emit()
            return
        
        time.sleep(5)

        if not self._start_skill_service():
            self._stop_logic()
            self.services_stopped.emit()
            return

        self.services_started.emit()

    def _stop_logic(self):
        """Internal logic to stop all running processes."""
        if self.skill_service_process and self.skill_service_process.poll() is None:
            self.log_updated.emit("[INFO] Stopping Calico skill service...")
            self.skill_service_process.terminate()
            try:
                self.skill_service_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.skill_service_process.kill()
            self.log_updated.emit("[OK] Calico skill service stopped.")
        self.skill_service_process = None

        self.log_updated.emit("[INFO] Stopping and removing Rhasspy container...")
        subprocess.run(["docker", "stop", RHASSPY_CONTAINER_NAME], capture_output=True, text=True)
        subprocess.run(["docker", "rm", RHASSPY_CONTAINER_NAME], capture_output=True, text=True)
        self.log_updated.emit("[OK] Rhasspy container removed.")

    def handle_stop(self):
        """Public slot to stop all services."""
        self._stop_logic()
        self.services_stopped.emit()

    def handle_reload_skills(self):
        """Public slot to restart only the skill service."""
        self.log_updated.emit(">>> Restarting skill service to reload skills...")
        # Stop the existing service
        if self.skill_service_process and self.skill_service_process.poll() is None:
            self.skill_service_process.terminate()
            self.skill_service_process.wait(timeout=5)
        
        # Start the new one
        if self._start_skill_service():
            self.log_updated.emit(">>> Skill service restarted successfully.")
        else:
            self.log_updated.emit("[ERROR] Failed to restart skill service.")
            self._stop_logic()
            self.services_stopped.emit()


# --- Main Application Window ---
class CalicoLauncher(QMainWindow):
    """The main GUI window for the application."""
    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    reload_skills_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Launcher")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.setGeometry(100, 100, 800, 600)
        self.is_shutting_down = False

        self.service_manager = ServiceManager()
        self.service_manager_thread = QThread()
        self.service_manager.moveToThread(self.service_manager_thread)

        self.service_manager.log_updated.connect(self.update_log_view)
        self.service_manager.services_started.connect(self.on_services_started)
        self.service_manager.services_stopped.connect(self.on_services_stopped)

        self.start_requested.connect(self.service_manager.handle_start)
        self.stop_requested.connect(self.service_manager.handle_stop)
        self.reload_skills_requested.connect(self.service_manager.handle_reload_skills)

        self.service_manager_thread.start()
        
        # **FIX:** The UI must be initialized *before* any function that tries to use it.
        self.init_ui()
        self.apply_stylesheet()
        self._download_assets()
        self.on_services_stopped()

    def _download_assets(self):
        """Downloads the spinner GIF if it doesn't exist."""
        if not SPINNER_PATH.exists():
            self.update_log_view("[INFO] Downloading UI assets...")
            try:
                response = requests.get(SPINNER_URL, timeout=10)
                response.raise_for_status()
                with open(SPINNER_PATH, 'wb') as f:
                    f.write(response.content)
                self.update_log_view("[INFO] Assets downloaded.")
            except Exception as e:
                self.update_log_view(f"[WARN] Could not download spinner asset: {e}")

    def init_ui(self):
        """Initializes all UI elements."""
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        header_layout = QHBoxLayout()
        title_label = QLabel(APP_NAME)
        title_label.setObjectName("TitleLabel")
        settings_button = QPushButton("Settings")
        settings_button.setObjectName("SettingsButton")
        settings_button.setFixedWidth(100)
        settings_button.clicked.connect(self.open_settings)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(settings_button)
        main_layout.addLayout(header_layout)

        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LogView")
        main_layout.addWidget(self.log_view)

        footer_layout = QHBoxLayout()
        self.start_button = QPushButton("Start")
        self.stop_button = QPushButton("Stop")
        self.spinner_label = QLabel()
        self.spinner_label.setFixedSize(32, 32)
        if SPINNER_PATH.exists():
            self.spinner_movie = QMovie(str(SPINNER_PATH))
            self.spinner_movie.setScaledSize(QSize(32, 32))
            self.spinner_label.setMovie(self.spinner_movie)
        self.spinner_label.hide()

        self.start_button.clicked.connect(self.handle_start)
        self.stop_button.clicked.connect(self.handle_stop)

        footer_layout.addWidget(self.spinner_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(self.start_button)
        footer_layout.addWidget(self.stop_button)
        main_layout.addLayout(footer_layout)

    def apply_stylesheet(self):
        """Applies the application-wide stylesheet."""
        self.setStyleSheet("""
            QMainWindow, QDialog { background-color: #6abf40; }
            QLabel { color: white; font-family: Helvetica; font-weight: bold; }
            #TitleLabel { font-size: 24px; }
            #LogView {
                background-color: #FFFFFF; color: #2E3440;
                font-family: Consolas, monospace; border: 1px solid #58a135;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #58a135; color: white; border: none;
                padding: 10px 20px; font-size: 16px; font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #80cf59; }
            QPushButton:pressed { background-color: #4a8a2c; }
            QPushButton:disabled { background-color: #4a8a2c; color: #cccccc; }
            #SettingsButton {
                background-color: transparent; border: 1px solid white;
                font-size: 14px; font-weight: normal; padding: 5px 10px;
            }
            #SettingsButton:hover { background-color: #80cf59; }
            QGroupBox {
                color: white; font-weight: bold; border: 1px solid white;
                border-radius: 5px; margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin; subcontrol-position: top left;
                padding: 0 3px;
            }
        """)

    def set_processing_state(self, is_processing):
        """Disables buttons and shows/hides the spinner."""
        self.start_button.setDisabled(is_processing)
        self.stop_button.setDisabled(is_processing)
        if is_processing:
            self.spinner_label.show()
            if self.spinner_movie: self.spinner_movie.start()
        else:
            if self.spinner_movie: self.spinner_movie.stop()
            self.spinner_label.hide()

    def handle_start(self):
        """Handles the start button click."""
        self.set_processing_state(True)
        self.update_log_view(">>> Attempting to start services...")
        self.start_requested.emit()

    def handle_stop(self):
        """Handles the stop button click."""
        self.set_processing_state(True)
        self.update_log_view(">>> Attempting to stop services...")
        self.stop_requested.emit()

    def update_log_view(self, text):
        """Appends text to the log view and auto-scrolls."""
        self.log_view.append(text)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def on_services_started(self):
        """Slot for when services have successfully started."""
        self.set_processing_state(False)
        self.start_button.setDisabled(True)
        self.stop_button.setDisabled(False)
        self.update_log_view(">>> All services started successfully.")

    def on_services_stopped(self):
        """Slot for when services have stopped."""
        self.set_processing_state(False)
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)
        self.update_log_view(">>> All services are stopped.")

    def open_settings(self):
        """Opens the settings dialog."""
        settings_dialog = SettingsWindow(self.reload_skills_requested, self)
        settings_dialog.exec()

    def closeEvent(self, event):
        """Handles the main window close event."""
        if self.is_shutting_down:
            event.accept()
            return

        reply = QMessageBox.question(self, "Confirm Exit",
                                     "This will stop all Calico services. Are you sure you want to exit?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.No:
            event.ignore()
            return

        self.update_log_view(">>> Application closing, stopping all services...")
        self.is_shutting_down = True
        self.setEnabled(False)

        self.service_manager.services_stopped.connect(self.close)
        self.stop_requested.emit()
        event.ignore()

# --- Settings Window ---
class SettingsWindow(QDialog):
    """A dialog for managing user settings."""
    def __init__(self, reload_skills_signal, parent=None):
        super().__init__(parent)
        self.reload_skills_signal = reload_skills_signal
        self.setWindowTitle(f"{APP_NAME} Settings")
        self.setMinimumWidth(450)

        self.config_file = CONFIG_DIR / "config.json"

        main_layout = QVBoxLayout(self)
        form_layout = QGridLayout()
        self.temp_combo = self._add_form_row(form_layout, 0, "Temperature Unit:", ["Fahrenheit", "Celsius"])
        self.other_units_combo = self._add_form_row(form_layout, 1, "Other Units:", ["Imperial", "Metric"])
        self.zip_code_entry = self._add_form_row(form_layout, 2, "Zip Code:")
        self.region_combo = self._add_form_row(form_layout, 3, "Region:", ["US", "CA", "GB"])
        main_layout.addLayout(form_layout)

        about_box = QGroupBox("About")
        about_layout = QVBoxLayout()
        about_layout.addWidget(QLabel(f"{APP_NAME} v0.5.0 pre-alpha"))
        about_layout.addWidget(QLabel("MIT License"))
        line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setFrameShadow(QFrame.Shadow.Sunken)
        about_layout.addWidget(line)
        about_layout.addWidget(self._create_link_label("Weather Data Provided by Open-Meteo.com", "https://open-meteo.com/"))
        about_layout.addWidget(self._create_link_label("Zip Code Data Provided by Zippopotam.us", "https://zippopotam.us/"))
        about_layout.addWidget(self._create_link_label("View on GitHub", "https://github.com/MrCarpenter24/Calico-Voice-Assistant/tree/main"))
        about_layout.addWidget(self._create_link_label("Built to work with Rhasspy 2.5", "https://rhasspy.readthedocs.io/en/latest/"))
        about_box.setLayout(about_layout)
        main_layout.addWidget(about_box)

        self.reload_button = QPushButton("Save and Reload Skills")
        self.reload_button.clicked.connect(self.validate_and_reload)
        main_layout.addWidget(self.reload_button)

        self.save_button = QPushButton("Save and Close")
        self.save_button.clicked.connect(self.save_and_close)
        main_layout.addWidget(self.save_button)

        self.load_settings()

    def _create_link_label(self, text, url):
        label = QLabel(f'<a href="{url}" style="color:white;">{text}</a>')
        label.setOpenExternalLinks(True)
        return label

    def _add_form_row(self, layout, row, label_text, combo_items=None):
        layout.addWidget(QLabel(label_text), row, 0)
        widget = QComboBox() if combo_items else QLineEdit()
        if combo_items: widget.addItems(combo_items)
        layout.addWidget(widget, row, 1)
        return widget

    def load_settings(self):
        if not self.config_file.exists(): return
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            self.temp_combo.setCurrentText("Fahrenheit" if data.get("temp_unit", "f") == 'f' else "Celsius")
            self.other_units_combo.setCurrentText(data.get("other_units", "imperial").capitalize())
            self.zip_code_entry.setText(data.get("zip_code", ""))
            self.region_combo.setCurrentText(data.get("region", "us").upper())
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not load config file: {e}")

    def save_settings(self) -> bool:
        zip_code = self.zip_code_entry.text().strip()
        if zip_code and not self._validate_zip_code_api(zip_code):
            return False

        temp_map = {"Fahrenheit": "f", "Celsius": "c"}
        settings = {
            "temp_unit": temp_map.get(self.temp_combo.currentText()),
            "other_units": self.other_units_combo.currentText().lower(),
            "zip_code": zip_code,
            "region": self.region_combo.currentText().lower()
        }
        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=4)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save settings: {e}")
            return False

    def _validate_zip_code_api(self, zip_code) -> bool:
        region = self.region_combo.currentText().lower()
        try:
            response = requests.get(f"https://api.zippopotam.us/{region}/{zip_code}", timeout=5)
            if response.status_code == 200: return True
            QMessageBox.critical(self, "Validation Error", f"Invalid postal code '{zip_code}' for region '{region.upper()}'.")
            return False
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Connection Error", f"Could not connect to validation service: {e}")
            return True

    def save_and_close(self):
        if self.save_settings():
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            self.accept()

    def validate_and_reload(self):
        if self.save_settings():
            QMessageBox.information(self, "Success", "Settings saved. Reloading skill service...")
            self.reload_skills_signal.emit()
            self.accept()

# --- Main Execution ---
if __name__ == "__main__":
    APP_DIR.mkdir(parents=True, exist_ok=True)
    
    instance_lock = SingleInstance()
    try:
        with instance_lock:
            app = QApplication(sys.argv)
            launcher = CalicoLauncher()
            launcher.show()
            sys.exit(app.exec())
    except SystemExit:
        pass
    finally:
        pass
