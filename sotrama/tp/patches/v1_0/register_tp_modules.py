"""
Patch: register_tp_modules
Registers the TP module and all its DocTypes in Frappe's Module Def system.
Run once during bench migrate.
"""


import frappe


def execute():
    """Register the TP module backed by the ``sotrama.tp`` package."""
    modules = ["TP"]

    for module_name in modules:
        if not frappe.db.exists("Module Def", module_name):
            module = frappe.new_doc("Module Def")
            module.module_name = module_name
            module.insert(ignore_permissions=True)
            frappe.db.commit()
            print("Created Module Def: {0}".format(module_name))
