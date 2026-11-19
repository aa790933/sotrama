"""
Sotrama — Algerian Localization & Public Works Fleet Management for ERPNext

Provides optional Algerian company registration fields and a TP
(Travaux Publics) Fleet Management module:
Vehicle, Driver, Maintenance Job Card, Breakdown Incident,
Maintenance Schedule, Vehicle Inspection, Operational Task,
Company Classification (Grade I–IX), and supporting masters.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from . import __version__ as _app_version

COMPANY_EXTENSION_MODULE = "Custom"
COMPANY_FIELD_OWNERSHIP_MARKER = "Managed by Sotrama — Algerian Company Extension."

app_name = "sotrama"
app_title = "Sotrama"
app_version = _app_version
app_publisher = "dekukoda41"
app_description = (
    "Algerian company localization and public-works fleet management "
    "for ERPNext and Frappe HR."
)
app_email = "dekukoda41@users.noreply.github.com"
app_license = "MIT"
app_color = "#d94736"
app_logo_url = "/assets/sotrama/images/sotrama-logo.svg"
app_home = "/desk/sotrama"
required_apps = ["frappe/erpnext", "frappe/hrms"]

add_to_apps_screen = [
    {
        "name": app_name,
        "logo": app_logo_url,
        "title": app_title,
        "route": app_home,
        "has_permission": "sotrama.permissions.has_app_permission",
        "sequence_id": 3,
    }
]


def ensure_roles():
    """Create the app roles before DocTypes and Role Profiles sync."""
    for role_name in ("Fleet Manager", "Workshop", "Driver"):
        if not frappe.db.exists("Role", role_name):
            frappe.get_doc(
                {
                    "doctype": "Role",
                    "role_name": role_name,
                    "desk_access": 1,
                }
            ).insert(ignore_permissions=True)


def prepare_before_install():
    """Prepare only Sotrama-owned records before Frappe syncs its modules."""
    ensure_roles()
    repair_orphaned_module_definitions()


def repair_orphaned_module_definitions():
    """Repair unplaced Sotrama Module Def rows left by an interrupted install.

    Frappe's installer creates Module Def records before syncing DocTypes. A
    previous failed install can leave a module row without an ``app_name`` or
    with a NULL ``custom`` flag; the next normal install then attempts to insert
    the same primary key again. Normalize only an unplaced, non-custom row whose
    module is declared by this app. Never rewrite a row owned by another app or
    a custom module; Frappe's installer remains responsible for custom-name clashes.
    """
    if not frappe.db.table_exists("Module Def"):
        return

    for module_name in frappe.get_module_list("sotrama"):
        existing = frappe.db.get_value(
            "Module Def", module_name, ["app_name", "custom"], as_dict=True
        )
        if not existing or existing.custom in (1, "1", True):
            continue
        if existing.app_name and existing.app_name != "sotrama":
            frappe.throw(
                frappe._(
                    "The module {0} already belongs to app {1}. Sotrama will not change another app's module ownership. "
                    "Review the existing Module Def before installing Sotrama."
                ).format(module_name, existing.app_name),
                title=frappe._("Module ownership conflict"),
            )

        values = {}
        if not existing.app_name:
            values["app_name"] = "sotrama"
        if existing.custom in (None, ""):
            values["custom"] = 0
        if values:
            frappe.db.set_value("Module Def", module_name, values, update_modified=False)


# ---------------------------------------------------------------------------
# Custom Field Definitions — Company doctype (Algerian registration)
# ---------------------------------------------------------------------------

def get_custom_fields():
    """Return complementary Algerian Company fields for explicit admin opt-in.

    ERPNext's standard ``Company.tax_id`` is the single source of truth for NIF.
    """
    return {
        "Company": [
            {
                "fieldname": "custom_sotrama_algerian_registration_section",
                "fieldtype": "Section Break",
                "label": "Algerian Legal & Registration Details",
                "module": COMPANY_EXTENSION_MODULE,
                "insert_after": "tax_id",
                "collapsible": 1,
                "description": COMPANY_FIELD_OWNERSHIP_MARKER,
                "depends_on": 'eval:doc.country=="Algeria"',
            },
            {
                "fieldname": "custom_article_imposition",
                "fieldtype": "Data",
                "label": "Article d'imposition",
                "module": COMPANY_EXTENSION_MODULE,
                "insert_after": "custom_sotrama_algerian_registration_section",
                "in_standard_filter": 1,
                "in_list_view": 0,
                "in_preview": 1,
                "reqd": 0,
                "description": "Numéro d'article fiscal recorded on the Certificate of Existence (certificat d'existence C n°20), distinct from the NIF. " + COMPANY_FIELD_OWNERSHIP_MARKER,
                "depends_on": 'eval:doc.country=="Algeria"',
            },
            {
                "fieldname": "custom_algerian_registration_column_break",
                "fieldtype": "Column Break",
                "module": COMPANY_EXTENSION_MODULE,
                "insert_after": "custom_article_imposition",
                "description": COMPANY_FIELD_OWNERSHIP_MARKER,
                "depends_on": 'eval:doc.country=="Algeria"',
            },
            {
                "fieldname": "custom_nis",
                "fieldtype": "Data",
                "label": "NIS (Statistical ID)",
                "module": COMPANY_EXTENSION_MODULE,
                "insert_after": "custom_algerian_registration_column_break",
                "in_standard_filter": 1,
                "in_list_view": 1,
                "in_preview": 1,
                "reqd": 0,
                "description": "Numéro d'Identification Statistique — Algerian statistical registration number. " + COMPANY_FIELD_OWNERSHIP_MARKER,
                "depends_on": 'eval:doc.country=="Algeria"',
            },
            {
                "fieldname": "custom_rc",
                "fieldtype": "Data",
                "label": "RC (Trade Registry)",
                "module": COMPANY_EXTENSION_MODULE,
                "insert_after": "custom_nis",
                "in_standard_filter": 1,
                "in_list_view": 1,
                "in_preview": 1,
                "reqd": 0,
                "description": "Registre de Commerce — Algerian trade registry number. " + COMPANY_FIELD_OWNERSHIP_MARKER,
                "depends_on": 'eval:doc.country=="Algeria"',
            },
            {
                "fieldname": "custom_capital_social",
                "fieldtype": "Currency",
                "label": "Capital Social",
                "module": COMPANY_EXTENSION_MODULE,
                "options": "default_currency",
                "insert_after": "custom_rc",
                "in_standard_filter": 0,
                "in_list_view": 0,
                "in_preview": 1,
                "reqd": 0,
                "description": "Registered share capital. Enter a numeric amount only; the value uses the Company's default currency. " + COMPANY_FIELD_OWNERSHIP_MARKER,
                "depends_on": 'eval:doc.country=="Algeria"',
            },
        ],
    }


def _is_managed_company_field(field):
    """Recognize only Sotrama-generated Company fields, including after uninstall.

    The marker is retained in the field description when a generated field is
    detached into Frappe's shared ``Custom`` module. A same-name Custom field
    without this marker may belong to another app and must not be claimed.
    """
    if not field or not field.is_system_generated:
        return False

    if field.module == "Sotrama":
        return True

    return (
        field.module == COMPANY_EXTENSION_MODULE
        and COMPANY_FIELD_OWNERSHIP_MARKER in (field.description or "")
    )


def _set_company_fields_hidden(hidden):
    """Hide or reveal Sotrama-owned fields without deleting metadata or data."""
    fieldnames = [field["fieldname"] for field in get_custom_fields()["Company"]]
    if not frappe.db.table_exists("Custom Field"):
        return

    fields = frappe.get_all(
        "Custom Field",
        filters={"dt": "Company", "fieldname": ["in", fieldnames]},
        fields=["name", "module", "is_system_generated", "description", "hidden"],
    )
    changed = False
    for field in fields:
        if not _is_managed_company_field(field):
            continue
        if bool(field.hidden) != bool(hidden):
            frappe.db.set_value(
                "Custom Field", field.name, "hidden", int(bool(hidden)), update_modified=False
            )
            changed = True

    # Retire legacy fields whose names changed or whose purpose is now covered
    # by ERPNext's standard Company.tax_id. Keep their values untouched.
    for legacy_fieldname in ("custom_nif", "custom_algerian_registration_section"):
        legacy_field = frappe.db.get_value(
            "Custom Field",
            {"dt": "Company", "fieldname": legacy_fieldname},
            ["name", "module", "is_system_generated", "description", "hidden"],
            as_dict=True,
        )
        if (
            legacy_field
            and _is_managed_company_field(legacy_field)
            and not legacy_field.hidden
        ):
            frappe.db.set_value(
                "Custom Field", legacy_field.name, "hidden", 1, update_modified=False
            )
            changed = True

    if changed:
        frappe.clear_cache(doctype="Company")


def enable_algerian_company_fields():
    """Install the optional Company extension after explicit admin opt-in.

    Existing fields are never silently converted or overwritten. This avoids
    schema casts of formatted currency text such as ``2 897 268 000.00 DA``.
    """
    definitions = get_custom_fields()
    for doctype, fields in definitions.items():
        for field in fields:
            existing = frappe.db.get_value(
                "Custom Field",
                {"dt": doctype, "fieldname": field["fieldname"]},
                ["name", "fieldtype", "module", "is_system_generated", "description"],
                as_dict=True,
            )
            if existing and not _is_managed_company_field(existing):
                frappe.throw(
                    frappe._(
                        "The field {0} already exists on {1} and is owned by module {2}. "
                        "Sotrama will not take ownership of or modify another app's field. "
                        "Choose a different field name or resolve the ownership conflict first."
                    ).format(field["fieldname"], doctype, existing.module or frappe._("Customizations")),
                    title=frappe._("Existing field is owned elsewhere"),
                )
            if existing and existing.fieldtype != field["fieldtype"]:
                frappe.throw(
                    frappe._(
                        "The existing {0} field on {1} is {2}, but Sotrama requires {3}. "
                        "No data was changed. Review or rename the existing field before enabling this feature."
                    ).format(field["fieldname"], doctype, existing.fieldtype, field["fieldtype"]),
                    title=frappe._("Existing field needs review"),
                )

    # An older duplicate NIF field or registration section must not remain
    # beside the standard Tax ID/current section. Reject a same-name field
    # unless Sotrama can prove it created that field in an earlier release.
    legacy_fieldnames = ("custom_nif", "custom_algerian_registration_section")
    for fieldname in legacy_fieldnames:
        legacy_field = frappe.db.get_value(
            "Custom Field",
            {"dt": "Company", "fieldname": fieldname},
            ["name", "module", "is_system_generated", "description"],
            as_dict=True,
        )
        if legacy_field and not _is_managed_company_field(legacy_field):
            frappe.throw(
                frappe._(
                    "The legacy Company field {0} exists but is not owned by Sotrama. "
                    "Review or rename it before enabling the Algerian Company Extension."
                ).format(fieldname),
                title=frappe._("Legacy Company field needs review"),
            )

    # Older releases stored generated Company fields in the app-owned Sotrama
    # module. Move them to the persistent Custom module only after all conflicts
    # and field types have passed validation; this does not alter SQL columns.
    _detach_legacy_module_fields(definitions)

    # Only create missing fields; do not overwrite site-specific customizations.
    create_custom_fields(definitions, update=False)
    _set_company_fields_hidden(False)


def _detach_legacy_module_fields(definitions=None):
    """Preserve ownership and fill only missing metadata on prior Sotrama fields.

    Earlier releases put generated fields in the app-owned Sotrama module and
    did not restrict them to Algerian Companies. Move those fields to Frappe's
    persistent Custom module. Add only the missing country dependency, and fix
    the old Article d'imposition position when it still points at the retired
    custom NIF field. Other user-edited presentation metadata remains untouched.
    """
    company_fields = (definitions or get_custom_fields())["Company"]
    definitions_by_name = {field["fieldname"]: field for field in company_fields}
    fieldnames = list(definitions_by_name)
    fieldnames.extend(("custom_nif", "custom_algerian_registration_section"))

    existing_fields = frappe.get_all(
        "Custom Field",
        filters={"dt": "Company", "fieldname": ["in", fieldnames]},
        fields=[
            "name",
            "fieldname",
            "module",
            "description",
            "is_system_generated",
            "depends_on",
            "insert_after",
        ],
    )
    changed = False
    for existing in existing_fields:
        if not _is_managed_company_field(existing):
            continue

        values = {}
        if existing.module == "Sotrama":
            values["module"] = COMPANY_EXTENSION_MODULE

        description = existing.description or ""
        if COMPANY_FIELD_OWNERSHIP_MARKER not in description:
            values["description"] = (
                f"{description.rstrip()} {COMPANY_FIELD_OWNERSHIP_MARKER}".strip()
            )

        definition = definitions_by_name.get(existing.fieldname)
        if definition:
            if not existing.depends_on and definition.get("depends_on"):
                values["depends_on"] = definition["depends_on"]

            if (
                existing.fieldname == "custom_article_imposition"
                and existing.insert_after == "custom_nif"
            ):
                values["insert_after"] = "custom_sotrama_algerian_registration_section"

        if values:
            frappe.db.set_value("Custom Field", existing.name, values, update_modified=False)
            changed = True

    if changed:
        frappe.clear_cache(doctype="Company")


def sync_company_fields():
    """Apply Company fields only when enabled in Sotrama Settings.

    A fresh install has no setting record and therefore creates no Company
    Custom Fields. Disabling the option hides existing fields but preserves
    their metadata and every value already stored on Company records.
    """
    if not frappe.db.exists("DocType", "Sotrama Settings"):
        return

    enabled = frappe.db.get_single_value("Sotrama Settings", "enable_algerian_company_fields")
    if enabled:
        enable_algerian_company_fields()
    else:
        _set_company_fields_hidden(True)


def initialize_app():
    """Initialize app roles and idempotent fleet masters after DocTypes sync."""
    ensure_roles()
    from sotrama.setup import ensure_default_masters

    ensure_default_masters()


def preserve_company_fields_on_uninstall():
    """Preserve Company extension fields before Frappe removes app-owned modules.

    Frappe deletes Custom Field records linked to an app-owned module during
    uninstall. Move the known Company extension fieldnames into the persistent
    core ``Custom`` module. Stamp only system-generated fields with the
    Sotrama ownership marker; same-name user-created fields remain unclaimed.
    """
    fieldnames = [field["fieldname"] for field in get_custom_fields()["Company"]]
    fieldnames.extend(("custom_nif", "custom_algerian_registration_section"))
    if not frappe.db.table_exists("Custom Field"):
        return

    fields = frappe.get_all(
        "Custom Field",
        filters={"dt": "Company", "fieldname": ["in", fieldnames]},
        fields=["name", "fieldname", "module", "description", "is_system_generated"],
    )
    changed = False
    for field in fields:
        values = {}
        if field.module == "Sotrama":
            # Even a manually created field filed under Sotrama is detached so
            # Frappe cannot delete it; without the marker it will not be adopted
            # by a later Sotrama install.
            values["module"] = COMPANY_EXTENSION_MODULE
            if field.is_system_generated:
                description = field.description or ""
                if COMPANY_FIELD_OWNERSHIP_MARKER not in description:
                    values["description"] = (
                        f"{description.rstrip()} {COMPANY_FIELD_OWNERSHIP_MARKER}".strip()
                    )
                values["hidden"] = 1
        elif (
            field.module == COMPANY_EXTENSION_MODULE
            and field.is_system_generated
            and COMPANY_FIELD_OWNERSHIP_MARKER in (field.description or "")
        ):
            values["hidden"] = 1

        if values:
            frappe.db.set_value("Custom Field", field.name, values, update_modified=False)
            changed = True

    if changed:
        frappe.clear_cache(doctype="Company")


before_install = "sotrama.hooks.prepare_before_install"
after_install = "sotrama.hooks.initialize_app"
before_uninstall = "sotrama.hooks.preserve_company_fields_on_uninstall"


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
# Frappe's app_include_js hook is a scalar path or a list of paths.
# A dict here conflicts with the same hook from Frappe/ERPNext/HRMS while
# the framework merges app hooks, causing append_hook() to call setdefault
# on a list during site installation.
app_include_js = "/assets/sotrama/js/sotrama.js"
# No custom CSS — app follows standard Frappe Desk styling


# ---------------------------------------------------------------------------
# DocType JS — per-DocType client-side scripts
# ---------------------------------------------------------------------------

doctype_js = {
    "Sotrama Settings": "public/js/sotrama_settings.js",
    "Vehicle": "public/js/vehicle.js",
    "Breakdown Incident": "public/js/breakdown.js",
    "Maintenance Job Card": "public/js/job_card.js",
    "Vehicle Inspection": "public/js/inspection.js",
    "Operational Task": "public/js/operational_task.js",
    "Driver": "public/js/driver.js",
    "Maintenance Schedule": "public/js/maintenance_schedule.js",
    "TP Settings": "public/js/tp_settings.js",
    "Company Classification": "public/js/company_classification.js",
}

# Role Profiles are standard Frappe records stored in the module's role_profile
# folder. Register the DocType with Frappe's supported importable_doctypes hook
# so the records are synchronized during install and migrate, not left unused.
importable_doctypes = ["Role Profile"]


# ---------------------------------------------------------------------------
# Workflow — none needed (state managed via DocType controller)
# ---------------------------------------------------------------------------

workflow = {}
