"""
Test suite for Sotrama — Algerian Localization & TP Fleet Management.

Run with: bench --site your-site run-tests --app sotrama
"""


import unittest
import uuid
from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate, today


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

    def test_app_lifecycle_hooks_are_import_paths(self):
        app_hooks = frappe.get_hooks(app_name="sotrama")
        self.assertEqual(app_hooks["before_install"][0], "sotrama.hooks.ensure_roles")
        self.assertEqual(app_hooks["after_install"][0], "sotrama.hooks.install_company_fields")
        self.assertEqual(app_hooks["after_migrate"][0], "sotrama.hooks.sync_company_fields")
        self.assertEqual(app_hooks["before_uninstall"][0], "sotrama.hooks.uninstall_company_fields")

    def test_app_is_registered_on_the_apps_screen(self):
        app_entry = frappe.get_hooks("add_to_apps_screen", app_name="sotrama")[0]
        self.assertEqual(app_entry["name"], "sotrama")
        self.assertEqual(app_entry["title"], "Sotrama")
        self.assertEqual(app_entry["route"], "/desk/sotrama-fleet")
        self.assertEqual(app_entry["has_permission"], "sotrama.permissions.has_app_permission")

    def test_fleet_dock_sidebar_and_workspace_are_installed(self):
        self.assertTrue(frappe.db.exists("Dock", {"app": "sotrama", "standard": 1}))
        self.assertTrue(frappe.db.exists("Sidebar", "TP"))
        self.assertTrue(frappe.db.exists("Workspace", "Sotrama Fleet"))
        workspace = frappe.get_doc("Workspace", "Sotrama Fleet")
        import json

        blocks = json.loads(workspace.content or "[]")
        card_names = {
            block.get("data", {}).get("number_card_name")
            for block in blocks
            if block.get("type") == "number_card"
        }
        self.assertEqual(
            card_names,
            {"Active Vehicles", "Vehicles Out of Service", "Active Maintenance Plans"},
        )
        for card_name in card_names:
            self.assertTrue(frappe.db.exists("Number Card", card_name), f"Missing Number Card: {card_name}")

        sidebar = frappe.get_doc("Sidebar", "TP")
        self.assertTrue(any(item.link_to == "TP Settings" for item in sidebar.items))
        self.assertTrue(any(item.link_to == "TP Settings" for item in workspace.links))
        self.assertIn("HR Manager", {row.role for row in workspace.roles})

    def test_fleet_manager_role_profile_does_not_escalate_to_system_manager(self):
        profile = frappe.get_doc("Role Profile", "Fleet Manager")
        roles = {row.role for row in profile.roles}
        self.assertIn("Fleet Manager", roles)
        self.assertNotIn("System Manager", roles)

    def test_tp_settings_is_a_single_central_configuration(self):
        meta = frappe.get_meta("TP Settings", cached=False)
        self.assertTrue(meta.issingle)
        for fieldname in (
            "default_company",
            "default_company_classification",
            "default_department",
            "default_cost_center",
            "default_parts_warehouse",
            "require_employee_link",
            "require_active_employee_for_active_driver",
            "block_expired_driver_license",
            "block_expired_medical_certificate",
            "block_expired_safety_training",
            "require_professional_certificate_for_transport",
            "driver_document_alert_days",
            "vehicle_document_alert_days",
            "maintenance_due_alert_days",
            "company_defaults",
        ):
            self.assertIsNotNone(meta.get_field(fieldname), f"Missing TP setting: {fieldname}")

        restricted_settings = (
            "require_employee_link",
            "require_active_employee_for_active_driver",
            "block_expired_medical_certificate",
            "block_expired_safety_training",
            "require_professional_certificate_for_transport",
        )
        for fieldname in restricted_settings:
            self.assertEqual(meta.get_field(fieldname).permlevel, 1)

        hr_permissions = [
            permission for permission in meta.permissions
            if permission.role == "HR Manager" and permission.permlevel == 1
        ]
        self.assertTrue(hr_permissions)
        self.assertTrue(hr_permissions[0].read)
        self.assertTrue(hr_permissions[0].write)

        system_permissions = [
            permission for permission in meta.permissions
            if permission.role == "System Manager" and permission.permlevel == 1
        ]
        self.assertTrue(system_permissions)
        self.assertTrue(system_permissions[0].read)
        self.assertTrue(system_permissions[0].write)

        fleet_permissions = [
            permission for permission in meta.permissions
            if permission.role == "Fleet Manager" and permission.permlevel == 1
        ]
        self.assertFalse(fleet_permissions)

        company_defaults = frappe.get_meta("TP Company Defaults", cached=False)
        self.assertTrue(company_defaults.istable)
        for fieldname in (
            "company",
            "company_classification",
            "default_department",
            "default_cost_center",
            "default_parts_warehouse",
            "active",
        ):
            self.assertIsNotNone(company_defaults.get_field(fieldname))

    def test_maintenance_job_card_can_select_a_specific_plan(self):
        card_meta = frappe.get_meta("Maintenance Job Card", cached=False)
        schedule_field = card_meta.get_field("maintenance_schedule")
        self.assertIsNotNone(schedule_field)
        self.assertEqual(schedule_field.fieldtype, "Link")
        self.assertEqual(schedule_field.options, "Maintenance Schedule")
        schedule_meta = frappe.get_meta("Maintenance Schedule", cached=False)
        last_job_card = schedule_meta.get_field("last_service_job_card")
        self.assertIsNotNone(last_job_card)
        self.assertEqual(last_job_card.options, "Maintenance Job Card")
        self.assertTrue(schedule_meta.get_field("status").read_only)
        self.assertFalse(schedule_meta.get_field("status").allow_on_submit)
        next_schedule = schedule_meta.get_field("next_schedule")
        self.assertEqual(next_schedule.fieldtype, "Link")
        self.assertEqual(next_schedule.options, "Maintenance Schedule")
        self.assertTrue(next_schedule.read_only)
        self.assertFalse(next_schedule.allow_on_submit)

    def test_company_classification_can_be_assigned_to_a_legal_entity(self):
        meta = frappe.get_meta("Company Classification", cached=False)
        company = meta.get_field("company")
        self.assertIsNotNone(company)
        self.assertEqual(company.fieldtype, "Link")
        self.assertEqual(company.options, "Company")

    def test_driver_employee_link_remains_available_and_optional_by_default(self):
        meta = frappe.get_meta("Driver", cached=False)
        employee_field = meta.get_field("employee")
        status_field = meta.get_field("status")
        self.assertIsNotNone(employee_field)
        self.assertEqual(employee_field.fieldtype, "Link")
        self.assertEqual(employee_field.options, "Employee")
        self.assertFalse(employee_field.hidden)
        self.assertFalse(employee_field.reqd)
        self.assertTrue(employee_field.allow_on_submit)
        self.assertFalse(status_field.allow_on_submit)
        self.assertEqual(status_field.read_only_depends_on, "eval:doc.docstatus == 1")

    def test_driver_licence_categories_include_the_2025_decree_categories(self):
        driver_meta = frappe.get_meta("Driver", cached=False)
        licence_field = driver_meta.get_field("license_class")
        categories = set((licence_field.options or "").splitlines())
        for category in ("A1", "A", "B", "B(E)", "C1", "C1(E)", "C", "C(E)", "D", "D(E)", "F"):
            self.assertIn(category, categories)
        for fieldname in ("license_number", "license_class", "license_expiry", "license_issue_date"):
            self.assertTrue(driver_meta.get_field(fieldname).allow_on_submit)

    def test_driver_compliance_history_is_restricted_to_hr_manager(self):
        driver_meta = frappe.get_meta("Driver", cached=False)
        compliance_field = driver_meta.get_field("compliance_records")
        medical_expiry = driver_meta.get_field("medical_expiry")
        date_of_birth = driver_meta.get_field("date_of_birth")
        national_id = driver_meta.get_field("national_id")
        self.assertEqual(compliance_field.fieldtype, "Table")
        self.assertEqual(compliance_field.options, "Driver Compliance Record")
        self.assertEqual(compliance_field.permlevel, 1)
        self.assertEqual(medical_expiry.permlevel, 1)
        self.assertEqual(date_of_birth.permlevel, 1)
        self.assertEqual(national_id.permlevel, 1)
        self.assertTrue(date_of_birth.allow_on_submit)
        self.assertTrue(national_id.allow_on_submit)
        self.assertTrue(compliance_field.allow_on_submit)
        self.assertTrue(medical_expiry.allow_on_submit)

        hr_permissions = [
            permission for permission in driver_meta.permissions
            if permission.role == "HR Manager" and permission.permlevel == 1
        ]
        self.assertTrue(hr_permissions)
        self.assertTrue(hr_permissions[0].read)
        self.assertTrue(hr_permissions[0].write)

        system_manager_permissions = [
            permission for permission in driver_meta.permissions
            if permission.role == "System Manager" and permission.permlevel == 1
        ]
        self.assertTrue(system_manager_permissions)
        self.assertTrue(system_manager_permissions[0].read)
        self.assertTrue(system_manager_permissions[0].write)

        fleet_permissions = [
            permission for permission in driver_meta.permissions
            if permission.role == "Fleet Manager" and permission.permlevel == 1
        ]
        workshop_permissions = [
            permission for permission in driver_meta.permissions
            if permission.role == "Workshop" and permission.permlevel == 1
        ]
        self.assertFalse(fleet_permissions)
        self.assertFalse(workshop_permissions)

        record_meta = frappe.get_meta("Driver Compliance Record", cached=False)
        self.assertTrue(record_meta.istable)
        self.assertIsNotNone(record_meta.get_field("valid_until"))

    def test_transport_activity_options_follow_road_code_articles_79_80(self):
        field = frappe.get_meta("Operational Task", cached=False).get_field("transport_kind")
        activities = set((field.options or "").splitlines())
        for activity in (
            "Transport collectif de personnes",
            "Transport scolaire",
            "Transport de marchandises",
            "Transport de matières dangereuses",
            "Transport par taxi",
        ):
            self.assertIn(activity, activities)

    def test_inspection_child_records_safety_and_issue_links(self):
        meta = frappe.get_meta("Inspection Item", cached=False)
        self.assertIsNotNone(meta.get_field("is_safety_critical"))
        linked_issue = meta.get_field("linked_issue")
        self.assertIsNotNone(linked_issue)
        self.assertEqual(linked_issue.fieldtype, "Link")
        self.assertEqual(linked_issue.options, "Issue")

        inspection_meta = frappe.get_meta("Vehicle Inspection", cached=False)
        follow_up = inspection_meta.get_field("follow_up_of")
        cleared_by = inspection_meta.get_field("critical_defect_cleared_by")
        self.assertEqual(follow_up.options, "Vehicle Inspection")
        self.assertEqual(cleared_by.options, "Vehicle Inspection")
        self.assertTrue(cleared_by.read_only)
        self.assertFalse(cleared_by.allow_on_submit)

    def test_breakdown_workflow_fields_are_locked_after_submit(self):
        meta = frappe.get_meta("Breakdown Incident", cached=False)
        for fieldname in ("status", "resolution_date", "resolution_notes", "downtime_hours"):
            self.assertTrue(meta.get_field(fieldname).read_only)
            self.assertFalse(meta.get_field(fieldname).allow_on_submit)

        vehicle_meta = frappe.get_meta("Vehicle", cached=False)
        self.assertTrue(vehicle_meta.get_field("primary_driver").allow_on_submit)

    def test_fleet_reports_have_reference_doctypes(self):
        self.assertEqual(frappe.get_value("Report", "Fleet Cost Analysis", "ref_doctype"), "Vehicle")
        self.assertEqual(
            frappe.get_value("Report", "Upcoming Document Expiries", "ref_doctype"),
            "Vehicle",
        )

    def test_fleet_print_formats_use_the_frappe_16_builder(self):
        import json

        formats = (
            ("Maintenance Job Card Report", "Maintenance Job Card"),
            ("Vehicle Inspection Report", "Vehicle Inspection"),
        )
        for name, doctype in formats:
            print_format = frappe.get_doc("Print Format", name)
            self.assertEqual(print_format.doc_type, doctype)
            self.assertTrue(print_format.print_format_builder_beta)
            self.assertFalse(print_format.custom_format)
            self.assertIn(print_format.pdf_generator, {"PlutoPrint", "Typst", "chrome"})
            layout = json.loads(print_format.format_data)
            self.assertIsInstance(layout, dict)
            self.assertTrue(layout.get("sections"))
            self.assertIn(layout.get("page", {}).get("size"), {"A4", "Letter", "Legal", "A3"})
            meta = frappe.get_meta(doctype, cached=False)

            custom_names = set()
            zones = [layout.get("header", {}), *layout["sections"], layout.get("footer", {})]
            for zone in zones:
                for column in zone.get("columns", []):
                    for field in column.get("fields", []):
                        if field.get("custom"):
                            self.assertTrue(field.get("fieldname"))
                            self.assertNotIn(field["fieldname"], custom_names)
                            custom_names.add(field["fieldname"])
                            continue
                        docfield = meta.get_field(field["fieldname"])
                        self.assertIsNotNone(
                            docfield,
                            f"{name}: unknown field {doctype}.{field['fieldname']}",
                        )
                        self.assertEqual(field.get("fieldtype"), docfield.fieldtype)
                        if docfield.options:
                            self.assertEqual(field.get("options"), docfield.options)
                        if field.get("fieldtype") == "Table":
                            self.assertEqual(docfield.fieldtype, "Table")
                            self.assertEqual(docfield.options, field.get("options"))
                            child_meta = frappe.get_meta(docfield.options, cached=False)
                            for table_column in field.get("table_columns", []):
                                child_field = child_meta.get_field(table_column["fieldname"])
                                self.assertIsNotNone(
                                    child_field,
                                    f"{name}: unknown child field {docfield.options}.{table_column['fieldname']}",
                                )
                                self.assertEqual(table_column.get("fieldtype"), child_field.fieldtype)
                                if child_field.options:
                                    self.assertEqual(table_column.get("options"), child_field.options)

            if doctype == "Maintenance Job Card":
                printed_fields = {
                    field.get("fieldname")
                    for section in layout["sections"]
                    for column in section.get("columns", [])
                    for field in column.get("fields", [])
                }
                self.assertIn("maintenance_schedule", printed_fields)

    def test_fleet_doctypes_have_distinct_icons(self):
        doctypes = frappe.get_all(
            "DocType",
            filters={"module": "TP", "istable": 0},
            fields=["name", "icon"],
        )
        icons = {doctype.name: doctype.icon for doctype in doctypes}
        self.assertTrue(all(icons.values()), icons)
        self.assertEqual(len(set(icons.values())), len(icons), icons)

    def test_fleet_roles_exist(self):
        for role in ("Fleet Manager", "Workshop", "Driver"):
            self.assertTrue(frappe.db.exists("Role", role), f"Missing role: {role}")


