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
                             QLineEdit)
from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QIcon, QPixmap, QFont

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

        # --- THIS IS THE FIX: Set Window Icon and Tooltip ---
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))
        # The tooltip that appears when hovering over the taskbar icon
        self.setToolTip("Calico Voice Assistant")

        # --- Service Manager Setup ---
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
        """)

    def handle_start_restart(self):
        # The Restart functionality is handled by stopping then starting
        if self.start_button.text() == "Restart":
            self.log_view.append(">>> Attempting to restart services...")
            self.stop_button.setDisabled(True)
            self.start_button.setDisabled(True)
            # Chain the start command after stop is confirmed
            self.service_manager.services_stopped.connect(self.service_manager.start_services)
            self.service_manager.stop_services()
        else: # It's a normal Start
            self.log_view.append(">>> Attempting to start services...")
            self.start_button.setDisabled(True)
            self.service_manager.start_services()

    def handle_stop(self):
        self.log_view.append(">>> Attempting to stop services...")
        self.stop_button.setDisabled(True)
        # Disconnect the restart chain if it exists
        try:
            self.service_manager.services_stopped.disconnect(self.service_manager.start_services)
        except TypeError:
            pass # It was not connected, which is fine
        self.service_manager.stop_services()

    def update_log_view(self, text):
        self.log_view.append(text)
        self.log_view.verticalScrollBar().setValue(self.log_view.verticalScrollBar().maximum())

    def on_services_started(self):
        # Disconnect the restart chain if it was used
        try:
            self.service_manager.services_stopped.disconnect(self.service_manager.start_services)
        except TypeError:
            pass
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
        self.log_view.append(">>> Application closing, stopping all services...")
        self.service_manager.is_monitoring = False
        self.handle_stop() # Use the same safe stop handler
        self.service_manager_thread.quit()
        self.service_manager_thread.wait()
        event.accept()

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
            subprocess.run(["sudo", "docker", "rm", "-f", RHASSPY_CONTAINER_NAME], capture_output=True, text=True)
            
            self.log_updated.emit("[INFO] Starting new Rhasspy container...")
            rhasspy_profile_dir = CONFIG_DIR / "rhasspy" / "profiles"
            rhasspy_profile_dir.mkdir(parents=True, exist_ok=True)
            
            docker_command = [
                "sudo", "docker", "run", "-d", "-p", "12101:12101",
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
            subprocess.run(["sudo", "docker", "stop", RHASSPY_CONTAINER_NAME], capture_output=True, text=True)
            subprocess.run(["sudo", "docker", "rm", RHASSPY_CONTAINER_NAME], capture_output=True, text=True)
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
        
        self.reload_button = QPushButton("Reload Skills (Restart Service)")
        self.reload_button.clicked.connect(self.service_manager.restart_skill_service)
        main_layout.addWidget(self.reload_button)
        
        self.save_button = QPushButton("Save Settings")
        self.save_button.clicked.connect(self.save_settings)
        main_layout.addWidget(self.save_button)
        
        self.load_settings()

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
        temp_map = {"Fahrenheit": "f", "Celsius": "c"}
        settings = {
            "temp_unit": temp_map.get(self.temp_combo.currentText()),
            "other_units": self.other_units_combo.currentText().lower(),
            "zip_code": self.zip_code_entry.text(),
            "region": self.region_combo.currentText().lower()
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(settings, f, indent=4)
            QMessageBox.information(self, "Success", "Settings saved successfully!")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not save settings: {e}")

# --- Main Execution ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = CalicoLauncher()
    launcher.show()
    sys.exit(app.exec())
