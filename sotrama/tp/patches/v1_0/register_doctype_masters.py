"""
Patch: register_doctype_masters
Creates master records (Vehicle Make, Vehicle Model, Maintenance Job Type)
that are needed for the TP Fleet Management module.
"""


import frappe


def execute():
    """Create default master records."""
    # Default vehicle makes for Algerian public works fleet
    default_makes = ["Mercedes-Benz", "Volvo", "Scania", "Renault Trucks", "IVECO", "MAN", "Tata"]

    for make in default_makes:
        if not frappe.db.exists("Vehicle Make", {"make_name": make}):
            doc = frappe.new_doc("Vehicle Make")
            doc.make_name = make
            doc.insert(ignore_permissions=True)
            print(f"Created Vehicle Make: {make}")

    # Default maintenance job types
    default_job_types = [
        ("Oil Change", "Engine", 1.0, 2500),
        ("Brake Service", "Braking", 2.0, 5000),
        ("Transmission Service", "Drive Line", 3.0, 7500),
        ("Tire Rotation", "Tyres", 0.5, 1500),
        ("Engine Tune-up", "Engine", 4.0, 10000),
        ("Electrical Check", "Electrical", 2.0, 4000),
        ("Suspension Service", "Suspension", 3.0, 6000),
        ("Annual Inspection", "Safety", 4.0, 8000),
    ]

    for job_type_name, category, std_hours, default_rate in default_job_types:
        if not frappe.db.exists(
            "Maintenance Job Type", {"job_type_name": job_type_name}
        ):
            doc = frappe.new_doc("Maintenance Job Type")
            doc.job_type_name = job_type_name
            doc.job_category = category
            doc.standard_labour_hours = std_hours
            doc.default_rate = default_rate
            doc.insert(ignore_permissions=True)
            print(f"Created Maintenance Job Type: {job_type_name}")

    print("Default masters registered successfully.")
