"""Non-invasive setup helpers for Sotrama and its ERPNext integration."""

import unicodedata

from sotrama.designations import PUBLIC_WORKS_DESIGNATIONS


def _designation_name_key(value):
    """Normalize names consistently with case/accent-insensitive DB collations."""
    normalized = unicodedata.normalize("NFKD", " ".join((value or "").split()))
    return "".join(
        character
        for character in normalized.casefold()
        if not unicodedata.combining(character)
    )


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
    from frappe.exceptions import DuplicateEntryError

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

    existing_names = {
        _designation_name_key(name)
        for name in frappe.get_all(
            "Designation",
            pluck="designation_name",
            limit_page_length=0,
        )
    }

    created = []
    for designation_name in PUBLIC_WORKS_DESIGNATIONS:
        name_key = _designation_name_key(designation_name)
        if name_key in existing_names:
            continue

        designation = frappe.new_doc("Designation")
        designation.designation_name = designation_name
        try:
            designation.insert()
        except DuplicateEntryError:
            # A concurrent seed or a database collation-equivalent spelling
            # may have created the same unique designation after the query.
            if not frappe.db.exists(
                "Designation", {"designation_name": designation_name}
            ):
                raise
            existing_names.add(name_key)
            continue
        created.append(designation.name)
        existing_names.add(name_key)

    return created


def setup(company, is_setup=True):
    """Keep regional setup non-invasive; Sotrama features require admin opt-in.

    ERPNext's standard regional setup remains authoritative for Company data.
    Optional Sotrama fields are enabled from Sotrama Settings after installation.
    """
