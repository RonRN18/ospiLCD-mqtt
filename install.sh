#!/bin/bash

set -e

SERVICE_NAME="ospilcd"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(id -un)"
VENV_DIR="${SCRIPT_DIR}/.venv"
CONFIG_FILE="${SCRIPT_DIR}/ospilcd.ini"
CONFIG_EXAMPLE="${SCRIPT_DIR}/ospilcd.ini.example"
REQUIREMENTS_FILE="${SCRIPT_DIR}/requirements.txt"
PYTHON_SCRIPT="${SCRIPT_DIR}/ospiLCD-mqtt.py"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo
echo "========================================"
echo " ospiLCD-mqtt installer"
echo "========================================"
echo
echo "User:              ${CURRENT_USER}"
echo "Project directory: ${SCRIPT_DIR}"
echo "Virtual env:       ${VENV_DIR}"
echo


######################### Initial Checks #########################

if [[ "${EUID}" -eq 0 ]]; then
    echo "ERROR: Do not run this entire script with sudo."
    echo
    echo "Run it as your normal user:"
    echo
    echo "    ./install.sh"
    echo
    exit 1
fi

if [[ ! -f "${PYTHON_SCRIPT}" ]]; then
    echo "ERROR: Could not find:"
    echo
    echo "    ${PYTHON_SCRIPT}"
    echo
    exit 1
fi

if [[ ! -f "${REQUIREMENTS_FILE}" ]]; then
    echo "ERROR: Could not find:"
    echo
    echo "    ${REQUIREMENTS_FILE}"
    echo
    exit 1
fi

if [[ ! -f "${CONFIG_EXAMPLE}" ]]; then
    echo "ERROR: Could not find:"
    echo
    echo "    ${CONFIG_EXAMPLE}"
    echo
    exit 1
fi


######################### Step 1 #########################

echo "[1/7] Checking required system packages..."

sudo apt update

sudo apt install -y \
    python3 \
    python3-venv \
    i2c-tools


######################### Step 2 #########################

echo
echo "[2/7] Checking I2C interface..."

if [[ ! -e /dev/i2c-1 ]]; then
    echo
    echo "WARNING: /dev/i2c-1 does not exist."
    echo
    echo "I2C may not be enabled."
    echo
    echo "On Raspberry Pi OS, run:"
    echo
    echo "    sudo raspi-config"
    echo
    echo "Then select:"
    echo
    echo "    Interface Options -> I2C -> Enable"
    echo
    echo "Reboot afterward and run this installer again."
    echo
    exit 1
fi

echo "I2C bus /dev/i2c-1 found."

if ! id -nG "${CURRENT_USER}" | grep -qw "i2c"; then
    echo
    echo "Adding ${CURRENT_USER} to the i2c group..."
    sudo usermod -aG i2c "${CURRENT_USER}"
    echo "Added ${CURRENT_USER} to the i2c group."
else
    echo "User ${CURRENT_USER} is already a member of the i2c group."
fi


######################### Step 3 #########################

echo
echo "[3/7] Creating Python virtual environment..."

if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
    echo "Created ${VENV_DIR}"
else
    echo "Existing virtual environment found."
fi


######################### Step 4 #########################

echo
echo "[4/7] Installing Python requirements..."

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${REQUIREMENTS_FILE}"

echo
echo "Checking Python script syntax..."

"${VENV_DIR}/bin/python" -m py_compile "${PYTHON_SCRIPT}"

echo "Python syntax check passed."


######################### Step 5 #########################

echo
echo "[5/7] Checking local configuration..."

if [[ ! -f "${CONFIG_FILE}" ]]; then
    cp "${CONFIG_EXAMPLE}" "${CONFIG_FILE}"

    echo
    echo "Created:"
    echo
    echo "    ${CONFIG_FILE}"
    echo
    echo "You MUST review this file for your installation."
else
    echo "Existing ospilcd.ini found."
    echo "It has NOT been changed."
fi


######################### Step 6 #########################

echo
echo "[6/7] Installing systemd service..."

sudo tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=OpenSprinkler Pi LCD
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${VENV_DIR}/bin/python -u ${PYTHON_SCRIPT}

Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

echo "Installed:"
echo
echo "    ${SERVICE_FILE}"


######################### Step 7 #########################

echo
echo "[7/7] Installation complete."
echo
echo "Before starting the service, review:"
echo
echo "    ${CONFIG_FILE}"
echo
echo "At minimum verify:"
echo
echo "    OpenSprinkler address"
echo "    OpenSprinkler password hash"
echo "    LCD I2C address"
echo "    LCD columns and rows"
echo
echo "You can scan the I2C bus with:"
echo
echo "    i2cdetect -y 1"
echo
echo "To test the program interactively:"
echo
echo "    cd \"${SCRIPT_DIR}\""
echo "    source .venv/bin/activate"
echo "    python ospiLCD-mqtt.py"
echo
echo "If the interactive test works, press Ctrl+C and start the service:"
echo
echo "    sudo systemctl start ${SERVICE_NAME}"
echo
echo "Check its status with:"
echo
echo "    systemctl status ${SERVICE_NAME} --no-pager"
echo
echo "View its log with:"
echo
echo "    journalctl -u ${SERVICE_NAME} -n 50 --no-pager"
echo
echo "If everything works, enable it automatically at boot:"
echo
echo "    sudo systemctl enable ${SERVICE_NAME}"
echo