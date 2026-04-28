# Complete Deployment Guide — AWS EC2 Ubuntu 24.04

---

## PART 1 — Launch EC2 Instance

### Step 1.1 — Create EC2 instance
1. Go to AWS Console → EC2 → Launch Instance
2. Name: `ssl-tracker`
3. AMI: **Ubuntu Server 24.04 LTS**
4. Instance type: `t3.micro` (free tier) or `t3.small`
5. Key pair: Create new → name it `ssl-tracker-key` → Download `.pem` file
6. Network settings → Edit:
   - Allow SSH (port 22) — My IP
   - Allow HTTP (port 80) — Anywhere
   - Allow HTTPS (port 443) — Anywhere
7. Storage: 20 GB gp3
8. Click **Launch Instance**

### Step 1.2 — Point your domain to EC2
Go to your DNS provider and add an **A record**:
```
Type : A
Name : ssl          (for ssl.adamastech.in)
Value: <EC2 Public IP>
TTL  : 300
```

---

## PART 2 — Connect to Server

### Step 2.1 — Fix key permissions (run on your local machine)
```bash
chmod 400 ssl-tracker-key.pem
```

### Step 2.2 — SSH into the server
```bash
ssh -i ssl-tracker-key.pem ubuntu@<EC2_PUBLIC_IP>
```

---

## PART 3 — Server Setup

### Step 3.1 — Update system packages
```bash
sudo apt update && sudo apt upgrade -y
```

### Step 3.2 — Install Python and tools
```bash
sudo apt install -y python3-pip python3-venv python3-dev build-essential
```

Verify:
```bash
python3 --version    # should show 3.12.x
```

### Step 3.3 — Install PostgreSQL
```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

### Step 3.4 — Create database and user
```bash
sudo -u postgres psql
```

Inside the psql prompt, run:
```sql
CREATE USER tracker WITH PASSWORD 'Ssl@123';
CREATE DATABASE domain_tracker OWNER tracker;
GRANT ALL PRIVILEGES ON DATABASE domain_tracker TO tracker;
\q
```

### Step 3.5 — Install Nginx
```bash
sudo apt install -y nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

---

## PART 4 — Deploy Application

### Step 4.1 — Clone from GitHub
```bash
cd /home/ubuntu
git clone https://github.com/ChandanKumarATC/SSL-Tracker-kiro.git domain-ssl-tracker
cd domain-ssl-tracker
```

### Step 4.2 — Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 4.3 — Install dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 4.4 — Create .env file
```bash
cp .env.example .env
nano .env
```

Fill in your values:
```env
DATABASE_URL=postgresql://tracker:StrongPassword123!@localhost:5432/domain_tracker

SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your@gmail.com
SMTP_PASSWORD=your_app_password_here
ALERT_FROM_EMAIL=your@gmail.com
ALERT_TO_EMAIL=alerts@yourdomain.com

APP_HOST=127.0.0.1
APP_PORT=8000
```

Save and exit: `Ctrl+X` → `Y` → `Enter`

> **Gmail App Password:** Go to myaccount.google.com → Security → 2-Step Verification → App Passwords → Generate one for "Mail"

### Step 4.5 — Test the app manually first
```bash
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

You should see:
```
INFO: Application startup complete.
```

Press `Ctrl+C` to stop.

---

## PART 5 — Systemd Service (keep app running)

### Step 5.1 — Create service file
```bash
sudo nano /etc/systemd/system/domain-tracker.service
```

Paste this exactly:
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

Save: `Ctrl+X` → `Y` → `Enter`

### Step 5.2 — Enable and start the service
```bash
sudo systemctl daemon-reload
sudo systemctl enable domain-tracker
sudo systemctl start domain-tracker
```

### Step 5.3 — Check it is running
```bash
sudo systemctl status domain-tracker
```

You should see `Active: active (running)` in green.

---

## PART 6 — Nginx Reverse Proxy

### Step 6.1 — Create Nginx config
```bash
sudo nano /etc/nginx/sites-available/domain-tracker
```

Paste (replace `ssl.adamastech.in` if your domain is different):
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

### Step 6.2 — Enable the site
```bash
sudo ln -s /etc/nginx/sites-available/domain-tracker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

`nginx -t` should say `syntax is ok` and `test is successful`.

### Step 6.3 — Test HTTP access
Open in browser: `http://ssl.adamastech.in`
You should see the dashboard.

---

## PART 7 — HTTPS with Let's Encrypt (Free SSL)

### Step 7.1 — Install Certbot
```bash
sudo apt install -y certbot python3-certbot-nginx
```

### Step 7.2 — Get SSL certificate
```bash
sudo certbot --nginx -d ssl.adamastech.in
```

Follow the prompts:
- Enter your email address
- Agree to terms: `Y`
- Share email with EFF (optional): `N`
- Certbot will automatically update your Nginx config for HTTPS

### Step 7.3 — Verify auto-renewal
```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

Both should succeed without errors.

---

## PART 8 — Firewall

```bash
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

Expected output:
```
Status: active
To                         Action      From
--                         ------      ----
OpenSSH                    ALLOW       Anywhere
Nginx Full                 ALLOW       Anywhere
```

---

## PART 9 — Verify Everything Works

```bash
# App service running?
sudo systemctl status domain-tracker

# Nginx running?
sudo systemctl status nginx

# PostgreSQL running?
sudo systemctl status postgresql

# App logs (live)
sudo journalctl -u domain-tracker -f
```

Open `https://ssl.adamastech.in` — you should see the dashboard over HTTPS.

---

## PART 10 — Update App (after code changes)

Every time you push new code to GitHub, run this on the server:

```bash
cd /home/ubuntu/domain-ssl-tracker
git pull origin master
source venv/bin/activate
pip install -r requirements.txt   # only needed if requirements changed
sudo systemctl restart domain-tracker
```

---

## PART 11 — Useful Commands

| Task | Command |
|------|---------|
| View live app logs | `sudo journalctl -u domain-tracker -f` |
| Restart app | `sudo systemctl restart domain-tracker` |
| Stop app | `sudo systemctl stop domain-tracker` |
| Restart Nginx | `sudo systemctl restart nginx` |
| View Nginx errors | `sudo tail -f /var/log/nginx/error.log` |
| View app log file | `tail -f /home/ubuntu/domain-ssl-tracker/logs/app.log` |
| Connect to database | `sudo -u postgres psql -d domain_tracker` |
| Check open ports | `sudo ss -tlnp` |

---

## PART 12 — Troubleshooting

**App not starting?**
```bash
sudo journalctl -u domain-tracker -n 50 --no-pager
```
Look for Python errors — usually a missing `.env` value or DB connection issue.

**502 Bad Gateway in browser?**
```bash
sudo systemctl status domain-tracker   # is the app running?
sudo systemctl restart domain-tracker
```

**Database connection error?**
```bash
# Test connection manually
sudo -u postgres psql -d domain_tracker -c "\dt"
# Should show the 'domains' table
```

**SSL certificate not renewing?**
```bash
sudo certbot renew --dry-run
sudo systemctl restart certbot.timer
```

**Port 8000 already in use?**
```bash
sudo ss -tlnp | grep 8000
sudo kill -9 <PID>
sudo systemctl start domain-tracker
```
