from datetime import date as dt_date, datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

from .database import Base

# --- SQLAlchemy Models ---

class EmissionFactor(Base):
    __tablename__ = "emission_factors"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    activity_type = Column(String, index=True, nullable=False)
    scope = Column(Integer, nullable=False)  # 1, 2, or 3
    unit = Column(String, nullable=False)
    co2e_factor = Column(Float, nullable=False)  # kgCO2e per unit
    source = Column(String, nullable=True)
    start_date = Column(Date, nullable=False)  # validity start
    end_date = Column(Date, nullable=True)    # validity end (null means currently active)

    records = relationship("EmissionRecord", back_populates="emission_factor")


class EmissionRecord(Base):
    __tablename__ = "emission_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    activity_type = Column(String, index=True, nullable=False)
    scope = Column(Integer, nullable=False)
    activity_data = Column(Float, nullable=False)
    unit = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    location = Column(String, nullable=False)
    section = Column(String, nullable=False)
    emission_factor_id = Column(Integer, ForeignKey("emission_factors.id"), nullable=False)
    calculated_emissions = Column(Float, nullable=False)  # in kgCO2e
    override_emissions = Column(Float, nullable=True)     # overridden value in kgCO2e
    is_overridden = Column(Boolean, default=False, nullable=False)
    override_justification = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    emission_factor = relationship("EmissionFactor", back_populates="records")
    audit_logs = relationship("AuditLog", back_populates="emission_record", cascade="all, delete-orphan")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    record_id = Column(Integer, ForeignKey("emission_records.id"), nullable=False)
    changed_by = Column(String, nullable=False, default="System User")
    old_value = Column(Float, nullable=False)
    new_value = Column(Float, nullable=False)
    justification = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    emission_record = relationship("EmissionRecord", back_populates="audit_logs")


class BusinessMetric(Base):
    __tablename__ = "business_metrics"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    date = Column(Date, nullable=False)
    metric_name = Column(String, index=True, nullable=False)  # e.g., 'Tons of Steel Produced', 'Employees'
    value = Column(Float, nullable=False)
    unit = Column(String, nullable=False)


# --- Pydantic Schemas for API Requests/Responses ---

class EmissionFactorBase(BaseModel):
    activity_type: str
    scope: int
    unit: str
    co2e_factor: float
    source: Optional[str] = None
    start_date: dt_date
    end_date: Optional[dt_date] = None

class EmissionFactorCreate(EmissionFactorBase):
    pass

class EmissionFactorResponse(EmissionFactorBase):
    id: int

    class Config:
        from_attributes = True


class EmissionRecordCreate(BaseModel):
    activity_type: str
    activity_data: float
    unit: str
    date: dt_date
    location: str
    section: str

class EmissionRecordResponse(BaseModel):
    id: int
    activity_type: str
    scope: int
    activity_data: float
    unit: str
    date: dt_date
    location: str
    section: str
    emission_factor_id: int
    calculated_emissions: float
    override_emissions: Optional[float]
    is_overridden: bool
    override_justification: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class OverrideRequest(BaseModel):
    override_emissions: float = Field(..., description="The manual override emissions value in kgCO2e")
    justification: str = Field(..., min_length=5, description="Explanation for the override")


class AuditLogResponse(BaseModel):
    id: int
    record_id: int
    changed_by: str
    old_value: float
    new_value: float
    justification: str
    timestamp: datetime

    class Config:
        from_attributes = True


class BusinessMetricCreate(BaseModel):
    date: dt_date
    metric_name: str
    value: float
    unit: str

class BusinessMetricResponse(BusinessMetricCreate):
    id: int

    class Config:
        from_attributes = True
