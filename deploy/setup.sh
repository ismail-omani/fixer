#!/usr/bin/env bash
set -euo pipefail

APP_NAME="fixer"
APP_DIR="/opt/$APP_NAME"
VENV="$APP_DIR/.venv"
SERVICE="$APP_NAME.service"
DOMAIN="${1:-}"
EMAIL="${2:-}"

echo "=== Fixer — Oracle Cloud Setup ==="

# --- 1. System deps ---
echo "[1/7] Installing system packages..."
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip nginx certbot python3-certbot-nginx > /dev/null

# --- 2. App directory ---
echo "[2/7] Setting up $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r ./*.py ./*.txt "$APP_DIR/" 2>/dev/null || true
cp -r ./static ./templates "$APP_DIR/" 2>/dev/null || true
cp -r ./deploy "$APP_DIR/" 2>/dev/null || true
cp ./.env.example "$APP_DIR/.env" 2>/dev/null || true
mkdir -p "$APP_DIR/tasks" "$APP_DIR/u"

# --- 3. Python venv + deps ---
echo "[3/7] Creating Python venv..."
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip -q
"$VENV/bin/pip" install -r "$APP_DIR/requirements.txt" -q

# --- 4. systemd service ---
echo "[4/7] Installing systemd service..."
cat > "/etc/systemd/system/$SERVICE" <<UNIT
[Unit]
Description=Fixer task forum
After=network.target

[Service]
Type=exec
WorkingDirectory=$APP_DIR
ExecStart=$VENV/bin/gunicorn app:app -c gunicorn.conf.py
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
UNIT

systemctl daemon-reload
systemctl enable "$SERVICE"
systemctl restart "$SERVICE"

# --- 5. Nginx reverse proxy ---
echo "[5/7] Configuring nginx..."
if [ -n "$DOMAIN" ]; then
    cat > /etc/nginx/sites-available/$APP_NAME <<NGINX
server {
    listen 80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
        client_max_body_size 35M;
    }
}
NGINX
else
    cat > /etc/nginx/sites-available/$APP_NAME <<NGINX
server {
    listen 80 default_server;
    server_name _;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 120s;
        client_max_body_size 35M;
    }
}
NGINX
fi

ln -sf /etc/nginx/sites-available/$APP_NAME /etc/nginx/sites-enabled/$APP_NAME
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx

# --- 6. SSL via Let's Encrypt ---
if [ -n "$DOMAIN" ] && [ -n "$EMAIL" ]; then
    echo "[6/7] Obtaining SSL certificate..."
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos -m "$EMAIL" || echo "  certbot failed — run manually later"
else
    echo "[6/7] Skipping SSL (no domain/email provided)"
fi

# --- 7. Done ---
echo "[7/7] Setup complete!"
echo ""
echo "App:     http://${DOMAIN:-<server-ip>}"
echo "Gunicorn: http://127.0.0.1:8000"
echo "Service:  systemctl status $SERVICE"
echo "Logs:     journalctl -u $SERVICE -f"
