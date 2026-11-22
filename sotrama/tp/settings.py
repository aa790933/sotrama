"""Small, safe accessors for the singleton TP Settings document."""

import frappe

# The public setting names are also used by TP Settings (the singleton), but
# TP Company Defaults is a child table with its own field names.
COMPANY_DEFAULT_ROW_FIELDS = {
    "default_company_classification": "company_classification",
}


def validate_company_access(
    company: str, applicable_for: str | None = None, *, user: str | None = None
):
    """Enforce applicable Company User Permissions after a controller derives Company."""
    user = user or frappe.session.user
    if not company:
        frappe.throw(frappe._("A Company is required for this Fleet operation."))
    if not frappe.db.exists("Company", company):
        frappe.throw(
            frappe._("Company is unavailable or you do not have permission to use it."),
            frappe.PermissionError,
        )

    from frappe.permissions import get_allowed_docs_for_doctype, get_user_permissions

    company_permissions = get_user_permissions(user).get("Company", [])
    if applicable_for:
        allowed_companies = get_allowed_docs_for_doctype(
            company_permissions, applicable_for
        )
    else:
        allowed_companies = [
            permission.get("doc")
            for permission in company_permissions
            if not permission.get("applicable_for")
        ]
    if allowed_companies and company not in allowed_companies:
        frappe.throw(
            frappe._("Company is unavailable or you do not have permission to use it."),
            frappe.PermissionError,
        )
    return company


def get_tp_setting(fieldname: str, default=None):
    """Return one TP setting, falling back safely during first install/migrate."""
    if not frappe.db.exists("DocType", "TP Settings"):
        return default

    value = frappe.db.get_single_value("TP Settings", fieldname)
    return default if value is None else value


def get_tp_company_setting(
    company: str | None,
    fieldname: str,
    applicable_for: str,
    default=None,
    *,
    validate_access=True,
):
    """Resolve a company-specific default before the primary-company fallback."""
    if not company:
        return get_tp_setting(fieldname, default)

    if validate_access:
        validate_company_access(company, applicable_for)
    if not frappe.db.exists("DocType", "TP Company Defaults"):
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
        COMPANY_DEFAULT_ROW_FIELDS.get(fieldname, fieldname),
    )
    if value is not None:
        return value

    if get_tp_setting("default_company") == company:
        value = get_tp_setting(fieldname)
        return default if value is None else value
    return default


@frappe.whitelist()
def get_tp_company_defaults(company: str):
    """Return a fixed, company-scoped projection for Vehicle form defaults.

    The underlying singleton/table fields are System Manager-only. This API is
    the intentional exception for the three operational defaults needed by
    Vehicle creation; it never returns other Companies' rows or arbitrary fields.
    Company access follows the Vehicle User Permission scope; it does not grant
    or require general Company read permission.
    """
    frappe.has_permission("TP Settings", "read", throw=True)
    frappe.has_permission("Vehicle", "create", throw=True)
    validate_company_access(company, "Vehicle")

    linked_defaults = {
        "default_department": "Department",
        "default_cost_center": "Cost Center",
        "default_parts_warehouse": "Warehouse",
    }
    return {
        fieldname: _get_accessible_company_default(company, fieldname, doctype)
        for fieldname, doctype in linked_defaults.items()
    }


@frappe.whitelist()
def get_tp_default_company(applicable_for: str = "Vehicle"):
    """Return the primary Company only when the caller may use it for this DocType.

    This is a constrained projection of the System Manager-only setting, not a
    general TP Settings field read. Company access follows the requested
    DocType's User Permission scope, without requiring broad Company read access.
    """
    if applicable_for not in {"Vehicle", "Company Classification"}:
        frappe.throw(
            frappe._("Unsupported Company default context."), frappe.PermissionError
        )
    frappe.has_permission("TP Settings", "read", throw=True)
    frappe.has_permission(applicable_for, "create", throw=True)
    company = get_tp_setting("default_company")
    if company:
        validate_company_access(company, applicable_for)
    return company


def _get_accessible_company_default(company: str, fieldname: str, doctype: str):
    """Return a linked default only when its target is readable and same-Company."""
    value = get_tp_company_setting(company, fieldname, "Vehicle", validate_access=False)
    if not value or not frappe.has_permission(doctype, "read", doc=value):
        return None

    linked_company = frappe.db.get_value(doctype, value, "company")
    if not linked_company or linked_company != company:
        return None

    try:
        validate_company_access(linked_company, doctype)
    except frappe.PermissionError:
        return None
    return value
