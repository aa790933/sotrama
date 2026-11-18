"""Small, safe accessors for the singleton TP Settings document."""

import frappe


def get_tp_setting(fieldname: str, default=None):
    """Return one TP setting, falling back safely during first install/migrate."""
    if not frappe.db.exists("DocType", "TP Settings"):
        return default

    value = frappe.db.get_single_value("TP Settings", fieldname)
    return default if value is None else value


def get_tp_company_setting(company: str | None, fieldname: str, default=None):
    """Resolve a company-specific default before the primary-company fallback."""
    if not company or not frappe.db.exists("DocType", "TP Company Defaults"):
        return get_tp_setting(fieldname, default)

    value = frappe.db.get_value(
        "TP Company Defaults",
        {
            "parent": "TP Settings",
            "parenttype": "TP Settings",
            "parentfield": "company_defaults",
            "company": company,
            "active": 1,
        },
        fieldname,
    )
    if value is not None:
        return value

    if get_tp_setting("default_company") == company:
        value = get_tp_setting(fieldname)
        return default if value is None else value
    return default


@frappe.whitelist()
def get_tp_company_defaults(company: str):
    """Return non-sensitive defaults for a Company to prefill new fleet forms."""
    frappe.has_permission("TP Settings", "read", throw=True)
    if not frappe.db.exists("Company", company):
        frappe.throw(frappe._("Company {0} does not exist.").format(company))

    fields = (
        "default_company_classification",
        "default_department",
        "default_cost_center",
        "default_parts_warehouse",
    )
    return {
        fieldname: get_tp_company_setting(company, fieldname)
        for fieldname in fields
    }
