"""Non-invasive setup helpers for Sotrama and its ERPNext integration."""

from sotrama.designations import PUBLIC_WORKS_DESIGNATIONS


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


def ensure_public_works_designations():
    """Create missing Algerian BTPH job titles in Frappe HR's Designation master.

    This helper is called only after an administrator explicitly enables the
    option in Sotrama Settings. Existing Designation records are never changed
    or deleted; HR users continue managing them through the standard HRMS UI.
    """
    import frappe

    if not frappe.db.exists("DocType", "Designation"):
        frappe.throw(
            frappe._(
                "Frappe HR's Designation DocType is unavailable. Install or enable Frappe HR first."
            )
        )

    meta = frappe.get_meta("Designation")
    if not meta.has_field("designation_name"):
        frappe.throw(
            frappe._(
                "The installed Designation DocType does not expose the expected designation_name field."
            )
        )

    if not frappe.has_permission("Designation", "create"):
        frappe.throw(
            frappe._(
                "You need permission to create Designation records before adding the BTPH list."
            )
        )

    designation_names = list(PUBLIC_WORKS_DESIGNATIONS)
    existing_names = set(
        frappe.get_all(
            "Designation",
            filters={"designation_name": ["in", designation_names]},
            pluck="designation_name",
        )
    )

    created = []
    for designation_name in PUBLIC_WORKS_DESIGNATIONS:
        if designation_name in existing_names:
            continue

        designation = frappe.new_doc("Designation")
        designation.designation_name = designation_name
        designation.insert()
        created.append(designation.name)

    return created


def setup(company, is_setup=True):
    """Keep regional setup non-invasive; Sotrama features require admin opt-in.

    ERPNext's standard regional setup remains authoritative for Company data.
    Optional Sotrama fields are enabled from Sotrama Settings after installation.
    """
