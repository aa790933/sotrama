"""Shared helpers for Sotrama domain-focused Frappe tests."""

from pathlib import Path

import frappe


def _get_test_company():
    company = (
        frappe.db.get_single_value("TP Settings", "default_company")
        if frappe.db.exists("DocType", "TP Settings")
        else None
    )
    if not company or not frappe.db.exists("Company", company):
        company = frappe.db.get_value("Company", {}, "name")
    if not company:
        raise AssertionError(
            "The Sotrama test suite requires at least one ERPNext Company."
        )
    return company


def _sotrama_package_path():
    """Return the importable Sotrama package directory inside the app checkout."""
    return Path(frappe.get_app_path("sotrama"))


def _delete_test_record(doctype, name):
    """Remove test fixtures without weakening production delete/cancel rules."""
    if not name or not frappe.db.exists(doctype, name):
        return

    if doctype == "Breakdown Incident":
        linked_job_cards = frappe.get_all(
            "Maintenance Job Card",
            filters={"linked_breakdown_incident": name},
            pluck="name",
        )
        for job_card_name in linked_job_cards:
            _delete_test_record("Maintenance Job Card", job_card_name)

    meta = frappe.get_meta(doctype)
    for field in meta.fields:
        if (
            field.fieldtype == "Table"
            and field.options
            and frappe.db.table_exists(field.options)
        ):
            frappe.db.delete(field.options, {"parent": name, "parenttype": doctype})

    related_records = (
        ("Comment", {"reference_doctype": doctype, "reference_name": name}),
        ("Version", {"ref_doctype": doctype, "docname": name}),
        ("ToDo", {"reference_type": doctype, "reference_name": name}),
        ("DocShare", {"share_doctype": doctype, "share_name": name}),
        ("File", {"attached_to_doctype": doctype, "attached_to_name": name}),
    )
    for related_doctype, filters in related_records:
        if frappe.db.table_exists(related_doctype):
            frappe.db.delete(related_doctype, filters)

    frappe.db.delete(doctype, {"name": name})
    frappe.clear_cache(doctype=doctype)
