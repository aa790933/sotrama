"""One-off security data migrations for pre-production Sotrama sites."""

import frappe
from frappe import _

from sotrama.permissions import (
    COMPANY_SCOPED_FLEET_DOCTYPES,
    DRIVER_FILE_PRIVACY_FIELD,
    FLEET_FILE_PRIVACY_FIELD,
    SOTRAMA_CHILD_TABLE_DOCTYPES,
    _clear_attached_file_field,
    _ensure_driver_file_privacy_field,
    _ensure_fleet_file_privacy_field,
    _is_remote_file,
    _redact_driver_attachment_comments,
    _remove_private_driver_file_shares,
    _secure_duplicate_driver_file_rows,
    _validate_driver_private_file_paths,
    is_driver_private_attachment,
    prevent_fleet_attachment_content_reuse,
    secure_duplicate_fleet_file_rows,
)
from sotrama.tp.scheduler.common import _user_for_role


def migrate_fleet_attachments_private():
    """Run Fleet File remediation with a narrowly scoped lifecycle bypass flag."""
    previous_flag = frappe.flags.get("in_fleet_attachment_migration")
    frappe.flags.in_fleet_attachment_migration = True
    try:
        _migrate_fleet_attachments_private()
    finally:
        frappe.flags.in_fleet_attachment_migration = previous_flag


def _migrate_fleet_attachments_private():
    """Make every existing Fleet attachment private before company scoping is relied on."""
    _ensure_fleet_file_privacy_field()
    attached_doctypes = sorted(
        COMPANY_SCOPED_FLEET_DOCTYPES | SOTRAMA_CHILD_TABLE_DOCTYPES
    )
    fleet_files = frappe.get_all(
        "File",
        filters={"attached_to_doctype": ["in", attached_doctypes]},
        fields=["name", "content_hash"],
        limit_page_length=0,
    )
    fleet_file_by_hash = {}

    for row in fleet_files:
        file_doc = frappe.get_doc("File", row.name)
        # Validate every existing hash group, including rows already marked
        # private, because those rows may never enter File.save/validate below.
        prevent_fleet_attachment_content_reuse(file_doc)
        if row.content_hash:
            fleet_file_by_hash.setdefault(row.content_hash, file_doc)
        if _is_remote_file(file_doc):
            attached_doctype = file_doc.attached_to_doctype
            attached_to_name = file_doc.attached_to_name
            _redact_driver_attachment_comments(
                attached_doctype, attached_to_name, file_doc
            )
            _clear_attached_file_field(file_doc)
            file_doc.attached_to_doctype = None
            file_doc.attached_to_name = None
            file_doc.attached_to_field = None
            file_doc.owner = "Administrator"
            setattr(file_doc, FLEET_FILE_PRIVACY_FIELD, 1)
            file_doc.is_private = 1
            file_doc.save(ignore_permissions=True)
            frappe.log_error(
                title="Remote Fleet attachment detached",
                message=(
                    f"File {file_doc.name} was a remote Fleet attachment and cannot be "
                    "secured by private site storage. It was detached; replace it with "
                    "a private upload."
                ),
            )
            continue
        if file_doc.is_private and (file_doc.file_url or "").startswith("/files/"):
            # Repair inconsistent legacy rows whose flag is private but whose
            # URL still points to public storage; validate() will not detect a
            # flag change because the database already says private.
            file_doc.handle_is_private_changed()
            setattr(file_doc, FLEET_FILE_PRIVACY_FIELD, 1)
            file_doc.save(ignore_permissions=True)
            continue
        if file_doc.is_private:
            if not file_doc.get(FLEET_FILE_PRIVACY_FIELD):
                setattr(file_doc, FLEET_FILE_PRIVACY_FIELD, 1)
                file_doc.save(ignore_permissions=True)
            continue
        setattr(file_doc, FLEET_FILE_PRIVACY_FIELD, 1)
        file_doc.is_private = 1
        file_doc.save(ignore_permissions=True)

    # File.handle_is_private_changed updates every File row sharing a content
    # hash. A duplicate attached to an unrelated, more widely readable parent
    # would otherwise become another permission path to the private Fleet blob.
    for file_doc in fleet_file_by_hash.values():
        secure_duplicate_fleet_file_rows(file_doc)


