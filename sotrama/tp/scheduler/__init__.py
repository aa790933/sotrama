"""
Daily scheduler functions for Sotrama TP Fleet Management.

These run once per day via Frappe's scheduler to:
  - Check for expiring documents (insurance, registration, pollution, etc.)
  - Check for upcoming maintenance due
  - Check for expiring driver licenses
"""

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from sotrama.tp.settings import get_tp_setting

# ---------------------------------------------------------------------------
# Document expiry alerts
# ---------------------------------------------------------------------------


def check_document_expiries():
    """
    Scan all Vehicles for documents expiring within 30 days.
    Uses the Vehicle Document child table for expiry tracking.
    Creates a ToDo for each expiring document.
    """
    configured_days = get_tp_setting("vehicle_document_alert_days", 30)
    alert_days = int(30 if configured_days is None else configured_days)
    threshold = add_days(today(), alert_days)

    vehicles = frappe.get_all(
        "Vehicle",
        fields=["name", "license_plate", "vehicle_status"],
        filters={"vehicle_status": ["not in", ["Retired", "Scrapped"]]},
        limit_page_length=0,
    )

    for v in vehicles:
        # Get all documents for this vehicle that are expiring soon or expired
        docs = frappe.get_all(
            "Vehicle Document",
            filters={
                "parent": v["name"],
                "parenttype": "Vehicle",
                "expiry_date": ["<=", threshold],
            },
            fields=["document_type", "expiry_date", "status"],
            limit_page_length=0,
        )

        for doc in docs:
            document_status = (
                "Expired"
                if doc["expiry_date"] and getdate(doc["expiry_date"]) < getdate(today())
                else "Expiring Soon"
            )
            title = _("Vehicle Document Expiring: {0} (Vehicle: {1})").format(
                doc["document_type"], v["license_plate"] or v["name"]
            )
            description = _(
                "Document '{0}' for vehicle {1} expires on {2}. Status: {3}"
            ).format(
                doc["document_type"],
                v["license_plate"] or v["name"],
                doc["expiry_date"],
                document_status,
            )
            allocated_to = _user_for_role("Fleet Manager", "Vehicle", v["name"])
            existing = frappe.db.get_value(
                "ToDo",
                {
                    "reference_type": "Vehicle",
                    "reference_name": v["name"],
                    "description": ["like", f"%{doc['document_type']}%"],
                    "status": "Open",
                },
                "name",
            )
            if existing:
                frappe.db.set_value(
                    "ToDo",
                    existing,
                    {"allocated_to": allocated_to, "description": description},
                    update_modified=False,
                )
            else:
                todo = frappe.new_doc("ToDo")
                todo.description = f"{title}\n{description}"
                todo.reference_type = "Vehicle"
                todo.reference_name = v["name"]
                todo.priority = "High" if document_status == "Expired" else "Medium"
                todo.allocated_to = allocated_to
                todo.assigned_by = "Administrator"
                todo.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Maintenance due alerts
# ---------------------------------------------------------------------------


def check_maintenance_due():
    """
    Scan all active Maintenance Schedules for upcoming due dates.
    Creates a ToDo for the Fleet Manager.
    """
    schedules = frappe.get_all(
        "Maintenance Schedule",
        filters={"status": "Active", "docstatus": 1},
        fields=["name", "vehicle", "next_due_date", "next_due_odometer", "job_type"],
        limit_page_length=0,
    )

    configured_days = get_tp_setting("maintenance_due_alert_days", 14)
    alert_days = int(14 if configured_days is None else configured_days)

    for sched in schedules:
        due_reasons = []
        if sched.next_due_date and getdate(sched.next_due_date) <= getdate(
            add_days(today(), alert_days)
        ):
            due_reasons.append(_("due date {0}").format(sched.next_due_date))

        if sched.next_due_odometer:
            current_odometer = (
                frappe.db.get_value("Vehicle", sched.vehicle, "current_odometer") or 0
            )
            if current_odometer >= sched.next_due_odometer:
                due_reasons.append(
                    _("odometer {0} km (target {1} km)").format(
                        current_odometer, sched.next_due_odometer
                    )
                )

        if not due_reasons:
            continue

        allocated_to = _user_for_role(
            "Fleet Manager", "Maintenance Schedule", sched.name
        )
        existing = frappe.db.get_value(
            "ToDo",
            {
                "reference_type": "Maintenance Schedule",
                "reference_name": sched["name"],
                "status": "Open",
            },
            "name",
        )
        if existing:
            frappe.db.set_value(
                "ToDo",
                existing,
                {
                    "allocated_to": allocated_to,
                    "description": _("Maintenance Due: {0} (Vehicle: {1})\n{2}").format(
                        sched.get("job_type", "Service"),
                        sched.get("vehicle", "Unknown"),
                        _("Scheduled maintenance for vehicle {0} is due: {1}.").format(
                            sched.get("vehicle"), "; ".join(due_reasons)
                        ),
                    ),
                },
                update_modified=False,
            )
        else:
            todo = frappe.new_doc("ToDo")
            title = _("Maintenance Due: {0} (Vehicle: {1})").format(
                sched.get("job_type", "Service"), sched.get("vehicle", "Unknown")
            )
            todo.description = (
                title
                + "\n"
                + _("Scheduled maintenance for vehicle {0} is due: {1}.").format(
                    sched.get("vehicle"), "; ".join(due_reasons)
                )
            )
            todo.reference_type = "Maintenance Schedule"
            todo.reference_name = sched["name"]
            todo.priority = "Medium"
            todo.allocated_to = allocated_to
            todo.assigned_by = "Administrator"
            todo.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Driver license expiry alerts
