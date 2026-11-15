"""
Setup script for the Algerian Localization app.

This is called by ERPNext's regional setup system when a Company is created
with country = "Algeria". It ensures the custom fields exist and sets up
any Algeria-specific defaults.
"""

from __future__ import unicode_literals

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def setup(company, is_setup=True):
    """
    Called automatically by ERPNext when a Company with country='Algeria'
    is created (via erpnext.setup.doctype.company.company.install_country_fixtures).

    Creates the NIF / NIS / RC custom fields if they don't already exist.
    """
    # Ensure the custom fields exist (idempotent — safe to call multiple times)
    create_custom_fields(get_custom_fields(), ignore_submit=True)

    # Set Algeria-specific defaults on the Company record
    if company:
        _set_algerian_defaults(company)


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


def _set_algerian_defaults(company):
    """Set Algeria-specific defaults on the Company document."""
    # Currently no additional defaults beyond the custom fields.
    # Add currency, tax template, or chart of accounts defaults here
    # as your requirements grow.
    pass