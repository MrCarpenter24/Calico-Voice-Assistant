#!/usr/bin/env python3
"""
Calico Launcher
A GUI application to manage and monitor the Calico Voice Assistant services.
"""
import sys
import subprocess
import os
import time
import threading
import json
import requests
import webbrowser
from pathlib import Path

# This requires PyQt6. Install with: pip install PyQt6
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QPushButton, QTextEdit, QLabel,
                             QMessageBox, QDialog, QGridLayout, QComboBox,
                             QLineEdit, QFrame, QGroupBox)
from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon

# --- Configuration ---
APP_DIR = Path.home() / ".local" / "share" / "calico"
CONFIG_DIR = Path.home() / ".config" / "calico"
SERVICES_DIR = APP_DIR / "services"
SKILL_SERVICE_SCRIPT = SERVICES_DIR / "calico_skill_service.py"
LOG_FILE = APP_DIR / "logs" / "calico_skill_service.log"
RHASSPY_CONTAINER_NAME = "calico-rhasspy"
ICON_PATH = APP_DIR / "icon.png"

# --- Main Application Window ---
class CalicoLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calico Launcher")
        self.setGeometry(100, 100, 800, 600)
        self.is_shutting_down = False

        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.setToolTip("Calico Voice Assistant")

        self.service_manager = ServiceManager()
        self.service_manager_thread = QThread()
        self.service_manager.moveToThread(self.service_manager_thread)

        self.service_manager.log_updated.connect(self.update_log_view)
        self.service_manager.services_started.connect(self.on_services_started)
        self.service_manager.services_stopped.connect(self.on_services_stopped)
        self.service_manager_thread.started.connect(self.service_manager.monitor_log_file)
        
        self.service_manager_thread.start()

        self.init_ui()
        self.apply_stylesheet()
        
        self.on_services_stopped()

    def init_ui(self):
        main_widget = QWidget()
        main_layout = QVBoxLayout(main_widget)
        self.setCentralWidget(main_widget)

        header_layout = QHBoxLayout()
        title_label = QLabel("Calico")
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
        
        self.start_button.clicked.connect(self.handle_start_restart)
        self.stop_button.clicked.connect(self.handle_stop)

        footer_layout.addStretch()
        footer_layout.addWidget(self.start_button)
        footer_layout.addWidget(self.stop_button)
        footer_layout.addStretch()
        main_layout.addLayout(footer_layout)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow, QDialog {
                background-color: #6abf40;
            }
            QLabel {
                color: white;
                font-family: Helvetica;
                font-weight: bold;
            }
            #TitleLabel {
                font-size: 24px;
            }
            #LogView {
                background-color: #FFFFFF;
                color: #2E3440;
                font-family: Consolas, monospace;
                border: 1px solid #58a135;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #58a135;
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #80cf59;
            }
            QPushButton:pressed {
                background-color: #4a8a2c;
            }
            QPushButton:disabled {
                background-color: #4a8a2c;
                color: #cccccc;
            }
            #SettingsButton {
                background-color: transparent;
                border: 1px solid white;
                font-size: 14px;
                font-weight: normal;
                padding: 5px 10px;
            }
            #SettingsButton:hover {
                background-color: #80cf59;
            }
            QGroupBox {
                color: white;
                font-weight: bold;
                border: 1px solid white;
                border-radius: 5px;
                margin-top: 1ex;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
            }
        """)

    def handle_start_restart(self):
        if self.start_button.text() == "Restart":
            self.log_view.append(">>> Attempting to restart services...")
            self.stop_button.setDisabled(True)
            self.start_button.setDisabled(True)
            self.service_manager.services_stopped.connect(self.service_manager.start_services, Qt.ConnectionType.SingleShotConnection)
            self.service_manager.stop_services()
        else:
            self.log_view.append(">>> Attempting to start services...")
            self.start_button.setDisabled(True)
            self.service_manager.start_services()

    def handle_stop(self):
        self.log_view.append(">>> Attempting to stop services...")
        self.stop_button.setDisabled(True)
        self.service_manager.stop_services()

    def update_log_view(self, text):
        self.log_view.append(text)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def on_services_started(self):
        self.start_button.setText("Restart")
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(False)
        self.log_view.append(">>> All services started successfully.")

    def on_services_stopped(self):
        self.start_button.setText("Start")
        self.start_button.setDisabled(False)
        self.stop_button.setDisabled(True)
        self.log_view.append(">>> All services are stopped.")
        
    def open_settings(self):
        settings_dialog = SettingsWindow(self.service_manager, self)
        settings_dialog.exec()
        
    def closeEvent(self, event):
        if self.is_shutting_down:
            event.accept()
            return

        self.log_view.append(">>> Application closing, stopping all services...")
        self.is_shutting_down = True
        self.setEnabled(False)
        self.service_manager.is_monitoring = False
        
        self.service_manager.services_stopped.connect(self.close)
        self.service_manager.stop_services()
        event.ignore()

# --- Service Management (The "Worker") ---
class ServiceManager(QObject):
    log_updated = pyqtSignal(str)
    services_started = pyqtSignal()
    services_stopped = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.skill_service_process = None
        self.is_monitoring = False

    def start_services(self):
        try:
            self.log_updated.emit("[INFO] Checking for existing Rhasspy container...")
            subprocess.run(["docker", "rm", "-f", RHASSPY_CONTAINER_NAME], capture_output=True, text=True)
            
            self.log_updated.emit("[INFO] Starting new Rhasspy container...")
            rhasspy_profile_dir = CONFIG_DIR / "rhasspy" / "profiles"
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
            subprocess.run(docker_command, check=True)
            time.sleep(5)

            self.log_updated.emit("[INFO] Starting Calico skill service...")
            python_executable = APP_DIR / ".venv" / "bin" / "python3"
            self.skill_service_process = subprocess.Popen(
                [str(python_executable), str(SKILL_SERVICE_SCRIPT)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True, bufsize=1, universal_newlines=True
            )
            
            self.services_started.emit()
        except Exception as e:
            self.log_updated.emit(f"[ERROR] Failed to start services: {e}")
            self.stop_services()

    def stop_services(self):
        try:
            if self.skill_service_process and self.skill_service_process.poll() is None:
                self.log_updated.emit("[INFO] Stopping Calico skill service...")
                self.skill_service_process.terminate()
                self.skill_service_process.wait(timeout=5)
            self.skill_service_process = None

            self.log_updated.emit("[INFO] Stopping and removing Rhasspy container...")
            subprocess.run(["docker", "stop", RHASSPY_CONTAINER_NAME], capture_output=True, text=True)
            subprocess.run(["docker", "rm", RHASSPY_CONTAINER_NAME], capture_output=True, text=True)
        except Exception as e:
            self.log_updated.emit(f"[ERROR] Error during shutdown: {e}")
        finally:
            self.services_stopped.emit()
            
    def restart_skill_service(self):
        self.log_updated.emit(">>> Restarting skill service...")
        if self.skill_service_process and self.skill_service_process.poll() is None:
            self.log_updated.emit("[INFO] Stopping Calico skill service...")
            self.skill_service_process.terminate()
            self.skill_service_process.wait(timeout=5)
        
        self.log_updated.emit("[INFO] Starting new Calico skill service...")
        python_executable = APP_DIR / ".venv" / "bin" / "python3"
        self.skill_service_process = subprocess.Popen(
            [str(python_executable), str(SKILL_SERVICE_SCRIPT)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, universal_newlines=True
        )
        self.log_updated.emit(">>> Skill service restarted.")

    def monitor_log_file(self):
        self.is_monitoring = True
        if not LOG_FILE.exists():
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            LOG_FILE.touch()
            
        with open(LOG_FILE, 'r') as f:
            f.seek(0, 2)
            while self.is_monitoring:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                self.log_updated.emit(line.strip())

# --- Settings Window (Ported from Tkinter) ---
class SettingsWindow(QDialog):
    def __init__(self, service_manager, parent=None):
        super().__init__(parent)
        self.service_manager = service_manager
        self.setWindowTitle("Calico Settings")
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
        about_layout.addWidget(QLabel("Calico v0.4.2 pre-alpha"))
        about_layout.addWidget(QLabel("MIT License"))
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        about_layout.addWidget(line)
        
        about_layout.addWidget(self._create_link_label("Weather Data Provided by Open-Meteo.com", "https://open-meteo.com/"))
        about_layout.addWidget(self._create_link_label("Zip Code Data Provided by Zippopotam.us", "https://zippopotam.us/"))
        about_layout.addWidget(self._create_link_label("View on GitHub", "https://github.com/MrCarpenter24/Calico-Voice-Assistant/tree/main"))
        about_layout.addWidget(self._create_link_label("Built to work with Rhasspy 2.5", "https://rhasspy.readthedocs.io/en/latest/"))
        
        about_box.setLayout(about_layout)
        main_layout.addWidget(about_box)
        
        self.reload_button = QPushButton("Reload Skills (Restart Service)")
        self.reload_button.clicked.connect(self.service_manager.restart_skill_service)
        main_layout.addWidget(self.reload_button)
        
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        main_layout.addWidget(self.save_button)
        
        self.load_settings()

    def _create_link_label(self, text, url):
        label = QLabel(f'<a href="{url}" style="color:white;">{text}</a>')
        label.setOpenExternalLinks(True)
        return label

    def _add_form_row(self, layout, row, label_text, combo_items=None):
        layout.addWidget(QLabel(label_text), row, 0)
        if combo_items:
            widget = QComboBox()
            widget.addItems(combo_items)
        else:
            widget = QLineEdit()
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

    def save_settings(self):
        zip_code = self.zip_code_entry.text().strip()

        # If zip code is blank, ask for confirmation
        if not zip_code:
            reply = QMessageBox.question(self, 'Confirm Save', 
                                         "The postal code field is blank. Some skills may not function correctly. Are you sure you want to save?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return # User cancelled, do not save
        
        # If zip code is not blank, validate it
        elif not self._validate_zip_code_api(zip_code):
            return # Validation failed, do not save

        # Proceed with saving
        temp_map = {"Fahrenheit": "f", "Celsius": "c"}
        settings = {
            "temp_unit": temp_map.get(self.temp_combo.currentText()),
            "other_units": self.other_units_combo.currentText().lower(),
            "zip_code": zip_code,
            "region": self.region_combo.currentText().lower()
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=4)
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save settings: {e}")

    def _validate_zip_code_api(self, zip_code):
        region = self.region_combo.currentText().lower()
        if not region: # Should not happen with a combo box, but good practice
            QMessageBox.warning(self, "Input Required", "Please select a region.")
            return False
        try:
            response = requests.get(f"https://api.zippopotam.us/{region}/{zip_code}", timeout=5)
            if response.status_code == 200: return True
            QMessageBox.critical(self, "Validation Error", f"Invalid postal code '{zip_code}' for the selected region.")
            return False
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "Connection Error", f"Could not connect to validation service: {e}")
            return False

# --- Main Execution ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # This ID should match the name of your .desktop file for consistency
    app.setApplicationName("calico-launcher")
    
    launcher = CalicoLauncher()
    launcher.show()
    sys.exit(app.exec())
