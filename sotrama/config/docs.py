"""
Documentation configuration for the Sotrama app.
"""




def get_docs_context(context):
    """Add app-specific context for documentation pages."""
    context["app"] = "sotrama"
    context["app_title"] = "Sotrama"
    return context