class TestSotramaCustomFields(unittest.TestCase):
    """Test that Algerian company fields exist on the standard Company DocType."""

    def test_custom_fields_exist(self):
        """Verify the Algeria localization fields exist on Company metadata."""
        company_meta = frappe.get_meta("Company", cached=False)
        fieldnames = (
            "custom_algerian_registration_section",
            "custom_nif",
            "custom_article_imposition",
            "custom_algerian_registration_column_break",
            "custom_nis",
            "custom_rc",
            "custom_capital_social",
        )
        for fieldname in fieldnames:
            self.assertTrue(
                frappe.db.exists(
                    "Custom Field",
                    {"dt": "Company", "fieldname": fieldname, "module": "Sotrama"},
                ),
                f"Custom field {fieldname} not found on Company doctype",
            )
            self.assertIsNotNone(
                company_meta.get_field(fieldname),
                f"{fieldname} is in Custom Field but missing from Company metadata",
            )

        self.assertEqual(
            frappe.get_value("Custom Field", {"dt": "Company", "fieldname": "custom_nif"}, "module"),
            "Sotrama",
        )

    def test_company_tax_id_alias_syncs_without_overwriting_conflicts(self):
        from sotrama.hooks import validate_algerian_company_tax_id

        doc = frappe._dict({
            "country": "Algeria",
            "custom_nif": "001234567890123",
            "tax_id": None,
        })
        validate_algerian_company_tax_id(doc)
        self.assertEqual(doc.tax_id, doc.custom_nif)

        reverse = frappe._dict({
            "country": "Algeria",
            "custom_nif": None,
            "tax_id": "001234567890123",
        })
        validate_algerian_company_tax_id(reverse)
        self.assertEqual(reverse.custom_nif, reverse.tax_id)

        conflict = frappe._dict({
            "country": "Algeria",
            "custom_nif": "111",
            "tax_id": "222",
        })
        with self.assertRaises(frappe.ValidationError):
            validate_algerian_company_tax_id(conflict)


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
        self.classification.submit()

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
            frappe.get_doc("Company Classification", self.classification.name).cancel()
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
        self.classification.submit()

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
            frappe.get_doc("Company Classification", self.classification.name).cancel()
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


