from __future__ import unicode_literals

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def after_install():
    """
    Called after the app is installed.
    Creates the NIF / NIS / RC custom fields on the Company doctype.
    """
    create_custom_fields(get_custom_fields(), ignore_submit=True)


def get_custom_fields():
    """
    Returns the custom field definitions for the Company doctype.
    These add Algerian business registration numbers:
      - NIF  : Numéro d'Identification Fiscale (tax ID)
      - NIS  : Numéro d'Identification Statistique (statistical ID)
      - RC   : Registre de Commerce (trade registry)
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
# Fixtures — export these so they're version-controlled and reinstall on new sites
# ---------------------------------------------------------------------------

fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "Algerian Localization"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "Algerian Localization"]]},
]

# ---------------------------------------------------------------------------
# Hooks — lifecycle events
# ---------------------------------------------------------------------------

doc_events = {
    "Company": {
        "after_insert": "algerian_localization.algerian_localization.setup.set_default_country",
    },
}

# ---------------------------------------------------------------------------
# Scheduler — none needed for this app
# ---------------------------------------------------------------------------

scheduler_events = {}

# ---------------------------------------------------------------------------
# Includes — none needed
# ---------------------------------------------------------------------------

includes = []
app_include_js = {}
app_include_css = {}