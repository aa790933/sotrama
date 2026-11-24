import unittest

# Frappe integration tests for Sotrama breakdown behavior.
import uuid
from unittest.mock import patch

import frappe
from frappe.utils import add_days, today

from sotrama.tests.helpers import (
    _delete_test_record,
    _get_test_company,
)


class TestBreakdownIncident(unittest.TestCase):
    """Test Breakdown Incident validation and workflow."""

    def setUp(self):
        self.company = _get_test_company()
        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.company = self.company
        self.vehicle.license_plate = "TEST-BRK-VEH-001"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.insert()
        self.vehicle.submit()
        self.created_breakdowns = []
        self.created_inspections = []
        self.created_drivers = []

    def tearDown(self):
        for name in reversed(self.created_inspections):
            if frappe.db.exists("Vehicle Inspection", name):
                _delete_test_record("Vehicle Inspection", name)
        for name in self.created_breakdowns:
            if frappe.db.exists("Breakdown Incident", name):
                _delete_test_record("Breakdown Incident", name)
        for name in self.created_drivers:
            if frappe.db.exists("Driver", name):
                _delete_test_record("Driver", name)
        for doctype, name in (("Vehicle", self.vehicle.name),):
            if frappe.db.exists(doctype, name):
                _delete_test_record(doctype, name)

    def test_breakdown_date_validation(self):
        """Test that Resolution Date cannot be before Incident Date."""

        breakdown = frappe.new_doc("Breakdown Incident")
        breakdown.vehicle = self.vehicle.name
        breakdown.incident_date = today()
        breakdown.resolution_date = add_days(today(), -1)  # Before incident
        breakdown.description = "Test breakdown"
        with self.assertRaises(frappe.ValidationError):
            breakdown.validate()

        # The invalid document was never inserted; there is no database record to clean up.

    def test_breakdown_can_record_a_historical_incident_for_a_suspended_driver(self):
        from frappe.utils import now_datetime

        from sotrama.tp.doctype.driver.driver import update_driver_status

        driver = frappe.new_doc("Driver")
        driver.driver_name = f"Suspended Driver {uuid.uuid4().hex[:8]}"
        driver.company = self.company
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
        with patch(
            "sotrama.tp.doctype.breakdown_incident.breakdown_incident.BreakdownIncident._create_job_card"
        ):
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
        with patch(
            "sotrama.tp.doctype.breakdown_incident.breakdown_incident.BreakdownIncident._create_job_card"
        ):
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
        inspection._ensure_standard_checklist()
        for row in inspection.inspection_items:
            row.status = "Okay"
        brake_check = next(
            row
            for row in inspection.inspection_items
            if row.category == "Freinage et direction"
        )
        brake_check.item_details = "Brake system check"
        brake_check.status = "Defective"
        brake_check.remarks = "Test brake defect"
        brake_check.is_safety_critical = 1
        inspection.insert(ignore_permissions=True)
        self.created_inspections.append(inspection.name)
        with patch(
            "sotrama.tp.doctype.vehicle_inspection.vehicle_inspection.VehicleInspection._create_defect_issues"
        ):
            inspection.submit()
        return inspection

    def _submit_follow_up_inspection(self, previous_inspection):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.vehicle = self.vehicle.name
        inspection.inspection_type = "Post-Incident"
        inspection.inspection_date = today()
        inspection.overall_status = "Pass"
        inspection.follow_up_of = previous_inspection.name
        inspection._ensure_standard_checklist()
        for row in inspection.inspection_items:
            row.status = "Okay"
        brake_check = next(
            row
            for row in inspection.inspection_items
            if row.category == "Freinage et direction"
        )
        brake_check.item_details = "Brake system reinspection"
        brake_check.is_safety_critical = 1
        inspection.insert(ignore_permissions=True)
        self.created_inspections.append(inspection.name)
        with patch(
            "sotrama.tp.doctype.vehicle_inspection.vehicle_inspection.VehicleInspection._create_defect_issues"
        ):
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
            filters={
                "reference_doctype": "Breakdown Incident",
                "reference_name": breakdown.name,
            },
            fields=["content"],
            order_by="creation asc",
        )
        self.assertTrue(
            any("Resolved" in (comment.content or "") for comment in comments)
        )

    def test_overlapping_breakdowns_keep_vehicle_out_of_service_until_last_resolves(
        self,
    ):
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
        frappe.db.set_value(
            "Vehicle", self.vehicle.name, "vehicle_status", "Out of Service"
        )
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

        with self.assertRaises(frappe.ValidationError):
            inspection.cancel()
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )

    def test_successful_follow_up_clears_critical_inspection_and_cancel_reinstates_hold(
        self,
    ):
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


class TestBreakdownIntegration(unittest.TestCase):
    """Domain-focused integration coverage extracted from the former setup monolith."""

    def test_breakdown_workflow_fields_are_locked_after_submit(self):
        meta = frappe.get_meta("Breakdown Incident", cached=False)
        for fieldname in (
            "status",
            "resolution_date",
            "resolution_notes",
            "downtime_hours",
        ):
            self.assertTrue(meta.get_field(fieldname).read_only)
            self.assertFalse(meta.get_field(fieldname).allow_on_submit)

        vehicle_meta = frappe.get_meta("Vehicle", cached=False)
        self.assertTrue(vehicle_meta.get_field("primary_driver").allow_on_submit)

    def test_breakdown_previous_vehicle_status_cannot_be_forged(self):
        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            BreakdownIncident,
        )

        incident = frappe.new_doc("Breakdown Incident")
        incident.previous_vehicle_status = "Active"
        with (
            patch.object(
                incident,
                "get_doc_before_save",
                return_value=frappe._dict(
                    docstatus=1, previous_vehicle_status="Out of Service"
                ),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            BreakdownIncident._validate_system_managed_fields(incident)

    def test_unresolved_breakdown_cannot_be_cancelled(self):
        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            BreakdownIncident,
        )

        incident = frappe.new_doc("Breakdown Incident")
        incident.status = "In Progress"
        with self.assertRaises(frappe.ValidationError):
            BreakdownIncident.before_cancel(incident)

        incident.status = "Resolved"
        incident.resolution_date = today()
        incident.resolution_notes = "Test resolution"
        with patch.object(incident, "_restore_vehicle_status"):
            BreakdownIncident.before_cancel(incident)

    def test_breakdown_resolution_requires_audit_notes(self):
        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            BreakdownIncident,
        )

        incident = frappe.new_doc("Breakdown Incident")
        incident.status = "Resolved"
        incident.resolution_date = "2026-11-19"
        with self.assertRaises(frappe.ValidationError):
            BreakdownIncident._validate_dates(incident)
