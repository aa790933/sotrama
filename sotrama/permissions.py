"""App-level access checks for the Sotrama Desk application."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

APP_ROLES = {
    "System Manager",
    "Fleet Manager",
    "Workshop",
    "HR Manager",
    "Accounts Manager",
}

HR_FILE_ROLES = {"System Manager", "HR Manager"}
COMPANY_SCOPED_FLEET_DOCTYPES = {
    "Vehicle",
    "Driver",
    "Vehicle Inspection",
    "Breakdown Incident",
    "Operational Task",
    "Maintenance Schedule",
    "Maintenance Job Card",
    "Company Classification",
}
COMPANY_SCOPED_FLEET_CHILD_TABLES = {
    "Vehicle Document": ("Vehicle", "vehicle_documents"),
    "Inspection Item": ("Vehicle Inspection", "inspection_items"),
    "Job Card Labour": ("Maintenance Job Card", "labour"),
    "Job Card Other Cost": ("Maintenance Job Card", "other_costs"),
    "Job Card Part": ("Maintenance Job Card", "parts"),
    "Job Card Photo": ("Maintenance Job Card", "photos"),
    "Breakdown Photo": ("Breakdown Incident", "photos"),
}
SOTRAMA_CHILD_TABLE_DOCTYPES = set(COMPANY_SCOPED_FLEET_CHILD_TABLES) | {
    "Driver Compliance Record",
    "TP Company Defaults",
}
DRIVER_FILE_PRIVACY_FIELD = "sotrama_private_driver_attachment"
DRIVER_FILE_PRIVACY_MARKER = "Managed by Sotrama — Driver Attachment Privacy."
FLEET_FILE_PRIVACY_FIELD = "sotrama_private_fleet_attachment"
FLEET_FILE_PRIVACY_MARKER = "Managed by Sotrama — Fleet Attachment Privacy."
PRIVATE_DRIVER_ATTACHMENT_DOCTYPES = {"Driver", "Driver Compliance Record"}


def _ensure_file_privacy_field(fieldname, label, marker, insert_after, purpose):
    existing = frappe.db.get_value(
        "Custom Field",
        {"dt": "File", "fieldname": fieldname},
        ["name", "fieldtype", "module", "is_system_generated", "description"],
        as_dict=True,
    )
    if existing:
        owned = (
            existing.fieldtype == "Check"
            and existing.is_system_generated
            and existing.module in ("Sotrama", "Custom")
            and marker in (existing.description or "")
        )
        if not owned:
            frappe.throw(
                frappe._(
                    "File field {0} already exists but is not owned by Sotrama. {1}"
                ).format(fieldname, purpose)
            )
    else:
        create_custom_fields(
            {
                "File": [
                    {
                        "fieldname": fieldname,
                        "fieldtype": "Check",
                        "label": label,
                        "module": "Custom",
                        "insert_after": insert_after,
                        "default": "0",
                        "hidden": 1,
                        "read_only": 1,
                        "no_copy": 1,
                        "description": marker,
                    }
                ]
            },
            update=False,
        )
    frappe.clear_cache(doctype="File")


def _ensure_driver_file_privacy_field():
    _ensure_file_privacy_field(
        DRIVER_FILE_PRIVACY_FIELD,
        "Sotrama Private Driver Attachment",
        DRIVER_FILE_PRIVACY_MARKER,
        "attached_to_field",
        frappe._(
            "Resolve the field ownership conflict before migrating Driver attachments."
        ),
    )


def _ensure_fleet_file_privacy_field():
    """Provision the persistent provenance marker used by Fleet File security."""
    _ensure_file_privacy_field(
        FLEET_FILE_PRIVACY_FIELD,
        "Sotrama Private Fleet Attachment",
        FLEET_FILE_PRIVACY_MARKER,
        DRIVER_FILE_PRIVACY_FIELD,
        frappe._(
            "Resolve the field ownership conflict before migrating Fleet attachments."
        ),
    )


def is_driver_private_attachment(file_doc):
    """Identify Driver evidence and every File row sharing its content hash."""
    if not file_doc:
        return False
    if file_doc.get(DRIVER_FILE_PRIVACY_FIELD):
        return True

    attached_doctype = file_doc.get("attached_to_doctype")

    if attached_doctype == "Driver":
        return True

    if attached_doctype == "Driver Compliance Record":
        return True

    content_hash = file_doc.get("content_hash")
    if not content_hash:
        return False
    filters = {"content_hash": content_hash}
    if frappe.get_meta("File").has_field(
        DRIVER_FILE_PRIVACY_FIELD
    ) and frappe.db.exists("File", {**filters, DRIVER_FILE_PRIVACY_FIELD: 1}):
        return True
    return bool(
        frappe.db.exists(
            "File",
            {
                **filters,
                "attached_to_doctype": [
                    "in",
                    sorted(PRIVATE_DRIVER_ATTACHMENT_DOCTYPES),
                ],
            },
        )
    )


def is_direct_company_scoped_fleet_attachment(file_doc):
    """Identify a File directly attached to a protected Fleet parent or child row."""
    if not file_doc:
        return False
    attached_doctype = file_doc.get("attached_to_doctype")
    attached_name = file_doc.get("attached_to_name")
    if not attached_doctype or not attached_name:
        return False
    return (
        attached_doctype in COMPANY_SCOPED_FLEET_DOCTYPES
        or attached_doctype in SOTRAMA_CHILD_TABLE_DOCTYPES
    )


def is_company_scoped_fleet_attachment(file_doc):
    """Identify direct Fleet attachments and duplicate File rows sharing their content."""
    if is_direct_company_scoped_fleet_attachment(file_doc):
        return True
    has_fleet_marker = frappe.get_meta("File").has_field(FLEET_FILE_PRIVACY_FIELD)
    if has_fleet_marker and file_doc and file_doc.get(FLEET_FILE_PRIVACY_FIELD):
        return True
    content_hash = file_doc.get("content_hash") if file_doc else None
    if not content_hash:
        return False
    attached_doctypes = sorted(
        COMPANY_SCOPED_FLEET_DOCTYPES | SOTRAMA_CHILD_TABLE_DOCTYPES
    )
    return bool(
        (
            has_fleet_marker
            and frappe.db.exists(
                "File",
                {
                    "content_hash": content_hash,
                    FLEET_FILE_PRIVACY_FIELD: 1,
                },
            )
        )
        or frappe.db.exists(
            "File",
            {
                "content_hash": content_hash,
                "attached_to_doctype": ["in", attached_doctypes],
            },
        )
    )


def _get_file_attachment_company(file_doc):
    """Resolve the Company owning a protected File attachment, including child rows."""
    doctype = file_doc.get("attached_to_doctype")
    name = file_doc.get("attached_to_name")
    if not doctype or not name:
        return None

    meta = frappe.get_meta(doctype)
    if doctype in SOTRAMA_CHILD_TABLE_DOCTYPES:
        fields = ["parenttype", "parent"]
        if meta.has_field("company"):
            fields.append("company")
        child = frappe.db.get_value(doctype, name, fields, as_dict=True)
        if not child:
            return None
        if child.get("company"):
            return child.company
        parent_doctype = child.get("parenttype")
        parent_name = child.get("parent")
        if not parent_doctype or not parent_name:
            return None
        parent_meta = frappe.get_meta(parent_doctype)
        if not parent_meta.has_field("company"):
            return None
        return frappe.db.get_value(parent_doctype, parent_name, "company")

    if not meta.has_field("company"):
        return None
    return frappe.db.get_value(doctype, name, "company")


def _prevent_cross_company_file_reuse(file_doc, content_hash):
    """Protect private Fleet sources from cross-company and owner-shortcut reuse."""
    file_url = file_doc.get("file_url") or ""
    get_previous = getattr(file_doc, "get_doc_before_save", None)
    previous = get_previous() if get_previous else None
    file_url_changed = bool(previous and previous.get("file_url") != file_url)
    _is_new = getattr(file_doc, "is_new", None)
    is_new_file = _is_new() if callable(_is_new) else False
    if not content_hash and not file_url.startswith(("/files/", "/private/files/")):
        return

    protected_doctypes = COMPANY_SCOPED_FLEET_DOCTYPES | SOTRAMA_CHILD_TABLE_DOCTYPES
    fields = ["name", "attached_to_doctype", "attached_to_name", "is_private"]
    file_meta = frappe.get_meta("File")
    if file_meta.has_field(FLEET_FILE_PRIVACY_FIELD):
        fields.append(FLEET_FILE_PRIVACY_FIELD)
    if file_meta.has_field(DRIVER_FILE_PRIVACY_FIELD):
        fields.append(DRIVER_FILE_PRIVACY_FIELD)

    duplicate_rows = {}
    url_matches = []
    filters = {"name": ["!=", file_doc.name]}
    if content_hash:
        duplicate_rows.update(
            {
                row.name: row
                for row in frappe.get_all(
                    "File",
                    filters={**filters, "content_hash": content_hash},
                    fields=fields + ["file_url"],
                    limit_page_length=0,
                )
            }
        )
    if file_url:
        url_matches = frappe.get_all(
            "File",
            filters={**filters, "file_url": file_url},
            fields=fields + ["file_url"],
            limit_page_length=0,
        )
        duplicate_rows.update({row.name: row for row in url_matches})
    duplicates = list(duplicate_rows.values())
    if not duplicates:
        if (
            file_url.startswith("/private/files/")
            and _get_file_attachment_company(file_doc)
            and (is_new_file or file_url_changed)
        ):
            user = frappe.session.user
            if user != "Administrator" and "System Manager" not in frappe.get_roles(
                user
            ):
                frappe.throw(
                    frappe._(
                        "A private Fleet file URL must reference an existing File record. Upload the file or use its authorized attachment instead."
                    ),
                    frappe.PermissionError,
                )
        return

    target_company = _get_file_attachment_company(file_doc)
    target_doctype = file_doc.get("attached_to_doctype")
    target_name = file_doc.get("attached_to_name")
    target_is_driver = target_doctype in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES
    for duplicate in duplicates:
        is_protected = duplicate.attached_to_doctype in protected_doctypes or bool(
            duplicate.get(FLEET_FILE_PRIVACY_FIELD)
            or duplicate.get(DRIVER_FILE_PRIVACY_FIELD)
        )
        if not is_protected:
            continue
        duplicate_is_driver = (
            duplicate.attached_to_doctype in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES
            or bool(duplicate.get(DRIVER_FILE_PRIVACY_FIELD))
        )
        if (
            target_doctype in protected_doctypes
            and target_is_driver != duplicate_is_driver
        ):
            frappe.throw(
                frappe._(
                    "File content cannot be reused between Driver HR evidence and general Fleet attachments."
                ),
                frappe.PermissionError,
            )
        same_parent = (
            duplicate.attached_to_doctype == target_doctype
            and duplicate.attached_to_name == target_name
        )
        if not same_parent:
            duplicate_company = _get_file_attachment_company(duplicate)
            if (
                not target_company
                or not duplicate_company
                or target_company != duplicate_company
            ):
                frappe.throw(
                    frappe._(
                        "Private Fleet attachment content cannot be reused across Companies or from a detached Fleet file."
                    ),
                    frappe.PermissionError,
                )
        if file_url and duplicate.file_url == file_url and duplicate.get("is_private"):
            user = frappe.session.user
            if duplicate.attached_to_doctype in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES:
                source_access = can_access_driver_private_attachment(
                    duplicate, user, ptype="read"
                )
            else:
                source_access = can_access_company_scoped_fleet_attachment(
                    duplicate, user, ptype="read"
                )
            if not source_access:
                frappe.throw(
                    frappe._(
                        "You must retain read access to the original parent before reusing its private attachment."
                    ),
                    frappe.PermissionError,
                )
    if (
        file_url.startswith("/private/files/")
        and not url_matches
        and _get_file_attachment_company(file_doc)
        and (is_new_file or file_url_changed)
    ):
        user = frappe.session.user
        if user != "Administrator" and "System Manager" not in frappe.get_roles(user):
            frappe.throw(
                frappe._(
                    "A private Fleet file URL must reference an existing File record. Upload the file or use its authorized attachment instead."
                ),
                frappe.PermissionError,
            )


def prevent_fleet_attachment_content_reuse(file_doc, content=None):
    """Prevent private Fleet file bytes being reattached through an unrelated parent."""
    content_hash = file_doc.get("content_hash")
    if content is not None:
        from frappe.core.doctype.file.utils import get_content_hash

        content_hash = get_content_hash(content)
    file_url = file_doc.get("file_url") or ""
    if not content_hash and not file_url.startswith(("/files/", "/private/files/")):
        return

    attached_doctype = file_doc.get("attached_to_doctype")
    target_is_driver = attached_doctype in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES
    is_direct_fleet_attachment = is_direct_company_scoped_fleet_attachment(file_doc)
    _prevent_cross_company_file_reuse(file_doc, content_hash)
    if not content_hash:
        return
    has_driver_marker = frappe.get_meta("File").has_field(DRIVER_FILE_PRIVACY_FIELD)
    has_fleet_marker = frappe.get_meta("File").has_field(FLEET_FILE_PRIVACY_FIELD)
    exclude_self = {"name": ["!=", file_doc.name]} if file_doc.get("name") else {}

    if is_direct_fleet_attachment:
        if target_is_driver:
            non_driver_fleet_doctypes = sorted(
                (COMPANY_SCOPED_FLEET_DOCTYPES | SOTRAMA_CHILD_TABLE_DOCTYPES)
                - PRIVATE_DRIVER_ATTACHMENT_DOCTYPES
            )
            crosses_scope = frappe.db.exists(
                "File",
                {
                    **exclude_self,
                    "content_hash": content_hash,
                    "attached_to_doctype": ["in", non_driver_fleet_doctypes],
                },
            )
            if has_fleet_marker and has_driver_marker:
                crosses_scope = crosses_scope or frappe.db.exists(
                    "File",
                    {
                        **exclude_self,
                        "content_hash": content_hash,
                        FLEET_FILE_PRIVACY_FIELD: 1,
                        DRIVER_FILE_PRIVACY_FIELD: 0,
                    },
                )
            if (
                has_fleet_marker
                and file_doc.get(FLEET_FILE_PRIVACY_FIELD)
                and has_driver_marker
                and not file_doc.get(DRIVER_FILE_PRIVACY_FIELD)
            ):
                crosses_scope = True
        else:
            crosses_scope = (
                bool(has_driver_marker and file_doc.get(DRIVER_FILE_PRIVACY_FIELD))
                or (
                    has_driver_marker
                    and frappe.db.exists(
                        "File",
                        {
                            **exclude_self,
                            "content_hash": content_hash,
                            DRIVER_FILE_PRIVACY_FIELD: 1,
                        },
                    )
                )
                or frappe.db.exists(
                    "File",
                    {
                        **exclude_self,
                        "content_hash": content_hash,
                        "attached_to_doctype": [
                            "in",
                            sorted(PRIVATE_DRIVER_ATTACHMENT_DOCTYPES),
                        ],
                    },
                )
            )
        if crosses_scope:
            frappe.throw(
                frappe._(
                    "File content cannot be reused between Driver HR evidence and general Fleet attachments."
                ),
                frappe.PermissionError,
            )
        return

    attached_doctypes = sorted(
        COMPANY_SCOPED_FLEET_DOCTYPES | SOTRAMA_CHILD_TABLE_DOCTYPES
    )
    if (
        (has_fleet_marker and file_doc.get(FLEET_FILE_PRIVACY_FIELD))
        or (has_driver_marker and file_doc.get(DRIVER_FILE_PRIVACY_FIELD))
        or (
            has_fleet_marker
            and frappe.db.exists(
                "File",
                {
                    **exclude_self,
                    "content_hash": content_hash,
                    FLEET_FILE_PRIVACY_FIELD: 1,
                },
            )
        )
        or frappe.db.exists(
            "File",
            {
                **exclude_self,
                "content_hash": content_hash,
                "attached_to_doctype": ["in", attached_doctypes],
            },
        )
    ):
        frappe.throw(
            frappe._(
                "This file content is already attached to a company-scoped Fleet record and cannot be reused on an unrelated document."
            ),
            frappe.PermissionError,
        )


def secure_duplicate_fleet_file_rows(file_doc):
    """Detach unrelated File rows that Frappe's content-hash lifecycle also privatized."""
    content_hash = file_doc.get("content_hash")
    if not content_hash:
        return False

    attached_doctypes = sorted(
        COMPANY_SCOPED_FLEET_DOCTYPES | SOTRAMA_CHILD_TABLE_DOCTYPES
    )
    duplicates = frappe.get_all(
        "File",
        filters={
            "content_hash": content_hash,
            "name": ["!=", file_doc.name],
        },
        fields=["name", "attached_to_doctype"],
        limit_page_length=0,
    )
    changed = False
    for row in duplicates:
        if row.attached_to_doctype in attached_doctypes:
            continue

        duplicate = frappe.get_doc("File", row.name)
        if (
            not duplicate.attached_to_doctype
            and duplicate.owner == "Administrator"
            and duplicate.is_private
            and duplicate.get(FLEET_FILE_PRIVACY_FIELD)
            and not (duplicate.file_url or "").startswith("/files/")
        ):
            continue

        _redact_driver_attachment_comments(
            duplicate.attached_to_doctype,
            duplicate.attached_to_name,
            duplicate,
        )
        _clear_attached_file_field(duplicate)
        duplicate.attached_to_doctype = None
        duplicate.attached_to_name = None
        duplicate.attached_to_field = None
        duplicate.owner = "Administrator"
        setattr(duplicate, FLEET_FILE_PRIVACY_FIELD, 1)

        if duplicate.is_private and (duplicate.file_url or "").startswith("/files/"):
            duplicate.handle_is_private_changed()
        duplicate.is_private = 1
        duplicate.save(ignore_permissions=True)
        _remove_private_driver_file_shares(duplicate.name)
        frappe.log_error(
            title="Duplicate Fleet attachment detached",
            message=(
                f"File {duplicate.name} shared content with a company-scoped Fleet attachment "
                "but was attached to an unrelated document. It was detached and made "
                "Administrator-owned to prevent an alternate access path."
            ),
        )
        changed = True
    return changed


