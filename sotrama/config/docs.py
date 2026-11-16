"""
Documentation configuration for the Sotrama app.
"""


import frappe


def get_docs_context(context):
    """Add app-specific context for documentation pages."""
    context["app"] = "sotrama"
    context["app_title"] = "Sotrama"
    return context