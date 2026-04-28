"""
Settings service — reads/writes SMTP and alert config from the DB.
Falls back to environment variables (config.py) when no DB value exists.
"""
from sqlalchemy.orm import Session
from app.models.settings import Setting
import app.config as cfg

# Keys stored in the settings table
SETTING_KEYS = [
    "smtp_host",
    "smtp_port",
    "smtp_user",
    "smtp_password",
    "alert_from_email",
    "alert_to_email",
    "ssl_alert_days",
    "domain_alert_days",
]

# Defaults pulled from config.py / .env
DEFAULTS = {
    "smtp_host":         cfg.SMTP_HOST,
    "smtp_port":         str(cfg.SMTP_PORT),
    "smtp_user":         cfg.SMTP_USER,
    "smtp_password":     cfg.SMTP_PASSWORD,
    "alert_from_email":  cfg.ALERT_FROM_EMAIL,
    "alert_to_email":    cfg.ALERT_TO_EMAIL,
    "ssl_alert_days":    str(cfg.SSL_ALERT_DAYS),
    "domain_alert_days": str(cfg.DOMAIN_ALERT_DAYS),
}


def get_all(db: Session) -> dict:
    """Return all settings as a dict, merging DB values over defaults."""
    rows = db.query(Setting).all()
    result = dict(DEFAULTS)  # start with defaults
    for row in rows:
        result[row.key] = row.value or ""
    return result


def get(db: Session, key: str) -> str:
    """Get a single setting value."""
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        return row.value or ""
    return DEFAULTS.get(key, "")


def save_all(db: Session, data: dict) -> None:
    """Upsert all provided key-value pairs into the settings table."""
    for key, value in data.items():
        if key not in SETTING_KEYS:
            continue
        row = db.query(Setting).filter(Setting.key == key).first()
        if row:
            row.value = value
        else:
            db.add(Setting(key=key, value=value))
    db.commit()
