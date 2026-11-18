"""Vehicle document renewal monitoring, scoped to the selected fleet/company."""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate, today

from sotrama.tp.settings import get_tp_setting


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("Vehicle"), "fieldname": "vehicle", "fieldtype": "Link", "options": "Vehicle", "width": 110},
        {"label": _("License Plate"), "fieldname": "license_plate", "fieldtype": "Data", "width": 120},
        {"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
        {"label": _("Document Type"), "fieldname": "document_type", "fieldtype": "Data", "width": 175},
        {"label": _("Expiry Date"), "fieldname": "expiry_date", "fieldtype": "Date", "width": 105},
        {"label": _("Days Remaining"), "fieldname": "days_remaining", "fieldtype": "Int", "width": 100},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 105},
    ]


def get_data(filters):
    """Fetch child rows in one query and their vehicles in one additional query."""
    configured_days = get_tp_setting("vehicle_document_alert_days", 30)
    requested_days = filters.get("alert_days")
    days_value = requested_days if requested_days not in (None, "") else configured_days
    alert_days = max(int(30 if days_value is None else days_value), 0)
    threshold = add_days(today(), alert_days)

    vehicle_filters = [["vehicle_status", "not in", ["Retired", "Scrapped"]]]
    if filters.get("company"):
        vehicle_filters.append(["company", "=", filters.company])
    if filters.get("vehicle"):
        vehicle_filters.append(["name", "=", filters.vehicle])

    vehicles = frappe.get_list(
        "Vehicle",
        fields=["name", "license_plate", "company"],
        filters=vehicle_filters,
        limit_page_length=0,
    )
    if not vehicles:
        return []

    vehicle_map = {row.name: row for row in vehicles}
    document_filters = {
        "parenttype": "Vehicle",
        "parent": ["in", list(vehicle_map)],
        "expiry_date": ["<=", threshold],
    }
    documents = frappe.get_all(
        "Vehicle Document",
        fields=["parent", "document_type", "expiry_date", "status"],
        filters=document_filters,
        order_by="expiry_date asc, parent asc",
        limit_page_length=0,
    )

    result = []
    current_date = getdate(today())
    for document in documents:
        vehicle = vehicle_map.get(document.parent)
        if not vehicle:
            continue

        expiry_date = getdate(document.expiry_date)
        days_remaining = date_diff(expiry_date, current_date)
        status = _("Expired") if days_remaining < 0 else _("Expiring Soon")
        result.append(
            {
                "vehicle": vehicle.name,
                "license_plate": vehicle.license_plate,
                "company": vehicle.company,
                "document_type": document.document_type,
                "expiry_date": document.expiry_date,
                "days_remaining": days_remaining,
                "status": status,
            }
        )

    return result