class TestDriverStatusWorkflow(unittest.TestCase):
    def setUp(self):
        self.driver = frappe.new_doc("Driver")
        self.driver.driver_name = f"Test Driver {uuid.uuid4().hex[:8]}"
        self.driver.license_number = f"TEST-{uuid.uuid4().hex[:8]}"
        self.driver.license_expiry = add_days(today(), 365)
        self.driver.insert(ignore_permissions=True)
        self.driver.submit()

    def tearDown(self):
        if frappe.db.exists("Driver", self.driver.name):
            driver = frappe.get_doc("Driver", self.driver.name)
            if driver.docstatus == 1:
                driver.cancel()
            frappe.delete_doc("Driver", self.driver.name, ignore_permissions=True)

    def test_driver_status_uses_audited_transitions_and_revalidates_on_reactivation(self):
        from sotrama.tp.doctype.driver.driver import update_driver_status

        update_driver_status(self.driver.name, "Suspended")
        self.assertEqual(frappe.db.get_value("Driver", self.driver.name, "status"), "Suspended")

        update_driver_status(self.driver.name, "Active")
        self.assertEqual(frappe.db.get_value("Driver", self.driver.name, "status"), "Active")

        update_driver_status(self.driver.name, "Terminated")
        with self.assertRaises(frappe.ValidationError):
            update_driver_status(self.driver.name, "Active")

        comments = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Driver", "reference_name": self.driver.name},
            fields=["content"],
            order_by="creation asc",
        )
        self.assertTrue(any("Terminated" in (comment.content or "") for comment in comments))


