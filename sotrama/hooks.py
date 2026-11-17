"""
Sotrama — Algerian Localization & Public Works Fleet Management for ERPNext

Adds NIF, NIS, and RC fields to the Company doctype.
Also provides a full TP (Travaux Publics) Fleet Management module:
Vehicle, Driver, Maintenance Job Card, Breakdown Incident,
Maintenance Schedule, Vehicle Inspection, Operational Task,
Company Classification (Grade I–IX), and supporting masters.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from . import __version__ as _app_version

app_name = "sotrama"
app_title = "Sotrama"
app_version = _app_version
app_publisher = "dekukoda41"
app_description = (
    "Algerian company localization and public-works fleet management "
    "for ERPNext and Frappe HR."
)
app_email = "dekukoda41@users.noreply.github.com"
app_license = "MIT"
app_color = "#d94736"
app_logo_url = "/assets/sotrama/images/sotrama-logo.svg"
app_home = "/desk/sotrama-fleet"
required_apps = ["frappe/erpnext", "frappe/hrms"]

add_to_apps_screen = [
    {
        "name": app_name,
        "logo": app_logo_url,
        "title": app_title,
        "route": app_home,
        "has_permission": "sotrama.permissions.has_app_permission",
        "sequence_id": 3,
    }
]


def ensure_roles():
    """Create the app roles before DocTypes and Role Profile fixtures sync."""
    for role_name in ("Fleet Manager", "Workshop", "Driver"):
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": 1,
                }
            ).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Custom Field Definitions — Company doctype (Algerian registration)
# ---------------------------------------------------------------------------

def get_custom_fields():
    """
    Returns the custom field definitions for the Company doctype.
    These are defined in code (not the database) so they survive
    `bench update` and migrate cleanly to new sites.
    """
    return {
        "Company": [
            {
                "fieldname": "custom_nif",
                "fieldtype": "Data",
                "label": "NIF (Tax ID)",
                "module": "Sotrama",
                "insert_after": "tax_id",
                "in_standard_filter": 1,
                "in_list_view": 1,
                "in_preview": 1,
                "reqd": 0,
                "description": "Numéro d'Identification Fiscale — Algerian tax registration number",
            },
            {
                "fieldname": "custom_nis",
                "fieldtype": "Data",
                "label": "NIS (Statistical ID)",
                "module": "Sotrama",
                "insert_after": "custom_nif",
                "in_standard_filter": 1,
                "in_list_view": 1,
                "in_preview": 1,
                "reqd": 0,
                "description": "Numéro d'Identification Statistique — Algerian statistical registration number",
            },
            {
                "fieldname": "custom_rc",
                "fieldtype": "Data",
                "label": "RC (Trade Registry)",
                "module": "Sotrama",
                "insert_after": "custom_nis",
                "in_standard_filter": 1,
                "in_list_view": 1,
                "in_preview": 1,
                "reqd": 0,
                "description": "Registre de Commerce — Algerian trade registry number",
            },
        ],
    }


# ---------------------------------------------------------------------------
# Setup — fields are installed and kept in sync through app lifecycle hooks.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Lifecycle Hooks
# ---------------------------------------------------------------------------

def install_company_fields():
    """Create Sotrama's Company fields after the app is installed."""
    ensure_roles()
    create_custom_fields(get_custom_fields())


def uninstall_company_fields():
    """Remove Sotrama-owned Company fields when the app is uninstalled."""
    for fieldname in ("custom_nif", "custom_nis", "custom_rc"):
        existing = frappe.db.get_value(
            "Custom Field",
            {"dt": "Company", "fieldname": fieldname, "module": "Sotrama"},
        )
        if existing:
            frappe.delete_doc("Custom Field", existing, ignore_on_trash=True)


def sync_company_fields():
    """Idempotently create or update the Company fields after migrations."""
    ensure_roles()
    create_custom_fields(get_custom_fields())


# ---------------------------------------------------------------------------
# Fixtures — export these so they're version-controlled and reinstall
# on new sites. Always filter by module so we don't export unrelated
# custom fields from other apps.
# ---------------------------------------------------------------------------

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Sotrama"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "Sotrama"]]},
]

before_install = "sotrama.hooks.ensure_roles"
after_install = "sotrama.hooks.install_company_fields"
before_uninstall = "sotrama.hooks.uninstall_company_fields"
after_migrate = "sotrama.hooks.sync_company_fields"


# ---------------------------------------------------------------------------
# Scheduler — daily expiry alerts for documents and maintenance
# ---------------------------------------------------------------------------

scheduler_events = {
    "daily": [
        "sotrama.tp.scheduler.check_document_expiries",
        "sotrama.tp.scheduler.check_maintenance_due",
        "sotrama.tp.scheduler.check_driver_license_expiry",
    ],
}


# ---------------------------------------------------------------------------
# Includes — global JS loaded on the Desk
# ---------------------------------------------------------------------------

includes = []
# Frappe's app_include_js hook is a scalar path or a list of paths.
# A dict here conflicts with the same hook from Frappe/ERPNext/HRMS while
# the framework merges app hooks, causing append_hook() to call setdefault
# on a list during site installation.
app_include_js = "/assets/sotrama/js/sotrama.js"
# No custom CSS — app follows standard Frappe Desk styling


# ---------------------------------------------------------------------------
# DocType JS — per-DocType client-side scripts
# ---------------------------------------------------------------------------

doctype_js = {
    "Company": "public/js/company.js",
    "Vehicle": "public/js/vehicle.js",
    "Breakdown Incident": "public/js/breakdown.js",
    "Maintenance Job Card": "public/js/job_card.js",
    "Vehicle Inspection": "public/js/inspection.js",
    "Operational Task": "public/js/operational_task.js",
    "Driver": "public/js/driver.js",
}


# ---------------------------------------------------------------------------
# Workflow — none needed (state managed via DocType controller)
# ---------------------------------------------------------------------------

workflow = {}