def secure_company_scoped_fleet_attachment(doc, method=None):
    """Keep Fleet attachments private so public URLs cannot bypass company scope."""
    get_previous = getattr(doc, "get_doc_before_save", None)
    previous = get_previous() if get_previous else None
    current_is_direct = is_direct_company_scoped_fleet_attachment(doc)
    previous_was_direct = is_direct_company_scoped_fleet_attachment(previous)
    migration = frappe.flags.get("in_fleet_attachment_migration")

    protected = (
        current_is_direct
        or previous_was_direct
        or bool(doc.get(FLEET_FILE_PRIVACY_FIELD))
        or bool(previous and previous.get(FLEET_FILE_PRIVACY_FIELD))
        or is_company_scoped_fleet_attachment(doc)
    )
    if not protected:
        return
    if not migration and _is_remote_file(doc):
        frappe.throw(
            frappe._(
                "Remote URLs cannot be attached to company-scoped Fleet records. Upload a private file instead."
            ),
            frappe.ValidationError,
        )
    if (
        not migration
        and current_is_direct
        and previous
        and previous.get(FLEET_FILE_PRIVACY_FIELD)
        and not previous_was_direct
        and (
            previous.get("attached_to_doctype") != doc.get("attached_to_doctype")
            or previous.get("attached_to_name") != doc.get("attached_to_name")
        )
    ):
        user = frappe.session.user
        if user != "Administrator" and "System Manager" not in frappe.get_roles(user):
            frappe.throw(
                frappe._(
                    "A detached or unrelated Fleet-protected file can only be reattached by Administrator or System Manager."
                ),
                frappe.PermissionError,
            )
    attachment_changed = bool(
        previous
        and (
            previous.get("attached_to_doctype") != doc.get("attached_to_doctype")
            or previous.get("attached_to_name") != doc.get("attached_to_name")
        )
    )
    if (
        not migration
        and previous_was_direct
        and current_is_direct
        and attachment_changed
    ):
        user = frappe.session.user
        roles = set(frappe.get_roles(user)) if user != "Administrator" else set()
        if user != "Administrator" and "System Manager" not in roles:
            previous_company = _get_file_attachment_company(previous)
            current_company = _get_file_attachment_company(doc)
            if (
                not previous_company
                or not current_company
                or previous_company != current_company
            ):
                frappe.throw(
                    frappe._(
                        "Only Administrator or System Manager can move a protected Fleet attachment between Companies."
                    ),
                    frappe.PermissionError,
                )
            if not can_access_company_scoped_fleet_attachment(
                previous, user, ptype="write"
            ):
                frappe.throw(
                    frappe._(
                        "You need write access to the original Fleet parent before moving its attachment."
                    ),
                    frappe.PermissionError,
                )
    if current_is_direct:
        prevent_fleet_attachment_content_reuse(doc)
    if (
        not migration
        and not current_is_direct
        and not previous_was_direct
        and doc.get("attached_to_doctype")
    ):
        frappe.throw(
            frappe._(
                "A duplicate of private Fleet attachment content cannot be attached to an unrelated document."
            ),
            frappe.PermissionError,
        )
    if not migration and previous_was_direct and not current_is_direct:
        previous_attachment = frappe._dict(
            attached_to_doctype=previous.attached_to_doctype,
            attached_to_name=previous.attached_to_name,
            attached_to_field=previous.attached_to_field,
            file_url=doc.get("file_url"),
            file_name=doc.get("file_name"),
        )
        _redact_driver_attachment_comments(
            previous.attached_to_doctype, previous.attached_to_name, doc
        )
        _clear_attached_file_field(previous_attachment)
        doc.attached_to_doctype = None
        doc.attached_to_name = None
        doc.attached_to_field = None
        doc.owner = "Administrator"
    setattr(doc, FLEET_FILE_PRIVACY_FIELD, 1)
    doc.is_private = 1


