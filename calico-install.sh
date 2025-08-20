#!/bin/bash
#
# Calico Voice Assistant Installer
# ==================================
# This script automates the installation of Calico and all its
# dependencies on a Debian-based system (like Ubuntu or Raspberry Pi OS).
# It follows standard Linux directory practices and creates a desktop entry.
#

set -euo pipefail #Error output n' stuffs

# Function to prompt user to exit program
function pauseForExit() {
	local code="${1:-0}"
	while read -r -t 0.1 -n 1; do :; done
	read -p "Press Enter to exit..."
	exit "$code"
}

# --- Configuration ---
# Use standard XDG Base Directory Specification paths
APP_DIR="$HOME/.local/share/calico"
CONFIG_DIR="$HOME/.config/calico"
GIT_REPO_URL="https://github.com/MrCarpenter24/Calico-Voice-Assistant.git"
RHASSPY_IMAGE="rhasspy/rhasspy:2.5.11"
PYTHON_VENV_DIR="$APP_DIR/.venv"
ICON_URL="https://placehold.co/128x128/6abf40/FFFFFF?text=Calico"
ICON_PATH="$APP_DIR/icon.png"

# --- Helper Functions ---
print_header() {
  echo ""
  echo "==================================================================="
  echo " $1"
  echo "==================================================================="
}