def migrate_driver_private_attachments():
    """Make legacy Driver HR/compliance files private during a one-off upgrade."""
    _ensure_driver_file_privacy_field()
    fields = ["name", "content_hash", "file_url", "is_private"]
    if frappe.db.has_column("File", "is_remote_file"):
        fields.append("is_remote_file")
    files_by_name = {
        row.name: row
        for row in frappe.get_all(
            "File",
            filters={
                "attached_to_doctype": ["in", ["Driver", "Driver Compliance Record"]],
            },
            fields=fields,
        )
    }
    if frappe.get_meta("File").has_field(DRIVER_FILE_PRIVACY_FIELD):
        for row in frappe.get_all(
            "File", filters={DRIVER_FILE_PRIVACY_FIELD: 1}, fields=fields
        ):
            files_by_name[row.name] = row
    content_hashes = {
        row.content_hash for row in files_by_name.values() if row.content_hash
    }
    if content_hashes:
        for row in frappe.get_all(
            "File",
            filters={"content_hash": ["in", sorted(content_hashes)]},
            fields=fields,
        ):
            files_by_name[row.name] = row
    files = list(files_by_name.values())
    _validate_driver_private_file_paths(files)
    for row in files:
        file_doc = frappe.get_doc("File", row.name)
        if not is_driver_private_attachment(file_doc):
            continue
        needs_save = (
            not file_doc.is_private
            or not file_doc.get(DRIVER_FILE_PRIVACY_FIELD)
            or (file_doc.file_url or "").startswith("/files/")
        )
        setattr(file_doc, DRIVER_FILE_PRIVACY_FIELD, 1)
        if _is_remote_file(file_doc):
            # A remote URL cannot be made private by Frappe. Detach it from docinfo;
            # the HR-only Driver field remains intact for HR to review/re-upload.
            attached_doctype = file_doc.attached_to_doctype
            attached_to_name = file_doc.attached_to_name
            _redact_driver_attachment_comments(attached_doctype, attached_to_name)
            file_doc.attached_to_doctype = None
            file_doc.attached_to_name = None
            file_doc.attached_to_field = None
            file_doc.is_private = 1
            file_doc.flags.allow_remote_driver_detach = True
            file_doc.save(ignore_permissions=True)
            _remove_private_driver_file_shares(file_doc.name)
            frappe.log_error(
                title="Remote Driver compliance attachment detached",
                message=(
                    f"File {file_doc.name} was a remote Driver HR/compliance attachment. "
                    "It was detached from the attachment list; HR must replace it with a private upload."
                ),
            )
            _secure_duplicate_driver_file_rows(file_doc)
            continue
        if needs_save:
            file_doc.is_private = 1
            file_doc.save(ignore_permissions=True)
        _secure_duplicate_driver_file_rows(file_doc)
        _remove_private_driver_file_shares(file_doc.name)


