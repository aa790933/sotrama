frappe.query_reports["Upcoming Document Expiries"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            get_query() {
                return { query: "sotrama.tp.settings.search_fleet_report_companies" };
            },
            on_change(report) {
                report.set_filter_value("vehicle", "");
            },
        },
        {
            fieldname: "vehicle",
            label: __("Vehicle"),
            fieldtype: "Link",
            options: "Vehicle",
            get_query() {
                const company = frappe.query_report.get_filter_value("company");
                const filters = [
                    ["docstatus", "=", 1],
                    ["vehicle_status", "not in", ["Retired", "Scrapped"]],
                ];
                if (company) filters.push(["company", "=", company]);
                return { filters };
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
