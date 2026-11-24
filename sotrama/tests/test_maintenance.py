import json
import unittest

# Frappe integration tests for Sotrama maintenance behavior.
import uuid
from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate, today

from sotrama.tests.helpers import (
    _delete_test_record,
    _get_test_company,
    _sotrama_package_path,
)


class TestMaintenanceJobCard(unittest.TestCase):
    """Test Maintenance Job Card cost calculations."""

    def setUp(self):
        """Create test dependencies."""
        self.company = _get_test_company()
        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.company = self.company
        self.vehicle.license_plate = f"TEST-MAIN-{uuid.uuid4().hex[:8].upper()}"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.insert()
        self.vehicle.submit()

        item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        if not item_group:
            if not frappe.db.exists("Item Group", "All Item Groups"):
                frappe.get_doc(
                    {
                        "doctype": "Item Group",
                        "item_group_name": "All Item Groups",
                        "is_group": 1,
                    }
                ).insert(ignore_permissions=True)
            item_group_doc = frappe.get_doc(
                {
                    "doctype": "Item Group",
                    "item_group_name": f"Sotrama Test Parts {uuid.uuid4().hex[:6]}",
                    "parent_item_group": "All Item Groups",
                    "is_group": 0,
                }
            ).insert(ignore_permissions=True)
            item_group = item_group_doc.name

        stock_uom = frappe.db.get_value("UOM", {}, "name")
        if not stock_uom:
            stock_uom_doc = frappe.get_doc(
                {"doctype": "UOM", "uom_name": "Sotrama Test Unit"}
            ).insert(ignore_permissions=True)
            stock_uom = stock_uom_doc.name
        self.item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": f"SOTRAMA-TEST-{uuid.uuid4().hex[:8].upper()}",
                "item_name": "Sotrama Test Spare Part",
                "item_group": item_group,
                "stock_uom": stock_uom,
                "is_stock_item": 1,
                "uoms": [{"uom": stock_uom, "conversion_factor": 1}],
            }
        ).insert(ignore_permissions=True)

    def test_automatic_schedule_lookup_uses_read_permission_and_company_scope(self):
        from sotrama.tp.doctype.maintenance_job_card.maintenance_job_card import (
            MaintenanceJobCard,
        )

        job_card = frappe._dict(
            job_nature="Scheduled Service",
            vehicle=self.vehicle.name,
            company=self.company,
            job_type="JT-TEST",
            maintenance_schedule=None,
        )
        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.get_list",
                return_value=[frappe._dict(name="MS-TEST", company=self.company)],
            ) as get_schedules,
            patch("frappe.has_permission", return_value=True) as has_permission,
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
        ):
            MaintenanceJobCard._validate_maintenance_schedule(job_card)

        self.assertEqual(job_card.maintenance_schedule, "MS-TEST")
        self.assertEqual(
            get_schedules.call_args.kwargs["filters"],
            {
                "vehicle": self.vehicle.name,
                "company": self.company,
                "job_type": "JT-TEST",
                "status": "Active",
                "docstatus": 1,
            },
        )
        has_permission.assert_called_once_with(
            "Maintenance Schedule", "read", doc="MS-TEST", throw=True
        )
        validate_company.assert_called_once_with(self.company, "Maintenance Schedule")

    def test_automatic_schedule_lookup_rejects_other_company(self):
        from sotrama.tp.doctype.maintenance_job_card.maintenance_job_card import (
            MaintenanceJobCard,
        )

        job_card = frappe._dict(
            job_nature="Scheduled Service",
            vehicle=self.vehicle.name,
            company=self.company,
            job_type="JT-TEST",
            maintenance_schedule=None,
        )
        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.get_list",
                return_value=[frappe._dict(name="MS-OTHER", company="OTHER-COMPANY")],
            ),
            patch("frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
            self.assertRaises(frappe.ValidationError),
        ):
            MaintenanceJobCard._validate_maintenance_schedule(job_card)

    def tearDown(self):
        if frappe.db.exists("Vehicle", self.vehicle.name):
            _delete_test_record("Vehicle", self.vehicle.name)
        if getattr(self, "item", None) and frappe.db.exists("Item", self.item.name):
            frappe.delete_doc("Item", self.item.name, ignore_permissions=True)

    def test_job_card_cost_calculation(self):
        """Test that parts, labour, and other costs are summed correctly."""
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.vehicle = self.vehicle.name
        job_card.job_date = today()
        job_card.job_nature = "Repair"
        job_card.status = "Draft"

        # Add a part
        job_card.append(
            "parts_used",
            {
                "item": self.item.name,
                "quantity": 2,
                "rate": 500,
            },
        )

        # Add labour
        job_card.append(
            "labour_lines",
            {
                "mechanic": "Test Mechanic",
                "hours": 3,
                "rate": 1000,
            },
        )

        # Add other cost
        job_card.append(
            "other_costs",
            {
                "description": "Towing",
                "amount": 2000,
            },
        )

        # Exercise cost arithmetic independently of the Employee link validator.
        job_card._calculate_totals()

        self.assertEqual(job_card.total_parts_cost, 1000)
        self.assertEqual(job_card.total_labour_cost, 3000)
        self.assertEqual(job_card.total_other_cost, 2000)
        self.assertEqual(job_card.total_cost, 6000)

        # Cleanup
        # The document was never inserted; there is no database record to clean up.

    def test_job_card_labour_employee_must_belong_to_the_job_company(self):
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.company = "SOTRAMA-TEST-COMPANY"
        job_card.append(
            "labour_lines",
            {"mechanic": "EMP-TEST-001", "hours": 2, "rate": 500},
        )

        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
            ),
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.db.get_value",
                return_value=None,
            ) as employee_get_value,
            self.assertRaises(frappe.ValidationError),
        ):
            job_card._validate_labour_lines()
        employee_get_value.assert_called_once_with(
            "Employee",
            {"name": "EMP-TEST-001", "company": "SOTRAMA-TEST-COMPANY"},
            ["company", "employee_name"],
            as_dict=True,
        )

        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
            ),
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.db.get_value",
                return_value=frappe._dict(
                    company="SOTRAMA-TEST-COMPANY", employee_name="Test Mechanic"
                ),
            ),
        ):
            job_card._validate_labour_lines()
        self.assertEqual(job_card.labour_lines[0].mechanic_name, "Test Mechanic")

        job_card.labour_lines[0].mechanic = None
        job_card.labour_lines[0].mechanic_name = "Forged Employee Name"
        with patch(
            "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
        ) as employee_lookup:
            job_card._validate_labour_lines()
        employee_lookup.assert_not_called()
        self.assertIsNone(job_card.labour_lines[0].mechanic_name)

    def test_job_card_rejects_disabled_stock_items_server_side(self):
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.append(
            "parts_used", {"item": self.item.name, "quantity": 1, "rate": 10}
        )
        with (
            patch("sotrama.tp.validation.validate_linked_document_read_permission"),
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.db.get_value",
                return_value=frappe._dict(is_stock_item=1, disabled=1),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            job_card._check_parts_available()

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


class TestMaintenanceScheduleWorkflow(unittest.TestCase):
    def setUp(self):
        self.company = _get_test_company()
        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.company = self.company
        self.vehicle.license_plate = f"TEST-SCH-{uuid.uuid4().hex[:6]}"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.insert(ignore_permissions=True)
        self.vehicle.submit()

        self.job_type = frappe.new_doc("Maintenance Job Type")
        self.job_type.job_category = "General"
        self.job_type.job_type_name = f"Test Service {uuid.uuid4().hex[:8]}"
        self.job_type.insert(ignore_permissions=True)
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
                _delete_test_record("Maintenance Job Card", name)
        for name in self.created_schedules:
            if frappe.db.exists("Maintenance Schedule", name):
                _delete_test_record("Maintenance Schedule", name)
        for doctype, name in (
            ("Maintenance Job Type", self.job_type.name),
            ("Vehicle", self.vehicle.name),
        ):
            if frappe.db.exists(doctype, name):
                _delete_test_record(doctype, name)

    def test_completion_creates_one_linked_successor_and_is_idempotent(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            update_maintenance_schedule_status,
        )

        self.job_type.db_set("active", 0)
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

    def test_new_schedule_rejects_inactive_maintenance_job_type(self):
        inactive_job_type = frappe.new_doc("Maintenance Job Type")
        inactive_job_type.job_category = "General"
        inactive_job_type.job_type_name = f"Inactive Service {uuid.uuid4().hex[:8]}"
        inactive_job_type.active = 0
        inactive_job_type.insert(ignore_permissions=True)

        schedule = frappe.new_doc("Maintenance Schedule")
        schedule.vehicle = self.vehicle.name
        schedule.job_type = inactive_job_type.name
        schedule.schedule_type = "Calendar"
        schedule.interval_months = 6
        schedule.last_service_date = today()
        with self.assertRaises(frappe.ValidationError):
            schedule.insert(ignore_permissions=True)

        _delete_test_record("Maintenance Job Type", inactive_job_type.name)

    def test_job_card_allows_inactive_job_type_only_for_its_active_schedule(self):
        self.job_type.db_set("active", 0)

        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.job_type = self.job_type.name
        with self.assertRaises(frappe.ValidationError):
            job_card._validate_job_type()

        job_card.maintenance_schedule = self.schedule.name
        job_card._validate_job_type()

    def test_completed_schedule_cannot_be_cancelled_while_successor_is_active(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            update_maintenance_schedule_status,
        )

        result = update_maintenance_schedule_status(self.schedule.name, "Completed")
        successor_name = result["next_schedule"]
        self.created_schedules.append(successor_name)
        self.schedule.reload()

        with self.assertRaises(frappe.ValidationError):
            self.schedule.before_cancel()

        successor = frappe.get_doc("Maintenance Schedule", successor_name)
        successor.cancel()
        self.schedule.reload()
        self.assertFalse(self.schedule.next_schedule)
        comments = frappe.get_all(
            "Comment",
            filters={
                "reference_doctype": "Maintenance Schedule",
                "reference_name": self.schedule.name,
            },
            fields=["content"],
        )
        self.assertTrue(
            any(successor_name in (comment.content or "") for comment in comments)
        )
        self.schedule.before_cancel()

    def test_mileage_plan_cannot_complete_without_a_last_service_reading(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            update_maintenance_schedule_status,
        )

        self.schedule.db_set({"schedule_type": "Mileage", "interval_km": 10000})
        with self.assertRaises(frappe.ValidationError):
            update_maintenance_schedule_status(self.schedule.name, "Completed")

    def test_schedule_interval_fields_are_conditionally_required_and_positive(self):
        meta = frappe.get_meta("Maintenance Schedule", cached=False)
        months = meta.get_field("interval_months")
        kilometres = meta.get_field("interval_km")

        self.assertEqual(
            months.mandatory_depends_on, "eval:doc.schedule_type == 'Calendar'"
        )
        self.assertEqual(
            kilometres.mandatory_depends_on, "eval:doc.schedule_type == 'Mileage'"
        )
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            MaintenanceSchedule,
        )

        calendar_schedule = frappe._dict(
            schedule_type="Calendar", interval_months=0, interval_km=None
        )
        with self.assertRaises(frappe.ValidationError):
            MaintenanceSchedule._validate_interval(calendar_schedule)
        mileage_schedule = frappe._dict(
            schedule_type="Mileage", interval_months=None, interval_km=0
        )
        with self.assertRaises(frappe.ValidationError):
            MaintenanceSchedule._validate_interval(mileage_schedule)

    def test_job_card_system_managed_odometer_history_allows_only_empty_float_normalization(
        self,
    ):
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.previous_schedule_last_service_odometer = 0
        previous = frappe._dict(
            {
                "stock_entry": None,
                "linked_maintenance_schedule": None,
                "previous_schedule_last_service_date": None,
                "previous_schedule_last_service_odometer": None,
                "previous_schedule_last_service_job_card": None,
                "previous_schedule_next_due_date": None,
                "previous_schedule_next_due_odometer": None,
                "applied_schedule_last_service_odometer": None,
                "linked_breakdown": None,
                "linked_breakdown_incident": None,
            }
        )
        with patch.object(job_card, "get_doc_before_save", return_value=previous):
            job_card._validate_system_managed_fields()

        job_card.previous_schedule_last_service_odometer = 1250
        with (
            patch.object(job_card, "get_doc_before_save", return_value=previous),
            self.assertRaises(frappe.ValidationError),
        ):
            job_card._validate_system_managed_fields()

    def test_completed_scheduled_job_card_advances_same_plan_and_cancel_restores_it(
        self,
    ):
        from frappe.utils import add_months

        original_due_date = add_days(today(), 30)
        self.schedule.db_set(
            {
                "last_service_date": add_days(today(), -30),
                "next_due_date": original_due_date,
                "last_service_job_card": None,
            }
        )

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
        self.assertEqual(
            getdate(updated_schedule.next_due_date), getdate(add_months(today(), 6))
        )
        self.assertEqual(updated_schedule.next_schedule, None)

        job_card = frappe.get_doc("Maintenance Job Card", job_card.name)
        job_card.cancel()
        restored_schedule = frappe.get_doc("Maintenance Schedule", self.schedule.name)
        self.assertIsNone(restored_schedule.last_service_job_card)
        self.assertEqual(
            getdate(restored_schedule.last_service_date),
            getdate(add_days(today(), -30)),
        )
        self.assertEqual(
            getdate(restored_schedule.next_due_date), getdate(original_due_date)
        )