def sotrama_child_table_query_conditions(user=None, doctype=None):
    """Prevent list/report APIs from querying child rows without a parent document."""
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return None
    return "1=0"


def _is_remote_file(file_doc):
    """Detect remote File links across Frappe versions with different File schemas."""
    if file_doc.get("is_remote_file"):
        return True
    file_url = file_doc.get("file_url") or ""
    return file_url.startswith(("http://", "https://", "/api/method/"))


def _can_read_driver_attachment_parent(doctype, name, user=None):
    """Check the parent Driver's read permission, including Company User Permissions."""
    if doctype == "Driver":
        driver_name = name
    elif doctype == "Driver Compliance Record":
        driver_name = frappe.db.get_value("Driver Compliance Record", name, "parent")
    else:
        return False
    if not driver_name:
        return False
    return bool(
        frappe.has_permission(
            "Driver",
            "read",
            doc=driver_name,
            user=user,
            ignore_share_permissions=True,
        )
    )


def can_access_driver_private_attachment(file_doc, user=None, ptype=None):
    """Require HR role and the matching parent permission for private file actions."""
    user = user or frappe.session.user
    if not _has_hr_file_access(user):
        return False
    if user == "Administrator":
        return True
    if file_doc.get("is_remote_file"):
        return False
    attached_doctype = file_doc.get("attached_to_doctype")
    attached_name = file_doc.get("attached_to_name")
    if attached_doctype == "Driver":
        driver_name = attached_name
    elif attached_doctype == "Driver Compliance Record":
        driver_name = frappe.db.get_value(
            "Driver Compliance Record", attached_name, "parent"
        )
    else:
        # Detached duplicates and copies on unrelated doctypes are Administrator-only.
        return False
    roles = set(frappe.get_roles(user))
    if ptype == "share" and "System Manager" not in roles:
        return False
    permission_type = "write" if ptype in {"write", "create", "delete"} else "read"
    return bool(
        driver_name
        and frappe.has_permission(
            "Driver",
            permission_type,
            doc=driver_name,
            user=user,
            ignore_share_permissions=True,
        )
    )


