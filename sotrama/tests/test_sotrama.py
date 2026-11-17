"""
Test suite for Sotrama — Algerian Localization & TP Fleet Management.

Run with: bench --site your-site run-tests --app sotrama
"""


import unittest
import uuid

import frappe
from frappe.utils import add_days, today


class TestSotramaHooks(unittest.TestCase):
    """Protect against incompatible hook value shapes across installed apps."""

    def test_app_metadata_is_complete_for_desk_boot(self):
        from frappe.utils.change_log import get_versions

        app_hooks = frappe.get_hooks(app_name="sotrama")
        self.assertTrue(app_hooks.get("app_name"))
        self.assertTrue(app_hooks.get("app_title"))
        self.assertTrue(app_hooks.get("app_description"))
        self.assertTrue(app_hooks.get("app_version"))

        # Reproduce the metadata lookup used by Desk boot and install-app.
        versions = get_versions()
        self.assertIn("sotrama", versions)
        self.assertEqual(versions["sotrama"]["title"], "Sotrama")
        self.assertTrue(versions["sotrama"]["description"])
        self.assertEqual(versions["sotrama"]["version"], app_hooks["app_version"][0])

    def test_global_hook_merge(self):
        hooks = frappe.get_hooks()
        self.assertIsInstance(hooks.get("app_include_js"), list)
        self.assertTrue(
            any("/assets/sotrama/js/sotrama.js" in path for path in hooks["app_include_js"])
        )
        self.assertIsInstance(hooks.get("filters_config"), list)

    def test_fleet_roles_exist(self):
        for role in ("Fleet Manager", "Workshop", "Driver"):
            self.assertTrue(frappe.db.exists("Role", role), f"Missing role: {role}")


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
        self.classification.category = "TP (Travaux Publics)"
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
        if getattr(self, "created_vehicle", None) and frappe.db.exists(
            "Vehicle", self.created_vehicle
        ):
            frappe.delete_doc("Vehicle", self.created_vehicle, ignore_permissions=True)
        for doctype in ["Vehicle Model", "Vehicle Make"]:
            for name in frappe.get_all(doctype, pluck="name"):
                if name.startswith("Test"):
                    frappe.delete_doc(doctype, name, ignore_on_trash=True)
        if frappe.db.exists("Company Classification", self.classification.name):
            frappe.delete_doc("Company Classification", self.classification.name, ignore_permissions=True)

    def test_vehicle_creation_with_required_fields(self):
        """Test that a Vehicle can be created with all required fields."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.license_plate = "TEST-001"
        vehicle.vehicle_make = self.make.name
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
        self.created_vehicle = vehicle.name

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
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = "TEST-CLAS-002"
        self.classification.insert(ignore_permissions=True)

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.license_plate = "TEST-MAIN-001"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert()

        item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        stock_uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value(
            "UOM", {}, "name"
        )
        self.item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": f"SOTRAMA-TEST-{uuid.uuid4().hex[:8].upper()}",
                "item_name": "Sotrama Test Spare Part",
                "item_group": item_group,
                "stock_uom": stock_uom,
                "is_stock_item": 1,
            }
        ).insert(ignore_permissions=True)

    def tearDown(self):
        if frappe.db.exists("Vehicle", self.vehicle.name):
            frappe.delete_doc("Vehicle", self.vehicle.name, ignore_permissions=True)
        if frappe.db.exists("Company Classification", self.classification.name):
            frappe.delete_doc("Company Classification", self.classification.name, ignore_permissions=True)
        if frappe.db.exists("Item", self.item.name):
            frappe.delete_doc("Item", self.item.name, ignore_permissions=True)

    def test_job_card_cost_calculation(self):
        """Test that parts, labour, and other costs are summed correctly."""
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.vehicle = self.vehicle.name
        job_card.job_date = today()
        job_card.job_nature = "Repair"
        job_card.status = "Draft"

        # Add a part
        job_card.append("parts_used", {
            "item": self.item.name,
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
        # The document was never inserted; there is no database record to clean up.

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

        # The invalid document was never inserted; there is no database record to clean up.


class TestCompanyClassification(unittest.TestCase):
    """Test Company Classification score calculation."""

    def test_grade_8_score_range(self):
        """Test that Grade 8 falls in the correct score range (63.0 - 72.8)."""
        classification = frappe.new_doc("Company Classification")
        classification.grade = 8
        classification.category = "TP (Travaux Publics)"
        classification.registration_number = "TEST-GRADE-8"
        # Set scores that should total in Grade 8 range
        classification.effectif_score = 8
        classification.effectif_coefficient = 1.0
        classification.encadrement_score = 4
        classification.encadrement_coefficient = 1.0
        classification.apprentice_score = 2
        classification.apprentice_coefficient = 1.0
        classification.training_score = 2
        classification.training_coefficient = 1.0
        classification.material_value_score = 10
        classification.material_value_coefficient = 1.0
        classification.capital_score = 8
        classification.capital_coefficient = 1.0
        classification.revenue_score = 9
        classification.revenue_coefficient = 1.0
        classification.abe_score = 1.0
        classification.abe_coefficient = 1.0

        classification.validate()

        # NT should be around 64-72 for Grade 8
        self.assertGreater(classification.total_score, 63.0)
        self.assertLessEqual(classification.total_score, 72.8)

        # The validation-only document was never inserted.


class TestBreakdownIncident(unittest.TestCase):
    """Test Breakdown Incident validation and workflow."""

    def setUp(self):
        self.classification = frappe.new_doc("Company Classification")
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = "TEST-BRK-001"
        self.classification.insert(ignore_permissions=True)

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.license_plate = "TEST-BRK-VEH-001"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert()

    def tearDown(self):
        for doctype, name in (
            ("Vehicle", self.vehicle.name),
            ("Company Classification", self.classification.name),
        ):
            if frappe.db.exists(doctype, name):
                frappe.delete_doc(doctype, name, ignore_permissions=True)

    def test_breakdown_date_validation(self):
        """Test that Resolution Date cannot be before Incident Date."""
        from frappe.utils import add_days

        breakdown = frappe.new_doc("Breakdown Incident")
        breakdown.vehicle = self.vehicle.name
        breakdown.incident_date = today()
        breakdown.resolution_date = add_days(today(), -1)  # Before incident
        breakdown.description = "Test breakdown"
        with self.assertRaises(frappe.ValidationError):
            breakdown.validate()

        # The invalid document was never inserted; there is no database record to clean up.
