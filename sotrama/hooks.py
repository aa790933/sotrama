"""Frappe hooks for the Sotrama application."""

app_name = "sotrama"
app_title = "Sotrama"
app_publisher = "Sotrama"
app_description = "Algerian localization and public works extensions"
app_email = "noreply@github.com"
app_license = "AGPL-3.0-only"

fixtures = ["Role"]

fixtures = [
    {
        "dt": "Role",
        "filters": [
            [
                "name",
                "in",
                ["Sotrama Payroll Manager", "Sotrama Compliance Manager", "Sotrama BTPH Manager"],
            ]
        ],
    }
]

# Keep integration opt-in and version-aware. Add hooks only after checking the
# target Frappe/ERPNext/HRMS source and covering behavior with integration tests.
