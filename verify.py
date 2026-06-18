import os
import unittest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Set environment to use a temporary SQLite file for testing
os.environ["TESTING"] = "1"

from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import EmissionFactor, EmissionRecord, BusinessMetric

# Setup testing database
TEST_DB_PATH = "test_emissions.db"
engine = create_engine(f"sqlite:///{TEST_DB_PATH}", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

# Override FastAPI dependency
app.dependency_overrides[get_db] = override_get_db

class TestCarbonPlatform(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def setUp(self):
        # Insert seed data for tests
        db = TestingSessionLocal()
        db.query(EmissionRecord).delete()
        db.query(EmissionFactor).delete()
        db.query(BusinessMetric).delete()
        
        # 1. Seed versioned factors for "Diesel" (Scope 1)
        # 2023 factor = 2.0 kgCO2e/L
        f23 = EmissionFactor(
            activity_type="Diesel",
            scope=1,
            unit="liters",
            co2e_factor=2.0,
            source="IPCC 2023",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31)
        )
        # 2024 factor = 1.8 kgCO2e/L (simulating lower footprint)
        f24 = EmissionFactor(
            activity_type="Diesel",
            scope=1,
            unit="liters",
            co2e_factor=1.8,
            source="IPCC 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31)
        )
        # 2025 factor = 1.5 kgCO2e/L
        f25 = EmissionFactor(
            activity_type="Diesel",
            scope=1,
            unit="liters",
            co2e_factor=1.5,
            source="IPCC 2025",
            start_date=date(2025, 1, 1),
            end_date=None # Active indefinitely
        )

        # 2. Seed versioned factors for "Grid Electricity" (Scope 2)
        e24 = EmissionFactor(
            activity_type="Grid Electricity",
            scope=2,
            unit="kWh",
            co2e_factor=0.8,
            source="CEA 2024",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31)
        )
        e23 = EmissionFactor(
            activity_type="Grid Electricity",
            scope=2,
            unit="kWh",
            co2e_factor=0.9,
            source="CEA 2023",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31)
        )

        db.add_all([f23, f24, f25, e23, e24])
        db.commit()

        # 3. Seed business metrics for 2024
        bm = BusinessMetric(
            date=date(2024, 6, 28),
            metric_name="Tons of Steel Produced",
            value=50000.0,
            unit="tonnes"
        )
        db.add(bm)
        db.commit()
        db.close()

    def test_historical_accuracy_calculation(self):
        # Test Case 1: Post Diesel record for 2023-06-15.
        # Should use 2023 factor (2.0) -> quantity 100 * 2.0 = 200.0 kgCO2e
        response = self.client.post("/api/emission-records", json={
            "activity_type": "Diesel",
            "activity_data": 100.0,
            "unit": "liters",
            "date": "2023-06-15",
            "location": "Central Plant",
            "section": "Transport"
        })
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["calculated_emissions"], 200.0)
        self.assertEqual(data["scope"], 1)

        # Test Case 2: Post Diesel record for 2024-06-15.
        # Should use 2024 factor (1.8) -> quantity 100 * 1.8 = 180.0 kgCO2e
        response = self.client.post("/api/emission-records", json={
            "activity_type": "Diesel",
            "activity_data": 100.0,
            "unit": "liters",
            "date": "2024-06-15",
            "location": "Central Plant",
            "section": "Transport"
        })
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["calculated_emissions"], 180.0)

        # Test Case 3: Post Diesel record for 2025-06-15.
        # Should use 2025 factor (1.5) -> quantity 100 * 1.5 = 150.0 kgCO2e
        response = self.client.post("/api/emission-records", json={
            "activity_type": "Diesel",
            "activity_data": 100.0,
            "unit": "liters",
            "date": "2025-06-15",
            "location": "Central Plant",
            "section": "Transport"
        })
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["calculated_emissions"], 150.0)

    def test_manual_override_and_audit(self):
        # Create record first
        response = self.client.post("/api/emission-records", json={
            "activity_type": "Diesel",
            "activity_data": 100.0,
            "unit": "liters",
            "date": "2024-06-15",
            "location": "Central Plant",
            "section": "Transport"
        })
        rec_id = response.json()["id"]

        # Call PUT override endpoint
        override_res = self.client.put(f"/api/emission-records/{rec_id}/override", json={
            "override_emissions": 100.0,
            "justification": "Incorrect meter calibration"
        })
        self.assertEqual(override_res.status_code, 200)
        rec_data = override_res.json()
        self.assertTrue(rec_data["is_overridden"])
        self.assertEqual(rec_data["override_emissions"], 100.0)
        self.assertEqual(rec_data["override_justification"], "Incorrect meter calibration")

        # Verify audit log was created
        audit_res = self.client.get("/api/audit-logs")
        self.assertEqual(audit_res.status_code, 200)
        audit_logs = audit_res.json()
        self.assertTrue(len(audit_logs) > 0)
        self.assertEqual(audit_logs[0]["record_id"], rec_id)
        self.assertEqual(audit_logs[0]["old_value"], 180.0)
        self.assertEqual(audit_logs[0]["new_value"], 100.0)
        self.assertEqual(audit_logs[0]["justification"], "Incorrect meter calibration")

    def test_analytics_endpoints(self):
        # Create 2023 records (Scope 1 and 2)
        self.client.post("/api/emission-records", json={
            "activity_type": "Diesel",
            "activity_data": 100.0,
            "unit": "liters",
            "date": "2023-06-15",
            "location": "Central Plant",
            "section": "Transport"
        })
        self.client.post("/api/emission-records", json={
            "activity_type": "Grid Electricity",
            "activity_data": 1000.0,
            "unit": "kWh",
            "date": "2023-06-15",
            "location": "Central Plant",
            "section": "Furnace"
        })

        # Create 2024 records (Scope 1 and 2)
        self.client.post("/api/emission-records", json={
            "activity_type": "Diesel",
            "activity_data": 200.0,
            "unit": "liters",
            "date": "2024-06-15",
            "location": "Central Plant",
            "section": "Transport"
        })
        self.client.post("/api/emission-records", json={
            "activity_type": "Grid Electricity",
            "activity_data": 2000.0,
            "unit": "kWh",
            "date": "2024-06-15",
            "location": "Central Plant",
            "section": "Furnace"
        })

        # 1. Test YoY Endpoint
        # Scope 1 2024 = 200*1.8 = 360 | Scope 1 2023 = 100*2.0 = 200
        # Scope 2 2024 = 2000*0.8 = 1600 | Scope 2 2023 = 1000*0.9 = 900
        yoy_res = self.client.get("/api/analytics/yoy?year=2024")
        self.assertEqual(yoy_res.status_code, 200)
        yoy_data = yoy_res.json()
        self.assertEqual(yoy_data["current_year"], 2024)
        self.assertEqual(yoy_data["previous_year"], 2023)
        
        s1 = next(s for s in yoy_data["scopes"] if s["scope"] == 1)
        s2 = next(s for s in yoy_data["scopes"] if s["scope"] == 2)
        self.assertEqual(s1["current_emissions"], 360.0)
        self.assertEqual(s1["previous_emissions"], 200.0)
        self.assertEqual(s2["current_emissions"], 1600.0)
        self.assertEqual(s2["previous_emissions"], 900.0)

        # 2. Test Hotspot Endpoint
        hot_res = self.client.get("/api/analytics/hotspot?year=2024")
        self.assertEqual(hot_res.status_code, 200)
        hot_data = hot_res.json()
        self.assertEqual(hot_data["total_emissions_kgCO2e"], 1960.0) # 360 + 1600
        self.assertEqual(hot_data["hotspots"][0]["source"], "Grid Electricity")
        self.assertEqual(hot_data["hotspots"][0]["emissions_kgCO2e"], 1600.0)

        # 3. Test Intensity Endpoint
        # June 2024 emissions = 360 + 1600 = 1960. June 2024 Steel = 50000.
        # June intensity = 1960 / 50000 = 0.0392
        int_res = self.client.get("/api/analytics/intensity?year=2024&metric_name=Tons of Steel Produced")
        self.assertEqual(int_res.status_code, 200)
        int_data = int_res.json()
        june_record = next(m for m in int_data["monthly_breakdown"] if m["month"] == "2024-06")
        self.assertEqual(june_record["emissions_kgCO2e"], 1960.0)
        self.assertEqual(june_record["intensity_kgCO2e_per_unit"], 0.0392)

if __name__ == "__main__":
    unittest.main()