def remediate_fleet_alert_todo_assignments():
    """Sanitize and reassign legacy alerts created before Company-aware routing."""
    todos = frappe.get_all(
        "ToDo",
        filters=[],
        or_filters=[
            ["ToDo", "description", "like", "Vehicle Document Expiring:%"],
            ["ToDo", "description", "like", "Expiration d'un document du véhicule :%"],
            ["ToDo", "description", "like", "Document '% expires on %"],
            ["ToDo", "description", "like", "%du véhicule%expire le%"],
            ["ToDo", "description", "like", "Maintenance Due:%"],
            ["ToDo", "description", "like", "Maintenance à effectuer :%"],
            [
                "ToDo",
                "description",
                "like",
                "Scheduled maintenance for vehicle % is due:%",
            ],
            ["ToDo", "description", "like", "%La maintenance planifiée du véhicule%"],
            ["ToDo", "description", "like", "Driver License Expiring:%"],
            ["ToDo", "description", "like", "Expiration du permis du conducteur :%"],
            ["ToDo", "description", "like", "% license expires on %"],
            ["ToDo", "description", "like", "%Le permis du conducteur%expire le%"],
            ["ToDo", "description", "like", "Safety Training Expiring:%"],
            ["ToDo", "description", "like", "Expiration de la formation sécurité :%"],
            ["ToDo", "description", "like", "% safety training expires on %"],
            [
                "ToDo",
                "description",
                "like",
                "%La formation sécurité du conducteur%expire le%",
            ],
            ["ToDo", "description", "like", "%Restricted Driver Compliance Review%"],
            [
                "ToDo",
                "description",
                "like",
                "%Contrôle restreint de conformité du conducteur%",
            ],
            [
                "ToDo",
                "description",
                "like",
                "%restricted professional-driver compliance records%",
            ],
            [
                "ToDo",
                "description",
                "like",
                "%dossiers de conformité professionnelle à accès restreint%",
            ],
        ],
        fields=[
            "name",
            "description",
            "reference_type",
            "reference_name",
            "allocated_to",
        ],
        limit_page_length=0,
    )
    driver_names = {
        todo.reference_name
        for todo in todos
        if todo.reference_type == "Driver" and todo.reference_name
    }
    drivers = (
        frappe.get_all(
            "Driver",
            filters={"name": ["in", sorted(driver_names)]},
            fields=["name", "driver_name", "license_expiry", "safety_training_expiry"],
            limit_page_length=0,
        )
        if driver_names
        else []
    )
    drivers_by_name = {driver.name: driver for driver in drivers}
    role_users_cache = {}
    for todo in todos:
        description = todo.description or ""
        reference_type = todo.reference_type
        reference_name = todo.reference_name
        allocated_to = "Administrator"
        updates = {}

        lowered_description = description.lower()
        if (
            lowered_description.startswith(
                ("vehicle document expiring:", "expiration d'un document du véhicule :")
            )
            or "document '" in lowered_description
            or "du véhicule" in lowered_description
            and "expire le" in lowered_description
        ) and reference_type == "Vehicle":
            allocated_to = _user_for_role(
                "Fleet Manager",
                "Vehicle",
                reference_name,
                role_users_cache=role_users_cache,
            )
        elif (
            lowered_description.startswith(
                (
                    "maintenance due:",
                    "scheduled maintenance for vehicle ",
                    "maintenance à effectuer :",
                    "la maintenance planifiée du véhicule ",
                )
            )
        ) and reference_type == "Maintenance Schedule":
            allocated_to = _user_for_role(
                "Fleet Manager",
                "Maintenance Schedule",
                reference_name,
                role_users_cache=role_users_cache,
            )
        elif (
            lowered_description.startswith(
                ("driver license expiring:", "expiration du permis du conducteur :")
            )
            or " license expires on " in lowered_description
            or "le permis du conducteur" in lowered_description
        ) and reference_type == "Driver":
            allocated_to = _user_for_role(
                "Fleet Manager",
                "Driver",
                reference_name,
                role_users_cache=role_users_cache,
            )
            driver = drivers_by_name.get(reference_name)
            updates["description"] = (
                _("Driver {0} license expires on {1}.").format(
                    driver.driver_name, driver.license_expiry
                )
                if driver
                else _("The referenced Driver record is unavailable; contact HR.")
            )
        elif (
            lowered_description.startswith(
                ("safety training expiring:", "expiration de la formation sécurité :")
            )
            or " safety training expires on " in lowered_description
            or "la formation sécurité du conducteur" in lowered_description
        ) and reference_type == "Driver":
            allocated_to = _user_for_role(
                "HR Manager",
                "Driver",
                reference_name,
                role_users_cache=role_users_cache,
            )
            driver = drivers_by_name.get(reference_name)
            updates["description"] = (
                _("Driver {0} safety training expires on {1}.").format(
                    driver.driver_name, driver.safety_training_expiry
                )
                if driver
                else _("The referenced Driver record is unavailable; contact HR.")
            )
        elif (
            lowered_description.startswith(
                (
                    "restricted driver compliance review",
                    "contrôle restreint de conformité du conducteur",
                )
            )
            or "restricted professional-driver compliance records"
            in lowered_description
            or "dossiers de conformité professionnelle à accès restreint"
            in lowered_description
        ) and reference_type == "Driver":
            allocated_to = _user_for_role(
                "HR Manager",
                "Driver",
                reference_name,
                role_users_cache=role_users_cache,
            )
            updates["description"] = _(
                "Review the restricted professional-driver compliance records. "
                "This task intentionally contains no medical result or date."
            )
        else:
            continue

        if todo.allocated_to != allocated_to:
            updates["allocated_to"] = allocated_to
        if updates:
            frappe.db.set_value("ToDo", todo.name, updates, update_modified=False)
