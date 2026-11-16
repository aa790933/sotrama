"""
Upcoming Document Expiries Report

Shows vehicle documents (registration, insurance, pollution, technical inspection,
etc.) that are expiring within a configurable number of days.
"""


import frappe
from frappe.utils import add_days, today


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "Vehicle",
            "fieldname": "vehicle",
            "fieldtype": "Link",
            "options": "Vehicle",
            "width": 120,
        },
        {
            "label": "License Plate",
            "fieldname": "license_plate",
            "fieldtype": "Data",
            "width": 120,
        },
        {
            "label": "Document Type",
            "fieldname": "document_type",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": "Expiry Date",
            "fieldname": "expiry_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": "Days Remaining",
            "fieldname": "days_remaining",
            "fieldtype": "Int",
            "width": 100,
        },
        {
            "label": "Status",
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 100,
        },
    ]


def get_data(filters):
    """Build the report data."""
    alert_days = filters.get("alert_days", 30) if filters else 30
    threshold = add_days(today(), alert_days)

    data = []

    # Get vehicles with expiring documents
    vehicles = frappe.get_all(
        "Vehicle",
        fields=["name", "license_plate"],
        filters={"vehicle_status": ["!=", "Retired"]},
    )

    for v in vehicles:
        docs = frappe.get_all(
            "Vehicle Document",
            fields=["document_type", "expiry_date", "status"],
            filters={
                "parent": v.name,
                "parenttype": "Vehicle",
                "expiry_date": ["<=", threshold],
            },
            order_by="expiry_date asc",
        )

        for doc in docs:
            from frappe.utils import date_diff
            days_remaining = date_diff(doc.expiry_date, today())

            data.append({
                "vehicle": v.name,
                "license_plate": v.license_plate,
                "document_type": doc.document_type,
                "expiry_date": doc.expiry_date,
                "days_remaining": days_remaining,
                "status": doc.status,
            })

    return data