#!/bin/bash

# ────────────────────────────────────────────────────────────────
#  Calico-Stop.sh – stops the Docker container *and* the host-side
#  skill service that was launched by Calico-Start.sh.
# ────────────────────────────────────────────────────────────────

set -euo pipefail

CONTAINER_NAME="rhasspy"
SKILL_SERVICE_PID_FILE="/tmp/calico_skill_service.pid"
SKILL_SERVICE="$HOME/Documents/Calico/services/calico_skill_service.py"
MOSQ_FLAG_FILE="/tmp/calico_mqtt_managed.txt"

function pauseForExit() {
  local code="${1:-0}"
  # Clear any buffered keystroke
  while read -r -t 0.1 -n 1; do :; done
  read -p "Press Enter to exit..."
  exit "$code"
}

function stop_container() {
  if sudo docker ps --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
    echo "Stopping container '${CONTAINER_NAME}'..."
    sudo docker stop "$CONTAINER_NAME"
  else
    echo "Container '${CONTAINER_NAME}' is not running. Skipping stop."
  fi
}

function remove_container() {
  if sudo docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}$"; then
    echo "Removing container '${CONTAINER_NAME}'..."
    sudo docker rm "$CONTAINER_NAME"
  else
    echo "Container '${CONTAINER_NAME}' does not exist. Skipping remove."
  fi
}

function stop_service_if_active() {
  local service=$1
  if sudo systemctl is-active --quiet "$service"; then
    echo "Stopping systemd service: $service..."
    sudo systemctl stop "$service"
  else
    echo "Systemd service '$service' is not active. Skipping."
  fi
}

function stop_mosquitto() {
  if systemctl is-active --quiet mosquitto; then
    echo "Stopping Mosquitto service…"
    sudo systemctl stop mosquitto || true
  else
    echo "Mosquitto service already stopped."
  fi

  # Clear flag file if present
  if [[ -f "$MOSQ_FLAG_FILE" ]]; then
  echo "[INFO] Removing Mosquitto flag file ($MOSQ_FLAG_FILE)"
  rm -f "$MOSQ_FLAG_FILE"
  fi
}

function stop_skill_service() {
  if [[ -f "$SKILL_SERVICE_PID_FILE" ]]; then
    local pid
    pid=$(cat "$SKILL_SERVICE_PID_FILE")

    # Confirm the PID is actually calico_skill_service.py
    if ps -p "$pid" -o comm= | grep -qE '^python3?'; then
      echo "Stopping skill service (PID $pid)…"

      # 1) Gentle interrupt (Ctrl-C equivalent)
      kill -INT "$pid" 2>/dev/null || true
      sleep 0.2

      # 2) If still alive, request termination
      if kill -0 "$pid" 2>/dev/null; then
        echo "Skill service still running, sending SIGTERM…"
        kill -TERM "$pid" 2>/dev/null || true
        sleep 0.2
      fi

      # 3) Last resort
      if kill -0 "$pid" 2>/dev/null; then
        echo "Skill service stubborn; forcing SIGKILL…" >&2
        kill -KILL "$pid" 2>/dev/null || true
      fi
    else
      echo "PID $pid is not calico_skill_service.py; skipping kill."
    fi

    rm -f "$SKILL_SERVICE_PID_FILE"
  else
    echo "No skill service PID file found; skill service may not be running."
  fi
  # Catch stray skill service instances
  mapfile -t stray_pids < <(pgrep -f "${SKILL_SERVICE}" 2>/dev/null || true)
  for stray in "${stray_pids[@]}"; do
      echo "Killing stray skill service PID $stray…"
      kill -KILL "$stray" 2>/dev/null || true
  done
}

echo "Stopping Rhasspy and Calico services..."
stop_container
remove_container
stop_skill_service
stop_mosquitto
stop_service_if_active docker
stop_service_if_active docker.socket

pauseForExit 0