def can_access_company_scoped_fleet_attachment(file_doc, user=None, ptype=None):
    """Require the exact Fleet parent permission; File ownership/shares are insufficient."""
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    if ptype == "share" or not is_direct_company_scoped_fleet_attachment(file_doc):
        return False
    attached_doctype = file_doc.get("attached_to_doctype")
    attached_name = file_doc.get("attached_to_name")
    if not attached_doctype or not attached_name:
        return False
    required_permission = "write" if ptype in {"write", "create", "delete"} else "read"
    if attached_doctype in SOTRAMA_CHILD_TABLE_DOCTYPES:
        if not frappe.has_permission(
            attached_doctype,
            required_permission,
            doc=attached_name,
            user=user,
        ):
            return False
        parent = frappe.db.get_value(
            attached_doctype,
            attached_name,
            ["parenttype", "parent"],
            as_dict=True,
        )
        if not parent or not parent.parenttype or not parent.parent:
            return False
        return bool(
            frappe.has_permission(
                parent.parenttype,
                required_permission,
                doc=parent.parent,
                user=user,
                ignore_share_permissions=True,
            )
        )
    return bool(
        frappe.has_permission(
            attached_doctype,
            required_permission,
            doc=attached_name,
            user=user,
            ignore_share_permissions=True,
        )
    )


def file_has_permission(doc, user=None, ptype=None, debug=False):
    """Enforce Driver HR privacy and block unrelated duplicates of private Fleet files.

    Frappe v16.60.2's form docinfo returns all attachments for a readable parent,
    independent of field-level permissions. This controller permission closes the
    File download/read path even when a file was previously made public.
    """
    if not doc:
        return True
    if is_driver_private_attachment(doc):
        return can_access_driver_private_attachment(doc, user, ptype)
    if is_company_scoped_fleet_attachment(doc):
        if not is_direct_company_scoped_fleet_attachment(doc):
            return (user or frappe.session.user) == "Administrator"
        return can_access_company_scoped_fleet_attachment(doc, user, ptype)
    return True


def _has_hr_file_access(user=None):
    user = user or frappe.session.user
    if user == "Administrator":
        return True
    return bool(HR_FILE_ROLES.intersection(frappe.get_roles(user)))


def _require_driver_private_file_write_access(file_doc, user=None):
    """Require HR and parent Driver write access before creating or changing evidence."""
    user = user or frappe.session.user
    roles = set(frappe.get_roles(user)) if user != "Administrator" else set()
    if user == "Administrator" or "System Manager" in roles:
        return
    if not _has_hr_file_access(user):
        frappe.throw(
            frappe._("Only HR may create or modify Driver compliance attachments."),
            frappe.PermissionError,
        )

    attached_doctype = file_doc.get("attached_to_doctype")
    attached_name = file_doc.get("attached_to_name")
    if attached_doctype == "Driver":
        driver_name = attached_name
    elif attached_doctype == "Driver Compliance Record":
        driver_name = frappe.db.get_value(
            "Driver Compliance Record", attached_name, "parent"
        )
    elif attached_doctype:
        frappe.throw(
            frappe._(
                "Driver compliance attachments cannot be attached to unrelated records."
            ),
            frappe.PermissionError,
        )
    else:
        if can_access_driver_private_attachment(file_doc, user, ptype="write"):
            return
        frappe.throw(
            frappe._(
                "You need write access to an owning Driver record to modify this file."
            ),
            frappe.PermissionError,
        )
        return

    if not driver_name or not frappe.has_permission(
        "Driver",
        "write",
        doc=driver_name,
        user=user,
        ignore_share_permissions=True,
    ):
        frappe.throw(
            frappe._(
                "You need Company-scoped write access to the owning Driver record."
            ),
            frappe.PermissionError,
        )


def _clear_attached_file_field(file_doc):
    """Remove a stale Attach-field URL when a duplicate is detached for privacy."""
    doctype = file_doc.get("attached_to_doctype")
    name = file_doc.get("attached_to_name")
    fieldname = file_doc.get("attached_to_field")
    file_url = file_doc.get("file_url") or ""
    if not (doctype and name and fieldname and file_url):
        return
    meta = frappe.get_meta(doctype)
    if not meta.has_field(fieldname):
        return

    current = (
        frappe.db.get_single_value(doctype, fieldname)
        if meta.issingle
        else frappe.db.get_value(doctype, name, fieldname)
    )
    file_name = file_url.rsplit("/", 1)[-1]
    if current and (
        current == file_url
        or current.endswith((f"/files/{file_name}", f"/private/files/{file_name}"))
    ):
        if meta.issingle:
            frappe.db.set_single_value(doctype, fieldname, None)
        else:
            frappe.db.set_value(doctype, name, fieldname, None, update_modified=False)


def _update_attached_file_field(file_doc):
    """Keep HR-only Driver Attach fields aligned when a duplicate URL is moved."""
    doctype = file_doc.get("attached_to_doctype")
    name = file_doc.get("attached_to_name")
    fieldname = file_doc.get("attached_to_field")
    file_url = file_doc.get("file_url") or ""
    if not (doctype and name and fieldname and file_url):
        return
    meta = frappe.get_meta(doctype)
    if not meta.has_field(fieldname):
        return

    current = (
        frappe.db.get_single_value(doctype, fieldname)
        if meta.issingle
        else frappe.db.get_value(doctype, name, fieldname)
    )
    file_name = file_url.rsplit("/", 1)[-1]
    if (
        current
        and (
            current == file_url
            or current.endswith((f"/files/{file_name}", f"/private/files/{file_name}"))
        )
        and current != file_url
    ):
        if meta.issingle:
            frappe.db.set_single_value(doctype, fieldname, file_url)
        else:
            frappe.db.set_value(
                doctype, name, fieldname, file_url, update_modified=False
            )


def _remove_private_driver_file_shares(file_name):
    """Remove existing DocShares when a File becomes private Driver evidence."""
    if not file_name:
        return
    for share in frappe.get_all(
        "DocShare",
        filters={"share_doctype": "File", "share_name": file_name},
        fields=["name"],
    ):
        frappe.db.delete("DocShare", {"name": share.name})


def _secure_duplicate_driver_file_rows(file_doc):
    """Propagate private storage and the marker to every File row sharing content."""
    content_hash = file_doc.get("content_hash")
    if not content_hash or frappe.flags.get("in_driver_private_file_duplicate_sync"):
        return

    rows = frappe.get_all(
        "File",
        filters={"content_hash": content_hash},
        fields=["name", "is_private", "file_url"],
    )
    previous_flag = frappe.flags.get("in_driver_private_file_duplicate_sync")
    frappe.flags.in_driver_private_file_duplicate_sync = True
    try:
        for row in rows:
            if row.name == file_doc.name:
                continue
            duplicate = frappe.get_doc("File", row.name)
            setattr(duplicate, DRIVER_FILE_PRIVACY_FIELD, 1)

            if _is_remote_file(duplicate):
                if (
                    duplicate.attached_to_doctype
                    not in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES
                ):
                    _clear_attached_file_field(duplicate)
                _redact_driver_attachment_comments(
                    duplicate.attached_to_doctype,
                    duplicate.attached_to_name,
                    duplicate,
                )
                duplicate.attached_to_doctype = None
                duplicate.attached_to_name = None
                duplicate.attached_to_field = None
                duplicate.owner = "Administrator"
                duplicate.is_private = 1
                duplicate.flags.allow_remote_driver_detach = True
                duplicate.save(ignore_permissions=True)
                _remove_private_driver_file_shares(duplicate.name)
                continue

            needs_save = not duplicate.is_private or (
                duplicate.file_url or ""
            ).startswith("/files/")
            if not duplicate.is_private:
                duplicate.is_private = 1
            elif (duplicate.file_url or "").startswith("/files/"):
                duplicate.handle_is_private_changed()

            if needs_save:
                duplicate.save(ignore_permissions=True)
            else:
                duplicate.db_set(DRIVER_FILE_PRIVACY_FIELD, 1, update_modified=False)
            if duplicate.attached_to_doctype not in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES:
                _redact_driver_attachment_comments(
                    duplicate.attached_to_doctype,
                    duplicate.attached_to_name,
                    duplicate,
                )
                _clear_attached_file_field(duplicate)
                duplicate.attached_to_doctype = None
                duplicate.attached_to_name = None
                duplicate.attached_to_field = None
                duplicate.owner = "Administrator"
                duplicate.save(ignore_permissions=True)
            else:
                _update_attached_file_field(duplicate)
            _remove_private_driver_file_shares(duplicate.name)
    finally:
        frappe.flags.in_driver_private_file_duplicate_sync = previous_flag