# --- Main Script ---
cat << 'EOL'
  ,-.       _,---._ __  / \
 /  )    .-'       `./ /   \
(  (   ,'            `/    /|
 \  `-"             \'\   / |
  `.              ,  \ \ /  |
   /`.          ,'-`----Y   |
  (            ;        |   '
  |  ,-.    ,-'         |  /
  |  | (   |        hjw | /
  )  |  \  `.___________|/
  `--'   `--'
EOL

print_header "Welcome to Calico v0.5.0 pre-alpha!"
echo "This script will install Calico and all required dependencies into:"
echo "Application files: $APP_DIR"
echo "Configuration:     $CONFIG_DIR"
echo ""
echo "It will ask for your password to install system packages."
echo ""
read -p "Press Enter to begin the installation..."

# Refresh sudo timestamp
sudo -v

# --- Step 1: System Dependencies ---
print_header "Step 1: Installing System Dependencies"
echo ">>> Updating package lists..."
sudo apt-get update
echo ">>> Installing core system packages..."
sudo apt-get install -y git python3-pip python3-full mosquitto mosquitto-clients curl python3-pyqt6
echo ">>> System dependencies installed successfully."

# --- Step 2: Docker Installation ---
print_header "Step 2: Installing Docker Engine"
if command -v docker &> /dev/null; then
    echo ">>> Docker is already installed. Skipping."
else
    echo ">>> Docker not found. Installing now..."
    sudo apt-get install -y ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    echo ">>> Docker installed successfully."
fi

if ! getent group docker | grep -q "\b$(whoami)\b"; then
    echo ">>> Adding current user to the 'docker' group..."
    sudo usermod -aG docker "$(whoami)"
    echo "[IMPORTANT] You must log out and log back in for Docker group changes to take effect."
fi

# --- Step 3: Calico Application Setup ---
print_header "Step 3: Setting up the Calico Application"
mkdir -p "$APP_DIR"
mkdir -p "$CONFIG_DIR"

if [ -d "$APP_DIR/.git" ]; then
    echo ">>> Calico repository already exists. Pulling latest changes..."
    cd "$APP_DIR"
    git pull
    cd - > /dev/null
else
    echo ">>> Cloning Calico repository from GitHub into $APP_DIR..."
    git clone "$GIT_REPO_URL" "$APP_DIR"
    echo ">>> Repository cloned successfully."
fi

# Re-create venv every time to ensure it's clean and correct
echo ">>> Creating a fresh Python virtual environment..."
rm -rf "$PYTHON_VENV_DIR"
python3 -m venv "$PYTHON_VENV_DIR"

# Verify venv creation before proceeding
VENV_PIP="$PYTHON_VENV_DIR/bin/pip"
if [ ! -f "$VENV_PIP" ]; then
    echo "[ERROR] Virtual environment creation failed: pip not found." >&2
    echo "Please check your Python installation and ensure the 'venv' module is working correctly." >&2
    exit 1
fi

echo ">>> Creating requirements.txt..."
cat > "$APP_DIR/requirements.txt" << EOL
paho-mqtt
requests
PyQt6
EOL

echo ">>> Installing Python dependencies into the virtual environment..."
"$VENV_PIP" install -r "$APP_DIR/requirements.txt"
echo ">>> Python dependencies installed."

if [ -f "$CONFIG_DIR/config.json" ]; then
    echo ">>> config.json already exists. Skipping."
else
    echo ">>> Copying default configuration..."
    cp "$APP_DIR/settings/config.default.json" "$CONFIG_DIR/config.json"
fi

# --- Step 4: Set File Permissions ---
print_header "Step 4: Setting File Permissions"
echo ">>> Making launcher and services executable..."
chmod +x "$APP_DIR/launcher.py"
chmod +x "$APP_DIR/services/calico_skill_service.py"
echo ">>> Permissions set."

# --- Step 5: Rhasspy Setup ---
print_header "Step 5: Setting up Rhasspy"
echo ">>> Pulling the Rhasspy Docker image ($RHASSPY_IMAGE)..."
echo "This may take a few minutes."
sudo docker pull "$RHASSPY_IMAGE"
echo ">>> Rhasspy Docker image pulled successfully."

echo ">>> Copying pre-configured Rhasspy profile..."
RHASSPY_PROFILE_DEST="$CONFIG_DIR/../rhasspy"
RHASSPY_PROFILE_SRC="$APP_DIR/rhasspy-config"

if [ -d "$RHASSPY_PROFILE_SRC" ]; then
    echo ">>> Creating destination directory at $RHASSPY_PROFILE_DEST"
    sudo mkdir -p "$RHASSPY_PROFILE_DEST"
    # The -T option ensures the contents of the source are copied into the destination
    sudo cp -rT "$RHASSPY_PROFILE_SRC" "$RHASSPY_PROFILE_DEST"
    echo ">>> Default Rhasspy profile copied successfully."
else
    echo "[WARN] Could not find source profile directory at '$RHASSPY_PROFILE_SRC'."
    echo "[WARN] You will need to configure Rhasspy manually."
fi

# --- Step 6: Creating Application Menu Entry ---
print_header "Step 6: Creating Application Menu Entry"
echo ">>> Downloading application icon..."
curl -L "$ICON_URL" -o "$ICON_PATH"

# Create .desktop file
DESKTOP_FILE_PATH="$HOME/.local/share/applications/calico-launcher.desktop"
echo ">>> Creating .desktop file at $DESKTOP_FILE_PATH..."
cat > "$DESKTOP_FILE_PATH" << EOL
[Desktop Entry]
Version=1.0
Type=Application
Name=Calico
Comment=A launcher for the Calico Voice Assistant
Exec="$PYTHON_VENV_DIR/bin/python3" "$APP_DIR/launcher.py"
Icon=$ICON_PATH
Terminal=false
Categories=Utility;System;
EOL
chmod +x "$DESKTOP_FILE_PATH"
echo ">>> Application menu entry created."

# --- Finalization ---
print_header "Installation Complete!"
echo ""
echo "What's next?"
echo "1. IMPORTANT: You must RESTART your machine for all permissions"
echo "   and the new application menu entry to take effect."
echo ""
echo "2. After restarting, you can find 'Calico' in your"
echo "   application menu, or run it from the terminal with:"
echo "   python3 $APP_DIR/launcher.py"
echo ""
echo "3. A partially pre-configured Rhasspy profile has been copied for you."
echo "   You can edit your sentences and add custom voice commands at:"
echo "   $CONFIG_DIR/rhasspy/profiles/en/sentences.ini"
echo ""
echo "4. After the first launch, navigate to http://localhost:12101/"
echo "   and click to download the recommended (required) files."
echo "   You can record your own wake word if need be by following"
echo "   the official Rhasspy 2.5 documentation here:"
echo "   https://rhasspy.readthedocs.io/en/latest/"
echo ""
echo "Thank you for installing Calico!"

pauseForExit 0
