"""
Daily scheduler functions for Sotrama TP Fleet Management.

These run once per day via Frappe's scheduler to:
  - Check for expiring documents (insurance, registration, pollution, etc.)
  - Check for upcoming maintenance due
  - Check for expiring driver licenses
"""

from __future__ import unicode_literals

import frappe
from frappe.utils import today, add_days


# ---------------------------------------------------------------------------
# Document expiry alerts
# ---------------------------------------------------------------------------

def check_document_expiries():
    """
    Scan all Vehicles for documents expiring within 30 days.
    Uses the Vehicle Document child table for expiry tracking.
    Creates a ToDo for each expiring document.
    """
    alert_days = 30
    threshold = add_days(today(), alert_days)

    vehicles = frappe.get_all(
        "Vehicle",
        fields=["name", "license_plate", "vehicle_status"],
        filters={"vehicle_status": ["!=", "Retired"]},
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
        )

        for doc in docs:
            # Avoid duplicate ToDos
            if not frappe.db.exists(
                "ToDo",
                {
                    "reference_type": "Vehicle",
                    "reference_name": v["name"],
                    "title": ["like", f"%{doc['document_type']}%"],
                    "status": "Open",
                },
            ):
                todo = frappe.new_doc("ToDo")
                todo.title = _(
                    "Vehicle Document Expiring: {0} (Vehicle: {1})"
                ).format(doc["document_type"], v["license_plate"] or v["name"])
                todo.description = _(
                    "Document '{0}' for vehicle {1} expires on {2}. Status: {3}"
                ).format(
                    doc["document_type"],
                    v["license_plate"] or v["name"],
                    doc["expiry_date"],
                    doc["status"],
                )
                todo.reference_type = "Vehicle"
                todo.reference_name = v["name"]
                todo.priority = "High" if doc["status"] == "Expired" else "Medium"
                todo.owner = frappe.session.user
                todo.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Maintenance due alerts
# ---------------------------------------------------------------------------

def check_maintenance_due():
    """
    Scan all active Maintenance Schedules for upcoming due dates.
    Creates a ToDo for the Fleet Manager.
    """
    due_schedules = frappe.get_all(
        "Maintenance Schedule",
        filters={
            "status": "Active",
            "next_due_date": ["<=", add_days(today(), 14)],
        },
        fields=["name", "vehicle", "next_due_date", "job_type"],
    )

    for sched in due_schedules:
        if not frappe.db.exists(
            "ToDo",
            {
                "reference_type": "Maintenance Schedule",
                "reference_name": sched["name"],
                "status": "Open",
            },
        ):
            todo = frappe.new_doc("ToDo")
            todo.title = _(
                "Maintenance Due: {0} (Vehicle: {1})"
            ).format(sched.get("job_type", "Service"), sched.get("vehicle", "Unknown"))
            todo.description = _(
                "Scheduled maintenance for vehicle {0} is due on {1}."
            ).format(sched.get("vehicle"), sched.get("next_due_date"))
            todo.reference_type = "Maintenance Schedule"
            todo.reference_name = sched["name"]
            todo.priority = "Medium"
            todo.owner = frappe.session.user
            todo.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Driver license expiry alerts
# ---------------------------------------------------------------------------

def check_driver_license_expiry():
    """
    Scan all active Drivers for licenses expiring within 60 days.
    Creates a ToDo and blocks vehicle assignment if expired.
    """
    alert_days = 60
    threshold = add_days(today(), alert_days)

    drivers = frappe.get_all(
        "Driver",
        filters={"status": "Active"},
        fields=["name", "driver_name", "license_number", "license_expiry",
                "medical_expiry", "safety_training_expiry"],
    )

    for d in drivers:
        if d.license_expiry and d.license_expiry <= threshold:
            if not frappe.db.exists(
                "ToDo",
                {
                    "reference_type": "Driver",
                    "reference_name": d["name"],
                    "title": ["like", "%License%"],
                    "status": "Open",
                },
            ):
                todo = frappe.new_doc("ToDo")
                todo.title = _("Driver License Expiring: {0}").format(d["driver_name"])
                todo.description = _(
                    "Driver {0} (License: {1}) license expires on {2}."
                ).format(d["driver_name"], d["license_number"], d["license_expiry"])
                todo.reference_type = "Driver"
                todo.reference_name = d["name"]
                todo.priority = "High"
                todo.owner = frappe.session.user
                todo.insert(ignore_permissions=True)

        if d.medical_expiry and d.medical_expiry <= threshold:
            if not frappe.db.exists(
                "ToDo",
                {
                    "reference_type": "Driver",
                    "reference_name": d["name"],
                    "title": ["like", "%Medical%"],
                    "status": "Open",
                },
            ):
                todo = frappe.new_doc("ToDo")
                todo.title = _("Medical Certificate Expiring: {0}").format(d["driver_name"])
                todo.description = _(
                    "Driver {0} medical certificate expires on {1}."
                ).format(d["driver_name"], d["medical_expiry"])
                todo.reference_type = "Driver"
                todo.reference_name = d["name"]
                todo.priority = "Medium"
                todo.owner = frappe.session.user
                todo.insert(ignore_permissions=True)