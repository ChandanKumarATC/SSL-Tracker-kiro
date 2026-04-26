# Domain & SSL Expiry Tracker

Track SSL certificate and domain registration expiry dates with automated email alerts.

## Features

- **SSL Check** — connects via TLS, extracts expiry date and detects wildcard certs
- **WHOIS Check** — fetches domain registration expiry
- **Dashboard** — dark-themed table sorted by nearest expiry, color-coded status
- **Email Alerts** — SSL alert 7 days before, domain alert 30 days before expiry
- **Scheduler** — APScheduler runs daily checks at 08:00 UTC automatically
- **CSV Export** — download all domain data as CSV
- **REST API** — full CRUD + manual check trigger

## Quick Start

```bash
# 1. Clone and enter directory
cd domain-ssl-tracker

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your DB and SMTP settings

# 5. Start the app
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`

## Project Structure

```
domain-ssl-tracker/
├── app/
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # Settings from .env
│   ├── database.py          # SQLAlchemy engine + session
│   ├── scheduler.py         # APScheduler daily job
│   ├── logging_config.py    # Rotating file + console logging
│   ├── models/
│   │   └── domain.py        # Domain SQLAlchemy model
│   ├── routes/
│   │   ├── domains.py       # REST API routes (/api/...)
│   │   └── dashboard.py     # HTML dashboard routes
│   ├── services/
│   │   ├── ssl_checker.py   # SSL cert check via socket/ssl
│   │   ├── whois_checker.py # WHOIS domain expiry check
│   │   ├── checker.py       # Orchestrates checks + alerts
│   │   ├── email_service.py # SMTP email sender
│   │   └── export_service.py# CSV export
│   ├── templates/
│   │   └── dashboard.html   # Jinja2 HTML template
│   └── static/
│       └── style.css        # Dark theme CSS
├── docs/
│   ├── deployment_aws_ec2.md
│   └── wildcard_ssl_guide.md
├── logs/                    # Created automatically
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard UI |
| POST | `/api/domains` | Add domain |
| GET | `/api/domains` | List all domains |
| PUT | `/api/domains/{id}` | Update domain |
| DELETE | `/api/domains/{id}` | Delete domain |
| POST | `/api/check-now` | Check all domains |
| POST | `/api/check-now/{id}` | Check single domain |
| GET | `/export-csv` | Download CSV |
| GET | `/docs` | Swagger UI |

## Alert Thresholds

| Type | Threshold |
|------|-----------|
| SSL Certificate | 7 days before expiry |
| Domain Registration | 30 days before expiry |

Alerts are sent once per expiry cycle. The flag resets automatically when a renewal is detected.

## Deployment

See [docs/deployment_aws_ec2.md](docs/deployment_aws_ec2.md) for full AWS EC2 Ubuntu 24 setup.

## Wildcard SSL

See [docs/wildcard_ssl_guide.md](docs/wildcard_ssl_guide.md) for free wildcard cert generation with Certbot.
