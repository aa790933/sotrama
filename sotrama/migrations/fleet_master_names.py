"""Normalize legacy IDs on Fleet lookup masters without merging records.

Random Make and Job Type IDs are replaced with their readable field values;
Model IDs are rebuilt from the linked make ID and model designation. Frappe's
rename operation updates Link fields. Existing target collisions are left
untouched and logged.
"""

import re

LEGACY_RANDOM_NAME = re.compile(r"^[a-z0-9]{10,12}$")


def normalize_fleet_master_names():
    import frappe
    from frappe.model.rename_doc import rename_doc

    from sotrama.tp.doctype.vehicle_model.vehicle_model import get_vehicle_model_name

    renamed = []
    skipped = []
    renamed_makes = {}

    if frappe.db.table_exists("Vehicle Make"):
        makes = frappe.get_all(
            "Vehicle Make", fields=["name", "make_name"], limit_page_length=0
        )
        for make in makes:
            old_name = make.name
            make_name = (make.make_name or "").strip()
            if not make_name:
                continue
            if old_name == make_name or not LEGACY_RANDOM_NAME.fullmatch(old_name):
                continue

            if frappe.db.exists("Vehicle Make", make_name):
                skipped.append(
                    f"Vehicle Make {old_name}: target {make_name!r} already exists"
                )
                continue

            try:
                rename_doc(
                    "Vehicle Make",
                    old_name,
                    make_name,
                    force=True,
                    ignore_permissions=True,
                    show_alert=False,
                    rebuild_search=False,
                )
            except frappe.ValidationError as exc:
                skipped.append(f"Vehicle Make {old_name}: {exc}")
                continue

            # rename_doc synchronizes the field-based autoname field as part
            # of the rename. Do not alter a legacy record when a collision
            # prevents the rename.
            renamed.append(("Vehicle Make", old_name, make_name))
            renamed_makes[old_name] = make_name

    # Normalize model IDs for every linked make, including models whose make
    # was already renamed manually before this patch was installed.
    if frappe.db.table_exists("Vehicle Model"):
        models = frappe.get_all(
            "Vehicle Model",
            fields=["name", "model_name", "vehicle_make", "make"],
            limit_page_length=0,
        )
        for model in models:
            vehicle_make = model.vehicle_make
            if not vehicle_make or not frappe.db.exists("Vehicle Make", vehicle_make):
                vehicle_make = renamed_makes.get(model.make) or frappe.db.get_value(
                    "Vehicle Make", {"make_name": model.make}, "name"
                )
                if (
                    not vehicle_make
                    and model.make
                    and frappe.db.exists("Vehicle Make", model.make)
                ):
                    vehicle_make = model.make
            if not vehicle_make:
                skipped.append(
                    f"Vehicle Model {model.name}: manufacturer could not be resolved"
                )
                continue

            make_name = (
                frappe.db.get_value("Vehicle Make", vehicle_make, "make_name")
                or vehicle_make
            ).strip()
            model_name = (model.model_name or "").strip()
            if not make_name or not model_name:
                skipped.append(
                    f"Vehicle Model {model.name}: make or model name is blank"
                )
                continue

            new_name = get_vehicle_model_name(vehicle_make, model_name)
            if model.name != new_name and frappe.db.exists("Vehicle Model", new_name):
                skipped.append(
                    f"Vehicle Model {model.name}: target {new_name!r} already exists"
                )
                continue

            old_model_name = model.name
            if old_model_name != new_name:
                try:
                    rename_doc(
                        "Vehicle Model",
                        old_model_name,
                        new_name,
                        force=True,
                        ignore_permissions=True,
                        show_alert=False,
                        rebuild_search=False,
                    )
                except frappe.ValidationError as exc:
                    skipped.append(f"Vehicle Model {old_model_name}: {exc}")
                    continue
                renamed.append(("Vehicle Model", old_model_name, new_name))

            # Apply the legacy Data-field synchronization only after the
            # target name is known to be safe and the rename has succeeded.
            frappe.db.set_value(
                "Vehicle Model",
                new_name,
                {
                    "vehicle_make": vehicle_make,
                    "make": vehicle_make,
                    "model_name": model_name,
                },
                update_modified=False,
            )

    if frappe.db.table_exists("Maintenance Job Type"):
        job_types = frappe.get_all(
            "Maintenance Job Type",
            fields=["name", "job_type_name"],
            limit_page_length=0,
        )
        for job_type in job_types:
            old_name = job_type.name
            job_type_name = (job_type.job_type_name or "").strip()
            if not job_type_name:
                continue
            if old_name == job_type_name or not LEGACY_RANDOM_NAME.fullmatch(old_name):
                continue

            if frappe.db.exists("Maintenance Job Type", job_type_name):
                skipped.append(
                    "Maintenance Job Type "
                    f"{old_name}: target {job_type_name!r} already exists"
                )
                continue

            try:
                rename_doc(
                    "Maintenance Job Type",
                    old_name,
                    job_type_name,
                    force=True,
                    ignore_permissions=True,
                    show_alert=False,
                    rebuild_search=False,
                )
            except frappe.ValidationError as exc:
                skipped.append(f"Maintenance Job Type {old_name}: {exc}")
                continue
            renamed.append(("Maintenance Job Type", old_name, job_type_name))

    for doctype in (
        "Vehicle Make",
        "Vehicle Model",
        "Maintenance Job Type",
        "Vehicle",
    ):
        if frappe.db.table_exists(doctype):
            frappe.clear_cache(doctype=doctype)

    if skipped:
        frappe.logger("sotrama").warning(
            "Fleet master names not normalized because of missing values "
            "or collisions:\n%s",
            "\n".join(skipped),
        )

    return renamed
