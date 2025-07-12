#!/bin/bash
set -euo pipefail

# Starts Rhasspy and Calico services

# Define container name
CONTAINER_NAME="rhasspy"
BASE_DIR="$HOME/Documents/Calico"
SERVICES_DIR="$BASE_DIR/services"
SKILL_SERVICE="$SERVICES_DIR/calico_skill_service.py"
SKILL_SERVICE_PID_FILE="/tmp/calico_skill_service.pid"
LOGS_DIR="$BASE_DIR/logs"
SKILL_SERVICE_LOG="$LOGS_DIR/calico_skill_service.log"
IMAGE_NAME="rhasspy/rhasspy"  #"rhasspy-local:latest"            # version with paho-mqtt installed (lets python talk to mqtt broker)
MQTT_FLAG_FILE="/tmp/calico_mqtt_managed.txt"


# Function to prompt user to exit program
function pauseForExit() {
	local code="${1:-0}"
	while read -r -t 0.1 -n 1; do :; done
	read -p "Press Enter to exit..."
	exit "$code"
}

# ── Dependency: Docker ─────────────────────────────────────────
function ensure_docker_running() {
  if ! systemctl is-active --quiet docker; then
    echo "[INFO] Docker is not running. Attempting to start Docker..."
    if sudo systemctl start docker; then
      echo "[OK] Docker started successfully."
    else
    	echo "[ERROR] Failed to start Docker. Please check your Docker installation." >&2
	pauseForExit 1
    fi
  fi
}

# ── Dependency: Mosquitto ──────────────────────────────────────
function ensure_mosquitto_running() {
  local installed=false started=false
  if ! command -v mosquitto >/dev/null; then
    echo "[INFO] Installing Mosquitto (requires sudo)…"
    sudo apt-get update -y && sudo apt-get install -y mosquitto mosquitto-clients || {
      echo "[ERROR] Failed to install Mosquitto" >&2; pauseForExit 1; }
    installed=true
  fi
  if ! systemctl is-active --quiet mosquitto; then
    echo "[INFO] Starting Mosquitto service…"
    sudo systemctl enable --now mosquitto || { echo "[ERR] Cannot start Mosquitto" >&2; pauseForExit 1; }
    started=true
  fi
  if [[ "$installed" == true || "$started" == true ]]; then
    echo "[INFO] This script now manages Mosquitto"
    touch "$MQTT_FLAG_FILE"
  else
    # Broker already running before we arrived
    rm -f "$MQTT_FLAG_FILE"
  fi
  echo "[OK] Mosquitto running on 1883"
}

# ── Dependency: Python Import tkinter ──────────────────────

function ensure_tkinter_installed() {
  # Check if tkinter is available to Python 3
  if python3 -c "import tkinter" &> /dev/null; then
    echo "[INFO] Tkinter is already installed."
  else
    echo "[WARNING] Tkinter not found. Attempting to install..."
    # --- Installation for Debian/Ubuntu ---
    sudo apt-get update && sudo apt-get install -y python3-tk

    # Verify installation
    if python3 -c "import tkinter" &> /dev/null; then
      echo "[OK] Tkinter has been successfully installed."
    else
      echo "[ERROR] Failed to install Tkinter. Please install it manually for your system."
      pauseForExit 1 # Return a non-zero exit code to indicate failure
    fi
  fi
}

# ── Verify Dependencies ────────────────────────────────────
ensure_tkinter_installed
ensure_docker_running
ensure_mosquitto_running

# ── (Re)start Rhasspy container ─────────────────────────────────
if sudo docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
  echo "[INFO] Removing existing Rhasspy container..."
  sudo docker rm -f "$CONTAINER_NAME"
fi

echo "[INFO] Starting a new Rhasspy container..."
if ! sudo docker run -d -p 12101:12101 \
  --name "$CONTAINER_NAME" --network host\
  --restart unless-stopped \
  -v "$HOME/.config/rhasspy/profiles:/profiles" \
  -v "/etc/localtime:/etc/localtime:ro" \
  -v "$LOGS_DIR:/logs" \
  --device /dev/snd:/dev/snd \
  "$IMAGE_NAME" --user-profiles /profiles --profile en; then
    echo "[ERROR] Failed to start Rhasspy container." >&2
    pauseForExit 1
fi

# ── Launch host skill service ─────────────────────────────────
# Catch stray skill services
mapfile -t stray_pids < <(pgrep -f "${SKILL_SERVICE}" 2>/dev/null || true)
for stray in "${stray_pids[@]}"; do
    echo "[INFO] Killing stray skill service PID $stray…"
    kill -KILL "$stray" 2>/dev/null || true
done

# Start fresh skill service
if [[ -f "$SKILL_SERVICE" ]]; then
  echo "[OK] Starting host-side skill service: $SKILL_SERVICE"
  # -u for unbuffered stdout so logs flush immediately
  nohup python3 -u "$SKILL_SERVICE" >>"$SKILL_SERVICE_LOG" 2>&1 &
  SKILL_SERVICE_PID=$!
  disown "$SKILL_SERVICE_PID"

  #  Verify it is still alive after a short grace period
  sleep 0.4
  if ! kill -0 "$SKILL_SERVICE_PID" 2>/dev/null; then
    echo "[STOP] Skill service failed to stay alive." >&2
    pauseForExit 1
  fi
  echo "$SKILL_SERVICE_PID" > "$SKILL_SERVICE_PID_FILE"
  echo "[OK] Skill service running (PID $SKILL_SERVICE_PID) - PID saved to $SKILL_SERVICE_PID_FILE"
else
  echo "[STOP] Skill service script not found: $SKILL_SERVICE" >&2
  pauseForExit 1
fi

echo "[SUCCESS] Calico started successfully! :D"

pauseForExit 0


