"""
Sotrama — Algerian Localization & Public Works Fleet Management for ERPNext

Adds NIF, NIS, and RC fields to the Company doctype.
Also provides a full TP (Travaux Publics) Fleet Management module:
Vehicle, Driver, Maintenance Job Card, Breakdown Incident,
Maintenance Schedule, Vehicle Inspection, Operational Task,
Company Classification (Grade I–IX), and supporting masters.
"""

from __future__ import unicode_literals

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


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
# Setup — called by ERPNext's regional system when a Company with
# country='Algeria' is created.
# ---------------------------------------------------------------------------

def setup(company, is_setup=True):
    """
    Called automatically by ERPNext via
    `erpnext.setup.doctype.company.company.install_country_fixtures`.

    Ensures the NIF / NIS / RC custom fields exist and applies any
    Algeria-specific Company defaults.
    """
    create_custom_fields(get_custom_fields(), ignore_submit=True)

    if company:
        _set_algerian_defaults(company)


def _set_algerian_defaults(company):
    """
    Apply Algeria-specific defaults to a Company record.
    """
    pass


# ---------------------------------------------------------------------------
# Lifecycle Hooks
# ---------------------------------------------------------------------------

def after_install():
    """Called after the app is installed on a site."""
    create_custom_fields(get_custom_fields(), ignore_submit=True)


def before_uninstall():
    """
    Called before the app is uninstalled.
    Removes the custom fields we added so the uninstall is clean.
    """
    _remove_custom_fields()


def after_migrate():
    """Called after `bench migrate` completes. Re-applies custom fields."""
    create_custom_fields(get_custom_fields(), ignore_submit=True)


def _remove_custom_fields():
    """Remove the NIF / NIS / RC custom fields from the Company doctype."""
    for fieldname in ("custom_nif", "custom_nis", "custom_rc"):
        existing = frappe.db.get_value(
            "Custom Field",
            {"dt": "Company", "fieldname": fieldname, "module": "Sotrama"},
        )
        if existing:
            frappe.delete_doc("Custom Field", existing, ignore_on_trash=True)


# ---------------------------------------------------------------------------
# Fixtures — export these so they're version-controlled and reinstall
# on new sites. Always filter by module so we don't export unrelated
# custom fields from other apps.
# ---------------------------------------------------------------------------

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Sotrama"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "Sotrama"]]},
]


# ---------------------------------------------------------------------------
# Doc Events — react to lifecycle events across TP DocTypes
# ---------------------------------------------------------------------------

doc_events = {
    # Company — Algerian registration fields
    "Company": {
        "after_insert": "sotrama.sotrama.setup.setup",
        "after_rename": "sotrama.sotrama.setup.on_company_rename",
    },
    # Vehicle — auto-create initial inspection on submit (via controller)
    "Vehicle": {
        "on_submit": "sotrama.tp.doctype.vehicle.vehicle.Vehicle.on_submit",
        "on_cancel": "sotrama.tp.doctype.vehicle.vehicle.Vehicle.on_cancel",
    },
    # Breakdown — auto-create job card, update driver count, mark OOS
    "Breakdown Incident": {
        "on_submit": "sotrama.tp.doctype.breakdown_incident.breakdown_incident.on_submit",
        "before_cancel": "sotrama.tp.doctype.breakdown_incident.breakdown_incident.before_cancel",
    },
    # Maintenance Job Card — auto-post stock, update odometer, gen next schedule
    "Maintenance Job Card": {
        "on_submit": "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.on_submit",
    },
    # Vehicle Inspection — auto-create defect issues, update vehicle status
    "Vehicle Inspection": {
        "on_submit": "sotrama.tp.doctype.vehicle_inspection.vehicle_inspection.on_submit",
    },
    # Operational Task — assign driver to vehicle
    "Operational Task": {
        "on_submit": "sotrama.tp.doctype.operational_task.operational_task.on_submit",
    },
    # Driver — validate license expiry
    "Driver": {
        "validate": "sotrama.tp.doctype.driver.driver.validate",
    },
}


def on_company_rename(doc):
    """Called after a Company is renamed. No action needed — fields are doctype-level."""
    pass


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
app_include_js = {
    "desk": "/assets/sotrama/js/sotrama.js",
}
# No custom CSS — app follows standard Frappe Desk styling

# ---------------------------------------------------------------------------
# DocType JS — per-DocType client-side scripts
# ---------------------------------------------------------------------------

doctype_js = {
    "Company": "/assets/sotrama/js/company.js",
    "Vehicle": "/assets/sotrama/js/vehicle.js",
    "Breakdown Incident": "/assets/sotrama/js/breakdown.js",
    "Maintenance Job Card": "/assets/sotrama/js/job_card.js",
    "Vehicle Inspection": "/assets/sotrama/js/inspection.js",
    "Operational Task": "/assets/sotrama/js/operational_task.js",
    "Driver": "/assets/sotrama/js/driver.js",
}

# ---------------------------------------------------------------------------
# Workflow — none needed (state managed via DocType controller)
# ---------------------------------------------------------------------------

workflow = {}

# ---------------------------------------------------------------------------
# Extend Core DocTypes (v16 best practice: extend, don't override)
# ---------------------------------------------------------------------------

extend_doctype_class = {
    # Extend core Vehicle with fleet-specific methods
    "Vehicle": "sotrama.tp.doctype.vehicle.vehicle.Vehicle",
}

# ---------------------------------------------------------------------------
# Override Whitelisted Methods — none needed
# ---------------------------------------------------------------------------

override_whitelisted_methods = {}