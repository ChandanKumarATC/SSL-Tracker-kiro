from sqlalchemy import Column, Integer, String
from app.database import Base


class Setting(Base):
    """Key-value store for app settings (SMTP, alert thresholds, etc.)
    Persisted in DB so changes survive restarts without editing .env."""
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, nullable=False, index=True)
    value = Column(String, nullable=True)
