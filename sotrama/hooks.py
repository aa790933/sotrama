"""
Sotrama — Algerian Localization for ERPNext

Adds NIF, NIS, and RC fields to the Company doctype.
These are Algerian business registration numbers:
  - NIF : Numéro d'Identification Fiscale (tax ID)
  - NIS : Numéro d'Identification Statistique (statistical ID)
  - RC  : Registre de Commerce (trade registry)
"""

from __future__ import unicode_literals

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


# ---------------------------------------------------------------------------
# Custom Field Definitions
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
                "fieldname": "nif",
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
                "fieldname": "nis",
                "fieldtype": "Data",
                "label": "NIS (Statistical ID)",
                "insert_after": "nif",
                "in_standard_filter": 1,
                "in_list_view": 1,
                "in_preview": 1,
                "reqd": 0,
                "description": "Numéro d'Identification Statistique — Algerian statistical registration number",
            },
            {
                "fieldname": "rc",
                "fieldtype": "Data",
                "label": "RC (Trade Registry)",
                "insert_after": "nis",
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

    Currently a placeholder — extend with currency, tax template,
    or chart of accounts defaults as requirements grow.
    """
    # Example: set default tax template for Algerian companies
    # doc = frappe.get_doc("Company", company)
    # if not doc.default_tax_template:
    #     doc.default_tax_template = "TVA Algeria"
    # doc.save()
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
    for fieldname in ("nif", "nis", "rc"):
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
# Doc Events — react to Company lifecycle events
# ---------------------------------------------------------------------------

doc_events = {
    "Company": {
        "after_insert": "sotrama.sotrama.setup.setup",
        "after_rename": "sotrama.sotrama.setup.on_company_rename",
    },
}


def on_company_rename(doc):
    """
    Called after a Company is renamed.
    Ensures the custom fields still reference the correct company.
    """
    # Custom fields are tied to the doctype, not the company name,
    # so no action is needed here. Placeholder for future logic.
    pass


# ---------------------------------------------------------------------------
# Scheduler — none needed for this app
# ---------------------------------------------------------------------------

scheduler_events = {}

# ---------------------------------------------------------------------------
# Includes — global JS/CSS loaded on the Desk
# ---------------------------------------------------------------------------

includes = []
app_include_js = {
    "desk": "/assets/sotrama/js/sotrama.js",
}
app_include_css = {
    "desk": "/assets/sotrama/css/sotrama.css",
}

# ---------------------------------------------------------------------------
# DocType JS — per-DocType client-side scripts
# ---------------------------------------------------------------------------

doctype_js = {
    "Company": "/assets/sotrama/js/company.js",
}

# ---------------------------------------------------------------------------
# Workflow — none needed
# ---------------------------------------------------------------------------

workflow = {}