# ---------------------------------------------------------------------------


def check_driver_license_expiry():
    """
    Scan all active Drivers for licenses expiring within 60 days.
    Creates a ToDo and blocks vehicle assignment if expired.
    """
    configured_days = get_tp_setting("driver_document_alert_days", 60)
    alert_days = int(60 if configured_days is None else configured_days)
    threshold = add_days(today(), alert_days)

    regulated_transport_kinds = [
        "Transport collectif de personnes",
        "Transport scolaire",
        "Transport de marchandises",
        "Transport de matières dangereuses",
        "Transport par taxi",
    ]
    regulated_driver_names = set(
        frappe.get_all(
            "Operational Task",
            filters={
                "docstatus": 1,
                "task_type": "Transport",
                "transport_kind": ["in", regulated_transport_kinds],
            },
            pluck="driver",
            limit_page_length=0,
        )
    )

    drivers = frappe.get_all(
        "Driver",
        filters={"status": "Active", "docstatus": 1},
        fields=["name", "driver_name", "license_expiry", "safety_training_expiry"],
        limit_page_length=0,
    )

    for d in drivers:
        if d.license_expiry and getdate(d.license_expiry) <= getdate(threshold):
            title = _("Driver License Expiring: {0}").format(d["driver_name"])
            description = _("Driver {0} license expires on {1}.").format(
                d["driver_name"], d["license_expiry"]
            )
            allocated_to = _user_for_role("Fleet Manager", "Driver", d.name)
            existing = frappe.db.get_value(
                "ToDo",
                {
                    "reference_type": "Driver",
                    "reference_name": d["name"],
                    "description": ["like", "%license expires%"],
                    "status": "Open",
                },
                "name",
            )
            if existing:
                frappe.db.set_value(
                    "ToDo",
                    existing,
                    {"allocated_to": allocated_to, "description": description},
                    update_modified=False,
                )
            else:
                todo = frappe.new_doc("ToDo")
                todo.description = f"{title}\n{description}"
                todo.reference_type = "Driver"
                todo.reference_name = d["name"]
                todo.priority = "High"
                todo.allocated_to = allocated_to
                todo.assigned_by = "Administrator"
                todo.insert(ignore_permissions=True)

        compliance_due = False
        if d.name in regulated_driver_names and frappe.db.exists(
            "DocType", "Driver Compliance Record"
        ):
            compliance_records = frappe.get_all(
                "Driver Compliance Record",
                filters={
                    "parent": d.name,
                    "parenttype": "Driver",
                    "parentfield": "compliance_records",
                },
                fields=["check_type", "test_date", "result", "valid_until"],
                order_by="test_date desc, idx desc",
                limit_page_length=0,
            )
            latest_by_type = {}
            for record in compliance_records:
                latest_by_type.setdefault(record.check_type, record)

            for check_type, expected in (
                ("Medical Fitness Examination", "Fit"),
                ("Drug Screening", "Negative"),
            ):
                record = latest_by_type.get(check_type)
                if (
                    not record
                    or record.result != expected
                    or not record.valid_until
                    or getdate(record.valid_until) <= getdate(threshold)
                ):
                    compliance_due = True
                    break

        if compliance_due:
            allocated_to = _user_for_role("HR Manager", "Driver", d.name)
            existing = frappe.db.get_value(
                "ToDo",
                {
                    "reference_type": "Driver",
                    "reference_name": d.name,
                    "description": [
                        "like",
                        "%restricted professional-driver compliance records%",
                    ],
                    "status": "Open",
                },
                "name",
            )
            if existing:
                frappe.db.set_value(
                    "ToDo",
                    existing,
                    "allocated_to",
                    allocated_to,
                    update_modified=False,
                )
            else:
                todo = frappe.new_doc("ToDo")
                todo.description = (
                    _("Restricted Driver Compliance Review")
                    + "\n"
                    + _(
                        "Review the restricted professional-driver compliance records for {0}. "
                        "This task intentionally contains no medical result or date."
                    ).format(d.driver_name)
                )
                todo.reference_type = "Driver"
                todo.reference_name = d.name
                todo.priority = "High"
                todo.allocated_to = allocated_to
                todo.assigned_by = "Administrator"
                todo.insert(ignore_permissions=True)

        if d.safety_training_expiry and getdate(d.safety_training_expiry) <= getdate(
            threshold
        ):
            title = _("Safety Training Expiring: {0}").format(d["driver_name"])
            description = _("Driver {0} safety training expires on {1}.").format(
                d["driver_name"], d["safety_training_expiry"]
            )
            allocated_to = _user_for_role("HR Manager", "Driver", d.name)
            existing = frappe.db.get_value(
                "ToDo",
                {
                    "reference_type": "Driver",
                    "reference_name": d["name"],
                    "description": ["like", "%safety training expires%"],
                    "status": "Open",
                },
                "name",
            )
            if existing:
                frappe.db.set_value(
                    "ToDo",
                    existing,
                    {"allocated_to": allocated_to, "description": description},
                    update_modified=False,
                )
            else:
                todo = frappe.new_doc("ToDo")
                todo.description = f"{title}\n{description}"
                todo.reference_type = "Driver"
                todo.reference_name = d["name"]
                todo.priority = "Medium"
                todo.allocated_to = allocated_to
                todo.assigned_by = "Administrator"
                todo.insert(ignore_permissions=True)


