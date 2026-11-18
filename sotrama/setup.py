"""
Sotrama setup — Algerian localization for ERPNext.

Optional setup helper for an ERPNext regional integration.

ERPNext v16 looks for country setup code under
``erpnext.regional.<country>.setup.setup``. This module is not discovered
automatically merely because it exists in a custom app. The Company's NIF,
NIS and RC fields are created by the app installation/migration hooks instead.
"""

from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from sotrama.hooks import get_custom_fields, migrate_legacy_company_capital_field


def setup(company, is_setup=True):
    """
    Entry point for a future, explicitly wired Algeria regional setup.
    """
    migrate_legacy_company_capital_field()
    create_custom_fields(get_custom_fields())

    # Company-specific defaults are intentionally not changed here; they
    # require a separately validated Algerian chart of accounts/tax setup.
