import os
import pandas as pd
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session

from .database import engine, init_db, SessionLocal
from .models import EmissionFactor, EmissionRecord, BusinessMetric

EXCEL_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "GHG Sheet .xlsx")

def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()

def seed_data():
    db = SessionLocal()
    try:
        # Clear existing tables
        db.query(EmissionRecord).delete()
        db.query(EmissionFactor).delete()
        db.query(BusinessMetric).delete()
        db.commit()

        print("Reading Excel file...")
        xl = pd.ExcelFile(EXCEL_FILE)

        # ----------------------------------------------------
        # 1. Parse and seed Emission Factors
        # ----------------------------------------------------
        factors_map = {}  # (activity_type, scope, year) -> factor_record

        # Scope 1 Factors
        df1 = xl.parse("Scope 1")
        for _, row in df1.iterrows():
            mat = str(row["Material"]).strip()
            unit = str(row["Unit of Material"]).strip()
            val = float(row["Emission Factor"])  # in tCO2/unit
            source = str(row["Data Source for Emission Factor"]).strip()
            
            # Convert tCO2/unit to kgCO2e/unit
            co2e_factor = val * 1000.0

            # Seed for 2024 (valid 2024-01-01 to 2024-12-31)
            key_2024 = (mat, 1, 2024)
            if key_2024 not in factors_map:
                f_2024 = EmissionFactor(
                    activity_type=mat,
                    scope=1,
                    unit=unit,
                    co2e_factor=co2e_factor,
                    source=source,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31)
                )
                db.add(f_2024)
                factors_map[key_2024] = f_2024

            # Seed for 2023 (valid 2023-01-01 to 2023-12-31) - 1.05x higher emission factor
            key_2023 = (mat, 1, 2023)
            if key_2023 not in factors_map:
                f_2023 = EmissionFactor(
                    activity_type=mat,
                    scope=1,
                    unit=unit,
                    co2e_factor=co2e_factor * 1.05,
                    source=source,
                    start_date=date(2023, 1, 1),
                    end_date=date(2023, 12, 31)
                )
                db.add(f_2023)
                factors_map[key_2023] = f_2023

            # Seed for 2025 (valid 2025-01-01 to 2025-12-31) - 0.95x lower emission factor
            key_2025 = (mat, 1, 2025)
            if key_2025 not in factors_map:
                f_2025 = EmissionFactor(
                    activity_type=mat,
                    scope=1,
                    unit=unit,
                    co2e_factor=co2e_factor * 0.95,
                    source=source,
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 12, 31)
                )
                db.add(f_2025)
                factors_map[key_2025] = f_2025

        # Scope 2 Factors
        df2 = xl.parse("Scope 2")
        for _, row in df2.iterrows():
            supplier = str(row["Supplier/Source"]).strip()
            unit = str(row["Unit"]).strip()
            # The column name has unicode subscript 2: "Emission Factor (tCO2/unit)" or similar. Let's find by index or check name.
            # In df2, we saw: 'Emission Factor (tCO\u2082/unit)'
            factor_col = [c for c in df2.columns if "Emission Factor" in c][0]
            val = float(row[factor_col])
            source = str(row["Grid Emission Factor Source"]).strip()

            co2e_factor = val * 1000.0

            # Seed 2024
            key_2024 = (supplier, 2, 2024)
            if key_2024 not in factors_map:
                f_2024 = EmissionFactor(
                    activity_type=supplier,
                    scope=2,
                    unit=unit,
                    co2e_factor=co2e_factor,
                    source=source,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31)
                )
                db.add(f_2024)
                factors_map[key_2024] = f_2024

            # Seed 2023 (1.05x higher)
            key_2023 = (supplier, 2, 2023)
            if key_2023 not in factors_map:
                f_2023 = EmissionFactor(
                    activity_type=supplier,
                    scope=2,
                    unit=unit,
                    co2e_factor=co2e_factor * 1.05,
                    source=source,
                    start_date=date(2023, 1, 1),
                    end_date=date(2023, 12, 31)
                )
                db.add(f_2023)
                factors_map[key_2023] = f_2023

            # Seed 2025 (0.95x lower)
            key_2025 = (supplier, 2, 2025)
            if key_2025 not in factors_map:
                f_2025 = EmissionFactor(
                    activity_type=supplier,
                    scope=2,
                    unit=unit,
                    co2e_factor=co2e_factor * 0.95,
                    source=source,
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 12, 31)
                )
                db.add(f_2025)
                factors_map[key_2025] = f_2025

        # Scope 3 Factors
        df3 = xl.parse("Scope 3")
        for _, row in df3.iterrows():
            desc = str(row["Activity Description"]).strip()
            unit = str(row["Unit of Activity"]).strip()
            factor_col = [c for c in df3.columns if "Emission Factor" in c][0]
            val = float(row[factor_col])
            source = str(row["Emission Factor Source"]).strip()

            co2e_factor = val * 1000.0

            # Seed 2024
            key_2024 = (desc, 3, 2024)
            if key_2024 not in factors_map:
                f_2024 = EmissionFactor(
                    activity_type=desc,
                    scope=3,
                    unit=unit,
                    co2e_factor=co2e_factor,
                    source=source,
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 12, 31)
                )
                db.add(f_2024)
                factors_map[key_2024] = f_2024

            # Seed 2023
            key_2023 = (desc, 3, 2023)
            if key_2023 not in factors_map:
                f_2023 = EmissionFactor(
                    activity_type=desc,
                    scope=3,
                    unit=unit,
                    co2e_factor=co2e_factor * 1.05,
                    source=source,
                    start_date=date(2023, 1, 1),
                    end_date=date(2023, 12, 31)
                )
                db.add(f_2023)
                factors_map[key_2023] = f_2023

            # Seed 2025
            key_2025 = (desc, 3, 2025)
            if key_2025 not in factors_map:
                f_2025 = EmissionFactor(
                    activity_type=desc,
                    scope=3,
                    unit=unit,
                    co2e_factor=co2e_factor * 0.95,
                    source=source,
                    start_date=date(2025, 1, 1),
                    end_date=date(2025, 12, 31)
                )
                db.add(f_2025)
                factors_map[key_2025] = f_2025

        db.commit()
        print("Successfully seeded Emission Factors!")

        # ----------------------------------------------------
        # 2. Parse and seed Emission Records for 2024
        # ----------------------------------------------------
        records_to_add = []

        # Scope 1 Records
        print("Parsing Scope 1 Records...")
        for _, row in df1.iterrows():
            mat = str(row["Material"]).strip()
            section = str(row["Section"]).strip()
            unit = str(row["Unit of Material"]).strip()
            timeline = str(row["Year/Timeline"]).strip()
            quantity = float(row["Q1 Quantity"])
            location = str(row["Location (Plant)"]).strip()

            # Assign date based on quarter
            if timeline == "Q1":
                rec_date = date(2024, 2, 15)
            elif timeline == "Q2":
                rec_date = date(2024, 5, 15)
            else:
                rec_date = date(2024, 8, 15)  # Fallback

            factor_record = factors_map.get((mat, 1, 2024))
            if factor_record:
                calc_val = quantity * factor_record.co2e_factor
                rec = EmissionRecord(
                    activity_type=mat,
                    scope=1,
                    activity_data=quantity,
                    unit=unit,
                    date=rec_date,
                    location=location,
                    section=section,
                    emission_factor_id=factor_record.id,
                    calculated_emissions=calc_val,
                    is_overridden=False
                )
                records_to_add.append(rec)

        # Scope 2 Records
        print("Parsing Scope 2 Records...")
        for _, row in df2.iterrows():
            supplier = str(row["Supplier/Source"]).strip()
            section = str(row["Section/Process"]).strip()
            unit = str(row["Unit"]).strip()
            timeline = str(row["Quarter"]).strip()
            quantity = float(row["Energy Consumed"])
            location = str(row["Location (Plant)"]).strip()

            if timeline == "Q1":
                rec_date = date(2024, 2, 15)
            elif timeline == "Q2":
                rec_date = date(2024, 5, 15)
            elif timeline == "Q3":
                rec_date = date(2024, 8, 15)
            else:
                rec_date = date(2024, 11, 15)

            factor_record = factors_map.get((supplier, 2, 2024))
            if factor_record:
                calc_val = quantity * factor_record.co2e_factor
                rec = EmissionRecord(
                    activity_type=supplier,
                    scope=2,
                    activity_data=quantity,
                    unit=unit,
                    date=rec_date,
                    location=location,
                    section=section,
                    emission_factor_id=factor_record.id,
                    calculated_emissions=calc_val,
                    is_overridden=False
                )
                records_to_add.append(rec)

        # Scope 3 Records
        print("Parsing Scope 3 Records...")
        for _, row in df3.iterrows():
            desc = str(row["Activity Description"]).strip()
            category = str(row["Scope 3 Category"]).strip()
            unit = str(row["Unit of Activity"]).strip()
            month_str = str(row["Month"]).strip()  # e.g. "2024-01"
            quantity = float(row["Quantity"])
            vendor = str(row["Vendor Involved"]) if not pd.isna(row["Vendor Involved"]) else "Various Vendors"

            # Parse month-based date
            try:
                rec_date = datetime.strptime(month_str, "%Y-%m").date()
                # Set to mid-month
                rec_date = date(rec_date.year, rec_date.month, 15)
            except Exception:
                rec_date = date(2024, 6, 15)

            factor_record = factors_map.get((desc, 3, 2024))
            if factor_record:
                calc_val = quantity * factor_record.co2e_factor
                rec = EmissionRecord(
                    activity_type=desc,
                    scope=3,
                    activity_data=quantity,
                    unit=unit,
                    date=rec_date,
                    location="Supply Chain",
                    section=category,
                    emission_factor_id=factor_record.id,
                    calculated_emissions=calc_val,
                    is_overridden=False
                )
                records_to_add.append(rec)

        # Save 2024 Records
        db.add_all(records_to_add)
        db.commit()
        print(f"Successfully seeded {len(records_to_add)} records for 2024!")

        # ----------------------------------------------------
        # 3. Synthesize Historical Records (2023 & 2025)
        # ----------------------------------------------------
        print("Synthesizing 2023 and 2025 records...")
        synthesized_records = []

        # Re-fetch the 2024 records to ensure they have IDs assigned
        records_2024 = db.query(EmissionRecord).all()

        for rec_24 in records_2024:
            # --- 2023 Record ---
            # 2023 activity has slightly higher quantities (e.g. 1.08x)
            qty_23 = rec_24.activity_data * 1.08
            date_23 = date(2023, rec_24.date.month, rec_24.date.day)
            
            # Find 2023 factor
            f_23 = factors_map.get((rec_24.activity_type, rec_24.scope, 2023))
            if f_23:
                calc_23 = qty_23 * f_23.co2e_factor
                rec_23 = EmissionRecord(
                    activity_type=rec_24.activity_type,
                    scope=rec_24.scope,
                    activity_data=qty_23,
                    unit=rec_24.unit,
                    date=date_23,
                    location=rec_24.location,
                    section=rec_24.section,
                    emission_factor_id=f_23.id,
                    calculated_emissions=calc_23,
                    is_overridden=False
                )
                synthesized_records.append(rec_23)

            # --- 2025 Record ---
            # 2025 activity has slightly lower quantities (e.g. 0.92x)
            qty_25 = rec_24.activity_data * 0.92
            date_25 = date(2025, rec_24.date.month, rec_24.date.day)
            
            # Find 2025 factor
            f_25 = factors_map.get((rec_24.activity_type, rec_24.scope, 2025))
            if f_25:
                calc_25 = qty_25 * f_25.co2e_factor
                rec_25 = EmissionRecord(
                    activity_type=rec_24.activity_type,
                    scope=rec_24.scope,
                    activity_data=qty_25,
                    unit=rec_24.unit,
                    date=date_25,
                    location=rec_24.location,
                    section=rec_24.section,
                    emission_factor_id=f_25.id,
                    calculated_emissions=calc_25,
                    is_overridden=False
                )
                synthesized_records.append(rec_25)

        db.add_all(synthesized_records)
        db.commit()
        print(f"Successfully seeded {len(synthesized_records)} synthesized records for 2023 and 2025!")

        # ----------------------------------------------------
        # 4. Seed Business Metrics
        # ----------------------------------------------------
        print("Seeding Business Metrics...")
        metrics = []

        # Steel production and employee counts from 2023-01 to 2025-12
        for year in [2023, 2024, 2025]:
            # Employee counts are stable
            for month in range(1, 13):
                metrics.append(BusinessMetric(
                    date=date(year, month, 28),
                    metric_name="Employees",
                    value=4800 + (10 * (month % 3)),  # slightly fluctuating around 4800-4820
                    unit="count"
                ))

            # Steel production has typical industrial variance
            # E.g. 50,000 tons average in 2023, 52,000 in 2024, 55,000 in 2025
            base_prod = {2023: 48000, 2024: 52000, 2025: 56000}[year]
            for month in range(1, 13):
                # Add monthly seasonal variance
                variance = 2000 * ((month % 4) - 2)
                metrics.append(BusinessMetric(
                    date=date(year, month, 28),
                    metric_name="Tons of Steel Produced",
                    value=float(base_prod + variance),
                    unit="tonnes"
                ))

        db.add_all(metrics)
        db.commit()
        print(f"Successfully seeded {len(metrics)} Business Metrics!")

    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise e
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
    seed_data()