def remediate_fleet_alert_todo_assignments():
    """Sanitize and reassign legacy alerts created before Company-aware routing."""
    todos = frappe.get_all(
        "ToDo",
        filters=[],
        or_filters=[
            ["ToDo", "description", "like", "Vehicle Document Expiring:%"],
            ["ToDo", "description", "like", "Document '% expires on %"],
            ["ToDo", "description", "like", "Maintenance Due:%"],
            [
                "ToDo",
                "description",
                "like",
                "Scheduled maintenance for vehicle % is due:%",
            ],
            ["ToDo", "description", "like", "Driver License Expiring:%"],
            ["ToDo", "description", "like", "% license expires on %"],
            ["ToDo", "description", "like", "Safety Training Expiring:%"],
            ["ToDo", "description", "like", "% safety training expires on %"],
            ["ToDo", "description", "like", "%Restricted Driver Compliance Review%"],
        ],
        fields=[
            "name",
            "description",
            "reference_type",
            "reference_name",
            "allocated_to",
        ],
        limit_page_length=0,
    )
    for todo in todos:
        description = todo.description or ""
        reference_type = todo.reference_type
        reference_name = todo.reference_name
        allocated_to = "Administrator"
        updates = {}

        if (
            description.startswith("Vehicle Document Expiring:")
            or "Document '" in description
        ) and reference_type == "Vehicle":
            allocated_to = _user_for_role("Fleet Manager", "Vehicle", reference_name)
        elif (
            description.startswith(
                ("Maintenance Due:", "Scheduled maintenance for vehicle ")
            )
        ) and reference_type == "Maintenance Schedule":
            allocated_to = _user_for_role(
                "Fleet Manager", "Maintenance Schedule", reference_name
            )
        elif (
            description.startswith("Driver License Expiring:")
            or " license expires on " in description
        ) and reference_type == "Driver":
            allocated_to = _user_for_role("Fleet Manager", "Driver", reference_name)
            driver = frappe.db.get_value(
                "Driver",
                reference_name,
                ["driver_name", "license_expiry"],
                as_dict=True,
            )
            updates["description"] = (
                _("Driver {0} license expires on {1}.").format(
                    driver.driver_name, driver.license_expiry
                )
                if driver
                else _("The referenced Driver record is unavailable; contact HR.")
            )
        elif (
            description.startswith("Safety Training Expiring:")
            or " safety training expires on " in description
        ) and reference_type == "Driver":
            allocated_to = _user_for_role("HR Manager", "Driver", reference_name)
            driver = frappe.db.get_value(
                "Driver",
                reference_name,
                ["driver_name", "safety_training_expiry"],
                as_dict=True,
            )
            updates["description"] = (
                _("Driver {0} safety training expires on {1}.").format(
                    driver.driver_name, driver.safety_training_expiry
                )
                if driver
                else _("The referenced Driver record is unavailable; contact HR.")
            )
        elif (
            description.startswith("Restricted Driver Compliance Review")
            or "restricted professional-driver compliance records" in description
        ) and reference_type == "Driver":
            allocated_to = _user_for_role("HR Manager", "Driver", reference_name)
            updates["description"] = _(
                "Review the restricted professional-driver compliance records. "
                "This task intentionally contains no medical result or date."
            )
        else:
            continue

        if todo.allocated_to != allocated_to:
            updates["allocated_to"] = allocated_to
        if updates:
            frappe.db.set_value("ToDo", todo.name, updates, update_modified=False)


def _user_for_role(role_name, doctype, docname):
    """Return a role user who can read this exact company-scoped document."""
    if not docname or not frappe.db.exists(doctype, docname):
        return "Administrator"
    users = frappe.get_all(
        "Has Role",
        filters={"role": role_name, "parenttype": "User"},
        pluck="parent",
        order_by="parent asc",
        limit_page_length=0,
    )
    for user in users:
        if (
            user != "Guest"
            and frappe.db.get_value("User", user, "enabled")
            and frappe.has_permission(
                doctype, "read", doc=docname, user=user, print_logs=False
            )
        ):
            return user
    return "Administrator"
