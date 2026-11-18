frappe.query_reports["Upcoming Document Expiries"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Data",
            description: __("Enter the exact ERPNext Company name."),
        },
        {
            fieldname: "vehicle",
            label: __("Vehicle"),
            fieldtype: "Link",
            options: "Vehicle",
            get_query() {
                const company = frappe.query_report.get_filter_value("company");
                return company ? { filters: { company } } : {};
            },
        },
        {
            fieldname: "alert_days",
            label: __("Alert Within Days"),
            fieldtype: "Int",
            description: __("Leave blank to use the alert window configured in TP Settings."),
        },
    ],
};
