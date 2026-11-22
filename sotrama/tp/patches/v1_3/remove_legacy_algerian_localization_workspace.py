"""Remove retired Algerian Localization navigation without touching business data."""


def execute():
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
