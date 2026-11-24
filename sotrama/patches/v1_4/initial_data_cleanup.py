"""Consolidate the pre-production 1.3.x upgrade path into one post-sync migration.

Fresh installs are marked patched by Frappe and use the normal install hooks.
This patch exists only for sites upgrading from the pre-production 1.3.x layout.
"""


def execute():
    from sotrama.migrations.company import (
        hide_managed_legacy_company_nif,
        migrate_legacy_company_nif,
    )
    from sotrama.migrations.fleet_documents import migrate_fleet_document_options
    from sotrama.migrations.fleet_master_names import normalize_fleet_master_names
    from sotrama.migrations.fleet_reference_masters import (
        simplify_fleet_reference_masters,
    )
    from sotrama.migrations.navigation import (
        remove_legacy_algerian_localization_workspace,
    )
    from sotrama.migrations.security import (
        migrate_driver_private_attachments,
        migrate_fleet_attachments_private,
        remediate_fleet_alert_todo_assignments,
    )
    from sotrama.permissions import remove_unsafe_fleet_docshares
    from sotrama.setup.masters import ensure_default_masters
    from sotrama.tp.doctype.vehicle_document.vehicle_document import (
        refresh_vehicle_document_statuses,
    )

    ensure_default_masters()
    migrate_fleet_document_options()
    simplify_fleet_reference_masters()
    remove_legacy_algerian_localization_workspace()
    normalize_fleet_master_names()

    # These security remediations must complete before the upgrade is considered successful.
    remove_unsafe_fleet_docshares()
    migrate_driver_private_attachments()
    migrate_fleet_attachments_private()
    remediate_fleet_alert_todo_assignments()

    # This is a one-off backfill for every Vehicle, including draft records.
    # The daily scheduler only processes submitted Vehicles, so it cannot
    # reliably recover a failed backfill; let the patch fail and retry instead.
    refresh_vehicle_document_statuses()

    # Do not swallow unexpected failures here: Frappe would otherwise mark this
    # one-off patch complete and the legacy Company migration could never be
    # retried through the normal upgrade path. Known ownership/data conflicts
    # are returned and logged by migrate_legacy_company_nif itself.
    migration_result = migrate_legacy_company_nif()
    hide_managed_legacy_company_nif(migration_result)
