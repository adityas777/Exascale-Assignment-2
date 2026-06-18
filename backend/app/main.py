import os
from datetime import date, datetime, timedelta
from typing import List, Optional

timedelta_one_day = timedelta(days=1)

from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from .database import engine, get_db, init_db
from .models import (
    EmissionFactor,
    EmissionRecord,
    AuditLog,
    BusinessMetric,
    EmissionRecordCreate,
    EmissionRecordResponse,
    OverrideRequest,
    AuditLogResponse,
    BusinessMetricCreate,
    BusinessMetricResponse,
    EmissionFactorResponse
)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Carbon Emissions Reporting Platform API",
    description="Backend API for Exascale GHG Emissions Reporting Platform Prototype",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Endpoints ---

# 1. Create and Read Emission Factors
@app.get("/api/emission-factors", response_model=List[EmissionFactorResponse])
def get_emission_factors(db: Session = Depends(get_db)):
    return db.query(EmissionFactor).all()


# 2. Create and Read Emission Records (Milestone 3)
@app.post("/api/emission-records", response_model=EmissionRecordResponse, status_code=status.HTTP_201_CREATED)
def create_emission_record(record_in: EmissionRecordCreate, db: Session = Depends(get_db)):
    # 1. Resolve Emission Factor based on date (Historical Accuracy - Milestone 2)
    # Filter factors where activity_type matches, start_date <= record_date, and (end_date is None or end_date >= record_date)
    factor = db.query(EmissionFactor).filter(
        EmissionFactor.activity_type == record_in.activity_type,
        EmissionFactor.start_date <= record_in.date,
        or_(
            EmissionFactor.end_date.is_(None),
            EmissionFactor.end_date >= record_in.date
        )
    ).first()

    if not factor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No valid emission factor found for activity '{record_in.activity_type}' on date {record_in.date}."
        )

    # 2. Calculate emissions: Activity Data * Factor (in kgCO2e)
    calculated_emissions = record_in.activity_data * factor.co2e_factor

    # 4. Create record
    db_record = EmissionRecord(
        activity_type=record_in.activity_type,
        scope=factor.scope,
        activity_data=record_in.activity_data,
        unit=record_in.unit,
        date=record_in.date,
        location=record_in.location,
        section=record_in.section,
        emission_factor_id=factor.id,
        calculated_emissions=calculated_emissions,
        is_overridden=False
    )
    db.add(db_record)
    db.commit()
    db.refresh(db_record)
    return db_record


@app.get("/api/emission-records", response_model=List[EmissionRecordResponse])
def get_emission_records(
    scope: Optional[int] = Query(None, description="Filter by scope (1, 2, or 3)"),
    location: Optional[str] = Query(None, description="Filter by location"),
    db: Session = Depends(get_db)
):
    query = db.query(EmissionRecord)
    if scope is not None:
        query = query.filter(EmissionRecord.scope == scope)
    if location is not None:
        query = query.filter(EmissionRecord.location == location)
    
    return query.order_by(EmissionRecord.date.desc()).all()


# 3. Manual Override with Audit Trail (Milestone 3)
@app.put("/api/emission-records/{record_id}/override", response_model=EmissionRecordResponse)
def override_emission_record(record_id: int, override_in: OverrideRequest, db: Session = Depends(get_db)):
    record = db.query(EmissionRecord).filter(EmissionRecord.id == record_id).first()
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Emission record with ID {record_id} not found."
        )

    # Determine old value
    old_val = record.override_emissions if record.is_overridden else record.calculated_emissions

    # Create Audit Log entry
    audit_log = AuditLog(
        record_id=record.id,
        changed_by="System Admin",
        old_value=old_val,
        new_value=override_in.override_emissions,
        justification=override_in.justification,
        timestamp=datetime.utcnow()
    )
    db.add(audit_log)

    # Update emission record
    record.override_emissions = override_in.override_emissions
    record.is_overridden = True
    record.override_justification = override_in.justification

    db.commit()
    db.refresh(record)
    return record


@app.get("/api/audit-logs", response_model=List[AuditLogResponse])
def get_audit_logs(db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.timestamp.desc()).all()


# 4. Create and Read Business Metrics (Milestone 1)
@app.post("/api/business-metrics", response_model=BusinessMetricResponse, status_code=status.HTTP_201_CREATED)
def create_business_metric(metric_in: BusinessMetricCreate, db: Session = Depends(get_db)):
    db_metric = BusinessMetric(
        date=metric_in.date,
        metric_name=metric_in.metric_name,
        value=metric_in.value,
        unit=metric_in.unit
    )
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric


@app.get("/api/business-metrics", response_model=List[BusinessMetricResponse])
def get_business_metrics(db: Session = Depends(get_db)):
    return db.query(BusinessMetric).order_by(BusinessMetric.date.desc()).all()


# --- Analytics & Reporting Engine (Milestone 2) ---

# A. Year-over-Year (YoY) Emissions API
@app.get("/api/analytics/yoy")
def get_yoy_emissions(
    year: int = Query(2024, description="The year to compare against the previous year"),
    db: Session = Depends(get_db)
):
    # YoY requires comparing year and year-1
    prev_year = year - 1

    def calculate_year_scope_emissions(y: int, s: int) -> float:
        records = db.query(EmissionRecord).filter(
            EmissionRecord.date >= date(y, 1, 1),
            EmissionRecord.date <= date(y, 12, 31),
            EmissionRecord.scope == s
        ).all()
        
        total = 0.0
        for r in records:
            total += r.override_emissions if r.is_overridden else r.calculated_emissions
        return total

    # Sum for Scope 1 and Scope 2
    s1_curr = calculate_year_scope_emissions(year, 1)
    s1_prev = calculate_year_scope_emissions(prev_year, 1)

    s2_curr = calculate_year_scope_emissions(year, 2)
    s2_prev = calculate_year_scope_emissions(prev_year, 2)

    # Optional: Include Scope 3 as well if present
    s3_curr = calculate_year_scope_emissions(year, 3)
    s3_prev = calculate_year_scope_emissions(prev_year, 3)

    return {
        "current_year": year,
        "previous_year": prev_year,
        "scopes": [
            {
                "scope": 1,
                "label": "Scope 1 (Direct)",
                "current_emissions": round(s1_curr, 2),
                "previous_emissions": round(s1_prev, 2),
                "change_absolute": round(s1_curr - s1_prev, 2),
                "change_percent": round(((s1_curr - s1_prev) / s1_prev * 100) if s1_prev > 0 else 0.0, 2)
            },
            {
                "scope": 2,
                "label": "Scope 2 (Indirect)",
                "current_emissions": round(s2_curr, 2),
                "previous_emissions": round(s2_prev, 2),
                "change_absolute": round(s2_curr - s2_prev, 2),
                "change_percent": round(((s2_curr - s2_prev) / s2_prev * 100) if s2_prev > 0 else 0.0, 2)
            },
            {
                "scope": 3,
                "label": "Scope 3 (Value Chain)",
                "current_emissions": round(s3_curr, 2),
                "previous_emissions": round(s3_prev, 2),
                "change_absolute": round(s3_curr - s3_prev, 2),
                "change_percent": round(((s3_curr - s3_prev) / s3_prev * 100) if s3_prev > 0 else 0.0, 2)
            }
        ]
    }


# B. Emission Intensity API
@app.get("/api/analytics/intensity")
def get_emission_intensity(
    year: int = Query(2024, description="The year to calculate intensity for"),
    metric_name: str = Query("Tons of Steel Produced", description="The business metric to use as denominator"),
    db: Session = Depends(get_db)
):
    monthly_data = []
    total_emissions_year = 0.0
    total_metric_value_year = 0.0
    metric_unit = "units"

    # We evaluate for months 1 to 12
    for m in range(1, 13):
        start_dt = date(year, m, 1)
        # Determine end of month
        if m == 12:
            end_dt = date(year, 12, 31)
        else:
            end_dt = date(year, m + 1, 1) - timedelta_one_day

        # Calculate monthly emissions (Scope 1 + Scope 2)
        records = db.query(EmissionRecord).filter(
            EmissionRecord.date >= start_dt,
            EmissionRecord.date <= end_dt,
            EmissionRecord.scope.in_([1, 2])
        ).all()

        m_emissions = 0.0
        for r in records:
            m_emissions += r.override_emissions if r.is_overridden else r.calculated_emissions

        # Get business metric value for this month
        metric = db.query(BusinessMetric).filter(
            BusinessMetric.date >= start_dt,
            BusinessMetric.date <= end_dt,
            BusinessMetric.metric_name == metric_name
        ).first()

        m_metric_val = metric.value if metric else 0.0
        if metric:
            metric_unit = metric.unit

        intensity = (m_emissions / m_metric_val) if m_metric_val > 0 else 0.0

        monthly_data.append({
            "month": f"{year}-{m:02d}",
            "emissions_kgCO2e": round(m_emissions, 2),
            "metric_value": m_metric_val,
            "intensity_kgCO2e_per_unit": round(intensity, 4)
        })

        total_emissions_year += m_emissions
        if metric_name == "Employees":
            # For employees, the total is the average across reporting months
            if m_metric_val > 0:
                total_metric_value_year += m_metric_val
        else:
            # For production metrics, we sum
            total_metric_value_year += m_metric_val

    # Calculate annual summary
    if metric_name == "Employees":
        # Average
        active_months = sum(1 for d in monthly_data if d["metric_value"] > 0)
        avg_metric_value = (total_metric_value_year / active_months) if active_months > 0 else 0.0
        annual_intensity = (total_emissions_year / avg_metric_value) if avg_metric_value > 0 else 0.0
        total_metric_value_year = avg_metric_value
    else:
        annual_intensity = (total_emissions_year / total_metric_value_year) if total_metric_value_year > 0 else 0.0

    return {
        "year": year,
        "metric_name": metric_name,
        "unit": metric_unit,
        "annual_summary": {
            "total_emissions_kgCO2e": round(total_emissions_year, 2),
            "total_metric_value": round(total_metric_value_year, 2),
            "intensity_kgCO2e_per_unit": round(annual_intensity, 4)
        },
        "monthly_breakdown": monthly_data
    }


