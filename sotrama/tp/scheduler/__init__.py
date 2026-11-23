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
    Recalculate Vehicle Document statuses and manage one alert per renewal row.
    Open alerts are closed when a document is renewed, removed, or no longer
    within the configured expiry window.
    """
    configured_days = get_tp_setting("vehicle_document_alert_days", 30)
    alert_days = int(30 if configured_days is None else configured_days)

    vehicles = frappe.get_all(
        "Vehicle",
        fields=["name", "license_plate", "vehicle_status"],
        filters={"docstatus": 1},
        limit_page_length=0,
    )
    if not vehicles:
        return

    vehicles_by_name = {vehicle.name: vehicle for vehicle in vehicles}
    vehicle_names = list(vehicles_by_name)
    docs = frappe.get_all(
        "Vehicle Document",
        filters={
            "parent": ["in", vehicle_names],
            "parenttype": "Vehicle",
            "parentfield": "vehicle_documents",
        },
        fields=["name", "parent", "document_type", "expiry_date", "status"],
        limit_page_length=0,
    )

    existing_todos = frappe.get_all(
        "ToDo",
        filters={
            "reference_type": "Vehicle",
            "reference_name": ["in", vehicle_names],
        },
        fields=["name", "reference_name", "description", "status"],
        limit_page_length=0,
    )
    todos_by_vehicle = {}
    for todo in existing_todos:
        todos_by_vehicle.setdefault(todo.reference_name, []).append(todo)

    user_languages = {}
    assignees_by_vehicle = {}
    role_users_cache = {}
    claimed_todo_names = set()
    active_document_markers = set()
    active_legacy_signatures = []
    legacy_alert_title_prefixes = {
        _("Vehicle Document Expiring: {0} (Vehicle: {1})", lang="en").split(
            "{0}", 1
        )[0],
        _("Vehicle Document Expiring: {0} (Vehicle: {1})", lang="fr").split(
            "{0}", 1
        )[0],
    }
    from sotrama.tp.doctype.vehicle_document.vehicle_document import (
        get_vehicle_document_status,
    )

    for doc in docs:
        vehicle = vehicles_by_name.get(doc.parent)
        if not vehicle:
            continue

        document_status = get_vehicle_document_status(
            doc.expiry_date, alert_days, reference_date=today()
        )
        if doc.status != document_status:
            frappe.db.set_value(
                "Vehicle Document",
                doc.name,
                "status",
                document_status,
                update_modified=False,
            )
            doc.status = document_status
        if (
            vehicle.vehicle_status in ("Retired", "Scrapped")
            or document_status not in ("Expired", "Expiring Soon")
        ):
            continue

        document_row_reference = (
            f"Vehicle Document Row: {doc.name} | Expiry: {doc.expiry_date}"
        )
        active_document_markers.add(document_row_reference)
        expiry_marker = str(doc.expiry_date)
        document_type_labels = {
            doc.document_type,
            _(doc.document_type, lang="en"),
            _(doc.document_type, lang="fr"),
        }
        active_legacy_signatures.append(
            (vehicle.name, expiry_marker, document_type_labels)
        )

        if vehicle.name not in assignees_by_vehicle:
            assignees_by_vehicle[vehicle.name] = _user_for_role(
                "Fleet Manager",
                "Vehicle",
                vehicle.name,
                role_users_cache=role_users_cache,
                known_existing=True,
            )
        allocated_to = assignees_by_vehicle[vehicle.name]
        if allocated_to not in user_languages:
            user_languages[allocated_to] = (
                frappe.db.get_value("User", allocated_to, "language")
                if allocated_to
                else None
            )
        language = user_languages[allocated_to]

        vehicle_label = vehicle.license_plate or vehicle.name
        document_type_label = _(doc.document_type, lang=language)
        document_status_label = _(document_status, lang=language)
        title = _(
            "Vehicle Document Expiring: {0} (Vehicle: {1})", lang=language
        ).format(document_type_label, vehicle_label)
        description = _(
            "Document '{0}' for vehicle {1} expires on {2}. Status: {3}",
            lang=language,
        ).format(
            document_type_label, vehicle_label, doc.expiry_date, document_status_label
        )
        # A vehicle can have multiple renewals of the same document type.
        # Identify each child row so its alert never overwrites another renewal.
        todo_description = f"{title}\n{description}\n{document_row_reference}"
        priority = "High" if document_status == "Expired" else "Medium"
        existing = next(
            (
                todo
                for todo in todos_by_vehicle.get(vehicle.name, [])
                if todo.name not in claimed_todo_names
                and document_row_reference in (todo.description or "")
            ),
            None,
        )
        if not existing:
            # Upgrade a legacy alert from before child-row references existed,
            # but only when its type and expiry date identify this row exactly.
            # Never reuse one legacy ToDo for two same-type renewal rows.
            existing = next(
                (
                    todo
                    for todo in todos_by_vehicle.get(vehicle.name, [])
                    if todo.name not in claimed_todo_names
                    and "Vehicle Document Row:" not in (todo.description or "")
                    and any(
                        prefix and prefix in (todo.description or "")
                        for prefix in legacy_alert_title_prefixes
                    )
                    and expiry_marker in (todo.description or "")
                    and any(
                        label and label in (todo.description or "")
                        for label in document_type_labels
                    )
                ),
                None,
            )
        if existing:
            claimed_todo_names.add(existing.name)
            if existing.status in ("Closed", "Cancelled"):
                continue
            frappe.db.set_value(
                "ToDo",
                existing.name,
                {
                    "allocated_to": allocated_to,
                    "description": todo_description,
                    "priority": priority,
                },
                update_modified=False,
            )
            existing.description = todo_description
            existing.allocated_to = allocated_to
        else:
            todo = frappe.new_doc("ToDo")
            todo.description = todo_description
            todo.reference_type = "Vehicle"
            todo.reference_name = vehicle.name
            todo.priority = priority
            todo.allocated_to = allocated_to
            todo.assigned_by = "Administrator"
            todo.insert(ignore_permissions=True)
            claimed_todo_names.add(todo.name)
            todos_by_vehicle.setdefault(vehicle.name, []).append(
                frappe._dict(
                    name=todo.name,
                    reference_name=vehicle.name,
                    description=todo_description,
                    status="Open",
                )
            )

    # Close alerts when a document is renewed, no longer near expiry, or its
    # child row is removed. Closed/cancelled alerts are never recreated daily.
    for vehicle_name, todos in todos_by_vehicle.items():
        for todo in todos:
            if todo.status != "Open":
                continue
            description = todo.description or ""
            if "Vehicle Document Row:" in description:
                should_close = not any(
                    marker in description for marker in active_document_markers
                )
            else:
                if not any(
                    prefix and prefix in description
                    for prefix in legacy_alert_title_prefixes
                ):
                    continue
                should_close = not any(
                    reference_name == vehicle_name
                    and expiry_marker in description
                    and any(
                        label and label in description for label in labels
                    )
                    for reference_name, expiry_marker, labels in active_legacy_signatures
                )
            if should_close:
                frappe.db.set_value(
                    "ToDo", todo.name, "status", "Closed", update_modified=False
                )


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
    vehicle_names = list({schedule.vehicle for schedule in schedules if schedule.vehicle})
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
        filters={
            "reference_type": "Maintenance Schedule",
            "status": "Open",
        },
        or_filters=[
            ["ToDo", "description", "like", "Maintenance Due:%"],
            ["ToDo", "description", "like", "Maintenance à effectuer :%"],
            ["ToDo", "description", "like", "%Scheduled maintenance for vehicle%"],
            ["ToDo", "description", "like", "%La maintenance planifiée du véhicule%"],
        ],
        fields=["name", "reference_name", "description"],
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
        existing = next(iter(todos_by_schedule.get(sched.name, [])), None)
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

    # Close generated alerts whose schedule is no longer due/active, whose
    # Vehicle was cancelled, or whose Vehicle is retired/scrapped.
    for todo in existing_todos:
        if todo.name not in retained_todo_names:
            frappe.db.set_value(
                "ToDo", todo.name, "status", "Closed", update_modified=False
            )


# ---------------------------------------------------------------------------
# Driver license expiry alerts
# ---------------------------------------------------------------------------


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
            fields=["parent", "check_type", "test_date", "result", "valid_until"],
            order_by="parent asc, test_date desc, idx desc",
            limit_page_length=0,
        )
        for record in compliance_records:
            compliance_records_by_driver.setdefault(record.parent, []).append(record)

    existing_todos = frappe.get_all(
        "ToDo",
        filters={"reference_type": "Driver", "status": "Open"},
        or_filters=[
            ["ToDo", "description", "like", "%license expires%"],
            ["ToDo", "description", "like", "%Le permis du conducteur%"],
            ["ToDo", "description", "like", "%Driver License Expiring:%"],
            ["ToDo", "description", "like", "%Expiration du permis du conducteur%"],
            ["ToDo", "description", "like", "%restricted professional-driver compliance records%"],
            ["ToDo", "description", "like", "%dossiers de conformité professionnelle à accès restreint%"],
            ["ToDo", "description", "like", "%Restricted Driver Compliance Review%"],
            ["ToDo", "description", "like", "%Contrôle restreint de conformité du conducteur%"],
            ["ToDo", "description", "like", "%safety training expires%"],
            ["ToDo", "description", "like", "%La formation sécurité du conducteur%"],
            ["ToDo", "description", "like", "%Safety Training Expiring:%"],
            ["ToDo", "description", "like", "%Expiration de la formation sécurité%"],
        ],
        fields=["name", "reference_name", "description"],
        order_by="creation asc, name asc",
        limit_page_length=0,
    )
    todos_by_driver = {}
    for todo in existing_todos:
        todos_by_driver.setdefault(todo.reference_name, []).append(todo)

    role_users_cache = {}
    active_alerts = set()

    for d in drivers:
        if d.license_expiry and getdate(d.license_expiry) <= getdate(threshold):
            active_alerts.add((d.name, "license"))
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
            existing = _find_driver_alert_todo(
                todos_by_driver, d.name, "license"
            )
            if existing:
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
                    )
                )

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
            active_alerts.add((d.name, "compliance"))
            allocated_to = _user_for_role(
                "HR Manager",
                "Driver",
                d.name,
                role_users_cache=role_users_cache,
                known_existing=True,
            )
            existing = _find_driver_alert_todo(
                todos_by_driver, d.name, "compliance"
            )
            if existing:
                frappe.db.set_value(
                    "ToDo",
                    existing.name,
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
                todos_by_driver.setdefault(d.name, []).append(
                    frappe._dict(
                        name=todo.name,
                        reference_name=d.name,
                        description=todo.description,
                    )
                )

        if d.safety_training_expiry and getdate(d.safety_training_expiry) <= getdate(
            threshold
        ):
            active_alerts.add((d.name, "safety"))
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
            existing = _find_driver_alert_todo(
                todos_by_driver, d.name, "safety"
            )
            if existing:
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
                    )
                )

    # Close obsolete alerts after renewals, cleared compliance requirements,
    # removed expiry dates, or Driver deactivation/cancellation.
    for driver_name, todos in todos_by_driver.items():
        for todo in todos:
            alert_kind = _driver_alert_kind(todo.description)
            if alert_kind and (driver_name, alert_kind) not in active_alerts:
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


def _find_driver_alert_todo(todos_by_driver, driver_name, alert_kind):
    return next(
        (
            todo
            for todo in todos_by_driver.get(driver_name, [])
            if _driver_alert_kind(todo.description) == alert_kind
        ),
        None,
    )


def remediate_fleet_alert_todo_assignments():
    """Sanitize and reassign legacy alerts created before Company-aware routing."""
    todos = frappe.get_all(
        "ToDo",
        filters=[],
        or_filters=[
            ["ToDo", "description", "like", "Vehicle Document Expiring:%"],
            ["ToDo", "description", "like", "Expiration d'un document du véhicule :%"],
            ["ToDo", "description", "like", "Document '% expires on %"],
            ["ToDo", "description", "like", "%du véhicule%expire le%"],
            ["ToDo", "description", "like", "Maintenance Due:%"],
            ["ToDo", "description", "like", "Maintenance à effectuer :%"],
            [
                "ToDo",
                "description",
                "like",
                "Scheduled maintenance for vehicle % is due:%",
            ],
            ["ToDo", "description", "like", "%La maintenance planifiée du véhicule%"],
            ["ToDo", "description", "like", "Driver License Expiring:%"],
            ["ToDo", "description", "like", "Expiration du permis du conducteur :%"],
            ["ToDo", "description", "like", "% license expires on %"],
            ["ToDo", "description", "like", "%Le permis du conducteur%expire le%"],
            ["ToDo", "description", "like", "Safety Training Expiring:%"],
            ["ToDo", "description", "like", "Expiration de la formation sécurité :%"],
            ["ToDo", "description", "like", "% safety training expires on %"],
            ["ToDo", "description", "like", "%La formation sécurité du conducteur%expire le%"],
            ["ToDo", "description", "like", "%Restricted Driver Compliance Review%"],
            ["ToDo", "description", "like", "%Contrôle restreint de conformité du conducteur%"],
            [
                "ToDo",
                "description",
                "like",
                "%restricted professional-driver compliance records%",
            ],
            ["ToDo", "description", "like", "%dossiers de conformité professionnelle à accès restreint%"],
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
    driver_names = {
        todo.reference_name
        for todo in todos
        if todo.reference_type == "Driver" and todo.reference_name
    }
    drivers = (
        frappe.get_all(
            "Driver",
            filters={"name": ["in", sorted(driver_names)]},
            fields=["name", "driver_name", "license_expiry", "safety_training_expiry"],
            limit_page_length=0,
        )
        if driver_names
        else []
    )
    drivers_by_name = {driver.name: driver for driver in drivers}
    role_users_cache = {}
    for todo in todos:
        description = todo.description or ""
        reference_type = todo.reference_type
        reference_name = todo.reference_name
        allocated_to = "Administrator"
        updates = {}

        lowered_description = description.lower()
        if (
            lowered_description.startswith(
                ("vehicle document expiring:", "expiration d'un document du véhicule :")
            )
            or "document '" in lowered_description
            or "du véhicule" in lowered_description and "expire le" in lowered_description
        ) and reference_type == "Vehicle":
            allocated_to = _user_for_role(
                "Fleet Manager", "Vehicle", reference_name, role_users_cache=role_users_cache
            )
        elif (
            lowered_description.startswith(
                (
                    "maintenance due:",
                    "scheduled maintenance for vehicle ",
                    "maintenance à effectuer :",
                    "la maintenance planifiée du véhicule ",
                )
            )
        ) and reference_type == "Maintenance Schedule":
            allocated_to = _user_for_role(
                "Fleet Manager",
                "Maintenance Schedule",
                reference_name,
                role_users_cache=role_users_cache,
            )
        elif (
            lowered_description.startswith(
                ("driver license expiring:", "expiration du permis du conducteur :")
            )
            or " license expires on " in lowered_description
            or "le permis du conducteur" in lowered_description
        ) and reference_type == "Driver":
            allocated_to = _user_for_role(
                "Fleet Manager", "Driver", reference_name, role_users_cache=role_users_cache
            )
            driver = drivers_by_name.get(reference_name)
            updates["description"] = (
                _("Driver {0} license expires on {1}.").format(
                    driver.driver_name, driver.license_expiry
                )
                if driver
                else _("The referenced Driver record is unavailable; contact HR.")
            )
        elif (
            lowered_description.startswith(
                ("safety training expiring:", "expiration de la formation sécurité :")
            )
            or " safety training expires on " in lowered_description
            or "la formation sécurité du conducteur" in lowered_description
        ) and reference_type == "Driver":
            allocated_to = _user_for_role(
                "HR Manager", "Driver", reference_name, role_users_cache=role_users_cache
            )
            driver = drivers_by_name.get(reference_name)
            updates["description"] = (
                _("Driver {0} safety training expires on {1}.").format(
                    driver.driver_name, driver.safety_training_expiry
                )
                if driver
                else _("The referenced Driver record is unavailable; contact HR.")
            )
        elif (
            lowered_description.startswith(
                (
                    "restricted driver compliance review",
                    "contrôle restreint de conformité du conducteur",
                )
            )
            or "restricted professional-driver compliance records" in lowered_description
            or "dossiers de conformité professionnelle à accès restreint" in lowered_description
        ) and reference_type == "Driver":
            allocated_to = _user_for_role(
                "HR Manager", "Driver", reference_name, role_users_cache=role_users_cache
            )
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


def _user_for_role(
    role_name, doctype, docname, *, role_users_cache=None, known_existing=False
):
    """Return a role user who can read this exact company-scoped document."""
    if not docname or (not known_existing and not frappe.db.exists(doctype, docname)):
        return "Administrator"
    role_users_cache = role_users_cache if role_users_cache is not None else {}
    if role_name not in role_users_cache:
        role_users = frappe.get_all(
            "Has Role",
            filters={"role": role_name, "parenttype": "User"},
            pluck="parent",
            order_by="parent asc",
            limit_page_length=0,
        )
        role_users_cache[role_name] = (
            frappe.get_all(
                "User",
                filters={"name": ["in", role_users], "enabled": 1},
                pluck="name",
                order_by="name asc",
                limit_page_length=0,
            )
            if role_users
            else []
        )

    for user in role_users_cache[role_name]:
        if user == "Guest":
            continue
        try:
            if frappe.has_permission(doctype, "read", doc=docname, user=user):
                return user
        except frappe.DoesNotExistError:
            # The record may have been deleted after the scheduler batch read.
            return "Administrator"
    return "Administrator"
