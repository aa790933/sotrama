"""
Test suite for Sotrama — Algerian Localization & TP Fleet Management.

Run with: bench --site your-site run-tests --app sotrama
"""

from __future__ import unicode_literals

import frappe
import unittest
from frappe.utils import today, add_days


class TestSotramaCustomFields(unittest.TestCase):
    """Test that NIF/NIS/RC custom fields exist on Company doctype."""

    def test_custom_fields_exist(self):
        """Verify that custom_nif, custom_nis, custom_rc fields exist on Company."""
        for fieldname in ("custom_nif", "custom_nis", "custom_rc"):
            self.assertTrue(
                frappe.db.exists(
                    "Custom Field",
                    {"dt": "Company", "fieldname": fieldname, "module": "Sotrama"},
                ),
                f"Custom field {fieldname} not found on Company doctype",
            )


class TestVehicle(unittest.TestCase):
    """Test Vehicle doctype validation and lifecycle."""

    def setUp(self):
        """Create test dependencies."""
        # Create a Company Classification
        self.classification = frappe.new_doc("Company Classification")
        self.classification.grade = 8
        self.classification.category = "TP"
        self.classification.registration_number = "TEST-CLAS-001"
        self.classification.insert(ignore_permissions=True)

        # Create a Vehicle Make
        self.make = frappe.new_doc("Vehicle Make")
        self.make.make_name = "Test Make"
        self.make.insert(ignore_permissions=True)

        # Create a Vehicle Model
        self.model = frappe.new_doc("Vehicle Model")
        self.model.vehicle_make = self.make.name
        self.model.model_name = "Test Model"
        self.model.insert(ignore_permissions=True)

    def tearDown(self):
        """Clean up test data."""
        for doctype in ["Vehicle Model", "Vehicle Make", "Company Classification"]:
            for name in frappe.get_all(doctype, pluck="name"):
                if name.startswith("Test"):
                    frappe.delete_doc(doctype, name, ignore_on_trash=True)

    def test_vehicle_creation_with_required_fields(self):
        """Test that a Vehicle can be created with all required fields."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.license_plate = "TEST-001"
        vehicle.vehicle_make = self.make.name
        self.make = self.make  # reference
        vehicle.model = self.model.name
        vehicle.year_of_manufacture = 2020
        vehicle.chassis_no = "TEST1234567890"
        vehicle.vehicle_category = "Truck"
        vehicle.vehicle_class = "Heavy"
        vehicle.tonnage = 15.0
        vehicle.number_of_axles = 3
        vehicle.fuel_type = "Diesel"
        vehicle.current_odometer = 50000.0
        vehicle.acquisition_date = today()
        vehicle.acquisition_value = 2000000
        vehicle.company_classification = self.classification.name
        vehicle.insert()

        self.assertEqual(vehicle.vehicle_status, "Active")
        self.assertEqual(vehicle.fuel_type, "Diesel")
        self.assertEqual(vehicle.license_plate, "TEST-001")

        # Cleanup
        frappe.delete_doc("Vehicle", vehicle.name, ignore_on_trash=True)

    def test_vehicle_license_plate_required(self):
        """Test that License Plate is required."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.vehicle_category = "Truck"
        vehicle.company_classification = self.classification.name
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert()

    def test_vehicle_chassis_too_short(self):
        """Test that Chassis Number must be at least 10 characters."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.license_plate = "TEST-002"
        vehicle.vehicle_category = "Truck"
        vehicle.company_classification = self.classification.name
        vehicle.chassis_no = "SHORT"
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert()


class TestDriver(unittest.TestCase):
    """Test Driver doctype validation."""

    def test_driver_license_required(self):
        """Test that License Number is required."""
        driver = frappe.new_doc("Driver")
        driver.driver_name = "Test Driver"
        with self.assertRaises(frappe.ValidationError):
            driver.insert()

    def test_driver_license_expiry_warning(self):
        """Test that expired license shows warning."""
        driver = frappe.new_doc("Driver")
        driver.driver_name = "Test Driver"
        driver.license_number = "LIC-001"
        driver.license_expiry = add_days(today(), -1)  # expired yesterday
        driver.insert()  # Should not throw, just msgprint
        frappe.delete_doc("Driver", driver.name, ignore_on_trash=True)


class TestMaintenanceJobCard(unittest.TestCase):
    """Test Maintenance Job Card cost calculations."""

    def setUp(self):
        """Create test dependencies."""
        self.classification = frappe.new_doc("Company Classification")
        self.classification.grade = 8
        self.classification.category = "TP"
        self.classification.registration_number = "TEST-CLAS-002"
        self.classification.insert(ignore_permissions=True)

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.license_plate = "TEST-MAIN-001"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert()

    def tearDown(self):
        for doctype in ["Vehicle", "Company Classification"]:
            for name in frappe.get_all(doctype, pluck="name"):
                if name.startswith("TEST"):
                    frappe.delete_doc(doctype, name, ignore_on_trash=True)

    def test_job_card_cost_calculation(self):
        """Test that parts, labour, and other costs are summed correctly."""
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.vehicle = self.vehicle.name
        job_card.job_date = today()
        job_card.job_nature = "Repair"
        job_card.status = "Draft"

        # Add a part
        job_card.append("parts_used", {
            "item": "Test Item",
            "quantity": 2,
            "rate": 500,
        })

        # Add labour
        job_card.append("labour_lines", {
            "mechanic": "Test Mechanic",
            "hours": 3,
            "rate": 1000,
        })

        # Add other cost
        job_card.append("other_costs", {
            "description": "Towing",
            "amount": 2000,
        })

        job_card.validate()

        self.assertEqual(job_card.total_parts_cost, 1000)
        self.assertEqual(job_card.total_labour_cost, 3000)
        self.assertEqual(job_card.total_other_cost, 2000)
        self.assertEqual(job_card.total_cost, 6000)

        # Cleanup
        frappe.delete_doc("Maintenance Job Card", job_card.name, ignore_on_trash=True)

    def test_job_card_odometer_validation(self):
        """Test that Odometer After cannot be less than Odometer Before."""
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.vehicle = self.vehicle.name
        job_card.job_date = today()
        job_card.job_nature = "Repair"
        job_card.status = "Draft"
        job_card.odometer_before = 50000
        job_card.odometer_after = 40000  # Less than before
        with self.assertRaises(frappe.ValidationError):
            job_card.validate()

        frappe.delete_doc("Maintenance Job Card", job_card.name, ignore_on_trash=True)


class TestCompanyClassification(unittest.TestCase):
    """Test Company Classification score calculation."""

    def test_grade_8_score_range(self):
        """Test that Grade 8 falls in the correct score range (63.0 - 72.8)."""
        classification = frappe.new_doc("Company Classification")
        classification.grade = 8
        classification.category = "TP"
        classification.registration_number = "TEST-GRADE-8"
        # Set scores that should total in Grade 8 range
        classification.effectif_score = 8
        classification.effectif_coefficient = 1.0
        classification.encadrement_score = 1
        classification.encadrement_coefficient = 1.0
        classification.apprentice_score = 1
        classification.apprentice_coefficient = 1.0
        classification.training_score = 1
        classification.training_coefficient = 1.0
        classification.material_value_score = 8
        classification.material_value_coefficient = 1.0
        classification.capital_score = 8
        classification.capital_coefficient = 1.0
        classification.revenue_score = 8
        classification.revenue_coefficient = 1.0
        classification.docs_score = 8
        classification.docs_coefficient = 1.0
        classification.certification_score = 8
        classification.certification_coefficient = 1.0

        classification.validate()

        # NT should be around 64-72 for Grade 8
        self.assertGreater(classification.total_score, 63.0)
        self.assertLessEqual(classification.total_score, 72.8)

        frappe.delete_doc("Company Classification", classification.name, ignore_on_trash=True)


class TestBreakdownIncident(unittest.TestCase):
    """Test Breakdown Incident validation and workflow."""

    def setUp(self):
        self.classification = frappe.new_doc("Company Classification")
        self.classification.grade = 8
        self.classification.category = "TP"
        self.classification.registration_number = "TEST-BRK-001"
        self.classification.insert(ignore_permissions=True)

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.license_plate = "TEST-BRK-VEH-001"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert()

    def tearDown(self):
        for doctype in ["Vehicle", "Company Classification", "Breakdown Incident"]:
            for name in frappe.get_all(doctype, pluck="name"):
                if name.startswith("TEST"):
                    frappe.delete_doc(doctype, name, ignore_on_trash=True)

    def test_breakdown_date_validation(self):
        """Test that Resolution Date cannot be before Incident Date."""
        from frappe.utils import nowdate, add_days

        breakdown = frappe.new_doc("Breakdown Incident")
        breakdown.vehicle = self.vehicle.name
        breakdown.incident_date = today()
        breakdown.resolution_date = add_days(today(), -1)  # Before incident
        breakdown.description = "Test breakdown"
        with self.assertRaises(frappe.ValidationError):
            breakdown.validate()

        frappe.delete_doc("Breakdown Incident", breakdown.name, ignore_on_trash=True)