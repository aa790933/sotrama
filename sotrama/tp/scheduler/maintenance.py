"""Maintenance schedule and odometer-based due reminders."""

import hashlib

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from sotrama.tp.settings import get_tp_setting

from .common import _user_for_role


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
    vehicle_names = list(
        {schedule.vehicle for schedule in schedules if schedule.vehicle}
    )
    vehicle_rows = (
        frappe.get_all(
            "Vehicle",
            filters={"name": ["in", vehicle_names]},
            fields=["name", "current_odometer", "docstatus", "vehicle_status"],
            limit_page_length=0,
        )
        if vehicle_names
        else []
    )
    vehicles_by_name = {vehicle.name: vehicle for vehicle in vehicle_rows}
    odometers_by_vehicle = {
        vehicle.name: vehicle.current_odometer or 0 for vehicle in vehicle_rows
    }

    existing_todos = frappe.get_all(
        "ToDo",
        filters={"reference_type": "Maintenance Schedule"},
        or_filters=[
            ["ToDo", "description", "like", "Maintenance Due:%"],
            ["ToDo", "description", "like", "Maintenance à effectuer :%"],
            ["ToDo", "description", "like", "%Scheduled maintenance for vehicle%"],
            ["ToDo", "description", "like", "%La maintenance planifiée du véhicule%"],
        ],
        fields=["name", "reference_name", "description", "status"],
        order_by="creation asc, name asc",
        limit_page_length=0,
    )
    todos_by_schedule = {}
    for todo in existing_todos:
        todos_by_schedule.setdefault(todo.reference_name, []).append(todo)

    configured_days = get_tp_setting("maintenance_due_alert_days", 14)
    alert_days = int(14 if configured_days is None else configured_days)
    due_date_threshold = getdate(add_days(today(), alert_days))
    role_users_cache = {}

    retained_todo_names = set()
    for sched in schedules:
        vehicle_row = vehicles_by_name.get(sched.vehicle)
        due_reasons = []
        if sched.next_due_date and getdate(sched.next_due_date) <= due_date_threshold:
            due_reasons.append(_("due date {0}").format(sched.next_due_date))

        if sched.next_due_odometer:
            current_odometer = odometers_by_vehicle.get(sched.vehicle, 0)
            if current_odometer >= sched.next_due_odometer:
                due_reasons.append(
                    _("odometer {0} km (target {1} km)").format(
                        current_odometer, sched.next_due_odometer
                    )
                )

        if (
            not due_reasons
            or not vehicle_row
            or vehicle_row.docstatus != 1
            or vehicle_row.vehicle_status in ("Retired", "Scrapped")
        ):
            continue

        allocated_to = _user_for_role(
            "Fleet Manager",
            "Maintenance Schedule",
            sched.name,
            role_users_cache=role_users_cache,
            known_existing=True,
        )
        schedule_todos = todos_by_schedule.get(sched.name, [])
        alert_signature = _maintenance_alert_signature(sched)
        closed_existing = next(
            (
                todo
                for todo in schedule_todos
                if todo.status in ("Closed", "Cancelled")
                and alert_signature in (todo.description or "")
            ),
            None,
        )
        if closed_existing:
            continue

        existing = next(
            (todo for todo in schedule_todos if todo.status in ("Open", "Replied")),
            None,
        )
        if existing:
            retained_todo_names.add(existing.name)
            frappe.db.set_value(
                "ToDo",
                existing.name,
                {
                    "allocated_to": allocated_to,
                    "description": _("Maintenance Due: {0} (Vehicle: {1})\n{2}").format(
                        sched.get("job_type", "Service"),
                        sched.get("vehicle", "Unknown"),
                        _("Scheduled maintenance for vehicle {0} is due: {1}.").format(
                            sched.get("vehicle"), "; ".join(due_reasons)
                        ),
                    )
                    + "\n"
                    + alert_signature,
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
                + "\n"
                + alert_signature
            )
            todo.reference_type = "Maintenance Schedule"
            todo.reference_name = sched["name"]
            todo.priority = "Medium"
            todo.allocated_to = allocated_to
            todo.assigned_by = "Administrator"
            todo.insert(ignore_permissions=True)

    # Close generated alerts whose schedule is no longer due/active, whose
    # Vehicle was cancelled, or whose Vehicle is retired/scrapped.
    for todo in existing_todos:
        if todo.status in ("Open", "Replied") and todo.name not in retained_todo_names:
            frappe.db.set_value(
                "ToDo", todo.name, "status", "Closed", update_modified=False
            )


def _maintenance_alert_signature(schedule):
    """Return a non-sensitive identity for one scheduled maintenance cycle."""
    cycle_data = (
        f"{schedule.name}|{schedule.next_due_date or '-'}|"
        f"{schedule.next_due_odometer or '-'}"
    )
    signature = hashlib.sha256(cycle_data.encode("utf-8")).hexdigest()[:16]
    return f"[SOTRAMA-MAINTENANCE-CYCLE:{signature}]"
