"""
Fleet Cost Analysis Report

Shows submitted maintenance costs, additional costs, estimated depreciation,
distance recorded on submitted operational tasks, and total cost per kilometre.
"""


import frappe
from frappe.utils import flt


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
            "label": "Distance (km)",
            "fieldname": "distance_km",
            "fieldtype": "Float",
            "width": 100,
        },
        {
            "label": "Maintenance Cost (DZD)",
            "fieldname": "maintenance_cost",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "Other Costs (DZD)",
            "fieldname": "other_costs",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Estimated Depreciation (DZD)",
            "fieldname": "depreciation",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Total Cost (DZD)",
            "fieldname": "total_cost",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Cost per km (DZD)",
            "fieldname": "cost_per_km",
            "fieldtype": "Currency",
            "width": 120,
        },
    ]


def get_data(filters):
    """Build the report data."""
    data = []

    # Get vehicles with their cost data
    vehicles = frappe.get_all(
        "Vehicle",
        fields=["name", "license_plate", "acquisition_date", "acquisition_value", "depreciation_rate",
                "salvage_value", "current_odometer"],
        filters={"vehicle_status": ["!=", "Retired"]},
    )

    for v in vehicles:
        # Get maintenance costs from submitted job cards
        maintenance_cost, other_costs = frappe.db.sql("""
            SELECT COALESCE(SUM(COALESCE(total_parts_cost, 0) + COALESCE(total_labour_cost, 0)), 0),
                   COALESCE(SUM(COALESCE(total_other_cost, 0)), 0)
            FROM `tabMaintenance Job Card`
            WHERE vehicle = %s AND docstatus = 1
        """, v.name)[0]

        # Get odometer-based distance (simplified - from operational tasks)
        distance = frappe.db.sql("""
            SELECT COALESCE(SUM(distance_covered), 0)
            FROM `tabOperational Task`
            WHERE vehicle = %s AND docstatus = 1
        """, v.name)[0][0]

        maintenance_cost = flt(maintenance_cost)
        other_costs = flt(other_costs)
        distance = flt(distance)

        # Estimate straight-line depreciation, capped at acquisition less salvage.
        depreciation = 0
        if v.acquisition_value and v.depreciation_rate:
            from frappe.utils import date_diff, today
            years = date_diff(today(), v.acquisition_date or today()) / 365.0
            depreciable_value = max(
                flt(v.acquisition_value) - flt(v.salvage_value), 0
            )
            depreciation = min(
                depreciable_value,
                depreciable_value * flt(v.depreciation_rate) / 100.0 * max(years, 0),
            )

        total_cost = maintenance_cost + other_costs + depreciation
        cost_per_km = total_cost / distance if distance else 0

        data.append({
            "vehicle": v.name,
            "license_plate": v.license_plate,
            "distance_km": distance,
            "maintenance_cost": maintenance_cost,
            "other_costs": other_costs,
            "depreciation": depreciation,
            "total_cost": total_cost,
            "cost_per_km": round(cost_per_km, 2),
        })

    return data
