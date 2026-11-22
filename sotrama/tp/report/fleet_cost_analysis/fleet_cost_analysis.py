"""Fleet cost analysis by vehicle, using submitted ERPNext fleet transactions.

Maintenance costs come from submitted Maintenance Job Cards and distance comes
from submitted Operational Tasks. Depreciation is a transparent straight-line
estimate for the selected period; it is not a replacement for ERPNext Asset
depreciation or ledger balances.
"""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, today


def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)
    return get_columns(), get_data(filters)


def validate_filters(filters):
    if (
        filters.get("from_date")
        and filters.get("to_date")
        and getdate(filters.from_date) > getdate(filters.to_date)
    ):
        frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
    return [
        {
            "label": _("Vehicle"),
            "fieldname": "vehicle",
            "fieldtype": "Link",
            "options": "Vehicle",
            "width": 115,
        },
        {
            "label": _("License Plate"),
            "fieldname": "license_plate",
            "fieldtype": "Data",
            "width": 115,
        },
        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Data",
            "width": 150,
        },
        {
            "label": _("Currency"),
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 85,
        },
        {
            "label": _("Distance (km)"),
            "fieldname": "distance_km",
            "fieldtype": "Float",
            "width": 100,
        },
        {
            "label": _("Parts & Labour"),
            "fieldname": "maintenance_cost",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 125,
        },
        {
            "label": _("Other Costs"),
            "fieldname": "other_costs",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 115,
        },
        {
            "label": _("Estimated Depreciation"),
            "fieldname": "depreciation",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 145,
        },
        {
            "label": _("Total Cost"),
            "fieldname": "total_cost",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 120,
        },
        {
            "label": _("Cost per km"),
            "fieldname": "cost_per_km",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 115,
        },
    ]


def _date_filters(filters, fieldname):
    conditions = []
    if filters.get("from_date"):
        conditions.append([fieldname, ">=", filters.from_date])
    if filters.get("to_date"):
        conditions.append([fieldname, "<=", filters.to_date])
    return conditions


def _estimate_depreciation(vehicle, filters):
    """Estimate straight-line depreciation for the report period, capped at cost."""
    if not vehicle.acquisition_date or not vehicle.acquisition_value:
        return 0.0

    rate = flt(vehicle.depreciation_rate)
    if rate <= 0:
        return 0.0

    acquisition_date = getdate(vehicle.acquisition_date)
    period_start = max(
        acquisition_date,
        getdate(filters.from_date) if filters.get("from_date") else acquisition_date,
    )
    period_end = min(
        getdate(filters.to_date) if filters.get("to_date") else getdate(today()),
        getdate(today()),
    )
    # Report date filters are inclusive (>= from_date and <= to_date), so a
    # one-day reporting period must accrue one day rather than zero.
    days = max(date_diff(period_end, period_start) + 1, 0)
    depreciable_value = max(flt(vehicle.acquisition_value) - flt(vehicle.salvage_value), 0)
    return min(depreciable_value, depreciable_value * rate / 100.0 * days / 365.0)


def get_data(filters):
    """Aggregate all submitted maintenance and task records in two grouped queries."""
    vehicle_filters = [
        ["docstatus", "=", 1],
        ["vehicle_status", "not in", ["Retired", "Scrapped"]],
    ]
    if filters.get("company"):
        vehicle_filters.append(["company", "=", filters.company])
    if filters.get("vehicle"):
        vehicle_filters.append(["name", "=", filters.vehicle])

    vehicles = frappe.get_list(
        "Vehicle",
        fields=[
            "name",
            "license_plate",
            "company",
            "acquisition_date",
            "acquisition_value",
            "depreciation_rate",
            "salvage_value",
        ],
        filters=vehicle_filters,
        order_by="license_plate asc, name asc",
        limit_page_length=0,
    )
    if not vehicles:
        return []

    vehicle_names = [vehicle.name for vehicle in vehicles]
    # TP cost fields currently use Frappe's site default currency (they are not
    # Company-currency fields). Label them with that same currency rather than
    # incorrectly substituting each Company's default_currency.
    report_currency = frappe.db.get_default("currency")

    maintenance_filters = [["docstatus", "=", 1], ["vehicle", "in", vehicle_names]]
    maintenance_filters.extend(_date_filters(filters, "job_date"))
    maintenance_rows = frappe.get_list(
        "Maintenance Job Card",
        fields=[
            "vehicle",
            {"SUM": "total_parts_cost", "as": "parts_cost"},
            {"SUM": "total_labour_cost", "as": "labour_cost"},
            {"SUM": "total_other_cost", "as": "other_cost"},
        ],
        filters=maintenance_filters,
        group_by="vehicle",
        limit_page_length=0,
    )

    task_filters = [["docstatus", "=", 1], ["vehicle", "in", vehicle_names]]
    task_filters.extend(_date_filters(filters, "task_date"))
    distance_rows = frappe.get_list(
        "Operational Task",
        fields=["vehicle", {"SUM": "distance_covered", "as": "distance_km"}],
        filters=task_filters,
        group_by="vehicle",
        limit_page_length=0,
    )

    costs_by_vehicle = {row.vehicle: row for row in maintenance_rows}
    distance_by_vehicle = {row.vehicle: flt(row.distance_km) for row in distance_rows}
    data = []

    for vehicle in vehicles:
        maintenance = costs_by_vehicle.get(vehicle.name)
        parts_and_labour = (
            flt(maintenance.parts_cost) + flt(maintenance.labour_cost) if maintenance else 0
        )
        other_costs = flt(maintenance.other_cost) if maintenance else 0
        distance = distance_by_vehicle.get(vehicle.name, 0)
        depreciation = _estimate_depreciation(vehicle, filters)
        total_cost = parts_and_labour + other_costs + depreciation

        data.append(
            {
                "vehicle": vehicle.name,
                "license_plate": vehicle.license_plate,
                "company": vehicle.company,
                "currency": report_currency,
                "distance_km": distance,
                "maintenance_cost": parts_and_labour,
                "other_costs": other_costs,
                "depreciation": round(depreciation, 2),
                "total_cost": round(total_cost, 2),
                "cost_per_km": round(total_cost / distance, 2) if distance > 0 else 0,
            }
        )

    return data
