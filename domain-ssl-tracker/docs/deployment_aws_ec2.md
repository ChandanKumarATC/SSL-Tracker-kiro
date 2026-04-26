# Deployment Guide — AWS EC2 Ubuntu 24.04

## Prerequisites

- EC2 instance: Ubuntu 24.04 LTS, t3.micro or larger
- Security Group: inbound ports 22 (SSH), 80 (HTTP), 443 (HTTPS)
- Domain: `ssl.adamastech.in` pointed to your EC2 public IP (for HTTPS)

---

## Step 1 — Connect & Update Server

```bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>

sudo apt update && sudo apt upgrade -y
```

---

## Step 2 — Install Python 3.12

Ubuntu 24.04 ships with Python 3.12. Verify:

```bash
python3 --version   # should show 3.12.x
sudo apt install -y python3-pip python3-venv python3-dev
```

---

## Step 3 — Install PostgreSQL

```bash
sudo apt install -y postgresql postgresql-contrib

# Start and enable
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql << 'EOF'
CREATE USER tracker WITH PASSWORD 'strongpassword123';
CREATE DATABASE domain_tracker OWNER tracker;
GRANT ALL PRIVILEGES ON DATABASE domain_tracker TO tracker;
EOF
```

---

## Step 4 — Deploy Application

```bash
# Clone or upload your project
cd /home/ubuntu
git clone https://github.com/youruser/domain-ssl-tracker.git
# OR: scp -r ./domain-ssl-tracker ubuntu@<IP>:/home/ubuntu/

cd domain-ssl-tracker

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Step 5 — Configure Environment

```bash
cp .env.example .env
nano .env
```

Edit `.env` with your actual values:

```env
DATABASE_URL=postgresql://tracker:strongpassword123@localhost:5432/domain_tracker
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password
ALERT_FROM_EMAIL=your@gmail.com
ALERT_TO_EMAIL=alerts@yourdomain.com
APP_HOST=127.0.0.1
APP_PORT=8000
```

> **Gmail tip:** Use an App Password (not your account password).
> Enable 2FA → Google Account → Security → App Passwords.

---

## Step 6 — Run with Uvicorn (test first)

```bash
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
# Visit http://<EC2_IP>:8000 to verify (temporarily open port 8000 in SG)
# Ctrl+C when done
```

---

## Step 7 — Create Systemd Service

```bash
sudo nano /etc/systemd/system/domain-tracker.service
```

Paste:

```ini
[Unit]
Description=Domain & SSL Expiry Tracker
After=network.target postgresql.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/domain-ssl-tracker
EnvironmentFile=/home/ubuntu/domain-ssl-tracker/.env
ExecStart=/home/ubuntu/domain-ssl-tracker/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable domain-tracker
sudo systemctl start domain-tracker
sudo systemctl status domain-tracker
```

---

## Step 8 — Install & Configure Nginx

```bash
sudo apt install -y nginx

sudo nano /etc/nginx/sites-available/domain-tracker
```

Paste (replace `yourdomain.com`):

```nginx
server {
    listen 80;
    server_name ssl.adamastech.in;

    location / {
        proxy_pass         http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/domain-tracker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

---

## Step 9 — HTTPS with Let's Encrypt

```bash
sudo apt install -y certbot python3-certbot-nginx

sudo certbot --nginx -d ssl.adamastech.in

# Auto-renewal is set up automatically; verify:
sudo systemctl status certbot.timer
```

---

## Step 10 — Optional Cron Job (backup scheduler)

The app uses APScheduler internally. If you prefer a system cron as a backup:

```bash
crontab -e
```

Add:

```cron
# Run domain/SSL check daily at 08:00 UTC
0 8 * * * /home/ubuntu/domain-ssl-tracker/venv/bin/python -c "
from app.database import SessionLocal
from app.services.checker import run_all_checks
db = SessionLocal()
run_all_checks(db)
db.close()
" >> /home/ubuntu/domain-ssl-tracker/logs/cron.log 2>&1
```

---

## Step 11 — Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## Useful Commands

```bash
# View app logs
sudo journalctl -u domain-tracker -f

# Restart app after code update
cd /home/ubuntu/domain-ssl-tracker
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart domain-tracker

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
```

---

## Running Locally (Replit / Dev)

```bash
# Install deps
pip install -r requirements.txt

# Copy and edit env
cp .env.example .env

# Start app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000` in your browser.
