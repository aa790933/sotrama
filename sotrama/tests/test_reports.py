import json
import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_days, today

from sotrama.tests.helpers import _sotrama_package_path


class TestFleetReports(unittest.TestCase):
    """Domain-focused integration coverage extracted from the former setup monolith."""

    def test_fleet_report_company_filters_use_permission_scoped_link_lookup(self):
        for report in ("fleet_cost_analysis", "upcoming_document_expiries"):
            with self.subTest(report=report):
                source = (
                    _sotrama_package_path() / "tp" / "report" / report / f"{report}.js"
                ).read_text(encoding="utf-8")
                self.assertIn('fieldtype: "Link"', source)
                self.assertIn('options: "Company"', source)
                self.assertIn(
                    "sotrama.tp.settings.search_fleet_report_companies", source
                )
                self.assertIn("on_change(report)", source)
                self.assertIn('report.set_filter_value("vehicle", "")', source)

    def test_fleet_report_company_lookup_uses_only_permission_visible_vehicles(self):
        from sotrama.tp.settings import search_fleet_report_companies

        with (
            patch("sotrama.tp.settings.frappe.has_permission") as has_permission,
            patch(
                "sotrama.tp.settings.frappe.get_list",
                return_value=[frappe._dict(company="SOTRAMA")],
            ) as get_list,
        ):
            result = search_fleet_report_companies("Company", "SOT", "name", 0, 20)

        has_permission.assert_called_once_with("Vehicle", "read", throw=True)
        get_list.assert_called_once_with(
            "Vehicle",
            fields=["company"],
            filters=[
                ["docstatus", "=", 1],
                ["vehicle_status", "not in", ["Retired", "Scrapped"]],
                ["company", "like", "%SOT%"],
            ],
            group_by="company",
            order_by="company asc",
            start=0,
            page_length=20,
        )
        self.assertEqual(result, [["SOTRAMA"]])

        with (
            patch(
                "sotrama.tp.settings.frappe.has_permission",
                side_effect=frappe.PermissionError,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            search_fleet_report_companies("Company", "", "name", 0, 20)

    def test_fleet_reports_have_reference_doctypes(self):
        self.assertEqual(
            frappe.get_value("Report", "Fleet Cost Analysis", "ref_doctype"), "Vehicle"
        )
        self.assertEqual(
            frappe.get_value("Report", "Upcoming Document Expiries", "ref_doctype"),
            "Vehicle",
        )

    def test_fleet_cost_report_uses_site_default_currency_for_cost_fields(self):
        from sotrama.tp.report.fleet_cost_analysis.fleet_cost_analysis import (
            get_columns,
            get_data,
        )

        self.assertFalse(
            frappe.get_value("Report", "Fleet Cost Analysis", "add_total_row")
        )
        columns = {column["fieldname"]: column for column in get_columns()}
        self.assertEqual(columns["company"]["fieldtype"], "Data")
        self.assertEqual(columns["currency"]["fieldtype"], "Link")
        self.assertEqual(columns["currency"]["options"], "Currency")
        for fieldname in (
            "maintenance_cost",
            "other_costs",
            "depreciation",
            "total_cost",
            "cost_per_km",
        ):
            self.assertEqual(columns[fieldname]["options"], "currency")

        visible_vehicle = frappe._dict(
            {
                "name": "VEH-REPORT-TEST",
                "license_plate": "TEST-REPORT",
                "company": "Test Company",
                "acquisition_date": None,
                "acquisition_value": 0,
                "depreciation_rate": 0,
                "salvage_value": 0,
            }
        )
        with (
            patch.object(
                frappe,
                "get_list",
                side_effect=[[visible_vehicle], [], []],
            ),
            patch.object(frappe.db, "get_default", return_value="DZD"),
        ):
            rows = get_data(frappe._dict())

        self.assertEqual(rows[0]["currency"], "DZD")

    def test_document_expiry_report_rejects_unbounded_alert_windows(self):
        from sotrama.tp.report.upcoming_document_expiries.upcoming_document_expiries import (
            get_data,
        )

        with (
            patch(
                "sotrama.tp.report.upcoming_document_expiries.upcoming_document_expiries.get_tp_setting",
                return_value=30,
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            get_data(frappe._dict({"alert_days": 3651}))

    def test_document_expiry_report_scopes_child_rows_to_permission_visible_vehicles(
        self,
    ):
        from frappe.utils import add_days, today

        from sotrama.tp.report.upcoming_document_expiries.upcoming_document_expiries import (
            get_data,
        )

        visible_vehicle = frappe._dict(
            name="VEH-REPORT-A",
            docstatus=1,
            license_plate="REPORT-A",
            company="COMPANY-A",
        )
        visible_document = frappe._dict(
            parent="VEH-REPORT-A",
            document_type="Insurance Certificate",
            expiry_date=add_days(today(), 5),
            status="Active",
        )
        with (
            patch(
                "sotrama.tp.report.upcoming_document_expiries.upcoming_document_expiries.get_tp_setting",
                return_value=30,
            ),
            patch.object(
                frappe, "get_list", return_value=[visible_vehicle]
            ) as get_list,
            patch.object(frappe, "get_all", return_value=[visible_document]) as get_all,
            patch(
                "sotrama.tp.report.upcoming_document_expiries.upcoming_document_expiries._",
                side_effect=lambda message: (
                    "Certificat d'assurance"
                    if message == "Insurance Certificate"
                    else message
                ),
            ),
        ):
            rows = get_data(frappe._dict(company="COMPANY-A", vehicle="VEH-REPORT-A"))

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["document_type"], "Certificat d'assurance")
        vehicle_filters = get_list.call_args.kwargs["filters"]
        self.assertIn(["docstatus", "=", 1], vehicle_filters)
        self.assertIn(["company", "=", "COMPANY-A"], vehicle_filters)
        self.assertIn(["name", "=", "VEH-REPORT-A"], vehicle_filters)
        self.assertEqual(
            get_all.call_args.kwargs["filters"]["parent"],
            ["in", ["VEH-REPORT-A"]],
        )
        self.assertEqual(
            get_all.call_args.kwargs["filters"]["parentfield"],
            "vehicle_documents",
        )

    def test_fleet_cost_report_scopes_aggregates_to_permission_visible_vehicles(self):
        from sotrama.tp.report.fleet_cost_analysis.fleet_cost_analysis import get_data

        visible_vehicle = frappe._dict(
            name="VEH-COST-A",
            docstatus=1,
            license_plate="COST-A",
            company="COMPANY-A",
            acquisition_date=None,
            acquisition_value=0,
            depreciation_rate=0,
            salvage_value=0,
        )
        maintenance_row = frappe._dict(
            vehicle="VEH-COST-A", parts_cost=100, labour_cost=50, other_cost=10
        )
        distance_row = frappe._dict(vehicle="VEH-COST-A", distance_km=100)
        with (
            patch.object(
                frappe,
                "get_list",
                side_effect=[[visible_vehicle], [maintenance_row], [distance_row]],
            ) as get_list,
            patch.object(frappe.db, "get_default", return_value="DZD"),
        ):
            rows = get_data(frappe._dict(company="COMPANY-A"))

        self.assertEqual(len(rows), 1)
        calls = get_list.call_args_list
        self.assertEqual(calls[0].args[0], "Vehicle")
        self.assertIn(["docstatus", "=", 1], calls[0].kwargs["filters"])
        self.assertIn(["company", "=", "COMPANY-A"], calls[0].kwargs["filters"])
        for call in calls[1:]:
            self.assertIn(["vehicle", "in", ["VEH-COST-A"]], call.kwargs["filters"])

    def test_fleet_cost_report_uses_frappe_16_aggregate_field_syntax(self):
        # Exercise the real Frappe 16 query parser, not just mocked get_list calls.
        maintenance_rows = frappe.get_list(
            "Maintenance Job Card",
            fields=[
                "vehicle",
                {"SUM": "total_parts_cost", "as": "parts_cost"},
                {"SUM": "total_labour_cost", "as": "labour_cost"},
                {"SUM": "total_other_cost", "as": "other_cost"},
            ],
            filters={"name": "__sotrama_missing_maintenance_job_card__"},
            group_by="vehicle",
            limit_page_length=0,
        )
        distance_rows = frappe.get_list(
            "Operational Task",
            fields=["vehicle", {"SUM": "distance_covered", "as": "distance_km"}],
            filters={"name": "__sotrama_missing_operational_task__"},
            group_by="vehicle",
            limit_page_length=0,
        )

        self.assertEqual(maintenance_rows, [])
        self.assertEqual(distance_rows, [])

    def test_fleet_cost_report_depreciation_counts_inclusive_single_day_period(self):
        from sotrama.tp.report.fleet_cost_analysis.fleet_cost_analysis import (
            _estimate_depreciation,
        )

        report_date = today()
        vehicle = frappe._dict(
            acquisition_date=report_date,
            acquisition_value=365000,
            depreciation_rate=10,
            salvage_value=0,
        )
        depreciation = _estimate_depreciation(
            vehicle,
            frappe._dict(from_date=report_date, to_date=report_date),
        )

        self.assertEqual(depreciation, 100)

    def test_fleet_cost_report_does_not_depreciate_beyond_salvage_value(self):
        from frappe.utils import add_days

        from sotrama.tp.report.fleet_cost_analysis import fleet_cost_analysis

        acquisition_date = "2020-01-01"
        period_start = add_days(acquisition_date, 3650)
        period_end = add_days(period_start, 364)
        vehicle = frappe._dict(
            acquisition_date=acquisition_date,
            acquisition_value=365000,
            depreciation_rate=10,
            salvage_value=36500,
        )

        with patch.object(fleet_cost_analysis, "today", return_value=period_end):
            depreciation = fleet_cost_analysis._estimate_depreciation(
                vehicle,
                frappe._dict(from_date=period_start, to_date=period_end),
            )

        self.assertEqual(depreciation, 0)

    def test_fleet_cost_report_caps_period_depreciation_at_remaining_basis(self):
        from frappe.utils import add_days

        from sotrama.tp.report.fleet_cost_analysis import fleet_cost_analysis

        acquisition_date = "2020-01-01"
        period_start = add_days(acquisition_date, 3600)
        period_end = add_days(period_start, 364)
        depreciable_value = 328500
        vehicle = frappe._dict(
            acquisition_date=acquisition_date,
            acquisition_value=365000,
            depreciation_rate=10,
            salvage_value=36500,
        )

        with patch.object(fleet_cost_analysis, "today", return_value=period_end):
            depreciation = fleet_cost_analysis._estimate_depreciation(
                vehicle,
                frappe._dict(from_date=period_start, to_date=period_end),
            )

        expected_remaining_basis = depreciable_value - (
            depreciable_value * 0.10 * 3600 / 365
        )
        self.assertAlmostEqual(depreciation, expected_remaining_basis)

    def test_fleet_cost_report_ignores_invalid_depreciation_inputs(self):
        from sotrama.tp.report.fleet_cost_analysis.fleet_cost_analysis import (
            _estimate_depreciation,
        )

        report_date = today()
        base_vehicle = {
            "acquisition_date": add_days(report_date, -365),
            "acquisition_value": 365000,
            "depreciation_rate": 10,
            "salvage_value": 0,
        }
        invalid_vehicles = (
            {**base_vehicle, "acquisition_value": -1},
            {**base_vehicle, "salvage_value": -1},
            {**base_vehicle, "salvage_value": 365001},
            {**base_vehicle, "depreciation_rate": -1},
            {**base_vehicle, "depreciation_rate": 101},
        )
        filters = frappe._dict(from_date=report_date, to_date=report_date)

        for values in invalid_vehicles:
            with self.subTest(values=values):
                self.assertEqual(
                    _estimate_depreciation(frappe._dict(values), filters), 0
                )

    def test_fleet_print_formats_use_the_frappe_16_builder(self):

        formats = (
            ("Maintenance Job Card Report", "Maintenance Job Card"),
            ("Vehicle Inspection Report", "Vehicle Inspection"),
        )

        def normalized_options(options):
            return [option for option in (options or "").splitlines() if option]

        for name, doctype in formats:
            print_format = frappe.get_doc("Print Format", name)
            self.assertEqual(print_format.doc_type, doctype)
            self.assertTrue(print_format.print_format_builder_beta)
            self.assertFalse(print_format.custom_format)
            self.assertIn(
                print_format.pdf_generator or "",
                {"", "chrome"},
                "Do not pin Builder Beta formats to PlutoPrint or a non-default renderer.",
            )
            layout = json.loads(print_format.format_data)
            self.assertIsInstance(layout, dict)
            self.assertTrue(layout.get("sections"))
            self.assertIn(
                layout.get("page", {}).get("size"), {"A4", "Letter", "Legal", "A3"}
            )
            meta = frappe.get_meta(doctype, cached=False)

            custom_names = set()
            zones = [
                layout.get("header", {}),
                *layout["sections"],
                layout.get("footer", {}),
            ]
            for zone in zones:
                for column in zone.get("columns", []):
                    for field in column.get("fields", []):
                        if field.get("custom"):
                            self.assertTrue(field.get("fieldname"))
                            self.assertNotIn(field["fieldname"], custom_names)
                            custom_names.add(field["fieldname"])
                            continue
                        docfield = meta.get_field(field["fieldname"])
                        self.assertIsNotNone(
                            docfield,
                            f"{name}: unknown field {doctype}.{field['fieldname']}",
                        )
                        self.assertEqual(field.get("fieldtype"), docfield.fieldtype)
                        if docfield.fieldtype == "Select" and docfield.options:
                            self.assertEqual(
                                normalized_options(field.get("options")),
                                normalized_options(docfield.options),
                            )
                        elif docfield.options:
                            self.assertEqual(field.get("options"), docfield.options)
                        if field.get("fieldtype") == "Table":
                            self.assertEqual(docfield.fieldtype, "Table")
                            self.assertEqual(docfield.options, field.get("options"))
                            child_meta = frappe.get_meta(docfield.options, cached=False)
                            for table_column in field.get("table_columns", []):
                                child_field = child_meta.get_field(
                                    table_column["fieldname"]
                                )
                                self.assertIsNotNone(
                                    child_field,
                                    f"{name}: unknown child field {docfield.options}.{table_column['fieldname']}",
                                )
                                self.assertEqual(
                                    table_column.get("fieldtype"), child_field.fieldtype
                                )
                                if (
                                    child_field.fieldtype == "Select"
                                    and child_field.options
                                ):
                                    self.assertEqual(
                                        normalized_options(table_column.get("options")),
                                        normalized_options(child_field.options),
                                    )
                                elif child_field.options:
                                    self.assertEqual(
                                        table_column.get("options"), child_field.options
                                    )

            if doctype == "Maintenance Job Card":
                printed_fields = {
                    field.get("fieldname")
                    for section in layout["sections"]
                    for column in section.get("columns", [])
                    for field in column.get("fields", [])
                }
                self.assertIn("maintenance_schedule", printed_fields)