# C. Emission Hotspot API
@app.get("/api/analytics/hotspot")
def get_emission_hotspots(
    year: int = Query(2024, description="The year to analyze hotspots for"),
    scope: Optional[int] = Query(None, description="Optional filter by Scope"),
    db: Session = Depends(get_db)
):
    query = db.query(EmissionRecord).filter(
        EmissionRecord.date >= date(year, 1, 1),
        EmissionRecord.date <= date(year, 12, 31)
    )
    if scope is not None:
        query = query.filter(EmissionRecord.scope == scope)
    
    records = query.all()

    source_totals = {}
    total_emissions = 0.0

    for r in records:
        val = r.override_emissions if r.is_overridden else r.calculated_emissions
        source_totals[r.activity_type] = source_totals.get(r.activity_type, 0.0) + val
        total_emissions += val

    hotspots = []
    for source, val in source_totals.items():
        pct = (val / total_emissions * 100.0) if total_emissions > 0 else 0.0
        
        # Find scope and unit of this source
        scope_found = 1
        unit_found = ""
        for r in records:
            if r.activity_type == source:
                scope_found = r.scope
                unit_found = r.unit
                break

        hotspots.append({
            "source": source,
            "scope": scope_found,
            "unit": unit_found,
            "emissions_kgCO2e": round(val, 2),
            "percentage": round(pct, 2)
        })

    # Sort descending
    hotspots.sort(key=lambda x: x["emissions_kgCO2e"], reverse=True)
    return {
        "year": year,
        "total_emissions_kgCO2e": round(total_emissions, 2),
        "hotspots": hotspots
    }


# D. Monthly Trend Line Chart API (tracks total monthly emissions over a year)
@app.get("/api/analytics/monthly-trend")
def get_monthly_trend(
    year: int = Query(2024, description="The year to get monthly trend for"),
    db: Session = Depends(get_db)
):
    monthly_data = []
    for m in range(1, 13):
        start_dt = date(year, m, 1)
        if m == 12:
            end_dt = date(year, 12, 31)
        else:
            end_dt = date(year, m + 1, 1) - timedelta_one_day

        records = db.query(EmissionRecord).filter(
            EmissionRecord.date >= start_dt,
            EmissionRecord.date <= end_dt
        ).all()

        s1_val = 0.0
        s2_val = 0.0
        s3_val = 0.0

        for r in records:
            val = r.override_emissions if r.is_overridden else r.calculated_emissions
            if r.scope == 1:
                s1_val += val
            elif r.scope == 2:
                s2_val += val
            elif r.scope == 3:
                s3_val += val

        monthly_data.append({
            "month": f"{year}-{m:02d}",
            "scope1": round(s1_val, 2),
            "scope2": round(s2_val, 2),
            "scope3": round(s3_val, 2),
            "total": round(s1_val + s2_val + s3_val, 2)
        })

    return monthly_data


# Serve Frontend
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "frontend")
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def read_index():
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Carbon Emissions Reporting Platform Backend Running. Frontend folder not found yet."}
