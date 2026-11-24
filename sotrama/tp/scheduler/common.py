"""Shared scheduler helpers for role-aware Fleet alert assignment."""

import frappe


def _user_for_role(
    role_name, doctype, docname, *, role_users_cache=None, known_existing=False
):
    """Return a role user who can read this exact company-scoped document."""
    if not docname or (not known_existing and not frappe.db.exists(doctype, docname)):
        return "Administrator"
    role_users_cache = role_users_cache if role_users_cache is not None else {}
    if role_name not in role_users_cache:
        role_users = frappe.get_all(
            "Has Role",
            filters={"role": role_name, "parenttype": "User"},
            pluck="parent",
            order_by="parent asc",
            limit_page_length=0,
        )
        role_users_cache[role_name] = (
            frappe.get_all(
                "User",
                filters={"name": ["in", role_users], "enabled": 1},
                pluck="name",
                order_by="name asc",
                limit_page_length=0,
            )
            if role_users
            else []
        )

    for user in role_users_cache[role_name]:
        if user == "Guest":
            continue
        try:
            if frappe.has_permission(doctype, "read", doc=docname, user=user):
                return user
        except frappe.DoesNotExistError:
            # The record may have been deleted after the scheduler batch read.
            return "Administrator"
    return "Administrator"
