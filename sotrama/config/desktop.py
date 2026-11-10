from frappe import _


def get_data():
    return [
        {
            "module_name": "Sotrama Core",
            "type": "module",
            "label": _("Sotrama Core"),
            "icon": "octicon octicon-globe",
        },
        {
            "module_name": "Sotrama HR Payroll",
            "type": "module",
            "label": _("Sotrama HR & Payroll"),
            "icon": "octicon octicon-people",
        },
        {
            "module_name": "Sotrama Compliance",
            "type": "module",
            "label": _("Sotrama Compliance"),
            "icon": "octicon octicon-shield-check",
        },
        {
            "module_name": "Sotrama BTPH",
            "type": "module",
            "label": _("Sotrama BTPH"),
            "icon": "octicon octicon-tools",
        },
    ]