class TestMaintenanceIntegration(unittest.TestCase):
    """Domain-focused integration coverage extracted from the former setup monolith."""

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

    def test_job_card_child_tables_explain_item_and_employee_sources(self):
        card_meta = frappe.get_meta("Maintenance Job Card", cached=False)
        parts = card_meta.get_field("parts_used")
        labour = card_meta.get_field("labour_lines")
        other_costs = card_meta.get_field("other_costs")
        self.assertEqual(parts.options, "Job Card Part")
        self.assertIn("ERPNext Item", parts.description)
        self.assertIn("configured parts warehouse", parts.description)
        self.assertEqual(labour.options, "Job Card Labour")
        self.assertIn("Frappe HR Employee", labour.description)
        self.assertIn("hourly rate", labour.description)
        self.assertIn("additional maintenance expenses", other_costs.description)

        part_meta = frappe.get_meta("Job Card Part", cached=False)
        for fieldname in ("item", "quantity", "rate", "amount"):
            self.assertTrue(part_meta.get_field(fieldname).in_list_view, fieldname)
        labour_meta = frappe.get_meta("Job Card Labour", cached=False)
        for fieldname in ("mechanic_name", "hours", "rate", "amount"):
            self.assertTrue(labour_meta.get_field(fieldname).in_list_view, fieldname)
        self.assertTrue(labour_meta.get_field("mechanic").in_list_view)
        other_cost_meta = frappe.get_meta("Job Card Other Cost", cached=False)
        for fieldname in ("description", "category", "amount", "date"):
            self.assertTrue(
                other_cost_meta.get_field(fieldname).in_list_view, fieldname
            )
        for doctype in ("Breakdown Photo", "Job Card Photo"):
            photo_meta = frappe.get_meta(doctype, cached=False)
            for fieldname in ("photo", "caption", "photo_date"):
                self.assertTrue(
                    photo_meta.get_field(fieldname).in_list_view,
                    f"{doctype}.{fieldname}",
                )

        print_format = frappe.get_doc("Print Format", "Maintenance Job Card Report")
        self.assertTrue(print_format.print_format_builder_beta)
        print_layout = json.loads(print_format.format_data)
        print_sections = {section["label"] for section in print_layout["sections"]}
        self.assertIn("Spare Parts (Stock Items)", print_sections)
        self.assertIn("Labour (Employees / Mechanics)", print_sections)
        inspection_print = frappe.get_doc("Print Format", "Vehicle Inspection Report")
        self.assertTrue(inspection_print.print_format_builder_beta)
        json.loads(inspection_print.format_data)

        self.assertEqual(labour_meta.get_field("mechanic").options, "Employee")
        self.assertEqual(labour_meta.get_field("mechanic").label, "Employee (Mechanic)")
        self.assertTrue(labour_meta.get_field("mechanic").in_list_view)
        self.assertTrue(labour_meta.get_field("mechanic_name").in_list_view)

        script = (_sotrama_package_path() / "public/js/job_card.js").read_text(
            encoding="utf-8"
        )
        for action in (
            "Add Spare Part (Item)",
            "Add Mechanic (Employee)",
            "Add Other Cost",
            "frm.set_query('mechanic', 'labour_lines'",
            "search_workshop_employees",
            "get_workshop_employee_name",
            "target_doctype: 'Maintenance Job Card'",
            "frappe.call({",
            "total_parts_cost: totalParts",
            "total_labour_cost: totalLabour",
            "parts_used_remove",
            "parts_used_delete",
            "labour_lines_remove",
            "labour_lines_delete",
            "other_costs_remove",
            "other_costs_delete",
        ):
            self.assertIn(action, script)
        self.assertIn("frm.perm?.[0]?.create", script)
        self.assertIn("frm.perm?.[0]?.write", script)
        self.assertNotIn("frappe.db.get_value('Employee'", script)

        inspection_script = (
            _sotrama_package_path() / "public/js/inspection.js"
        ).read_text(encoding="utf-8")
        self.assertIn("target_doctype: 'Vehicle Inspection'", inspection_script)
        task_script = (
            _sotrama_package_path() / "public/js/operational_task.js"
        ).read_text(encoding="utf-8")
        self.assertIn("target_doctype: 'Operational Task'", task_script)

    def test_workshop_employee_lookup_is_limited_to_accessible_company_and_safe_fields(
        self,
    ):
        from sotrama.tp.doctype.maintenance_job_card.maintenance_job_card import (
            get_workshop_employee_name,
            search_workshop_employees,
        )

        module = "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card"
        with (
            patch(f"{module}.frappe.only_for") as only_for,
            patch(f"{module}.frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
            patch(
                f"{module}.frappe.get_all",
                return_value=[("EMP-001", "Ali Mechanic", "Mécanicien")],
            ) as get_all,
        ):
            result = search_workshop_employees(
                "Employee",
                "Ali",
                "name",
                0,
                10,
                {"company": "SOTRAMA", "target_doctype": "Maintenance Job Card"},
            )

        self.assertEqual(result, [("EMP-001", "Ali Mechanic", "Mécanicien")])
        only_for.assert_called_once_with(
            ["System Manager", "Fleet Manager", "Workshop"]
        )
        query = get_all.call_args.kwargs
        self.assertEqual(query["fields"], ["name", "employee_name", "designation"])
        self.assertEqual(query["filters"], {"company": "SOTRAMA", "status": "Active"})
        self.assertTrue(query["as_list"])
        self.assertEqual(
            [call.args for call in validate_company.call_args_list],
            [
                ("SOTRAMA", "Maintenance Job Card"),
                ("SOTRAMA", "Employee"),
                ("SOTRAMA", "Vehicle"),
            ],
        )

        with (
            patch(f"{module}.frappe.only_for"),
            patch(f"{module}.frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
            patch(f"{module}.frappe.db.get_value", return_value="Ali Mechanic"),
        ):
            self.assertEqual(
                get_workshop_employee_name("EMP-001", "SOTRAMA"), "Ali Mechanic"
            )

        with (
            patch(f"{module}.frappe.only_for"),
            patch(f"{module}.frappe.has_permission", return_value=True),
            patch(
                "sotrama.tp.settings.validate_company_access",
                side_effect=frappe.PermissionError,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            get_workshop_employee_name("EMP-001", "OTHER-COMPANY")

        with (
            patch(f"{module}.frappe.only_for"),
            patch(f"{module}.frappe.has_permission", return_value=False),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
            self.assertRaises(frappe.PermissionError),
        ):
            get_workshop_employee_name("EMP-001", "SOTRAMA")
        validate_company.assert_not_called()

        with (
            patch(f"{module}.frappe.only_for"),
            self.assertRaises(frappe.PermissionError),
        ):
            get_workshop_employee_name("EMP-001", "SOTRAMA", "TP Settings")

    def test_inspection_checklist_has_an_explicit_add_action(self):
        inspection_meta = frappe.get_meta("Vehicle Inspection", cached=False)
        checklist = inspection_meta.get_field("inspection_items")
        self.assertEqual(checklist.options, "Inspection Item")
        self.assertIn("standard checklist", checklist.description)
        self.assertTrue(inspection_meta.get_field("overall_status").read_only)

        item_meta = frappe.get_meta("Inspection Item", cached=False)
        status = item_meta.get_field("status")
        self.assertEqual(status.default, "Not Checked")
        self.assertIn("Not Checked", status.options.splitlines())
        self.assertIn("Okay", status.options.splitlines())
        self.assertIn("Defective", status.options.splitlines())
        self.assertTrue(item_meta.get_field("category").in_list_view)
        self.assertTrue(item_meta.get_field("item_details").in_list_view)
        self.assertTrue(status.in_list_view)

        script = (_sotrama_package_path() / "public/js/inspection.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("Add Custom Check", script)
        self.assertIn("new frappe.ui.Dialog", script)
        self.assertIn("status: 'Not Checked'", script)
        self.assertNotIn("is_safety_critical: 1", script)
        self.assertIn("inspection_items_add", script)
        self.assertIn("inspection_items_remove", script)
        self.assertIn("inspection_items_delete", script)
        self.assertIn("frm.perm?.[0]?.create", script)
        self.assertIn("frm.perm?.[0]?.write", script)

    def test_inspection_cannot_be_submitted_with_unchecked_items(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.append(
            "inspection_items",
            {
                "category": "Freinage et direction",
                "item_details": "Brake system",
                "status": "Not Checked",
            },
        )
        inspection.validate()
        with self.assertRaises(frappe.ValidationError):
            inspection.before_submit()

        for row in inspection.inspection_items:
            row.status = "Okay"
        inspection.before_submit()

        inspection.inspection_items[0].status = "Defective"
        with self.assertRaises(frappe.ValidationError):
            inspection.before_submit()
        inspection.inspection_items[0].remarks = "Brake hose damaged"
        inspection.before_submit()

    def test_follow_up_inspection_can_be_saved_as_draft_before_checks_are_complete(
        self,
    ):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.vehicle = "VEH-TEST-001"
        inspection.follow_up_of = "INSP-CRITICAL-001"
        inspection.append(
            "inspection_items",
            {
                "category": "Freinage et direction",
                "item_details": "Brake system",
                "status": "Not Checked",
                "is_safety_critical": 1,
            },
        )
        previous = frappe._dict(
            docstatus=1,
            has_critical_defect=1,
            vehicle="VEH-TEST-001",
            company="SOTRAMA-TEST-COMPANY",
            critical_defect_cleared_by=None,
        )
        with (
            patch(
                "sotrama.tp.validation.validate_submitted_vehicle",
                return_value=frappe._dict(company="SOTRAMA-TEST-COMPANY", docstatus=1),
            ),
            patch("frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
            patch("frappe.get_doc", return_value=previous),
        ):
            inspection.validate()
            self.assertIsNone(inspection.overall_status)
            with self.assertRaises(frappe.ValidationError):
                inspection.before_submit()

    def test_inspection_overall_status_is_derived_from_checked_items(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.append(
            "inspection_items",
            {
                "category": "Documents réglementaires",
                "item_details": "Registration documents",
                "status": "Not Checked",
                "is_safety_critical": 0,
            },
        )
        inspection._calculate_defects()
        self.assertIsNone(inspection.overall_status)

        inspection.inspection_items[0].status = "Okay"
        inspection._calculate_defects()
        self.assertEqual(inspection.overall_status, "Pass")

        inspection.inspection_items[0].status = "Defective"
        inspection.inspection_items[0].is_safety_critical = 0
        inspection.inspection_items[0].remarks = "Minor documentation defect"
        inspection._calculate_defects()
        self.assertEqual(inspection.overall_status, "Conditional Pass")

        inspection.inspection_items[0].is_safety_critical = 1
        inspection._calculate_defects()
        self.assertEqual(inspection.overall_status, "Fail")

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

    def test_inspection_supervisor_must_be_active_and_match_company(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            VehicleInspection,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.company = "SOTRAMA-TEST-COMPANY"
        inspection.supervisor = "EMP-TEST-001"
        module = "sotrama.tp.doctype.vehicle_inspection.vehicle_inspection"
        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
            ) as employee_lookup,
            patch(
                f"{module}.frappe.db.get_value",
                return_value=None,
            ) as employee_get_value,
            self.assertRaises(frappe.ValidationError),
        ):
            VehicleInspection._validate_supervisor(inspection)
        employee_lookup.assert_called_once_with(
            "SOTRAMA-TEST-COMPANY", "Vehicle Inspection"
        )
        employee_get_value.assert_called_once_with(
            "Employee",
            {"name": "EMP-TEST-001", "company": "SOTRAMA-TEST-COMPANY"},
            ["company", "status"],
            as_dict=True,
        )

        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
            ) as employee_lookup,
            patch(
                f"{module}.frappe.db.get_value",
                return_value=frappe._dict(
                    company="SOTRAMA-TEST-COMPANY", status="Inactive"
                ),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            VehicleInspection._validate_supervisor(inspection)
        employee_lookup.assert_called_once_with(
            "SOTRAMA-TEST-COMPANY", "Vehicle Inspection"
        )

    def test_workshop_cannot_downgrade_custom_inspection_safety_checks(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        row = inspection.append(
            "inspection_items",
            {
                "category": "Custom hydraulic hose",
                "status": "Not Checked",
                "is_safety_critical": 0,
            },
        )
        with (
            patch("frappe.get_roles", return_value=["Workshop"]),
            patch.object(inspection, "get_doc_before_save", return_value=None),
        ):
            inspection._enforce_safety_critical_flags()
        self.assertEqual(row.is_safety_critical, 1)

        row.is_safety_critical = 0
        row.category = "Documents réglementaires"
        previous = frappe._dict(
            inspection_items=[frappe._dict(name=row.name, is_safety_critical=1)]
        )
        with (
            patch("frappe.get_roles", return_value=["Workshop"]),
            patch.object(inspection, "get_doc_before_save", return_value=previous),
        ):
            inspection._enforce_safety_critical_flags()
        self.assertEqual(row.is_safety_critical, 1)

    def test_workshop_cannot_hide_custom_checks_in_noncritical_categories(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            STANDARD_INSPECTION_CHECKS,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        custom = inspection.append(
            "inspection_items",
            {
                "category": "Documents réglementaires",
                "item_details": "Freins défectueux à contrôler",
                "status": "Defective",
                "is_safety_critical": 0,
            },
        )
        standard = next(
            check
            for check in STANDARD_INSPECTION_CHECKS
            if not check["is_safety_critical"]
        )
        standard_row = inspection.append(
            "inspection_items", {**standard, "status": "Not Checked"}
        )
        duplicate_standard_row = inspection.append(
            "inspection_items", {**standard, "status": "Not Checked"}
        )
        with (
            patch("frappe.get_roles", return_value=["Workshop"]),
            patch.object(inspection, "get_doc_before_save", return_value=None),
        ):
            inspection._enforce_safety_critical_flags()

        self.assertEqual(custom.is_safety_critical, 1)
        self.assertEqual(standard_row.is_safety_critical, 0)
        self.assertEqual(duplicate_standard_row.is_safety_critical, 1)

    def test_inspection_server_restores_every_required_standard_check(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            STANDARD_INSPECTION_CHECKS,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.append(
            "inspection_items",
            {
                "category": "Custom check",
                "item_details": "Custom item",
                "status": "Not Checked",
            },
        )
        inspection._ensure_standard_checklist()
        categories = {row.category for row in inspection.inspection_items}
        expected = {check["category"] for check in STANDARD_INSPECTION_CHECKS}
        self.assertTrue(expected.issubset(categories))
        self.assertEqual(len(expected), 9)
        self.assertTrue(
            all(
                row.status == "Not Checked"
                for row in inspection.inspection_items
                if row.category in expected
            )
        )

    def test_negative_other_costs_are_rejected(self):
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.append("other_costs", {"description": "Credit", "amount": -100})
        with self.assertRaises(frappe.ValidationError):
            job_card._validate_other_costs()

    def test_vehicle_cannot_return_to_service_with_an_open_safety_hold(self):
        from sotrama.tp.doctype.vehicle.vehicle import Vehicle

        vehicle = frappe.new_doc("Vehicle")
        vehicle.name = "VEH-TEST-001"
        vehicle.vehicle_status = "Active"
        with (
            patch(
                "sotrama.tp.validation.get_open_vehicle_safety_holds",
                return_value={"breakdown": "BI-OPEN", "critical_inspection": None},
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            Vehicle._validate_safety_hold(vehicle)

        with (
            patch(
                "sotrama.tp.validation.get_open_vehicle_safety_holds",
                return_value={"breakdown": None, "critical_inspection": "INSP-OPEN"},
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            Vehicle._validate_safety_hold(vehicle)

        with (
            patch(
                "sotrama.tp.validation.get_open_vehicle_safety_holds",
                return_value={"breakdown": "BI-OPEN", "critical_inspection": None},
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            Vehicle.before_cancel(vehicle)

    def test_critical_inspection_cannot_be_cancelled(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            VehicleInspection,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.has_critical_defect = 1
        with self.assertRaises(frappe.ValidationError):
            VehicleInspection.before_cancel(inspection)

        inspection.has_critical_defect = 0
        VehicleInspection.before_cancel(inspection)

    def test_inspection_workflow_fields_cannot_be_forged_after_submission(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            VehicleInspection,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.critical_defect_cleared_by = "INSP-FAKE"
        inspection.previous_vehicle_status = "Active"
        with (
            patch.object(
                inspection,
                "get_doc_before_save",
                return_value=frappe._dict(
                    docstatus=1,
                    critical_defect_cleared_by=None,
                    previous_vehicle_status="Out of Service",
                ),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            VehicleInspection._validate_system_managed_fields(inspection)

    def test_completed_mileage_schedule_requires_last_service_odometer(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            MaintenanceSchedule,
        )

        schedule = frappe.new_doc("Maintenance Schedule")
        schedule.schedule_type = "Mileage"
        schedule.interval_km = 10000
        schedule.status = "Completed"
        with self.assertRaises(frappe.ValidationError):
            MaintenanceSchedule._validate_status_transition(schedule)
