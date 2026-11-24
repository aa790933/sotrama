"""Remove the retired Algerian Localization module without touching business data."""


def remove_legacy_algerian_localization_workspace():
    import frappe

    module = "Algerian Localization"
    for doctype in ("Workspace", "Sidebar"):
        if not frappe.db.exists(doctype, module):
            continue

        record = frappe.db.get_value(
            doctype, module, ["module", "standard"], as_dict=True
        )
        if record and record.module == module and record.standard:
            if doctype == "Workspace":
                if frappe.db.exists("Custom Workspace", module):
                    frappe.delete_doc(
                        "Custom Workspace",
                        module,
                        ignore_permissions=True,
                        force=True,
                    )

                workspace = frappe.get_doc(doctype, module)
                workspace.drop_sidebar_rows()
                workspace.delete_desktop_icon()

            frappe.delete_doc(
                doctype,
                module,
                ignore_permissions=True,
                force=True,
                ignore_on_trash=(doctype == "Workspace"),
            )

    for sidebar in frappe.get_all(
        "Custom Sidebar", filters={"module": module}, pluck="name"
    ):
        frappe.delete_doc(
            "Custom Sidebar", sidebar, ignore_permissions=True, force=True
        )

    module_def = frappe.db.get_value(
        "Module Def", module, ["app_name", "custom"], as_dict=True
    )
    if module_def and module_def.app_name == "sotrama" and not module_def.custom:
        has_doctypes = frappe.get_all(
            "DocType", filters={"module": module}, pluck="name", limit_page_length=1
        )
        if not has_doctypes:
            frappe.delete_doc("Module Def", module, ignore_permissions=True, force=True)
