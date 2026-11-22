"""Make Fleet lookup masters ordinary records and normalize legacy rows."""


def execute():
    import frappe

    for doctype in ("Vehicle Make", "Vehicle Model", "Maintenance Job Type"):
        if not frappe.db.table_exists(doctype):
            continue

        records = frappe.get_all(
            doctype,
            fields=["name", "docstatus", "active"],
            limit_page_length=0,
        )
        for record in records:
            values = {}
            if record.docstatus == 2:
                # A cancelled lookup master must not become selectable again.
                values["active"] = 0
            if record.docstatus:
                values["docstatus"] = 0
            if values:
                frappe.db.set_value(
                    doctype, record.name, values, update_modified=False
                )

    if not frappe.db.table_exists("Vehicle Model") or not frappe.db.table_exists(
        "Vehicle Make"
    ):
        return

    # Older Vehicle Model rows stored the make only in the legacy Data field.
    # Resolve it by the manufacturer's display name first, then by document name.
    models = frappe.get_all(
        "Vehicle Model",
        fields=["name", "make", "vehicle_make"],
        limit_page_length=0,
    )
    unresolved_models = []
    for model in models:
        if model.vehicle_make and frappe.db.exists("Vehicle Make", model.vehicle_make):
            if model.make != model.vehicle_make:
                frappe.db.set_value(
                    "Vehicle Model",
                    model.name,
                    "make",
                    model.vehicle_make,
                    update_modified=False,
                )
            continue

        if not model.make:
            unresolved_models.append(
                f"{model.name}: no legacy make value (invalid vehicle_make={model.vehicle_make or 'blank'})"
            )
            if model.vehicle_make:
                frappe.db.set_value(
                    "Vehicle Model",
                    model.name,
                    "vehicle_make",
                    "",
                    update_modified=False,
                )
            continue

        make_name = frappe.db.get_value(
            "Vehicle Make", {"make_name": model.make}, "name"
        )
        if not make_name and frappe.db.exists("Vehicle Make", model.make):
            make_name = model.make

        if make_name:
            frappe.db.set_value(
                "Vehicle Model",
                model.name,
                {"vehicle_make": make_name, "make": make_name},
                update_modified=False,
            )
        else:
            unresolved_models.append(
                f"{model.name}: legacy make '{model.make}' not found "
                f"(invalid vehicle_make={model.vehicle_make or 'blank'})"
            )
            if model.vehicle_make:
                frappe.db.set_value(
                    "Vehicle Model",
                    model.name,
                    "vehicle_make",
                    "",
                    update_modified=False,
                )

    if unresolved_models:
        frappe.log_error(
            "\n".join(unresolved_models),
            "Unresolved Legacy Vehicle Model Makes",
        )

    for doctype in ("Vehicle Make", "Vehicle Model", "Maintenance Job Type"):
        frappe.clear_cache(doctype=doctype)
