"""
 Sotrama — Algerian Company Setup & Public Works Fleet Management for ERPNext

Provides optional Algerian company registration fields and a TP
(Travaux Publics) Fleet Management module:
Vehicle, Driver, Maintenance Job Card, Breakdown Incident,
Maintenance Schedule, Vehicle Inspection, Operational Task,
Company Classification (Grade I–IX), and supporting masters.
"""

from . import __version__ as _app_version

app_name = "sotrama"
app_title = "Sotrama"
app_version = _app_version
app_publisher = "dekukoda41"
app_description = (
    "Algerian company setup and public-works fleet management "
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


# ---------------------------------------------------------------------------
# Company field definitions live in sotrama.setup.company.
# ---------------------------------------------------------------------------


before_install = "sotrama.setup.install.prepare_before_install"
after_install = "sotrama.setup.install.initialize_app"
after_migrate = "sotrama.setup.install.recover_incomplete_install"
before_uninstall = "sotrama.setup.uninstall.preserve_company_fields_on_uninstall"

# The consolidated upgrade migration includes security-sensitive backfills and must not be skipped.
never_skip_patches = ["sotrama.patches.v1_4.initial_data_cleanup"]


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
# Desk assets are registered per DocType; no global bundle is needed.
# ---------------------------------------------------------------------------

# No global Desk JavaScript or CSS is required; form scripts are registered per DocType.


# ---------------------------------------------------------------------------
# DocType JS — per-DocType client-side scripts
# ---------------------------------------------------------------------------

doctype_js = {
    "Sotrama Settings": "public/js/sotrama_settings.js",
    "Vehicle": "public/js/vehicle.js",
    "Vehicle Model": "public/js/vehicle_model.js",
    "Breakdown Incident": "public/js/breakdown.js",
    "Maintenance Job Card": "public/js/job_card.js",
    "Vehicle Inspection": "public/js/inspection.js",
    "Operational Task": "public/js/operational_task.js",
    "Driver": "public/js/driver.js",
    "Maintenance Schedule": "public/js/maintenance_schedule.js",
    "TP Settings": "public/js/tp_settings.js",
    "Company Classification": "public/js/company_classification.js",
}

doc_events = {
    "DocShare": {
        "before_insert": "sotrama.permissions.prevent_unsafe_fleet_docsharing",
        "before_save": "sotrama.permissions.prevent_unsafe_fleet_docsharing",
    },
    "File": {
        "before_validate": "sotrama.permissions.secure_company_scoped_fleet_attachment",
        "before_insert": "sotrama.permissions.secure_driver_private_attachment",
        "before_save": "sotrama.permissions.secure_driver_private_attachment",
        "on_update": [
            "sotrama.permissions.secure_driver_private_attachment",
            "sotrama.permissions.remove_unsafe_fleet_docshares_for_file",
        ],
        "after_insert": "sotrama.permissions.secure_driver_private_attachment",
    },
    "User Permission": {
        "after_insert": "sotrama.permissions.remove_unsafe_fleet_docshares_for_user",
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_user",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_user",
    },
    "User": {
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_user",
    },
    "Has Role": {
        "after_insert": "sotrama.permissions.remove_unsafe_fleet_docshares_for_user",
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_user",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_user",
    },
    "Vehicle": {
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_update_after_submit": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_trash": "sotrama.tp.validation.prevent_submitted_fleet_record_deletion",
    },
    "Driver": {
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_update_after_submit": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_trash": "sotrama.tp.validation.prevent_submitted_fleet_record_deletion",
    },
    "Maintenance Job Card": {
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_update_after_submit": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_trash": "sotrama.tp.validation.prevent_submitted_fleet_record_deletion",
    },
    "Vehicle Inspection": {
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_update_after_submit": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_trash": "sotrama.tp.validation.prevent_submitted_fleet_record_deletion",
    },
    "Breakdown Incident": {
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_update_after_submit": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_trash": "sotrama.tp.validation.prevent_submitted_fleet_record_deletion",
    },
    "Operational Task": {
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_update_after_submit": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_trash": "sotrama.tp.validation.prevent_submitted_fleet_record_deletion",
    },
    "Maintenance Schedule": {
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_update_after_submit": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_trash": "sotrama.tp.validation.prevent_submitted_fleet_record_deletion",
    },
    "Company Classification": {
        "on_update": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_update_after_submit": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "after_delete": "sotrama.permissions.remove_unsafe_fleet_docshares_for_document",
        "on_trash": "sotrama.tp.validation.prevent_submitted_fleet_record_deletion",
    },
}

has_permission = {
    "File": "sotrama.permissions.file_has_permission",
    "Vehicle": "sotrama.permissions.enforce_fleet_company_user_permissions",
    "Driver": "sotrama.permissions.enforce_fleet_company_user_permissions",
    "Vehicle Inspection": "sotrama.permissions.enforce_fleet_company_user_permissions",
    "Breakdown Incident": "sotrama.permissions.enforce_fleet_company_user_permissions",
    "Operational Task": "sotrama.permissions.enforce_fleet_company_user_permissions",
    "Maintenance Schedule": "sotrama.permissions.enforce_fleet_company_user_permissions",
    "Maintenance Job Card": "sotrama.permissions.enforce_fleet_company_user_permissions",
    "Company Classification": "sotrama.permissions.enforce_fleet_company_user_permissions",
}

# Frappe 16 form docinfo and the attachment gallery use get_all(), bypassing
# File permissions and query conditions; wrap those endpoints for Driver evidence.
permission_query_conditions = {
    "File": "sotrama.permissions.file_query_conditions",
    "TP Company Defaults": "sotrama.permissions.tp_company_defaults_query_conditions",
    "TP Settings": "sotrama.permissions.tp_settings_query_conditions",
    "Driver Compliance Record": "sotrama.permissions.driver_compliance_record_query_conditions",
    "Breakdown Photo": "sotrama.permissions.sotrama_child_table_query_conditions",
    "Inspection Item": "sotrama.permissions.sotrama_child_table_query_conditions",
    "Job Card Labour": "sotrama.permissions.sotrama_child_table_query_conditions",
    "Job Card Other Cost": "sotrama.permissions.sotrama_child_table_query_conditions",
    "Job Card Part": "sotrama.permissions.sotrama_child_table_query_conditions",
    "Job Card Photo": "sotrama.permissions.sotrama_child_table_query_conditions",
    "Vehicle Document": "sotrama.permissions.sotrama_child_table_query_conditions",
}

override_whitelisted_methods = {
    "frappe.desk.form.load.getdoc": "sotrama.permissions.getdoc_with_driver_attachment_filter",
    "frappe.desk.form.load.get_docinfo": "sotrama.permissions.get_docinfo_with_driver_attachment_filter",
    "frappe.desk.form.load.get_filtered_attachments": "sotrama.permissions.get_filtered_attachments_with_driver_attachment_filter",
    "frappe.client.get_value": "sotrama.permissions.get_value_with_tp_settings_field_permissions",
    "frappe.client.get_list": "sotrama.permissions.get_list_with_tp_settings_permissions",
    "frappe.client.get_single_value": "sotrama.permissions.get_single_value_with_tp_settings_field_permissions",
    "frappe.client.validate_link_and_fetch": "sotrama.permissions.validate_link_and_fetch_without_tp_settings_singleton",
}

extend_doctype_class = {
    "File": "sotrama.overrides.file.DriverPrivateFileMixin",
}

# Role Profiles are standard Frappe records stored in the module's role_profile
# folder. Register the DocType with Frappe's supported importable_doctypes hook
# so the records are synchronized during install and migrate, not left unused.
importable_doctypes = ["Role Profile"]
