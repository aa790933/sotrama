"""Vehicle document expiry and status reminders."""

import frappe
from frappe import _
from frappe.utils import today

from sotrama.tp.settings import get_tp_setting

from .common import _user_for_role


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
        _("Vehicle Document Expiring: {0} (Vehicle: {1})", lang="en").split("{0}", 1)[
            0
        ],
        _("Vehicle Document Expiring: {0} (Vehicle: {1})", lang="fr").split("{0}", 1)[
            0
        ],
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
        if vehicle.vehicle_status in ("Retired", "Scrapped") or document_status not in (
            "Expired",
            "Expiring Soon",
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
                    and any(label and label in description for label in labels)
                    for reference_name, expiry_marker, labels in active_legacy_signatures
                )
            if should_close:
                frappe.db.set_value(
                    "ToDo", todo.name, "status", "Closed", update_modified=False
                )
