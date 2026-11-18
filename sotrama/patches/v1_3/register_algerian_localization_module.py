"""Register the Algerian Localization module as part of the Sotrama app."""

import frappe


def execute():
    module_name = "Algerian Localization"
    existing = frappe.db.get_value(
        "Module Def", module_name, ["app_name", "custom"], as_dict=True
    )
    if existing:
        if existing.app_name == "sotrama" and not existing.custom:
            return
        frappe.throw(
            frappe._(
                "The Module Def '{0}' already exists but is not owned by the Sotrama app. "
                "Resolve this module-name conflict before installing Algerian Localization."
            ).format(module_name),
            title=frappe._("Module name conflict"),
        )

    module = frappe.new_doc("Module Def")
    module.module_name = module_name
    module.app_name = "sotrama"
    module.insert(ignore_permissions=True)
