"""Non-invasive setup helpers for Sotrama and its ERPNext integration."""


def ensure_default_masters():
    """Create missing fleet reference records without overwriting site edits."""
    import frappe

    default_makes = (
        "Mercedes-Benz",
        "Volvo",
        "Scania",
        "Renault Trucks",
        "IVECO",
        "MAN",
        "Tata",
    )
    for make_name in default_makes:
        if not frappe.db.exists("Vehicle Make", {"make_name": make_name}):
            frappe.get_doc({"doctype": "Vehicle Make", "make_name": make_name}).insert(
                ignore_permissions=True
            )

    default_job_types = (
        ("Oil Change", "Engine", 1.0, 2500),
        ("Brake Service", "Braking", 2.0, 5000),
        ("Transmission Service", "Drive Line", 3.0, 7500),
        ("Tire Rotation", "Tyres", 0.5, 1500),
        ("Engine Tune-up", "Engine", 4.0, 10000),
        ("Electrical Check", "Electrical", 2.0, 4000),
        ("Suspension Service", "Suspension", 3.0, 6000),
        ("Annual Inspection", "Safety", 4.0, 8000),
    )
    for job_type_name, category, standard_hours, default_rate in default_job_types:
        if not frappe.db.exists(
            "Maintenance Job Type", {"job_type_name": job_type_name}
        ):
            frappe.get_doc(
                {
                    "doctype": "Maintenance Job Type",
                    "job_type_name": job_type_name,
                    "job_category": category,
                    "standard_labour_hours": standard_hours,
                    "default_rate": default_rate,
                }
            ).insert(ignore_permissions=True)


def setup(company, is_setup=True):
    """Keep regional setup non-invasive; Sotrama features require admin opt-in.

    ERPNext's standard regional setup remains authoritative for Company data.
    Optional Sotrama fields are enabled from Sotrama Settings after installation.
    """
