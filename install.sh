#!/bin/bash

set -e

SERVICE_NAME="ospilcd"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(id -un)"
VENV_DIR="${SCRIPT_DIR}/.venv"
CONFIG_FILE="${SCRIPT_DIR}/ospilcd.ini"
CONFIG_EXAMPLE="${SCRIPT_DIR}/ospilcd.ini.example"
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

if [[ "${EUID}" -eq 0 ]]; then
    echo "ERROR: Do not run this entire script with sudo."
    echo
    echo "Run it as your normal user:"
    echo
    echo "    ./install.sh"
    echo
    exit 1
fi


echo "[1/7] Checking required system packages..."

sudo apt update

sudo apt install -y \
    python3 \
    python3-venv \
    i2c-tools


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


echo
echo "[3/7] Creating Python virtual environment..."

if [[ ! -d "${VENV_DIR}" ]]; then
    python3 -m venv "${VENV_DIR}"
    echo "Created ${VENV_DIR}"
else
    echo "Existing virtual environment found."
fi


echo
echo "[4/7] Installing Python requirements..."

"${VENV_DIR}/bin/python" -m pip install --upgrade pip
"${VENV_DIR}/bin/python" -m pip install -r "${SCRIPT_DIR}/requirements.txt"


echo
echo "[5/7] Checking local configuration..."

if [[ ! -f "${CONFIG_FILE}" ]]; then
    cp "${CONFIG_EXAMPLE}" "${CONFIG_FILE}"

    echo
    echo "Created:"
    echo
    echo "    ${CONFIG_FILE}"
    echo
    echo "You MUST edit this file for your installation."
else
    echo "Existing ospilcd.ini found."
    echo "It has NOT been changed."
fi


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
ExecStart=${VENV_DIR}/bin/python ${SCRIPT_DIR}/ospiLCD-mqtt.py

Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload


echo
echo "[7/7] Installation complete."
echo
echo "Before starting the service, edit:"
echo
echo "    ${CONFIG_FILE}"
echo
echo "At minimum verify:"
echo
echo "    OpenSprinkler password hash"
echo "    LCD I2C address"
echo "    LCD columns and rows"
echo
echo
echo "You can scan the I2C bus with:"
echo
echo "    i2cdetect -y 1"
echo
echo
echo "Then start ospiLCD-mqtt with:"
echo
echo "    sudo systemctl start ${SERVICE_NAME}"
echo
echo "Check its status with:"
echo
echo "    systemctl status ${SERVICE_NAME}"
echo
echo "If everything works, enable it at boot with:"
echo
echo "    sudo systemctl enable ${SERVICE_NAME}"
echo