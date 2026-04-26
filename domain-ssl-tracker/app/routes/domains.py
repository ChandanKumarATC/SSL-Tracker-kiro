from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.models.domain import Domain
from app.services.checker import run_all_checks, check_and_update_domain

router = APIRouter()


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class DomainCreate(BaseModel):
    domain_name: str

    @field_validator("domain_name")
    @classmethod
    def clean_domain(cls, v: str) -> str:
        # Strip protocol and trailing slashes
        v = v.strip().lower()
        v = v.replace("https://", "").replace("http://", "").split("/")[0]
        if not v or "." not in v:
            raise ValueError("Invalid domain name")
        return v


class DomainUpdate(BaseModel):
    domain_name: Optional[str] = None
    ssl_expiry_date: Optional[datetime] = None
    ssl_type: Optional[str] = None
    domain_expiry_date: Optional[datetime] = None
    alert_sent_ssl: Optional[bool] = None
    alert_sent_domain: Optional[bool] = None


class DomainResponse(BaseModel):
    id: int
    domain_name: str
    ssl_expiry_date: Optional[datetime]
    ssl_type: Optional[str]
    ssl_issuer: Optional[str]
    ssl_error: Optional[str]
    domain_expiry_date: Optional[datetime]
    last_checked: Optional[datetime]
    alert_sent_ssl: bool
    alert_sent_domain: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
def add_domain(payload: DomainCreate, db: Session = Depends(get_db)):
    """Add a new domain to track."""
    existing = db.query(Domain).filter(Domain.domain_name == payload.domain_name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Domain already exists")

    domain = Domain(domain_name=payload.domain_name)
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


@router.get("/domains", response_model=list[DomainResponse])
def list_domains(db: Session = Depends(get_db)):
    """List all tracked domains."""
    return db.query(Domain).order_by(Domain.domain_name).all()


@router.put("/domains/{domain_id}", response_model=DomainResponse)
def update_domain(domain_id: int, payload: DomainUpdate, db: Session = Depends(get_db)):
    """Update domain fields manually."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(domain, field, value)

    db.commit()
    db.refresh(domain)
    return domain


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(domain_id: int, db: Session = Depends(get_db)):
    """Delete a domain from tracking."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    db.delete(domain)
    db.commit()


@router.post("/check-now")
def check_now(db: Session = Depends(get_db)):
    """Manually trigger expiry checks for all domains."""
    results = run_all_checks(db)
    return {"message": f"Checked {len(results)} domains", "results": results}


@router.post("/check-now/{domain_id}")
def check_single(domain_id: int, db: Session = Depends(get_db)):
    """Manually trigger expiry check for a single domain."""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="Domain not found")

    result = check_and_update_domain(db, domain)
    return {"message": "Check complete", "result": result}