class TestMaintenanceScheduleWorkflow(unittest.TestCase):
    def setUp(self):
        self.classification = frappe.new_doc("Company Classification")
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = f"TEST-SCH-{uuid.uuid4().hex[:6]}"
        self.classification.insert(ignore_permissions=True)
        self.classification.submit()

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.license_plate = f"TEST-SCH-{uuid.uuid4().hex[:6]}"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert(ignore_permissions=True)
        self.vehicle.submit()

        self.job_type = frappe.new_doc("Maintenance Job Type")
        self.job_type.job_category = "General"
        self.job_type.job_type_name = f"Test Service {uuid.uuid4().hex[:8]}"
        self.job_type.insert(ignore_permissions=True)
        self.job_type.submit()
        self.created_schedules = []
        self.created_job_cards = []

        self.schedule = frappe.new_doc("Maintenance Schedule")
        self.schedule.vehicle = self.vehicle.name
        self.schedule.job_type = self.job_type.name
        self.schedule.schedule_type = "Calendar"
        self.schedule.interval_months = 6
        self.schedule.last_service_date = today()
        self.schedule.insert(ignore_permissions=True)
        self.schedule.submit()
        self.created_schedules.append(self.schedule.name)

    def tearDown(self):
        for name in self.created_job_cards:
            if frappe.db.exists("Maintenance Job Card", name):
                job_card = frappe.get_doc("Maintenance Job Card", name)
                if job_card.docstatus == 1:
                    job_card.cancel()
                frappe.delete_doc("Maintenance Job Card", name, ignore_permissions=True)
        for name in self.created_schedules:
            if frappe.db.exists("Maintenance Schedule", name):
                schedule = frappe.get_doc("Maintenance Schedule", name)
                if schedule.docstatus == 1:
                    schedule.cancel()
                frappe.delete_doc("Maintenance Schedule", name, ignore_permissions=True)
        for doctype, name in (
            ("Maintenance Job Type", self.job_type.name),
            ("Vehicle", self.vehicle.name),
            ("Company Classification", self.classification.name),
        ):
            if frappe.db.exists(doctype, name):
                doc = frappe.get_doc(doctype, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(doctype, name, ignore_permissions=True)

    def test_completion_creates_one_linked_successor_and_is_idempotent(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            update_maintenance_schedule_status,
        )

        update_maintenance_schedule_status(self.schedule.name, "Paused")
        update_maintenance_schedule_status(self.schedule.name, "Active")
        result = update_maintenance_schedule_status(self.schedule.name, "Completed")
        self.assertEqual(result["status"], "Completed")
        self.assertTrue(result["next_schedule"])
        self.created_schedules.append(result["next_schedule"])

        successor = frappe.get_doc("Maintenance Schedule", result["next_schedule"])
        self.assertEqual(successor.docstatus, 1)
        self.assertEqual(successor.status, "Active")
        self.assertEqual(successor.vehicle, self.vehicle.name)
        self.assertEqual(successor.job_type, self.job_type.name)
        self.assertTrue(successor.next_due_date)

        repeated = update_maintenance_schedule_status(self.schedule.name, "Completed")
        self.assertEqual(repeated["next_schedule"], successor.name)

    def test_mileage_plan_cannot_complete_without_a_last_service_reading(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            update_maintenance_schedule_status,
        )

        self.schedule.db_set({"schedule_type": "Mileage", "interval_months": None, "interval_km": 10000})
        with self.assertRaises(frappe.ValidationError):
            update_maintenance_schedule_status(self.schedule.name, "Completed")

    def test_completed_scheduled_job_card_advances_same_plan_and_cancel_restores_it(self):
        from frappe.utils import add_days, add_months

        original_due_date = add_days(today(), 30)
        self.schedule.db_set({
            "last_service_date": add_days(today(), -30),
            "next_due_date": original_due_date,
            "last_service_job_card": None,
        })

        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.job_date = today()
        job_card.completion_date = today()
        job_card.vehicle = self.vehicle.name
        job_card.job_nature = "Scheduled Service"
        job_card.job_type = self.job_type.name
        job_card.maintenance_schedule = self.schedule.name
        job_card.status = "Completed"
        job_card.insert(ignore_permissions=True)
        self.created_job_cards.append(job_card.name)
        job_card.submit()

        updated_schedule = frappe.get_doc("Maintenance Schedule", self.schedule.name)
        self.assertEqual(updated_schedule.status, "Active")
        self.assertEqual(updated_schedule.last_service_job_card, job_card.name)
        self.assertEqual(getdate(updated_schedule.last_service_date), getdate(today()))
        self.assertEqual(getdate(updated_schedule.next_due_date), getdate(add_months(today(), 6)))
        self.assertEqual(updated_schedule.next_schedule, None)

        job_card.cancel()
        restored_schedule = frappe.get_doc("Maintenance Schedule", self.schedule.name)
        self.assertIsNone(restored_schedule.last_service_job_card)
        self.assertEqual(getdate(restored_schedule.last_service_date), getdate(add_days(today(), -30)))
        self.assertEqual(getdate(restored_schedule.next_due_date), getdate(original_due_date))


class TestBreakdownIncident(unittest.TestCase):
    """Test Breakdown Incident validation and workflow."""

    def setUp(self):
        self.classification = frappe.new_doc("Company Classification")
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = "TEST-BRK-001"
        self.classification.insert(ignore_permissions=True)
        self.classification.submit()

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.license_plate = "TEST-BRK-VEH-001"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert()
        self.created_breakdowns = []
        self.created_inspections = []
        self.created_drivers = []

    def tearDown(self):
        for name in reversed(self.created_inspections):
            if frappe.db.exists("Vehicle Inspection", name):
                inspection = frappe.get_doc("Vehicle Inspection", name)
                if inspection.docstatus == 1:
                    inspection.cancel()
                frappe.delete_doc("Vehicle Inspection", name, ignore_permissions=True)
        for name in self.created_breakdowns:
            if frappe.db.exists("Breakdown Incident", name):
                incident = frappe.get_doc("Breakdown Incident", name)
                if incident.docstatus == 1:
                    incident.cancel()
                frappe.delete_doc("Breakdown Incident", name, ignore_permissions=True)
        for name in self.created_drivers:
            if frappe.db.exists("Driver", name):
                driver = frappe.get_doc("Driver", name)
                if driver.docstatus == 1:
                    driver.cancel()
                frappe.delete_doc("Driver", name, ignore_permissions=True)
        for doctype, name in (
            ("Vehicle", self.vehicle.name),
            ("Company Classification", self.classification.name),
        ):
            if frappe.db.exists(doctype, name):
                if doctype == "Company Classification":
                    frappe.get_doc(doctype, name).cancel()
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

    def test_breakdown_can_record_a_historical_incident_for_a_suspended_driver(self):
        from frappe.utils import add_days, now_datetime

        from sotrama.tp.doctype.driver.driver import update_driver_status

        driver = frappe.new_doc("Driver")
        driver.driver_name = f"Suspended Driver {uuid.uuid4().hex[:8]}"
        driver.license_number = f"TEST-{uuid.uuid4().hex[:8]}"
        driver.license_expiry = add_days(today(), 365)
        driver.insert(ignore_permissions=True)
        driver.submit()
        self.created_drivers.append(driver.name)
        update_driver_status(driver.name, "Suspended")

        breakdown = frappe.new_doc("Breakdown Incident")
        breakdown.vehicle = self.vehicle.name
        breakdown.driver = driver.name
        breakdown.incident_date = now_datetime()
        breakdown.description = "Historical incident attributed to a suspended driver"
        breakdown.insert(ignore_permissions=True)
        self.created_breakdowns.append(breakdown.name)
        with patch("sotrama.tp.doctype.breakdown_incident.breakdown_incident.BreakdownIncident._create_job_card"):
            breakdown.submit()

        self.assertEqual(breakdown.driver, driver.name)

    def _submit_breakdown(self):
        from frappe.utils import now_datetime

        breakdown = frappe.new_doc("Breakdown Incident")
        breakdown.vehicle = self.vehicle.name
        breakdown.incident_date = now_datetime()
        breakdown.description = "Test vehicle breakdown"
        breakdown.insert(ignore_permissions=True)
        self.created_breakdowns.append(breakdown.name)
        # Job-card creation has its own workflow; isolate the vehicle-status
        # lifecycle here so the test does not create a cross-linked work order.
        with patch("sotrama.tp.doctype.breakdown_incident.breakdown_incident.BreakdownIncident._create_job_card"):
            breakdown.submit()
        return frappe.get_doc("Breakdown Incident", breakdown.name)

    def _set_breakdown_status(self, name, status):
        from frappe.utils import now_datetime

        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            update_breakdown_status,
        )

        values = {}
        if status == "Resolved":
            values = {
                "resolution_date": now_datetime(),
                "resolution_notes": "Test repair completed",
            }
        update_breakdown_status(name, status, **values)
        return frappe.get_doc("Breakdown Incident", name)

    def _submit_critical_inspection(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.vehicle = self.vehicle.name
        inspection.inspection_type = "Periodic"
        inspection.inspection_date = today()
        inspection.append("inspection_items", {
            "category": "Freinage et direction",
            "item_details": "Brake system check",
            "status": "Defective",
            "remarks": "Test brake defect",
            "is_safety_critical": 1,
        })
        inspection.insert(ignore_permissions=True)
        self.created_inspections.append(inspection.name)
        with patch("sotrama.tp.doctype.vehicle_inspection.vehicle_inspection.VehicleInspection._create_defect_issues"):
            inspection.submit()
        return inspection

    def _submit_follow_up_inspection(self, previous_inspection):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.vehicle = self.vehicle.name
        inspection.inspection_type = "Post-Incident"
        inspection.inspection_date = today()
        inspection.overall_status = "Pass"
        inspection.follow_up_of = previous_inspection.name
        inspection.append("inspection_items", {
            "category": "Freinage et direction",
            "item_details": "Brake system reinspection",
            "status": "Okay",
            "is_safety_critical": 1,
        })
        inspection.insert(ignore_permissions=True)
        self.created_inspections.append(inspection.name)
        with patch("sotrama.tp.doctype.vehicle_inspection.vehicle_inspection.VehicleInspection._create_defect_issues"):
            inspection.submit()
        return inspection

    def test_resolving_breakdown_restores_vehicle_status(self):
        breakdown = self._submit_breakdown()
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )
        self.assertEqual(breakdown.previous_vehicle_status, "Active")

        self._set_breakdown_status(breakdown.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )

    def test_reopening_resolved_breakdown_marks_vehicle_out_of_service_again(self):
        breakdown = self._submit_breakdown()
        self._set_breakdown_status(breakdown.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )

        self._set_breakdown_status(breakdown.name, "In Progress")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )
        self.assertEqual(
            frappe.db.get_value(
                "Breakdown Incident", breakdown.name, "previous_vehicle_status"
            ),
            "Active",
        )
        self.assertFalse(
            frappe.db.get_value("Breakdown Incident", breakdown.name, "resolution_date")
        )
        self.assertEqual(
            frappe.db.get_value("Breakdown Incident", breakdown.name, "downtime_hours"),
            0,
        )

    def test_resolved_breakdown_requires_a_resolution_date(self):
        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            update_breakdown_status,
        )

        breakdown = self._submit_breakdown()
        with self.assertRaises(frappe.ValidationError):
            update_breakdown_status(breakdown.name, "Resolved")

    def test_breakdown_status_transition_is_audited_and_disallows_invalid_jumps(self):
        from frappe.utils import now_datetime

        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            update_breakdown_status,
        )

        breakdown = self._submit_breakdown()
        with self.assertRaises(frappe.ValidationError):
            update_breakdown_status(breakdown.name, "Closed")

        self._set_breakdown_status(breakdown.name, "Acknowledged")
        self._set_breakdown_status(breakdown.name, "In Progress")
        update_breakdown_status(
            breakdown.name,
            "Resolved",
            resolution_date=now_datetime(),
            resolution_notes="Resolved in test",
        )

        comments = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Breakdown Incident", "reference_name": breakdown.name},
            fields=["content"],
            order_by="creation asc",
        )
        self.assertTrue(any("Resolved" in (comment.content or "") for comment in comments))

    def test_overlapping_breakdowns_keep_vehicle_out_of_service_until_last_resolves(self):
        first = self._submit_breakdown()
        second = self._submit_breakdown()

        self._set_breakdown_status(first.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )

        self._set_breakdown_status(second.name, "Resolved")
        self._set_breakdown_status(second.name, "Closed")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )

    def test_resolving_breakdown_preserves_preexisting_manual_out_of_service(self):
        frappe.db.set_value("Vehicle", self.vehicle.name, "vehicle_status", "Out of Service")
        breakdown = self._submit_breakdown()
        self.assertEqual(breakdown.previous_vehicle_status, "Out of Service")

        self._set_breakdown_status(breakdown.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )

    def test_resolving_breakdown_does_not_override_critical_inspection(self):
        breakdown = self._submit_breakdown()
        inspection = self._submit_critical_inspection()

        self._set_breakdown_status(breakdown.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )

        inspection.cancel()
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )

    def test_successful_follow_up_clears_critical_inspection_and_cancel_reinstates_hold(self):
        critical = self._submit_critical_inspection()
        follow_up = self._submit_follow_up_inspection(critical)

        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )
        self.assertEqual(
            frappe.db.get_value(
                "Vehicle Inspection", critical.name, "critical_defect_cleared_by"
            ),
            follow_up.name,
        )

        follow_up.cancel()
        self.assertFalse(
            frappe.db.get_value(
                "Vehicle Inspection", critical.name, "critical_defect_cleared_by"
            )
        )
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )
