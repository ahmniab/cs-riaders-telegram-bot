#!/usr/bin/env bash

set -Eeuo pipefail

BOT_USER="botuser"
BOT_HOME="/home/${BOT_USER}"
APP_DIR="${BOT_HOME}/app"
VENV_DIR="${APP_DIR}/.venv"
SERVICE_DIR="${BOT_HOME}/.config/systemd/user"
SERVICE_FILE="${SERVICE_DIR}/bot.service"

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root, for example: sudo ./setup_server.sh" >&2
    exit 1
fi

if ! id "${BOT_USER}" >/dev/null 2>&1; then
    useradd --create-home --shell /bin/bash "${BOT_USER}"
fi

loginctl enable-linger "${BOT_USER}"

install -d -o "${BOT_USER}" -g "${BOT_USER}" -m 0755 \
    "${APP_DIR}" \
    "${SERVICE_DIR}"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    python3 -m venv "${VENV_DIR}"
fi

install -o "${BOT_USER}" -g "${BOT_USER}" -m 0600 /dev/null "${BOT_HOME}/.env"

cat > "${SERVICE_FILE}" <<'EOF'
[Unit]
Description=CS Raiders Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/botuser/app
EnvironmentFile=/home/botuser/.env
ExecStart=/home/botuser/app/.venv/bin/python /home/botuser/app/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

chown "${BOT_USER}:${BOT_USER}" "${SERVICE_FILE}"
chmod 0644 "${SERVICE_FILE}"
chown -R "${BOT_USER}:${BOT_USER}" "${APP_DIR}" "${BOT_HOME}/.config"
chmod 0700 "${BOT_HOME}/.config" "${BOT_HOME}/.config/systemd" "${SERVICE_DIR}"
chmod 0600 "${BOT_HOME}/.env"

echo
echo "Server setup complete. The application directory is ${APP_DIR}."
echo "Copy or deploy the repository there, then run these commands as ${BOT_USER}:"
echo
echo "  systemctl --user daemon-reload"
echo "  systemctl --user enable bot.service"
echo "  systemctl --user start bot.service"
echo "  systemctl --user status bot.service"
echo
echo "The deployment workflow will maintain ${BOT_HOME}/.env and restart the service."