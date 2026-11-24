# Frappe integration tests for Sotrama vehicle behavior.

import unittest
import uuid
from unittest.mock import call as mock_call
from unittest.mock import patch

import frappe
from frappe.utils import add_days, today

from sotrama.tests.helpers import (
    _delete_test_record,
    _get_test_company,
    _sotrama_package_path,
)


class TestVehicle(unittest.TestCase):
    """Test Vehicle doctype validation and lifecycle."""

    def setUp(self):
        """Create test dependencies."""
        self.company = _get_test_company()
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
            _delete_test_record("Vehicle", self.created_vehicle)
        for doctype, document in (
            ("Vehicle Model", getattr(self, "model", None)),
            ("Vehicle Make", getattr(self, "make", None)),
        ):
            if document and frappe.db.exists(doctype, document.name):
                _delete_test_record(doctype, document.name)
        for doctype in ["Vehicle Model", "Vehicle Make"]:
            for name in frappe.get_all(doctype, pluck="name"):
                if name.startswith("Test"):
                    _delete_test_record(doctype, name)

    def test_vehicle_creation_with_required_fields(self):
        """Test that a Vehicle can be created with all required fields."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
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
        vehicle.insert()
        self.created_vehicle = vehicle.name

        self.assertEqual(vehicle.vehicle_status, "Active")
        self.assertEqual(vehicle.fuel_type, "Diesel")
        self.assertEqual(vehicle.license_plate, "TEST-001")
        self.assertRegex(vehicle.name, r"^VEH-\d{4}-\d{4}$")
        self.assertFalse(vehicle.company_classification)

        vehicle_meta = frappe.get_meta("Vehicle", cached=False)
        self.assertTrue(vehicle_meta.get_field("company_classification").hidden)
        self.assertFalse(vehicle_meta.get_field("company_classification").reqd)
        self.assertFalse(vehicle_meta.get_field("section_vehicle_identity").collapsible)
        for section in (
            "section_specs",
            "section_acquisition",
            "section_assignment",
        ):
            self.assertTrue(vehicle_meta.get_field(section).collapsible, section)
        self.assertTrue(vehicle_meta.get_field("section_documents").collapsible)
        self.assertIn(
            "carte grise", vehicle_meta.get_field("section_documents").description
        )
        document_meta = frappe.get_meta("Vehicle Document", cached=False)
        self.assertTrue(document_meta.get_field("issue_date").in_list_view)
        self.assertTrue(document_meta.get_field("expiry_date").in_list_view)
        self.assertTrue(document_meta.get_field("attachment").in_list_view)
        self.assertTrue(document_meta.get_field("status").in_list_view)
        vehicle_field_order = [field.fieldname for field in vehicle_meta.fields]
        self.assertLess(
            vehicle_field_order.index("vehicle_documents"),
            vehicle_field_order.index("section_assignment"),
        )
        self.assertLess(
            vehicle_field_order.index("vehicle_documents"),
            vehicle_field_order.index("notes"),
        )
        self.assertEqual(
            [
                field.fieldname
                for field in vehicle_meta.fields
                if field.fieldtype == "Tab Break"
            ],
            [
                "tab_vehicle_identity",
                "tab_vehicle_value",
                "tab_vehicle_assignment",
            ],
        )

        _delete_test_record("Vehicle", vehicle.name)

    def test_vehicle_rejects_invalid_acquisition_and_depreciation_values(self):
        invalid_values = (
            ({"acquisition_value": -1}, "Acquisition Value cannot be negative"),
            ({"salvage_value": -1}, "Salvage Value cannot be negative"),
            (
                {"acquisition_value": 100000, "salvage_value": 100001},
                "Salvage Value cannot exceed Acquisition Value",
            ),
            (
                {"depreciation_rate": -0.01},
                "Depreciation Rate must be between 0 and 100 percent",
            ),
            (
                {"depreciation_rate": 100.01},
                "Depreciation Rate must be between 0 and 100 percent",
            ),
        )
        for index, (values, message) in enumerate(invalid_values):
            with self.subTest(values=values):
                vehicle = frappe.new_doc("Vehicle")
                vehicle.company = self.company
                vehicle.license_plate = (
                    f"TEST-INVALID-ASSET-{index}-{uuid.uuid4().hex[:4]}"
                )
                vehicle.vehicle_category = "Truck"
                vehicle.acquisition_value = 100000
                vehicle.depreciation_rate = 10
                vehicle.salvage_value = 0
                for fieldname, value in values.items():
                    setattr(vehicle, fieldname, value)

                try:
                    with self.assertRaisesRegex(frappe.ValidationError, message):
                        vehicle.insert(ignore_permissions=True)
                finally:
                    if vehicle.name and frappe.db.exists("Vehicle", vehicle.name):
                        _delete_test_record("Vehicle", vehicle.name)

    def test_legacy_invalid_asset_values_do_not_block_unrelated_vehicle_edits(self):
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = f"TEST-LEGACY-ASSET-{uuid.uuid4().hex[:6]}"
        vehicle.vehicle_category = "Truck"
        vehicle.acquisition_value = 100000
        vehicle.depreciation_rate = 10
        vehicle.salvage_value = 0
        vehicle.insert(ignore_permissions=True)
        self.created_vehicle = vehicle.name

        frappe.db.set_value(
            "Vehicle",
            vehicle.name,
            {
                "acquisition_value": -1,
                "depreciation_rate": 101,
                "salvage_value": -2,
            },
        )
        vehicle.reload()
        vehicle.notes = "Unrelated legacy record update"
        vehicle.save(ignore_permissions=True)

        self.assertEqual(vehicle.acquisition_value, -1)
        self.assertEqual(vehicle.depreciation_rate, 101)
        self.assertEqual(vehicle.salvage_value, -2)
        self.assertEqual(vehicle.notes, "Unrelated legacy record update")
        _delete_test_record("Vehicle", vehicle.name)

    def test_vehicle_document_statuses_are_recalculated_on_parent_save(self):
        vehicle = frappe.new_doc("Vehicle")
        vehicle.append(
            "vehicle_documents",
            {
                "document_type": "Insurance Certificate",
                "expiry_date": add_days(today(), 5),
            },
        )
        vehicle.append(
            "vehicle_documents",
            {
                "document_type": "Technical Inspection",
                "expiry_date": add_days(today(), -1),
            },
        )
        vehicle.append(
            "vehicle_documents",
            {"document_type": "Registration Certificate"},
        )
        vehicle.append(
            "vehicle_documents",
            {"document_type": "Other Document", "expiry_date": add_days(today(), 31)},
        )

        with patch("sotrama.tp.settings.get_tp_setting", return_value=30):
            vehicle._update_vehicle_document_statuses()

        self.assertEqual(
            [row.status for row in vehicle.vehicle_documents],
            ["Expiring Soon", "Expired", "Pending", "Valid"],
        )

    def test_cancelling_vehicle_closes_only_its_document_expiry_alerts(self):
        vehicle = frappe.new_doc("Vehicle")
        vehicle.name = "VEH-CANCEL-EXPIRY-001"
        expiry_todo = frappe._dict(
            name="TODO-VEHICLE-EXPIRY",
            description="Vehicle Document Row: ROW-VEHICLE-EXPIRY | Expiry: 2026-12-01",
        )
        legacy_todo = frappe._dict(
            name="TODO-VEHICLE-EXPIRY-LEGACY",
            description="Vehicle Document Expiring: Insurance Certificate (Vehicle: TEST-001)",
        )
        unrelated_todo = frappe._dict(
            name="TODO-VEHICLE-OTHER", description="Follow up with workshop"
        )

        with (
            patch(
                "sotrama.tp.doctype.vehicle.vehicle.frappe.get_all",
                return_value=[expiry_todo, legacy_todo, unrelated_todo],
            ) as get_all,
            patch(
                "sotrama.tp.doctype.vehicle.vehicle.frappe.db.set_value"
            ) as set_value,
        ):
            vehicle._cancel_related_records()

        get_all.assert_called_once_with(
            "ToDo",
            filters={
                "reference_type": "Vehicle",
                "reference_name": vehicle.name,
                "status": "Open",
            },
            fields=["name", "description"],
            limit_page_length=0,
        )
        set_value.assert_any_call(
            "Vehicle", vehicle.name, "vehicle_status", "Out of Service"
        )
        set_value.assert_any_call(
            "ToDo", expiry_todo.name, "status", "Closed", update_modified=False
        )
        set_value.assert_any_call(
            "ToDo", legacy_todo.name, "status", "Closed", update_modified=False
        )
        self.assertNotIn(
            mock_call(
                "ToDo", unrelated_todo.name, "status", "Closed", update_modified=False
            ),
            set_value.call_args_list,
        )

    def test_vehicle_registration_or_fleet_number_is_unique_within_company(self):
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = " duplicate-fleet-001 "
        vehicle.vehicle_category = "Truck"
        vehicle.insert(ignore_permissions=True)
        self.assertEqual(vehicle.license_plate, "DUPLICATE-FLEET-001")

        duplicate = frappe.new_doc("Vehicle")
        duplicate.company = self.company
        duplicate.license_plate = "duplicate-fleet-001"
        duplicate.vehicle_category = "Truck"
        with self.assertRaises(frappe.ValidationError):
            duplicate.insert(ignore_permissions=True)

        _delete_test_record("Vehicle", vehicle.name)

    def test_vehicle_rejects_a_model_from_a_different_make(self):
        other_make = frappe.new_doc("Vehicle Make")
        other_make.make_name = f"Other Make {uuid.uuid4().hex[:6]}"
        other_make.insert(ignore_permissions=True)

        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = f"TEST-MODEL-{uuid.uuid4().hex[:6]}"
        vehicle.vehicle_category = "Truck"
        vehicle.vehicle_make = other_make.name
        vehicle.model = self.model.name
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert(ignore_permissions=True)

        _delete_test_record("Vehicle Make", other_make.name)

    def test_legacy_company_classification_reference_does_not_block_vehicle_edits(self):
        classification = frappe.new_doc("Company Classification")
        classification.company = self.company
        classification.grade = 1
        classification.category = "Public Works (TP)"
        classification.registration_number = f"LEGACY-{uuid.uuid4().hex[:8]}"
        classification.insert(ignore_permissions=True)

        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = f"TEST-LEGACY-{uuid.uuid4().hex[:6]}"
        vehicle.vehicle_category = "Truck"
        vehicle.company_classification = classification.name
        vehicle.insert(ignore_permissions=True)

        self.assertEqual(vehicle.company_classification, classification.name)
        classification.db_set("active", 0)
        vehicle.license_plate = f"{vehicle.license_plate}-EDITED"
        vehicle.save(ignore_permissions=True)
        self.assertEqual(vehicle.company_classification, classification.name)
        _delete_test_record("Vehicle", vehicle.name)
        _delete_test_record("Company Classification", classification.name)

    def test_vehicle_rejects_an_inactive_model(self):
        self.model.db_set("active", 0)
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = f"TEST-INACTIVE-{uuid.uuid4().hex[:6]}"
        vehicle.vehicle_category = "Truck"
        vehicle.vehicle_make = self.make.name
        vehicle.model = self.model.name
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert(ignore_permissions=True)

    def test_vehicle_model_cannot_use_an_inactive_make(self):
        inactive_make = frappe.new_doc("Vehicle Make")
        inactive_make.make_name = f"Inactive Make {uuid.uuid4().hex[:6]}"
        inactive_make.active = 0
        inactive_make.insert(ignore_permissions=True)
        model = frappe.new_doc("Vehicle Model")
        model.vehicle_make = inactive_make.name
        model.model_name = f"Invalid Model {uuid.uuid4().hex[:6]}"
        with self.assertRaises(frappe.ValidationError):
            model.insert(ignore_permissions=True)

        _delete_test_record("Vehicle Make", inactive_make.name)

    def test_fleet_lookup_masters_do_not_require_submission(self):
        for doctype in ("Vehicle Make", "Vehicle Model", "Maintenance Job Type"):
            meta = frappe.get_meta(doctype, cached=False)
            self.assertFalse(meta.is_submittable, doctype)
            for permission in meta.permissions:
                self.assertFalse(permission.submit, doctype)
                self.assertFalse(permission.cancel, doctype)
                self.assertFalse(permission.amend, doctype)
        model_meta = frappe.get_meta("Vehicle Model", cached=False)
        self.assertEqual(model_meta.title_field, "model_name")
        self.assertTrue(model_meta.show_title_field_in_link)
        self.assertEqual(model_meta.naming_rule, "By script")
        self.assertTrue(model_meta.get_field("make").hidden)
        make_meta = frappe.get_meta("Vehicle Make", cached=False)
        self.assertEqual(make_meta.title_field, "make_name")
        self.assertTrue(make_meta.show_title_field_in_link)
        self.assertEqual(make_meta.naming_rule, "By fieldname")
        self.assertEqual(make_meta.autoname, "field:make_name")
        self.assertEqual(
            frappe.get_meta("Vehicle", cached=False).title_field, "license_plate"
        )
        self.assertEqual(
            frappe.get_meta("Driver", cached=False).title_field, "driver_name"
        )
        self.assertEqual(
            frappe.get_meta("Maintenance Job Type", cached=False).title_field,
            "job_type_name",
        )
        self.assertEqual(
            frappe.get_meta("Maintenance Job Type", cached=False).naming_rule,
            "By fieldname",
        )
        self.assertEqual(
            frappe.get_meta("Maintenance Job Type", cached=False).autoname,
            "field:job_type_name",
        )

    def test_fleet_documents_use_native_v16_naming_patterns(self):
        expected_patterns = {
            "Breakdown Incident": "BRK-.YYYY.-.####",
            "Company Classification": "CLAS-.YYYY.-.####",
            "Driver": "DRV-.####",
            "Maintenance Job Card": "JC-.YYYY.-.####",
            "Maintenance Schedule": "SCH-.YYYY.-.####",
            "Operational Task": "OT-.YYYY.-.####",
            "Vehicle": "VEH-.YYYY.-.####",
            "Vehicle Inspection": "INSP-.YYYY.-.####",
        }
        for doctype, pattern in expected_patterns.items():
            with self.subTest(doctype=doctype):
                meta = frappe.get_meta(doctype, cached=False)
                self.assertEqual(meta.naming_rule, "Expression")
                self.assertEqual(meta.autoname, pattern)
                self.assertFalse(getattr(meta, "naming_expression", None))

    def test_maintenance_job_type_uses_trimmed_readable_name(self):
        job_type = frappe.new_doc("Maintenance Job Type")
        job_type_name = f"Preventive Service {uuid.uuid4().hex[:6]}"
        job_type.job_type_name = f"  {job_type_name}  "
        job_type.job_category = "General"
        job_type.insert(ignore_permissions=True)

        self.assertEqual(job_type.name, job_type_name)
        self.assertEqual(job_type.job_type_name, job_type_name)
        _delete_test_record("Maintenance Job Type", job_type.name)

    def test_vehicle_model_link_uses_readable_title_with_stable_internal_id(self):
        from sotrama.tp.doctype.vehicle_model.vehicle_model import (
            get_vehicle_model_name,
        )

        make_name = f"Tata UX {uuid.uuid4().hex[:6]}"
        make = frappe.new_doc("Vehicle Make")
        make.make_name = f"  {make_name}  "
        make.insert(ignore_permissions=True)

        model = frappe.new_doc("Vehicle Model")
        model.vehicle_make = make.name
        model.model_name = " Actros 2646 "
        model.insert(ignore_permissions=True)

        self.assertEqual(make.name, make_name)
        self.assertEqual(make.make_name, make_name)
        self.assertEqual(model.model_name, "Actros 2646")
        self.assertEqual(model.name, get_vehicle_model_name(make.name, "Actros 2646"))
        self.assertTrue(
            frappe.get_meta("Vehicle Model", cached=False).show_title_field_in_link
        )
        _delete_test_record("Vehicle Model", model.name)
        _delete_test_record("Vehicle Make", make.name)

    def test_same_model_designation_is_allowed_for_different_makes(self):
        from sotrama.tp.doctype.vehicle_model.vehicle_model import (
            get_vehicle_model_name,
        )

        makes = []
        models = []
        model_name = f"Shared Model {uuid.uuid4().hex[:6]}"
        try:
            for label in ("Make A", "Make B"):
                make = frappe.new_doc("Vehicle Make")
                make.make_name = f"{label} {uuid.uuid4().hex[:6]}"
                make.insert(ignore_permissions=True)
                makes.append(make)

                model = frappe.new_doc("Vehicle Model")
                model.vehicle_make = make.name
                model.model_name = model_name
                model.insert(ignore_permissions=True)
                models.append(model)

            self.assertEqual(len({model.name for model in models}), 2)
            self.assertEqual(
                {model.name for model in models},
                {get_vehicle_model_name(make.name, model_name) for make in makes},
            )
        finally:
            for model in models:
                _delete_test_record("Vehicle Model", model.name)
            for make in makes:
                _delete_test_record("Vehicle Make", make.name)

    def test_model_id_uses_linked_make_identity_when_legacy_make_id_is_random(self):
        from sotrama.tp.doctype.vehicle_model.vehicle_model import (
            get_vehicle_model_name,
        )

        legacy_make = frappe.get_doc(
            {
                "doctype": "Vehicle Make",
                "name": f"legacy-{uuid.uuid4().hex[:8]}",
                "make_name": f"Tata Legacy {uuid.uuid4().hex[:6]}",
                "active": 1,
            }
        )
        legacy_make.db_insert()

        model = frappe.new_doc("Vehicle Model")
        model.vehicle_make = legacy_make.name
        model.model_name = "Actros 2646"
        model.insert(ignore_permissions=True)

        self.assertEqual(
            model.name, get_vehicle_model_name(legacy_make.name, "Actros 2646")
        )
        _delete_test_record("Vehicle Model", model.name)
        _delete_test_record("Vehicle Make", legacy_make.name)

    def test_fleet_master_name_migration_updates_existing_links(self):
        from sotrama.migrations.fleet_master_names import (
            normalize_fleet_master_names as execute,
        )
        from sotrama.tp.doctype.vehicle_model.vehicle_model import (
            get_vehicle_model_name,
        )

        old_make_name = f"m{uuid.uuid4().hex[:11]}"
        make_name = f"Tata Migration {uuid.uuid4().hex[:6]}"
        model_name = "Actros 2646"
        old_model_name = f"{old_make_name}-{model_name}"
        old_job_type_name = f"j{uuid.uuid4().hex[:11]}"
        job_type_name = f"Legacy Job {uuid.uuid4().hex[:6]}"

        legacy_make = frappe.get_doc(
            {
                "doctype": "Vehicle Make",
                "name": old_make_name,
                "make_name": make_name,
                "active": 1,
            }
        )
        legacy_make.db_insert()
        legacy_model = frappe.get_doc(
            {
                "doctype": "Vehicle Model",
                "name": old_model_name,
                "vehicle_make": old_make_name,
                "make": old_make_name,
                "model_name": model_name,
                "active": 1,
            }
        )
        legacy_model.db_insert()
        legacy_model_without_link = frappe.get_doc(
            {
                "doctype": "Vehicle Model",
                "name": f"{old_make_name}-Legacy Model",
                "make": old_make_name,
                "model_name": "Legacy Model",
                "active": 1,
            }
        )
        legacy_model_without_link.db_insert()
        legacy_job_type = frappe.get_doc(
            {
                "doctype": "Maintenance Job Type",
                "name": old_job_type_name,
                "job_type_name": job_type_name,
                "job_category": "Engine",
                "active": 1,
            }
        )
        legacy_job_type.db_insert()

        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = f"TEST-RENAME-{uuid.uuid4().hex[:6]}"
        vehicle.vehicle_category = "Truck"
        vehicle.vehicle_make = old_make_name
        vehicle.model = old_model_name
        vehicle.insert(ignore_permissions=True)

        execute()

        new_model_name = get_vehicle_model_name(make_name, model_name)
        new_legacy_model_name = get_vehicle_model_name(make_name, "Legacy Model")
        vehicle.reload()
        self.assertTrue(frappe.db.exists("Vehicle Make", make_name))
        self.assertFalse(frappe.db.exists("Vehicle Make", old_make_name))
        self.assertTrue(frappe.db.exists("Vehicle Model", new_model_name))
        self.assertFalse(frappe.db.exists("Vehicle Model", old_model_name))
        self.assertEqual(vehicle.vehicle_make, make_name)
        self.assertEqual(vehicle.model, new_model_name)
        self.assertEqual(
            frappe.db.get_value("Vehicle Model", new_model_name, "make"),
            make_name,
        )
        self.assertTrue(frappe.db.exists("Vehicle Model", new_legacy_model_name))
        self.assertFalse(
            frappe.db.exists("Vehicle Model", f"{old_make_name}-Legacy Model")
        )
        self.assertEqual(
            frappe.db.get_value("Vehicle Model", new_legacy_model_name, "vehicle_make"),
            make_name,
        )
        self.assertTrue(frappe.db.exists("Maintenance Job Type", job_type_name))
        self.assertFalse(frappe.db.exists("Maintenance Job Type", old_job_type_name))

        # The normalization is safe to invoke again (for example from a
        # manually retried migration in a disposable test database).
        execute()
        self.assertTrue(frappe.db.exists("Vehicle Make", make_name))
        self.assertTrue(frappe.db.exists("Vehicle Model", new_model_name))
        self.assertTrue(frappe.db.exists("Maintenance Job Type", job_type_name))

        _delete_test_record("Vehicle", vehicle.name)
        _delete_test_record("Vehicle Model", new_legacy_model_name)
        _delete_test_record("Vehicle Model", new_model_name)
        _delete_test_record("Vehicle Make", make_name)
        _delete_test_record("Maintenance Job Type", job_type_name)

    def test_fleet_master_name_migration_skips_name_collisions(self):
        from sotrama.migrations.fleet_master_names import (
            normalize_fleet_master_names as execute,
        )

        target_name = f"Tata Collision {uuid.uuid4().hex[:6]}"
        old_name = f"m{uuid.uuid4().hex[:11]}"
        existing = frappe.get_doc(
            {
                "doctype": "Vehicle Make",
                "name": target_name,
                "make_name": target_name,
                "active": 1,
            }
        )
        existing.db_insert()
        legacy = frappe.get_doc(
            {
                "doctype": "Vehicle Make",
                "name": old_name,
                "make_name": target_name,
                "active": 1,
            }
        )
        legacy.db_insert()

        job_type_target = f"Legacy Job Collision {uuid.uuid4().hex[:6]}"
        old_job_type_name = f"j{uuid.uuid4().hex[:11]}"
        existing_job_type = frappe.get_doc(
            {
                "doctype": "Maintenance Job Type",
                "name": job_type_target,
                "job_type_name": job_type_target,
                "job_category": "Engine",
                "active": 1,
            }
        )
        existing_job_type.db_insert()
        legacy_job_type = frappe.get_doc(
            {
                "doctype": "Maintenance Job Type",
                "name": old_job_type_name,
                "job_type_name": f" {job_type_target} ",
                "job_category": "Engine",
                "active": 1,
            }
        )
        legacy_job_type.db_insert()

        execute()

        self.assertTrue(frappe.db.exists("Vehicle Make", target_name))
        self.assertTrue(frappe.db.exists("Vehicle Make", old_name))
        self.assertTrue(frappe.db.exists("Maintenance Job Type", job_type_target))
        self.assertTrue(frappe.db.exists("Maintenance Job Type", old_job_type_name))
        self.assertEqual(
            frappe.db.get_value(
                "Maintenance Job Type", old_job_type_name, "job_type_name"
            ),
            f" {job_type_target} ",
            "A colliding legacy Job Type must remain untouched",
        )
        _delete_test_record("Vehicle Make", old_name)
        _delete_test_record("Vehicle Make", target_name)
        _delete_test_record("Maintenance Job Type", old_job_type_name)
        _delete_test_record("Maintenance Job Type", job_type_target)

    def test_fleet_master_name_migration_keeps_duplicate_make_records_distinct(
        self,
    ):
        from sotrama.migrations.fleet_master_names import (
            normalize_fleet_master_names as execute,
        )
        from sotrama.tp.doctype.vehicle_model.vehicle_model import (
            get_vehicle_model_name,
        )

        make_name = f"Tata Model Collision {uuid.uuid4().hex[:6]}"
        old_make_name = f"m{uuid.uuid4().hex[:11]}"
        model_name = f"Model {uuid.uuid4().hex[:6]}"
        old_model_name = f"{old_make_name}-{model_name}"
        canonical_model_name = get_vehicle_model_name(make_name, model_name)
        legacy_model_name = get_vehicle_model_name(old_make_name, model_name)

        canonical_make = frappe.get_doc(
            {
                "doctype": "Vehicle Make",
                "name": make_name,
                "make_name": make_name,
                "active": 1,
            }
        )
        canonical_make.db_insert()
        legacy_make = frappe.get_doc(
            {
                "doctype": "Vehicle Make",
                "name": old_make_name,
                "make_name": make_name,
                "active": 1,
            }
        )
        legacy_make.db_insert()
        canonical_model = frappe.get_doc(
            {
                "doctype": "Vehicle Model",
                "name": canonical_model_name,
                "vehicle_make": make_name,
                "make": make_name,
                "model_name": model_name,
                "active": 1,
            }
        )
        canonical_model.db_insert()
        legacy_model = frappe.get_doc(
            {
                "doctype": "Vehicle Model",
                "name": old_model_name,
                "vehicle_make": old_make_name,
                "make": old_make_name,
                "model_name": model_name,
                "active": 1,
            }
        )
        legacy_model.db_insert()

        try:
            execute()

            self.assertTrue(frappe.db.exists("Vehicle Make", old_make_name))
            self.assertFalse(frappe.db.exists("Vehicle Model", old_model_name))
            self.assertEqual(
                frappe.db.get_value("Vehicle Model", legacy_model_name, "vehicle_make"),
                old_make_name,
            )
            self.assertEqual(
                frappe.db.get_value("Vehicle Model", legacy_model_name, "make"),
                old_make_name,
            )
            self.assertEqual(
                frappe.db.get_value("Vehicle Model", legacy_model_name, "model_name"),
                model_name,
            )
            self.assertTrue(frappe.db.exists("Vehicle Model", canonical_model_name))
            self.assertNotEqual(canonical_model_name, legacy_model_name)
        finally:
            _delete_test_record("Vehicle Model", old_model_name)
            _delete_test_record("Vehicle Model", legacy_model_name)
            _delete_test_record("Vehicle Model", canonical_model_name)
            _delete_test_record("Vehicle Make", old_make_name)
            _delete_test_record("Vehicle Make", make_name)

    def test_vehicle_picker_queries_only_offer_submitted_vehicles(self):
        for script_name in (
            "operational_task.js",
            "maintenance_schedule.js",
            "job_card.js",
            "inspection.js",
            "breakdown.js",
        ):
            source = (
                _sotrama_package_path() / "public" / "js" / script_name
            ).read_text(encoding="utf-8")
            self.assertRegex(
                source,
                r"(?s)frm\.set_query\('vehicle'.*?filters:\s*\{\s*docstatus:\s*1",
                script_name,
            )

        inspection_js = (
            _sotrama_package_path() / "public" / "js" / "inspection.js"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "const filters = { status: 'Active', docstatus: 1 }", inspection_js
        )

        for script_name in ("maintenance_schedule.js", "job_card.js"):
            source = (
                _sotrama_package_path() / "public" / "js" / script_name
            ).read_text(encoding="utf-8")
            self.assertIn(
                "frm.set_query('job_type', () => ({ filters: { active: 1 } }));",
                source,
            )

    def test_same_vehicle_model_name_can_exist_under_different_makes(self):
        duplicate_model = frappe.new_doc("Vehicle Model")
        duplicate_model.vehicle_make = self.make.name
        duplicate_model.model_name = self.model.model_name
        with self.assertRaises(frappe.ValidationError):
            duplicate_model.insert(ignore_permissions=True)

        second_make = frappe.new_doc("Vehicle Make")
        second_make.make_name = f"Second Make {uuid.uuid4().hex[:6]}"
        second_make.insert(ignore_permissions=True)

        second_model = frappe.new_doc("Vehicle Model")
        second_model.vehicle_make = second_make.name
        second_model.model_name = self.model.model_name
        second_model.insert(ignore_permissions=True)

        self.assertNotEqual(second_model.name, self.model.name)
        self.assertEqual(second_model.model_name, self.model.model_name)
        self.assertEqual(second_model.vehicle_make, second_make.name)

        _delete_test_record("Vehicle Model", second_model.name)
        _delete_test_record("Vehicle Make", second_make.name)

    def test_vehicle_model_ids_do_not_collide_on_hyphenated_make_and_model_names(self):
        makes = []
        models = []
        prefix = f"Model Prefix {uuid.uuid4().hex[:6]}"
        try:
            for make_name, model_name in (
                (f"{prefix}-B", "C"),
                (prefix, "B-C"),
            ):
                make = frappe.new_doc("Vehicle Make")
                make.make_name = make_name
                make.insert(ignore_permissions=True)
                makes.append(make)

                model = frappe.new_doc("Vehicle Model")
                model.vehicle_make = make.name
                model.model_name = model_name
                model.insert(ignore_permissions=True)
                models.append(model)

            self.assertEqual(len({model.name for model in models}), 2)
            self.assertEqual([model.model_name for model in models], ["C", "B-C"])
        finally:
            for model in models:
                _delete_test_record("Vehicle Model", model.name)
            for make in makes:
                _delete_test_record("Vehicle Make", make.name)

    def test_legacy_vehicle_model_make_is_resolved_before_naming(self):
        from sotrama.tp.doctype.vehicle_model.vehicle_model import (
            get_vehicle_model_name,
        )

        legacy_model = frappe.new_doc("Vehicle Model")
        legacy_model.make = self.make.name
        legacy_model.model_name = f"Legacy Model {uuid.uuid4().hex[:6]}"
        legacy_model.insert(ignore_permissions=True)

        self.assertEqual(legacy_model.vehicle_make, self.make.name)
        self.assertEqual(
            legacy_model.name,
            get_vehicle_model_name(self.make.name, legacy_model.model_name),
        )
        _delete_test_record("Vehicle Model", legacy_model.name)

    def test_inactive_make_does_not_block_unrelated_vehicle_edits(self):
        alternate_model = frappe.new_doc("Vehicle Model")
        alternate_model.vehicle_make = self.make.name
        alternate_model.model_name = f"Alternate Model {uuid.uuid4().hex[:6]}"
        alternate_model.insert(ignore_permissions=True)

        vehicle = frappe.new_doc("Vehicle")
        vehicle.license_plate = f"MAKE-TEST-{uuid.uuid4().hex[:6]}"
        vehicle.company = self.company
        vehicle.vehicle_category = "Truck"
        vehicle.vehicle_make = self.make.name
        vehicle.model = self.model.name
        vehicle.insert(ignore_permissions=True)

        self.make.db_set("active", 0)
        vehicle.current_odometer = 100
        vehicle.save(ignore_permissions=True)

        vehicle.model = alternate_model.name
        with self.assertRaises(frappe.ValidationError):
            vehicle.save(ignore_permissions=True)

        _delete_test_record("Vehicle", vehicle.name)
        _delete_test_record("Vehicle Model", alternate_model.name)

    def test_fleet_transactions_reject_draft_vehicle_links(self):
        vehicle = frappe.new_doc("Vehicle")
        vehicle.license_plate = f"DRAFT-TEST-{uuid.uuid4().hex[:6]}"
        vehicle.company = self.company
        vehicle.vehicle_category = "Truck"
        vehicle.insert(ignore_permissions=True)

        operations = (
            (frappe.new_doc("Operational Task"), "_validate_vehicle"),
            (frappe.new_doc("Maintenance Schedule"), "_set_company_from_vehicle"),
            (frappe.new_doc("Maintenance Job Card"), "_set_company_and_cost_center"),
            (frappe.new_doc("Vehicle Inspection"), "_set_company_from_vehicle"),
            (frappe.new_doc("Breakdown Incident"), "_set_company_from_vehicle"),
        )
        for operation, method_name in operations:
            operation.vehicle = vehicle.name
            with (
                self.subTest(doctype=operation.doctype),
                self.assertRaises(frappe.ValidationError),
            ):
                getattr(operation, method_name)()

        vehicle.submit()
        from sotrama.tp.validation import validate_submitted_vehicle

        self.assertEqual(validate_submitted_vehicle(vehicle.name).docstatus, 1)
        _delete_test_record("Vehicle", vehicle.name)

    def test_fleet_reference_master_migration_normalizes_legacy_rows(self):
        from sotrama.migrations.fleet_reference_masters import (
            simplify_fleet_reference_masters as execute,
        )

        legacy_make = frappe.new_doc("Vehicle Make")
        legacy_make.make_name = f"Legacy Make {uuid.uuid4().hex[:6]}"
        legacy_make.insert(ignore_permissions=True)
        legacy_model = frappe.new_doc("Vehicle Model")
        legacy_model.vehicle_make = legacy_make.name
        legacy_model.model_name = f"Legacy Model {uuid.uuid4().hex[:6]}"
        legacy_model.insert(ignore_permissions=True)
        unresolved_model = frappe.new_doc("Vehicle Model")
        unresolved_model.vehicle_make = legacy_make.name
        unresolved_model.model_name = f"Unresolved Model {uuid.uuid4().hex[:6]}"
        unresolved_model.insert(ignore_permissions=True)
        broken_link_model = frappe.new_doc("Vehicle Model")
        broken_link_model.vehicle_make = legacy_make.name
        broken_link_model.model_name = f"Broken Link Model {uuid.uuid4().hex[:6]}"
        broken_link_model.insert(ignore_permissions=True)

        frappe.db.set_value(
            "Vehicle Make", legacy_make.name, "docstatus", 1, update_modified=False
        )
        frappe.db.set_value(
            "Vehicle Model",
            legacy_model.name,
            {"docstatus": 1, "vehicle_make": ""},
            update_modified=False,
        )
        frappe.db.set_value(
            "Vehicle Model",
            unresolved_model.name,
            {"docstatus": 1, "make": "Unknown Legacy Make", "vehicle_make": ""},
            update_modified=False,
        )
        frappe.db.set_value(
            "Vehicle Model",
            broken_link_model.name,
            {
                "docstatus": 1,
                "make": "Unknown Legacy Make",
                "vehicle_make": "Missing Make",
            },
            update_modified=False,
        )

        cancelled_make = frappe.new_doc("Vehicle Make")
        cancelled_make.make_name = f"Cancelled Make {uuid.uuid4().hex[:6]}"
        cancelled_make.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Vehicle Make", cancelled_make.name, "docstatus", 2, update_modified=False
        )

        legacy_job_type = frappe.new_doc("Maintenance Job Type")
        legacy_job_type.job_category = "General"
        legacy_job_type.job_type_name = f"Legacy Job Type {uuid.uuid4().hex[:6]}"
        legacy_job_type.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Maintenance Job Type",
            legacy_job_type.name,
            "docstatus",
            1,
            update_modified=False,
        )

        cancelled_job_type = frappe.new_doc("Maintenance Job Type")
        cancelled_job_type.job_category = "General"
        cancelled_job_type.job_type_name = f"Cancelled Job Type {uuid.uuid4().hex[:6]}"
        cancelled_job_type.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Maintenance Job Type",
            cancelled_job_type.name,
            "docstatus",
            2,
            update_modified=False,
        )

        with patch("frappe.log_error") as log_error:
            execute()
            execute()
            self.assertEqual(log_error.call_count, 2)
            self.assertIn(unresolved_model.name, log_error.call_args.args[0])
            self.assertIn(broken_link_model.name, log_error.call_args.args[0])
            self.assertEqual(
                log_error.call_args.args[1],
                "Unresolved Legacy Vehicle Model Makes",
            )

        self.assertEqual(
            frappe.db.get_value("Vehicle Make", legacy_make.name, "docstatus"), 0
        )
        self.assertEqual(
            frappe.db.get_value("Vehicle Model", legacy_model.name, "docstatus"), 0
        )
        self.assertEqual(
            frappe.db.get_value("Vehicle Model", legacy_model.name, "vehicle_make"),
            legacy_make.name,
        )
        self.assertEqual(
            frappe.db.get_value("Vehicle Model", unresolved_model.name, "vehicle_make"),
            "",
        )
        self.assertEqual(
            frappe.db.get_value("Vehicle Model", unresolved_model.name, "docstatus"),
            0,
        )
        self.assertEqual(
            frappe.db.get_value(
                "Vehicle Model", broken_link_model.name, "vehicle_make"
            ),
            "",
        )
        self.assertEqual(
            frappe.db.get_value("Vehicle Make", cancelled_make.name, "active"), 0
        )
        self.assertEqual(
            frappe.db.get_value(
                "Maintenance Job Type", legacy_job_type.name, "docstatus"
            ),
            0,
        )
        self.assertEqual(
            frappe.db.get_value(
                "Maintenance Job Type", cancelled_job_type.name, "active"
            ),
            0,
        )

        _delete_test_record("Vehicle Model", legacy_model.name)
        _delete_test_record("Vehicle Model", unresolved_model.name)
        _delete_test_record("Vehicle Model", broken_link_model.name)
        _delete_test_record("Vehicle Make", legacy_make.name)
        _delete_test_record("Vehicle Make", cancelled_make.name)
        _delete_test_record("Maintenance Job Type", legacy_job_type.name)
        _delete_test_record("Maintenance Job Type", cancelled_job_type.name)

    def test_vehicle_asset_link_requires_readable_submitted_same_company_asset(self):
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.asset = "ASSET-TEST-001"
        asset = frappe._dict(
            company=self.company,
            status="Submitted",
            docstatus=1,
        )

        with (
            patch(
                "sotrama.tp.validation.validate_linked_document_read_permission"
            ) as check_read,
            patch("sotrama.tp.settings.validate_company_access") as check_company,
            patch(
                "sotrama.tp.doctype.vehicle.vehicle.frappe.db.get_value",
                return_value=asset,
            ),
        ):
            vehicle._validate_asset_link()

        check_read.assert_called_once_with("Asset", "ASSET-TEST-001")
        check_company.assert_called_once_with(self.company, "Asset")

        asset.company = "OTHER-COMPANY"
        with (
            patch("sotrama.tp.validation.validate_linked_document_read_permission"),
            patch("sotrama.tp.settings.validate_company_access"),
            patch(
                "sotrama.tp.doctype.vehicle.vehicle.frappe.db.get_value",
                return_value=asset,
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            vehicle._validate_asset_link()

        asset.company = self.company
        asset.status = "Sold"
        with (
            patch("sotrama.tp.validation.validate_linked_document_read_permission"),
            patch(
                "sotrama.tp.doctype.vehicle.vehicle.frappe.db.get_value",
                return_value=asset,
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            vehicle._validate_asset_link()

    def test_vehicle_document_migration_consolidates_legacy_attachments_once(self):
        from sotrama.migrations.fleet_documents import (
            migrate_fleet_document_options as execute,
        )

        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = f"TEST-DOC-{uuid.uuid4().hex[:8]}"
        vehicle.registration_document = "/files/test-shared-document.pdf"
        vehicle.insurance_document = "/files/test-shared-document.pdf"
        vehicle.pollution_document = "/files/test-pollution.pdf"
        vehicle.technical_document = "/files/test-technical.pdf"
        vehicle.insert(ignore_permissions=True)
        frappe.db.set_value(
            "Vehicle", vehicle.name, "vehicle_category", "Grader", update_modified=False
        )

        legacy_row = frappe.get_doc(
            {
                "doctype": "Vehicle Document",
                "parent": vehicle.name,
                "parenttype": "Vehicle",
                "parentfield": "vehicle_documents",
                "idx": 1,
                "document_type": "Carte d'immatriculation",
                "attachment": "/files/test-existing-registration.pdf",
                "status": "Pending",
            }
        )
        legacy_row.db_insert()

        legacy_task = frappe.new_doc("Operational Task")
        legacy_task.task_type = "Transport"
        legacy_task.transport_kind = "Transport de marchandises"
        legacy_task.transport_basis = "Compte propre"
        legacy_task.transport_regulatory_status = "À confirmer"
        legacy_task.db_insert()

        legacy_classification = frappe.new_doc("Company Classification")
        legacy_classification.company = self.company
        legacy_classification.grade = 1
        legacy_classification.category = "TP (Travaux Publics)"
        legacy_classification.registration_number = f"LEGACY-{uuid.uuid4().hex[:8]}"
        legacy_classification.db_insert()

        execute()
        execute()

        self.assertEqual(
            frappe.db.get_value("Vehicle", vehicle.name, "vehicle_category"),
            "Motor Grader",
        )
        self.assertEqual(
            frappe.db.get_value("Operational Task", legacy_task.name, "transport_kind"),
            "Goods Transport",
        )
        self.assertEqual(
            frappe.db.get_value(
                "Operational Task", legacy_task.name, "transport_basis"
            ),
            "Own-Account Transport",
        )
        self.assertEqual(
            frappe.db.get_value(
                "Operational Task", legacy_task.name, "transport_regulatory_status"
            ),
            "To Be Confirmed",
        )
        self.assertEqual(
            frappe.db.get_value(
                "Company Classification", legacy_classification.name, "category"
            ),
            "Public Works (TP)",
        )

        rows = frappe.get_all(
            "Vehicle Document",
            filters={"parent": vehicle.name, "parenttype": "Vehicle"},
            fields=["document_type", "attachment"],
            order_by="idx asc",
        )
        migrated = {(row.attachment, row.document_type) for row in rows}
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            migrated,
            {
                ("/files/test-existing-registration.pdf", "Registration Certificate"),
                ("/files/test-shared-document.pdf", "Registration Certificate"),
                ("/files/test-shared-document.pdf", "Insurance Certificate"),
                ("/files/test-pollution.pdf", "Other Document"),
                ("/files/test-technical.pdf", "Technical Inspection"),
            },
        )
        _delete_test_record("Vehicle", vehicle.name)
        _delete_test_record("Operational Task", legacy_task.name)
        _delete_test_record("Company Classification", legacy_classification.name)

    def test_vehicle_document_types_use_canonical_english_values(self):
        options = (
            frappe.get_meta("Vehicle Document", cached=False)
            .get_field("document_type")
            .options.splitlines()
        )
        self.assertEqual(
            [option for option in options if option],
            [
                "Registration Certificate",
                "Insurance Certificate",
                "Technical Inspection",
                "Vehicle Tax Sticker",
                "Transport Permit",
                "Certificate of Conformity",
                "Other Document",
            ],
        )
        vehicle_meta = frappe.get_meta("Vehicle", cached=False)
        for legacy_field in (
            "registration_document",
            "insurance_document",
            "pollution_document",
            "technical_document",
        ):
            self.assertTrue(vehicle_meta.get_field(legacy_field).hidden, legacy_field)

    def test_vehicle_categories_cover_public_works_machinery(self):
        meta = frappe.get_meta("Vehicle", cached=False)
        category = meta.get_field("vehicle_category")
        self.assertEqual(category.label, "Vehicle / Equipment Category")
        options = set(category.options.splitlines())
        self.assertTrue(
            {
                "Bulldozer",
                "Dump Truck",
                "Wheel Loader",
                "Excavator",
                "Backhoe Loader",
                "Motor Grader",
                "Road Roller",
                "Asphalt Paver",
                "Concrete Pump",
                "Forklift",
                "Other Equipment",
            }.issubset(options)
        )
        self.assertEqual(
            meta.get_field("license_plate").label, "Registration / Fleet Number"
        )
        package_path = _sotrama_package_path()
        vehicle_js = (package_path / "public" / "js" / "vehicle.js").read_text(
            encoding="utf-8"
        )
        model_js = (package_path / "public" / "js" / "vehicle_model.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("active: 1", vehicle_js)
        self.assertIn("vehicle_make: frm.doc.vehicle_make", vehicle_js)
        self.assertIn("active: 1", model_js)

    def test_company_classification_is_optional_and_hidden_from_vehicle_workflow(self):
        vehicle_field = frappe.get_meta("Vehicle", cached=False).get_field(
            "company_classification"
        )
        settings_field = frappe.get_meta("TP Settings", cached=False).get_field(
            "default_company_classification"
        )
        company_row_field = frappe.get_meta(
            "TP Company Defaults", cached=False
        ).get_field("company_classification")

        self.assertTrue(vehicle_field.hidden)
        self.assertFalse(vehicle_field.reqd)
        self.assertTrue(settings_field.hidden)
        self.assertTrue(company_row_field.hidden)
        classification_options = set(
            frappe.get_meta("Company Classification", cached=False)
            .get_field("category")
            .options.splitlines()
        )
        self.assertTrue(
            {
                "Public Works (TP)",
                "Building and Public Works (BTP)",
                "Hydraulics",
                "Forestry",
            }.issubset(classification_options)
        )

    def test_vehicle_license_plate_required(self):
        """Test that License Plate is required."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.vehicle_category = "Truck"
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert()

    def test_vehicle_chassis_too_short(self):
        """Test that Chassis Number must be at least 10 characters."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = "TEST-002"
        vehicle.vehicle_category = "Truck"
        vehicle.chassis_no = "SHORT"
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert()
