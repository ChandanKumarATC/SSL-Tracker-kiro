from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from app.database import Base


class Domain(Base):
    __tablename__ = "domains"

    id = Column(Integer, primary_key=True, index=True)
    domain_name = Column(String, unique=True, nullable=False, index=True)

    # SSL info
    ssl_expiry_date = Column(DateTime, nullable=True)
    ssl_type = Column(String, nullable=True)       # "wildcard" or "single"
    ssl_issuer = Column(String, nullable=True)     # e.g. "Let's Encrypt R13"
    ssl_error = Column(String, nullable=True)      # last SSL check error message

    # Domain/WHOIS info
    domain_expiry_date = Column(DateTime, nullable=True)

    # Tracking
    last_checked = Column(DateTime, nullable=True)

    # Alert flags — reset when expiry date changes (renewal detected)
    alert_sent_ssl = Column(Boolean, default=False, nullable=False)
    alert_sent_domain = Column(Boolean, default=False, nullable=False)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
