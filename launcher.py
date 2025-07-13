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
SERVICES_DIR = APP_DIR / "services"
SKILL_SERVICE_SCRIPT = SERVICES_DIR / "calico_skill_service.py"
LOG_FILE = APP_DIR / "logs" / "calico_skill_service.log" # Assumes logs are within the app dir
RHASSPY_CONTAINER_NAME = "calico-rhasspy" # Use a unique name

# --- Main Application Window ---
class CalicoLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calico Launcher")
        self.setGeometry(100, 100, 800, 600)

        # --- Service Manager ---
        self.service_manager = ServiceManager()
        self.service_manager_thread = QThread()
        self.service_manager.moveToThread(self.service_manager_thread)

        # --- Connections from Service Manager to UI ---
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

        # --- Header ---
        header_layout = QHBoxLayout()
        title_label = QLabel("Calico")
        title_label.setObjectName("TitleLabel")
        
        settings_button = QPushButton("Settings")
        settings_button.setObjectName("SettingsButton")
        settings_button.setFixedWidth(100)
        # settings_button.clicked.connect(self.open_settings) # Re-enable when settings window is built

        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(settings_button)
        main_layout.addLayout(header_layout)

        # --- Live Log Feed ---
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setObjectName("LogView")
        main_layout.addWidget(self.log_view)

        # --- Footer ---
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
            #TitleLabel {
                font-size: 24px;
                font-weight: bold;
                color: white;
                padding: 5px;
            }
            #LogView {
                background-color: #FFFFFF;
                color: #2E3440;
                font-family: Consolas, monospace;
                border: 1px solid #58a135;
                border-radius: 5px;
            }
            QPushButton {
                background-color: #58a135; /* Darker green */
                color: white;
                border: none;
                padding: 10px 20px;
                font-size: 16px;
                font-weight: bold;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #80cf59; /* Lighter green */
            }
            QPushButton:pressed {
                background-color: #4a8a2c; /* Even darker green */
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
        
    def closeEvent(self, event):
        self.log_view.append(">>> Application closing, stopping all services...")
        self.service_manager.stop_services()
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
        self.log_thread = None
        self.is_monitoring = False

    def start_services(self):
        try:
            self.log_updated.emit("[INFO] Checking for existing Rhasspy container...")
            subprocess.run(["docker", "rm", "-f", RHASSPY_CONTAINER_NAME], capture_output=True)
            
            self.log_updated.emit("[INFO] Starting new Rhasspy container...")
            rhasspy_profile_dir = Path.home() / ".config" / "calico" / "rhasspy" / "profiles"
            rhasspy_profile_dir.mkdir(parents=True, exist_ok=True)
            
            docker_command = [
                "docker", "run", "-d", "-p", "12101:12101",
                "--name", RHASSPY_CONTAINER_NAME, "--network", "host",
                "--restart", "unless-stopped",
                "-v", f"{rhasspy_profile_dir}:/profiles",
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
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            self.services_started.emit()

        except Exception as e:
            self.log_updated.emit(f"[ERROR] Failed to start services: {e}")
            self.stop_services()

    def stop_services(self):
        try:
            if self.skill_service_process:
                self.log_updated.emit("[INFO] Stopping Calico skill service...")
                self.skill_service_process.terminate()
                self.skill_service_process.wait(timeout=5)
                self.skill_service_process = None

            self.log_updated.emit("[INFO] Stopping and removing Rhasspy container...")
            subprocess.run(["docker", "stop", RHASSPY_CONTAINER_NAME], capture_output=True)
            subprocess.run(["docker", "rm", RHASSPY_CONTAINER_NAME], capture_output=True)
        except Exception as e:
            self.log_updated.emit(f"[ERROR] Error during shutdown: {e}")
        finally:
            self.services_stopped.emit()

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

# --- Main Execution ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = CalicoLauncher()
    launcher.show()
    sys.exit(app.exec())