def file_query_conditions(user=None):
    """Keep Driver evidence, Fleet files and duplicate-content rows out of generic lists."""
    user = user or frappe.session.user
    if user == "Administrator":
        return None
    attached_parent_condition = (
        "COALESCE(`tabFile`.`attached_to_doctype`, '') "
        "NOT IN ('Driver', 'Driver Compliance Record')"
    )
    private_sources = [
        (
            "`driver_private_file`.`attached_to_doctype` "
            "IN ('Driver', 'Driver Compliance Record')"
        )
    ]
    has_marker = frappe.get_meta("File").has_field(DRIVER_FILE_PRIVACY_FIELD)
    if has_marker:
        private_sources.append(
            f"COALESCE(`driver_private_file`.`{DRIVER_FILE_PRIVACY_FIELD}`, 0) = 1"
        )
    duplicate_content_condition = (
        "COALESCE(`tabFile`.`content_hash`, '') NOT IN ("
        "SELECT `driver_private_file`.`content_hash` FROM `tabFile` AS `driver_private_file` "
        "WHERE `driver_private_file`.`content_hash` IS NOT NULL "
        "AND `driver_private_file`.`content_hash` <> '' AND ("
        + " OR ".join(private_sources)
        + "))"
    )
    conditions = [attached_parent_condition, duplicate_content_condition]
    if has_marker:
        conditions.insert(
            0, f"COALESCE(`tabFile`.`{DRIVER_FILE_PRIVACY_FIELD}`, 0) = 0"
        )

    fleet_doctypes = sorted(
        COMPANY_SCOPED_FLEET_DOCTYPES | SOTRAMA_CHILD_TABLE_DOCTYPES
    )
    fleet_doctype_sql = ", ".join(f"'{doctype}'" for doctype in fleet_doctypes)
    fleet_sources = [
        f"`fleet_private_file`.`attached_to_doctype` IN ({fleet_doctype_sql})"
    ]
    has_fleet_marker = frappe.get_meta("File").has_field(FLEET_FILE_PRIVACY_FIELD)
    if has_fleet_marker:
        fleet_sources.append(
            f"COALESCE(`fleet_private_file`.`{FLEET_FILE_PRIVACY_FIELD}`, 0) = 1"
        )
    fleet_hash_condition = (
        "COALESCE(`tabFile`.`content_hash`, '') = '' OR "
        "COALESCE(`tabFile`.`content_hash`, '') NOT IN ("
        "SELECT `fleet_private_file`.`content_hash` FROM `tabFile` AS `fleet_private_file` "
        "WHERE `fleet_private_file`.`content_hash` IS NOT NULL "
        "AND `fleet_private_file`.`content_hash` <> '' AND ("
        + " OR ".join(fleet_sources)
        + "))"
    )
    fleet_duplicate_condition = f"COALESCE(`tabFile`.`attached_to_doctype`, '') NOT IN ({fleet_doctype_sql}) AND "
    if has_fleet_marker:
        fleet_duplicate_condition += (
            f"COALESCE(`tabFile`.`{FLEET_FILE_PRIVACY_FIELD}`, 0) = 0 "
            f"AND ({fleet_hash_condition})"
        )
    else:
        fleet_duplicate_condition += f"({fleet_hash_condition})"
    conditions.append(fleet_duplicate_condition)
    return " AND ".join(conditions)


def _get_driver_private_attachment_names(attachments):
    names = {
        attachment.get("name")
        for attachment in attachments or []
        if attachment.get("name")
    }
    if not names:
        return set()
    fields = ["name", "content_hash", "attached_to_doctype", "attached_to_name"]
    if frappe.get_meta("File").has_field(DRIVER_FILE_PRIVACY_FIELD):
        fields.append(DRIVER_FILE_PRIVACY_FIELD)
    files = frappe.get_all(
        "File", filters={"name": ["in", sorted(names)]}, fields=fields
    )
    return {
        file_doc.name for file_doc in files if is_driver_private_attachment(file_doc)
    }


def _filter_driver_attachment_metadata(doctype, name=None):
    docinfo = frappe.response.get("docinfo")
    if not docinfo:
        return
    if doctype in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES:
        if _has_hr_file_access() and _can_read_driver_attachment_parent(
            doctype, name, frappe.session.user
        ):
            return
        docinfo.attachments = []
        docinfo.attachment_logs = []
        return

    private_names = _get_driver_private_attachment_names(docinfo.get("attachments"))
    if private_names:
        docinfo.attachments = [
            attachment
            for attachment in docinfo.get("attachments", [])
            if attachment.get("name") not in private_names
        ]
        docinfo.attachment_logs = []


def _file_belongs_to_parent(file_doc, doctype, name):
    """Resolve child-row attachments to the parent document shown in Desk."""
    if not doctype or not name:
        return False
    attached_doctype = file_doc.get("attached_to_doctype")
    attached_name = file_doc.get("attached_to_name")
    if attached_doctype == doctype and attached_name == name:
        return True
    if attached_doctype not in SOTRAMA_CHILD_TABLE_DOCTYPES or not attached_name:
        return False
    parent = frappe.db.get_value(
        attached_doctype,
        attached_name,
        ["parenttype", "parent"],
        as_dict=True,
    )
    return bool(parent and parent.parenttype == doctype and parent.parent == name)


def _get_unrelated_fleet_attachment_names(attachments, doctype, name):
    """Find Fleet-derived File rows incorrectly exposed through another parent's docinfo."""
    names = sorted(
        {
            attachment.get("name")
            for attachment in attachments or []
            if attachment.get("name")
        }
    )
    if not names:
        return set()
    fields = ["name", "content_hash", "attached_to_doctype", "attached_to_name"]
    if frappe.get_meta("File").has_field(FLEET_FILE_PRIVACY_FIELD):
        fields.append(FLEET_FILE_PRIVACY_FIELD)
    files = frappe.get_all("File", filters={"name": ["in", names]}, fields=fields)
    return {
        file_doc.name
        for file_doc in files
        if is_company_scoped_fleet_attachment(file_doc)
        and not _file_belongs_to_parent(file_doc, doctype, name)
    }


def _filter_fleet_attachment_metadata(doctype, name=None):
    """Remove Fleet-derived duplicates from docinfo unless they belong to this parent."""
    docinfo = frappe.response.get("docinfo")
    if not docinfo:
        return
    private_names = _get_unrelated_fleet_attachment_names(
        docinfo.get("attachments"), doctype, name
    )
    if private_names:
        docinfo.attachments = [
            attachment
            for attachment in docinfo.get("attachments", [])
            if attachment.get("name") not in private_names
        ]
        docinfo.attachment_logs = []


def _require_driver_attachment_parent_read(doctype, name, user=None):
    """Require HR for child evidence and Company-scoped read on the parent Driver."""
    user = user or frappe.session.user
    if doctype == "Driver":
        driver_name = name
    elif doctype == "Driver Compliance Record":
        if not _has_hr_file_access(user):
            frappe.throw(
                frappe._("Driver compliance records are restricted to HR."),
                frappe.PermissionError,
            )
        driver_name = frappe.db.get_value("Driver Compliance Record", name, "parent")
    else:
        return

    if not driver_name or not frappe.has_permission(
        "Driver",
        "read",
        doc=driver_name,
        user=user,
        ignore_share_permissions=True,
    ):
        frappe.throw(
            frappe._(
                "You do not have Company-scoped read access to this Driver record."
            ),
            frappe.PermissionError,
        )


