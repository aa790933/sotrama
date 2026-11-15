"""
Sotrama setup — Algerian localization for ERPNext.

Called by ERPNext's regional setup system when a Company with
country='Algeria' is created. Ensures NIF / NIS / RC custom fields
exist and applies Algeria-specific defaults.
"""

from __future__ import unicode_literals

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def get_custom_fields():
    """Return the custom field definitions for the Company doctype."""
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