"""Driver licence, safety training and professional compliance reminders."""

import hashlib

import frappe
from frappe import _
from frappe.utils import add_days, getdate, today

from sotrama.tp.settings import get_tp_setting

from .common import _user_for_role


def check_driver_license_expiry():
    """Alert Fleet/HR about expiring driver documents and regulated compliance.

    Driver and Operational Task validation independently enforce assignment
    eligibility; this scheduled job only creates role-scoped follow-up tasks.
    """
    configured_days = get_tp_setting("driver_document_alert_days", 60)
    alert_days = int(60 if configured_days is None else configured_days)
    threshold = add_days(today(), alert_days)

    regulated_transport_kinds = [
        "Collective Passenger Transport",
        "School Transport",
        "Goods Transport",
        "Dangerous Goods Transport",
        "Taxi Transport",
    ]
    regulated_driver_names = {
        driver_name
        for driver_name in frappe.get_all(
            "Operational Task",
            filters={
                "docstatus": 1,
                "task_type": "Transport",
                "transport_regulatory_status": "Regulated",
                "transport_kind": ["in", regulated_transport_kinds],
            },
            pluck="driver",
            limit_page_length=0,
        )
        if driver_name
    }

    drivers = frappe.get_all(
        "Driver",
        filters={"status": "Active", "docstatus": 1},
        fields=["name", "driver_name", "license_expiry", "safety_training_expiry"],
        limit_page_length=0,
    )
    regulated_driver_names.intersection_update(driver.name for driver in drivers)

    compliance_records_by_driver = {}
    if regulated_driver_names and frappe.db.exists(
        "DocType", "Driver Compliance Record"
    ):
        compliance_records = frappe.get_all(
            "Driver Compliance Record",
            filters={
                "parent": ["in", list(regulated_driver_names)],
                "parenttype": "Driver",
                "parentfield": "compliance_records",
            },
            fields=[
                "name",
                "parent",
                "check_type",
                "test_date",
                "result",
                "valid_until",
                "modified",
            ],
            order_by="parent asc, test_date desc, idx desc",
            limit_page_length=0,
        )
        for record in compliance_records:
            compliance_records_by_driver.setdefault(record.parent, []).append(record)

    existing_todos = frappe.get_all(
        "ToDo",
        filters={"reference_type": "Driver"},
        or_filters=[
            ["ToDo", "description", "like", "%license expires%"],
            ["ToDo", "description", "like", "%Le permis du conducteur%"],
            ["ToDo", "description", "like", "%Driver License Expiring:%"],
            ["ToDo", "description", "like", "%Expiration du permis du conducteur%"],
            [
                "ToDo",
                "description",
                "like",
                "%restricted professional-driver compliance records%",
            ],
            [
                "ToDo",
                "description",
                "like",
                "%dossiers de conformité professionnelle à accès restreint%",
            ],
            ["ToDo", "description", "like", "%Restricted Driver Compliance Review%"],
            [
                "ToDo",
                "description",
                "like",
                "%Contrôle restreint de conformité du conducteur%",
            ],
            ["ToDo", "description", "like", "%safety training expires%"],
            ["ToDo", "description", "like", "%La formation sécurité du conducteur%"],
            ["ToDo", "description", "like", "%Safety Training Expiring:%"],
            ["ToDo", "description", "like", "%Expiration de la formation sécurité%"],
        ],
        fields=["name", "reference_name", "description", "status"],
        order_by="creation asc, name asc",
        limit_page_length=0,
    )
    todos_by_driver = {}
    for todo in existing_todos:
        todos_by_driver.setdefault(todo.reference_name, []).append(todo)

    role_users_cache = {}
    retained_todo_names = set()

    for d in drivers:
        if d.license_expiry and getdate(d.license_expiry) <= getdate(threshold):
            title = _("Driver License Expiring: {0}").format(d["driver_name"])
            description = _("Driver {0} license expires on {1}.").format(
                d["driver_name"], d["license_expiry"]
            )
            allocated_to = _user_for_role(
                "Fleet Manager",
                "Driver",
                d.name,
                role_users_cache=role_users_cache,
                known_existing=True,
            )
            closed_existing = any(
                todo.status in ("Closed", "Cancelled")
                and _driver_alert_kind(todo.description) == "license"
                and str(d.license_expiry) in (todo.description or "")
                for todo in todos_by_driver.get(d.name, [])
            )
            if not closed_existing:
                existing = _find_driver_alert_todo(
                    todos_by_driver, d.name, "license", statuses=("Open", "Replied")
                )
                if existing:
                    retained_todo_names.add(existing.name)
                    frappe.db.set_value(
                        "ToDo",
                        existing.name,
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
                    todos_by_driver.setdefault(d.name, []).append(
                        frappe._dict(
                            name=todo.name,
                            reference_name=d.name,
                            description=todo.description,
                            status="Open",
                        )
                    )
                    retained_todo_names.add(todo.name)

        compliance_due = False
        if d.name in regulated_driver_names:
            latest_by_type = {}
            for record in compliance_records_by_driver.get(d.name, []):
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
            compliance_signature = _driver_compliance_signature(latest_by_type)
            compliance_description = _driver_compliance_description(
                d.driver_name, compliance_signature
            )
            allocated_to = _user_for_role(
                "HR Manager",
                "Driver",
                d.name,
                role_users_cache=role_users_cache,
                known_existing=True,
            )
            closed_existing = next(
                (
                    todo
                    for todo in todos_by_driver.get(d.name, [])
                    if todo.status in ("Closed", "Cancelled")
                    and _driver_alert_kind(todo.description) == "compliance"
                    and _driver_compliance_signature_from_description(todo.description)
                    == compliance_signature
                ),
                None,
            )
            existing = _find_driver_alert_todo(
                todos_by_driver, d.name, "compliance", statuses=("Open", "Replied")
            )
            if not closed_existing and existing:
                retained_todo_names.add(existing.name)
                frappe.db.set_value(
                    "ToDo",
                    existing.name,
                    {
                        "allocated_to": allocated_to,
                        "description": compliance_description,
                    },
                    update_modified=False,
                )
            elif not closed_existing and not existing:
                todo = frappe.new_doc("ToDo")
                todo.description = compliance_description
                todo.reference_type = "Driver"
                todo.reference_name = d.name
                todo.priority = "High"
                todo.allocated_to = allocated_to
                todo.assigned_by = "Administrator"
                todo.insert(ignore_permissions=True)
                todos_by_driver.setdefault(d.name, []).append(
                    frappe._dict(
                        name=todo.name,
                        reference_name=d.name,
                        description=todo.description,
                        status="Open",
                    )
                )
                retained_todo_names.add(todo.name)

        if d.safety_training_expiry and getdate(d.safety_training_expiry) <= getdate(
            threshold
        ):
            title = _("Safety Training Expiring: {0}").format(d["driver_name"])
            description = _("Driver {0} safety training expires on {1}.").format(
                d["driver_name"], d["safety_training_expiry"]
            )
            allocated_to = _user_for_role(
                "HR Manager",
                "Driver",
                d.name,
                role_users_cache=role_users_cache,
                known_existing=True,
            )
            closed_existing = any(
                todo.status in ("Closed", "Cancelled")
                and _driver_alert_kind(todo.description) == "safety"
                and str(d.safety_training_expiry) in (todo.description or "")
                for todo in todos_by_driver.get(d.name, [])
            )
            if not closed_existing:
                existing = _find_driver_alert_todo(
                    todos_by_driver, d.name, "safety", statuses=("Open", "Replied")
                )
                if existing:
                    retained_todo_names.add(existing.name)
                    frappe.db.set_value(
                        "ToDo",
                        existing.name,
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
                    todos_by_driver.setdefault(d.name, []).append(
                        frappe._dict(
                            name=todo.name,
                            reference_name=d.name,
                            description=todo.description,
                            status="Open",
                        )
                    )
                    retained_todo_names.add(todo.name)

    # Keep one active alert per driver/type. Close duplicates and obsolete
    # alerts after renewals, cleared compliance requirements, or deactivation.
    for todos in todos_by_driver.values():
        for todo in todos:
            if (
                todo.status in ("Open", "Replied")
                and todo.name not in retained_todo_names
            ):
                frappe.db.set_value(
                    "ToDo", todo.name, "status", "Closed", update_modified=False
                )


def _driver_alert_kind(description):
    description = (description or "").lower()
    if any(
        phrase in description
        for phrase in (
            "license expires",
            "le permis du conducteur",
            "driver license expiring:",
            "expiration du permis du conducteur",
        )
    ):
        return "license"
    if any(
        phrase in description
        for phrase in (
            "restricted professional-driver compliance records",
            "dossiers de conformité professionnelle à accès restreint",
            "restricted driver compliance review",
            "contrôle restreint de conformité du conducteur",
        )
    ):
        return "compliance"
    if any(
        phrase in description
        for phrase in (
            "safety training expires",
            "la formation sécurité du conducteur",
            "safety training expiring:",
            "expiration de la formation sécurité",
        )
    ):
        return "safety"
    return None


def _driver_compliance_signature(latest_by_type):
    """Hash compliance record identities, never medical results or dates."""
    parts = []
    for check_type in ("Medical Fitness Examination", "Drug Screening"):
        record = latest_by_type.get(check_type)
        if record:
            parts.append(f"{check_type}:{record.name}:{record.modified or ''}")
        else:
            parts.append(f"{check_type}:missing")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _driver_compliance_description(driver_name, signature):
    return (
        _("Restricted Driver Compliance Review")
        + "\n"
        + _(
            "Review the restricted professional-driver compliance records for {0}. "
            "This task intentionally contains no medical result or date."
        ).format(driver_name)
        + "\n"
        + f"[SOTRAMA-DRIVER-COMPLIANCE:{signature}]"
    )


def _driver_compliance_signature_from_description(description):
    marker = "[SOTRAMA-DRIVER-COMPLIANCE:"
    description = description or ""
    marker_start = description.find(marker)
    if marker_start >= 0:
        marker_end = description.find("]", marker_start)
        if marker_end > marker_start:
            return description[marker_start + len(marker) : marker_end].strip()
    return None


def _find_driver_alert_todo(
    todos_by_driver, driver_name, alert_kind, statuses=("Open", "Replied")
):
    return next(
        (
            todo
            for todo in todos_by_driver.get(driver_name, [])
            if todo.status in statuses
            and _driver_alert_kind(todo.description) == alert_kind
        ),
        None,
    )