@frappe.whitelist()
def getdoc_with_driver_attachment_filter(doctype, name):
    """Filter protected attachment metadata from the standard Desk form response."""
    if doctype in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES:
        _require_driver_attachment_parent_read(doctype, name)
    from frappe.desk.form.load import getdoc

    result = getdoc(doctype, name)
    _filter_driver_attachment_metadata(doctype, name)
    _filter_fleet_attachment_metadata(doctype, name)
    return result


@frappe.whitelist()
def get_docinfo_with_driver_attachment_filter(*args, **kwargs):
    """Filter protected attachments when the client requests docinfo separately."""
    doc = kwargs.get("doc", args[0] if args else None)
    doctype = kwargs.get("doctype")
    if not doctype and doc:
        doctype = getattr(doc, "doctype", None)
        if not doctype and isinstance(doc, dict):
            doctype = doc.get("doctype")
    name = kwargs.get("name") or (doc.get("name") if isinstance(doc, dict) else None)
    if not name and doc:
        name = getattr(doc, "name", None)

    if doctype in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES:
        if not name:
            frappe.throw(
                frappe._(
                    "A readable Driver record is required to load its document details."
                ),
                frappe.PermissionError,
            )
        _require_driver_attachment_parent_read(doctype, name)

    from frappe.desk.form.load import get_docinfo

    result = get_docinfo(*args, **kwargs)
    _filter_driver_attachment_metadata(doctype, name)
    _filter_fleet_attachment_metadata(doctype, name)
    return result


@frappe.whitelist()
def get_filtered_attachments_with_driver_attachment_filter(dt, dn, filters):
    """Filter protected attachments from the standard attachment gallery endpoint."""
    if dt in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES:
        _require_driver_attachment_parent_read(dt, dn)
    from frappe.desk.form.load import get_filtered_attachments

    attachments = get_filtered_attachments(dt, dn, filters)
    if dt in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES:
        if not (
            _has_hr_file_access()
            and _can_read_driver_attachment_parent(dt, dn, frappe.session.user)
        ):
            return []
        return attachments

    private_names = _get_driver_private_attachment_names(attachments)
    attachments = [
        attachment for attachment in attachments if attachment.name not in private_names
    ]
    fleet_private_names = _get_unrelated_fleet_attachment_names(attachments, dt, dn)
    return [
        attachment
        for attachment in attachments
        if attachment.get("name") not in fleet_private_names
    ]


def _mark_duplicate_driver_file_rows(file_doc):
    content_hash = file_doc.get("content_hash")
    if not content_hash or not frappe.get_meta("File").has_field(
        DRIVER_FILE_PRIVACY_FIELD
    ):
        return
    names = frappe.get_all("File", filters={"content_hash": content_hash}, pluck="name")
    for name in names:
        if name != file_doc.name:
            frappe.db.set_value(
                "File", name, DRIVER_FILE_PRIVACY_FIELD, 1, update_modified=False
            )


def _validate_driver_private_file_paths(files):
    """Fail before migration if a public source is missing or its private target collides."""
    from pathlib import Path

    conflicts = []
    for file_doc in files:
        file_url = file_doc.get("file_url") or ""
        if _is_remote_file(file_doc) or not file_url.startswith("/files/"):
            continue
        file_name = file_url.rsplit("/", 1)[-1]
        public_path = Path(frappe.get_site_path("public", "files", file_name))
        private_path = Path(frappe.get_site_path("private", "files", file_name))
        if not public_path.exists():
            conflicts.append(f"{file_doc.name}: missing {public_path}")
        elif private_path.exists():
            conflicts.append(f"{file_doc.name}: target already exists {private_path}")

    if conflicts:
        frappe.throw(
            frappe._(
                "Driver private-file migration stopped because file paths need manual resolution:\n{0}"
            ).format("\n".join(conflicts)),
            frappe.ValidationError,
        )


def secure_driver_private_attachment(doc, method=None):
    """Force local Driver HR/compliance attachments to private storage."""
    if frappe.flags.get("in_driver_private_file_duplicate_sync"):
        return
    previous = (
        doc.get_doc_before_save() if method in ("before_save", "on_update") else None
    )
    was_driver_private = bool(previous and is_driver_private_attachment(previous))
    is_driver_private = is_driver_private_attachment(doc)
    if not (was_driver_private or is_driver_private):
        return
    _require_driver_private_file_write_access(doc)
    setattr(doc, DRIVER_FILE_PRIVACY_FIELD, 1)
    if _is_remote_file(doc):
        if (
            doc.flags.get("allow_remote_driver_detach")
            and not doc.get("attached_to_doctype")
            and not doc.get("attached_to_name")
        ):
            _remove_private_driver_file_shares(doc.name)
            return
        frappe.throw(
            frappe._(
                "Remote links are not allowed for Driver HR/compliance attachments. Upload a private file instead."
            )
        )

    if (doc.file_url or "").startswith("/files/"):
        _validate_driver_private_file_paths([doc])

    if method in ("before_insert", "before_save"):
        _mark_duplicate_driver_file_rows(doc)
        if not doc.is_private:
            doc.is_private = 1
            if method == "before_insert" and doc.file_url:
                doc.handle_is_private_changed()
        elif doc.file_url and doc.file_url.startswith("/files/"):
            doc.handle_is_private_changed()
        return

    if not doc.is_private:
        doc.is_private = 1
        if not doc.is_new():
            doc.save(ignore_permissions=True)
    elif doc.file_url and doc.file_url.startswith("/files/"):
        # Repair an inconsistent legacy row whose flag is private but URL is public.
        doc.handle_is_private_changed()
        if not doc.is_new():
            doc.save(ignore_permissions=True)
    _secure_duplicate_driver_file_rows(doc)
    _remove_private_driver_file_shares(doc.name)


def _redact_driver_attachment_comments(
    attached_doctype, attached_to_name, file_doc=None
):
    """Redact whole Driver attachment comments; URLs may be encoded or normalized."""
    from urllib.parse import unquote

    if not attached_doctype or not attached_to_name:
        return
    for comment in frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": attached_doctype,
            "reference_name": attached_to_name,
            "comment_type": "Attachment",
        },
        fields=["name", "content"],
    ):
        if file_doc:
            content = unquote(comment.content or "")
            file_name = unquote(file_doc.get("file_name") or "")
            file_url = unquote(file_doc.get("file_url") or "")
            if not (
                (file_name and file_name in content)
                or (file_url and file_url in content)
            ):
                continue
        if (
            comment.content
            and comment.content != "[Private Driver compliance attachment]"
        ):
            frappe.db.set_value(
                "Comment",
                comment.name,
                "content",
                "[Private Driver compliance attachment]",
            )


def preserve_driver_file_privacy_on_uninstall():
    """Leave Driver compliance files private and Administrator-owned on uninstall."""
    _ensure_driver_file_privacy_field()
    files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": ["in", ["Driver", "Driver Compliance Record"]],
        },
        fields=["name", "content_hash"],
    )
    marked_files = frappe.get_all(
        "File",
        filters={DRIVER_FILE_PRIVACY_FIELD: 1},
        fields=["name", "content_hash"],
    )
    names = {row.name for row in files + marked_files}
    content_hashes = {
        row.content_hash for row in files + marked_files if row.content_hash
    }
    if content_hashes:
        duplicate_files = frappe.get_all(
            "File",
            filters={"content_hash": ["in", sorted(content_hashes)]},
            fields=["name"],
        )
        names.update(row.name for row in duplicate_files)
    for name in names:
        file_doc = frappe.get_doc("File", name)
        if not is_driver_private_attachment(file_doc):
            continue
        _redact_driver_attachment_comments(
            file_doc.attached_to_doctype,
            file_doc.attached_to_name,
            file_doc
            if file_doc.attached_to_doctype not in PRIVATE_DRIVER_ATTACHMENT_DOCTYPES
            else None,
        )
        _remove_private_driver_file_shares(file_doc.name)
        _clear_attached_file_field(file_doc)
        setattr(file_doc, DRIVER_FILE_PRIVACY_FIELD, 1)
        file_doc.is_private = 1
        file_doc.attached_to_doctype = None
        file_doc.attached_to_name = None
        file_doc.attached_to_field = None
        file_doc.owner = "Administrator"
        file_doc.flags.allow_remote_driver_detach = True
        file_doc.save(ignore_permissions=True)


