import unittest
from unittest.mock import patch

import frappe

# Frappe integration tests for Sotrama company classification behavior.
from sotrama.tests.helpers import (
    _get_test_company,
)


class TestCompanyClassification(unittest.TestCase):
    """Test Company Classification score calculation."""

    def test_grade_score_mismatch_uses_frappe_16_msgprint_signature(self):
        classification = frappe.new_doc("Company Classification")
        classification.grade = 8
        classification.total_score = 10

        with patch("frappe.msgprint") as msgprint:
            classification._verify_grade_range()

        msgprint.assert_called_once()
        message = msgprint.call_args.args[0]
        self.assertIn("Total score 10", message)
        self.assertEqual(msgprint.call_args.kwargs["title"], "Score Mismatch")
        self.assertEqual(msgprint.call_args.kwargs["indicator"], "orange")

    def test_grade_8_score_range(self):
        """Test that Grade 8 falls in the correct score range (63.0 - 72.8)."""
        classification = frappe.new_doc("Company Classification")
        classification.company = _get_test_company()
        classification.grade = 8
        classification.category = "Public Works (TP)"
        classification.registration_number = "TEST-GRADE-8"
        # Set scores that should total in Grade 8 range
        classification.effectif_score = 8
        classification.effectif_coefficient = 1.0
        classification.encadrement_score = 4
        classification.encadrement_coefficient = 1.0
        classification.apprentice_score = 2
        classification.apprentice_coefficient = 1.0
        classification.training_score = 2
        classification.training_coefficient = 1.0
        classification.material_value_score = 10
        classification.material_value_coefficient = 1.0
        classification.capital_score = 8
        classification.capital_coefficient = 1.0
        classification.revenue_score = 9
        classification.revenue_coefficient = 1.0
        classification.abe_score = 1.0
        classification.abe_coefficient = 1.0

        classification.validate()

        # NT should be around 64-72 for Grade 8
        self.assertGreater(classification.total_score, 63.0)
        self.assertLessEqual(classification.total_score, 72.8)


class TestCompanyClassificationIntegration(unittest.TestCase):
    """Domain-focused integration coverage extracted from the former setup monolith."""

    def test_company_classification_can_be_assigned_to_a_legal_entity(self):
        meta = frappe.get_meta("Company Classification", cached=False)
        company = meta.get_field("company")
        self.assertIsNotNone(company)
        self.assertEqual(company.fieldtype, "Link")
        self.assertEqual(company.options, "Company")

    def test_company_classification_default_maps_to_child_table_field(self):
        from sotrama.tp.settings import get_tp_company_setting

        with (
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
            patch("sotrama.tp.settings.frappe.db.exists", return_value=True),
            patch(
                "sotrama.tp.settings.frappe.db.get_value", return_value="CLASS-A"
            ) as get_value,
            patch("sotrama.tp.settings.get_tp_setting") as get_setting,
        ):
            result = get_tp_company_setting(
                "COMPANY-A", "default_company_classification", "Vehicle"
            )

        self.assertEqual(result, "CLASS-A")
        validate_company.assert_called_once_with("COMPANY-A", "Vehicle")
        self.assertEqual(get_value.call_args.args[2], "company_classification")
        get_setting.assert_not_called()

        with (
            patch("sotrama.tp.settings.validate_company_access"),
            patch("sotrama.tp.settings.frappe.db.exists", return_value=True),
            patch(
                "sotrama.tp.settings.frappe.db.get_value", return_value=None
            ) as get_value,
            patch(
                "sotrama.tp.settings.get_tp_setting",
                side_effect=lambda fieldname, default=None: {
                    "default_company": "COMPANY-A",
                    "default_company_classification": "PRIMARY-CLASS",
                }.get(fieldname, default),
            ) as get_setting,
        ):
            result = get_tp_company_setting(
                "COMPANY-A", "default_company_classification", "Vehicle"
            )

        self.assertEqual(result, "PRIMARY-CLASS")
        self.assertEqual(get_value.call_args.args[2], "company_classification")
        get_setting.assert_any_call("default_company_classification")

        with (
            patch("sotrama.tp.settings.validate_company_access"),
            patch("sotrama.tp.settings.frappe.db.exists", return_value=True),
            patch("sotrama.tp.settings.frappe.db.get_value", return_value=None),
            patch(
                "sotrama.tp.settings.get_tp_setting",
                side_effect=lambda fieldname, default=None: {
                    "default_company": "COMPANY-A",
                    "default_cost_center": "PRIMARY-COST-CENTER",
                }.get(fieldname, default),
            ),
        ):
            self.assertEqual(
                get_tp_company_setting("COMPANY-A", "default_cost_center", "Vehicle"),
                "PRIMARY-COST-CENTER",
            )

        with (
            patch("sotrama.tp.settings.validate_company_access"),
            patch("sotrama.tp.settings.frappe.db.exists", return_value=True),
            patch("sotrama.tp.settings.frappe.db.get_value", return_value=None),
            patch(
                "sotrama.tp.settings.get_tp_setting",
                side_effect=lambda fieldname, default=None: (
                    "COMPANY-A" if fieldname == "default_company" else "GLOBAL-COST"
                ),
            ),
        ):
            self.assertIsNone(
                get_tp_company_setting("COMPANY-B", "default_cost_center", "Vehicle")
            )
