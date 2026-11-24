const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { runInNewContext } = require("node:vm");

const reports = {};
let selectedCompany = "COMPANY-A";
const context = {
    __: (value) => value,
    frappe: {
        query_reports: reports,
        query_report: {
            get_filter_value: () => selectedCompany,
        },
        datetime: {
            add_months: (date, months) => `${date}:${months}`,
            get_today: () => "2026-11-23",
        },
    },
};

for (const [reportName, moduleName] of [
    ["Fleet Cost Analysis", "fleet_cost_analysis"],
    ["Upcoming Document Expiries", "upcoming_document_expiries"],
]) {
    const source = readFileSync(
        `sotrama/tp/report/${moduleName}/${moduleName}.js`,
        "utf8",
    );
    runInNewContext(source, context, { filename: `${moduleName}.js` });

    const filters = reports[reportName].filters;
    const companyFilter = filters.find((filter) => filter.fieldname === "company");
    const vehicleFilter = filters.find((filter) => filter.fieldname === "vehicle");

    assert.equal(typeof companyFilter.on_change, "function");
    const calls = [];
    companyFilter.on_change({
        set_filter_value: (...args) => calls.push(args),
    });
    assert.deepEqual(calls, [["vehicle", ""]]);

    selectedCompany = "COMPANY-B";
    assert.deepEqual(
        JSON.parse(JSON.stringify(vehicleFilter.get_query())),
        {
            filters: [
                ["docstatus", "=", 1],
                ["vehicle_status", "not in", ["Retired", "Scrapped"]],
                ["company", "=", "COMPANY-B"],
            ],
        },
    );
    selectedCompany = "";
    assert.deepEqual(
        JSON.parse(JSON.stringify(vehicleFilter.get_query())),
        {
            filters: [
                ["docstatus", "=", 1],
                ["vehicle_status", "not in", ["Retired", "Scrapped"]],
            ],
        },
    );
}

console.log("Report Company changes clear stale Vehicle filters in both Fleet reports.");