def preserve_fleet_file_privacy_on_uninstall():
    """Detach Fleet-derived files before their parent DocTypes are removed."""
    from sotrama.migrations.security import migrate_fleet_attachments_private

    migrate_fleet_attachments_private()
    files = frappe.get_all(
        "File",
        filters={FLEET_FILE_PRIVACY_FIELD: 1},
        fields=["name"],
        limit_page_length=0,
    )
    previous_migration_flag = frappe.flags.get("in_fleet_attachment_migration")
    frappe.flags.in_fleet_attachment_migration = True
    try:
        for row in files:
            file_doc = frappe.get_doc("File", row.name)
            if (
                not file_doc.attached_to_doctype
                and not file_doc.attached_to_name
                and file_doc.owner == "Administrator"
                and file_doc.is_private
                and not (file_doc.file_url or "").startswith("/files/")
            ):
                continue
            _redact_driver_attachment_comments(
                file_doc.attached_to_doctype,
                file_doc.attached_to_name,
                file_doc,
            )
            _clear_attached_file_field(file_doc)
            if file_doc.is_private and (file_doc.file_url or "").startswith("/files/"):
                file_doc.handle_is_private_changed()
            file_doc.is_private = 1
            setattr(file_doc, FLEET_FILE_PRIVACY_FIELD, 1)
            file_doc.attached_to_doctype = None
            file_doc.attached_to_name = None
            file_doc.attached_to_field = None
            file_doc.owner = "Administrator"
            file_doc.save(ignore_permissions=True)
            _remove_private_driver_file_shares(file_doc.name)
    finally:
        frappe.flags.in_fleet_attachment_migration = previous_migration_flag


def _check_tp_settings_field_read_permission(
    doctype, fieldnames, user=None, filters=None
):
    """Apply field permlevels to Frappe's single-value endpoints for TP Settings."""
    if doctype != "TP Settings":
        return

    if isinstance(filters, dict) or filters:
        frappe.throw(
            frappe._("Filtered TP Settings value queries are not permitted."),
            frappe.PermissionError,
        )

    user = user or frappe.session.user
    if not frappe.has_permission(doctype, "read", user=user):
        frappe.throw(
            frappe._("No permission to read TP Settings."), frappe.PermissionError
        )
    if user == "Administrator":
        return

    if isinstance(fieldnames, str):
        try:
            fieldnames = frappe.parse_json(fieldnames)
        except TypeError, ValueError:
            fieldnames = [fieldnames]
    if isinstance(fieldnames, dict):
        fieldnames = list(fieldnames)
    elif not isinstance(fieldnames, (list, tuple, set)):
        fieldnames = [fieldnames]
    if not fieldnames:
        frappe.throw(
            frappe._("A specific TP Settings field must be requested."),
            frappe.PermissionError,
        )

    meta = frappe.get_meta(doctype)
    roles = set(frappe.get_roles(user))
    standard_fields = {
        "name",
        "owner",
        "creation",
        "modified",
        "modified_by",
        "docstatus",
        "idx",
    }
    for fieldname in fieldnames:
        if fieldname in standard_fields:
            continue
        field = meta.get_field(fieldname)
        if not field:
            frappe.throw(frappe._("Unknown TP Settings field."), frappe.PermissionError)
        permlevel = int(field.permlevel or 0)
        if permlevel and not any(
            permission.role in roles
            and permission.read
            and int(permission.permlevel or 0) == permlevel
            for permission in meta.permissions
        ):
            frappe.throw(
                frappe._("You do not have permission to read the {0} field.").format(
                    field.label or field.fieldname
                ),
                frappe.PermissionError,
            )


def _check_tp_company_defaults_child_access(doctype, user=None):
    if doctype != "TP Company Defaults":
        return
    user = user or frappe.session.user
    if user != "Administrator" and "System Manager" not in frappe.get_roles(user):
        frappe.throw(
            frappe._(
                "Only System Manager can read the complete Company Defaults table."
            ),
            frappe.PermissionError,
        )


def tp_company_defaults_query_conditions(user=None):
    """Do not expose child rows outside the protected TP Settings table field."""
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return None
    return "1=0"


def tp_settings_query_conditions(user=None):
    """Keep the singleton out of generic list/report queries for lower roles."""
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return None
    return "1=0"


def _check_sotrama_child_table_rpc_access(doctype, user=None):
    """Require parent-document access for every Sotrama child-table read."""
    if doctype not in SOTRAMA_CHILD_TABLE_DOCTYPES:
        return
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return
    frappe.throw(
        frappe._(
            "Sotrama child-table rows must be accessed through their parent document."
        ),
        frappe.PermissionError,
    )


def _check_driver_compliance_child_rpc_access(doctype, user=None):
    """Keep medical child rows out of generic list/value APIs."""
    if doctype != "Driver Compliance Record":
        return
    user = user or frappe.session.user
    if user != "Administrator" and "System Manager" not in frappe.get_roles(user):
        frappe.throw(
            frappe._(
                "Driver compliance records can only be accessed through the permitted Driver form."
            ),
            frappe.PermissionError,
        )


def driver_compliance_record_query_conditions(user=None):
    """Block generic child-table lists; the parent Driver form is the safe view."""
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return None
    return "1=0"


def enforce_fleet_company_user_permissions(doc, user=None, ptype=None, debug=False):
    """Prevent DocShare from overriding Company and linked-record User Permissions."""
    if not doc:
        return True
    user = user or frappe.session.user
    if user == "Administrator" or "System Manager" in frappe.get_roles(user):
        return True

    company = doc.get("company")
    if not company:
        if doc.get("__islocal") or not doc.get("name"):
            return True
        frappe.throw(
            frappe._("Company is required to access this Fleet record."),
            frappe.PermissionError,
        )

    from frappe.permissions import has_user_permission

    from sotrama.tp.settings import validate_company_access

    validate_company_access(company, doc.doctype, user=user)
    if not has_user_permission(doc, user=user, ptype=ptype):
        frappe.throw(
            frappe._("You do not have User Permission access to this Fleet record."),
            frappe.PermissionError,
        )
    return True


def prevent_unsafe_fleet_docsharing(doc, method=None):
    """Allow only System Manager shares that cannot bypass recipient Company scope."""
    grants_access = any(
        frappe.utils.cint(doc.get(field))
        for field in ("read", "write", "submit", "share")
    )
    if doc.share_doctype in {"TP Settings", "TP Company Defaults"}:
        if grants_access:
            frappe.throw(
                frappe._("TP Settings configuration records cannot be shared."),
                frappe.PermissionError,
            )
        return
    if doc.share_doctype == "File":
        try:
            file_doc = frappe.get_doc("File", doc.share_name)
        except frappe.DoesNotExistError:
            return
        if grants_access and is_driver_private_attachment(file_doc):
            frappe.throw(
                frappe._("Driver compliance attachments cannot be shared directly."),
                frappe.PermissionError,
            )
        if grants_access and is_company_scoped_fleet_attachment(file_doc):
            frappe.throw(
                frappe._(
                    "Fleet attachments inherit access from their parent record and cannot be shared independently."
                ),
                frappe.PermissionError,
            )
    if doc.share_doctype in COMPANY_SCOPED_FLEET_DOCTYPES:
        user = frappe.session.user
        if user != "Administrator" and "System Manager" not in frappe.get_roles(user):
            frappe.throw(
                frappe._("Only System Manager can share company-scoped Fleet records."),
                frappe.PermissionError,
            )

        if not grants_access:
            return

        recipient = doc.get("user")
        if frappe.utils.cint(doc.get("everyone")) or not recipient:
            frappe.throw(
                frappe._("Fleet records cannot be shared with everyone."),
                frappe.PermissionError,
            )

        target = frappe.get_doc(doc.share_doctype, doc.share_name)
        if not frappe.has_permission(
            doc.share_doctype,
            "read",
            doc=target,
            user=recipient,
            ignore_share_permissions=True,
        ):
            frappe.throw(
                frappe._(
                    "The recipient must already have Company-scoped read access to this Fleet record."
                ),
                frappe.PermissionError,
            )


