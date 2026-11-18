"""
Sotrama setup — Algerian localization for ERPNext.

Optional setup helper for an ERPNext regional integration.

ERPNext v16 looks for country setup code under
``erpnext.regional.<country>.setup.setup``. This module is not discovered
automatically merely because it exists in a custom app. Sotrama's optional
Company extension is activated explicitly from Sotrama Settings.
"""

def setup(company, is_setup=True):
    """Keep regional setup non-invasive; Sotrama features require admin opt-in.

    ERPNext's standard regional setup remains authoritative for Company data.
    Optional Sotrama fields are enabled from Sotrama Settings after installation.
    """