def remove_unsafe_fleet_docshares(user=None, owner=None, doctype=None, name=None):
    """Remove shares that bypass Company scope or expose private Driver files."""
    if doctype and doctype not in COMPANY_SCOPED_FLEET_DOCTYPES | {"File"}:
        return
    if user:
        frappe.clear_cache(user=user)

    if doctype is None:
        protected_filters = {
            "share_doctype": ["in", ["TP Settings", "TP Company Defaults"]]
        }
        principal_filters = []
        if user:
            principal_filters.append(["DocShare", "user", "=", user])
        if owner:
            principal_filters.append(["DocShare", "owner", "=", owner])
        protected_shares = frappe.get_all(
            "DocShare",
            filters=protected_filters,
            or_filters=principal_filters or None,
            fields=["name"],
        )
        for share in protected_shares:
            frappe.db.delete("DocShare", {"name": share.name})

    if doctype is None or doctype in COMPANY_SCOPED_FLEET_DOCTYPES:
        filters = {"share_doctype": ["in", sorted(COMPANY_SCOPED_FLEET_DOCTYPES)]}
        if doctype:
            filters["share_doctype"] = doctype
        if name:
            filters["share_name"] = name
        principal_filters = []
        if user:
            principal_filters.append(["DocShare", "user", "=", user])
        if owner:
            principal_filters.append(["DocShare", "owner", "=", owner])
        shares = frappe.get_all(
            "DocShare",
            filters=filters,
            or_filters=principal_filters or None,
            fields=[
                "name",
                "owner",
                "share_doctype",
                "share_name",
                "user",
                "everyone",
                "read",
                "write",
                "submit",
                "share",
            ],
        )
        for share in shares:
            share_owner = share.get("owner")
            if not share_owner or (
                share_owner != "Administrator"
                and "System Manager" not in frappe.get_roles(share_owner)
            ):
                frappe.db.delete("DocShare", {"name": share.name})
                continue

            if (
                not any(
                    frappe.utils.cint(share.get(field))
                    for field in ("read", "write", "submit", "share")
                )
                or frappe.utils.cint(share.get("everyone"))
                or not share.user
            ):
                frappe.db.delete("DocShare", {"name": share.name})
                continue

            try:
                target = frappe.get_doc(share.share_doctype, share.share_name)
                allowed = frappe.has_permission(
                    share.share_doctype,
                    "read",
                    doc=target,
                    user=share.user,
                    ignore_share_permissions=True,
                )
            except (
                frappe.DoesNotExistError,
                frappe.PermissionError,
                frappe.ValidationError,
            ):
                allowed = False
            if not allowed:
                frappe.db.delete("DocShare", {"name": share.name})

    if doctype is None or doctype == "File":
        file_filters = {"share_doctype": "File"}
        if name:
            file_filters["share_name"] = name
        principal_filters = []
        if user:
            principal_filters.append(["DocShare", "user", "=", user])
        if owner:
            principal_filters.append(["DocShare", "owner", "=", owner])
        for share in frappe.get_all(
            "DocShare",
            filters=file_filters,
            or_filters=principal_filters or None,
            fields=["name", "share_name"],
        ):
            try:
                file_doc = frappe.get_doc("File", share.share_name)
            except frappe.DoesNotExistError:
                file_doc = None
            if (
                not file_doc
                or is_driver_private_attachment(file_doc)
                or is_company_scoped_fleet_attachment(file_doc)
            ):
                frappe.db.delete("DocShare", {"name": share.name})


def remove_unsafe_fleet_docshares_for_file(doc, method=None):
    """Remove independent shares when a File is or was attached to a Fleet record."""
    previous = doc.get_doc_before_save()
    if (
        is_driver_private_attachment(doc)
        or is_company_scoped_fleet_attachment(doc)
        or is_driver_private_attachment(previous)
        or is_company_scoped_fleet_attachment(previous)
    ):
        frappe.db.delete("DocShare", {"share_doctype": "File", "share_name": doc.name})


def remove_unsafe_fleet_docshares_for_user(doc, method=None):
    """Revalidate shares after a user's Company User Permissions or roles change."""
    if doc.doctype == "User Permission":
        user = doc.user
    elif doc.doctype == "Has Role" and doc.parenttype == "User":
        user = doc.parent
    else:
        user = doc.name
    if user:
        if doc.doctype == "User Permission":
            remove_unsafe_fleet_docshares(user=user)
        else:
            remove_unsafe_fleet_docshares(user=user, owner=user)


def remove_unsafe_fleet_docshares_for_document(doc, method=None):
    """Revalidate shares when a Fleet record's Company or linked scope changes."""
    remove_unsafe_fleet_docshares(doctype=doc.doctype, name=doc.name)


@frappe.whitelist()
def get_value_with_tp_settings_field_permissions(
    doctype, fieldname, filters=None, as_dict=True, debug=False, parent=None
):
    """Protect field-level TP Settings values exposed by frappe.client.get_value."""
    _check_sotrama_child_table_rpc_access(doctype)
    _check_driver_compliance_child_rpc_access(doctype)
    _check_tp_company_defaults_child_access(doctype)
    _check_tp_settings_field_read_permission(doctype, fieldname, filters=filters)
    from frappe.client import get_value

    return get_value(doctype, fieldname, filters, as_dict, debug, parent)


@frappe.whitelist()
def get_list_with_tp_settings_permissions(
    doctype,
    fields=None,
    filters=None,
    group_by=None,
    order_by=None,
    limit_start=None,
    limit_page_length=20,
    parent=None,
    debug=False,
    as_dict=True,
    or_filters=None,
    expand=None,
):
    """Protect TP Settings singleton and child-table list RPCs."""
    _check_sotrama_child_table_rpc_access(doctype)
    _check_driver_compliance_child_rpc_access(doctype)
    if (
        doctype == "TP Settings"
        and frappe.session.user != "Administrator"
        and "System Manager" not in frappe.get_roles()
    ):
        frappe.throw(
            frappe._("TP Settings is not available through generic list queries."),
            frappe.PermissionError,
        )
    _check_tp_company_defaults_child_access(doctype)
    from frappe.client import get_list

    return get_list(
        doctype,
        fields,
        filters,
        group_by,
        order_by,
        limit_start,
        limit_page_length,
        parent,
        debug,
        as_dict,
        or_filters,
        expand,
    )


@frappe.whitelist()
def get_single_value_with_tp_settings_field_permissions(doctype, field):
    """Protect field-level TP Settings values exposed by frappe.client.get_single_value."""
    _check_tp_settings_field_read_permission(doctype, field)
    from frappe.client import get_single_value

    return get_single_value(doctype, field)


@frappe.whitelist()
def validate_link_and_fetch_without_tp_settings_singleton(
    doctype, docname, fields_to_fetch=None, query=None, filters=None, **search_args
):
    """Protect restricted singleton and HR-only child records from link-fetch RPCs."""
    _check_sotrama_child_table_rpc_access(doctype)
    _check_driver_compliance_child_rpc_access(doctype)
    _check_tp_company_defaults_child_access(doctype)
    if doctype in {"TP Settings", "TP Company Defaults"}:
        frappe.throw(
            frappe._("TP Settings configuration records are not valid Link targets."),
            frappe.PermissionError,
        )

    from frappe.client import validate_link_and_fetch

    return validate_link_and_fetch(
        doctype, docname, fields_to_fetch, query, filters, **search_args
    )


def has_app_permission():
    """Show Sotrama only to authenticated Desk users with an approved app role."""
    if frappe.session.user == "Administrator":
        return True

    if frappe.session.user == "Guest":
        return False

    return bool(APP_ROLES.intersection(frappe.get_roles()))
