import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load_doctype(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_payroll_rule_requires_legal_source_and_review_fields():
    rule = load_doctype(
        "sotrama/sotrama_core/doctype/sotrama_payroll_rule/sotrama_payroll_rule.json"
    )
    fields = {field["fieldname"]: field for field in rule["fields"]}

    assert rule["name"] == "Sotrama Payroll Rule"
    assert rule["module"] == "Sotrama Core"
    for fieldname in (
        "rule_code",
        "rule_version",
        "authority",
        "source_title",
        "legal_reference",
        "source_url",
        "effective_from",
        "base_definition",
        "status",
    ):
        assert fields[fieldname]["reqd"] == 1


def test_payroll_audit_keeps_rule_and_input_snapshots():
    audit = load_doctype(
        "sotrama/sotrama_hr_payroll/doctype/sotrama_payroll_audit/sotrama_payroll_audit.json"
    )
    fields = {field["fieldname"]: field for field in audit["fields"]}

    assert audit["name"] == "Sotrama Payroll Audit"
    assert audit["is_submittable"] == 1
    assert fields["salary_slip"]["unique"] == 1
    assert fields["rule_versions"]["reqd"] == 1
    assert fields["input_snapshot"]["reqd"] == 1
    assert fields["calculation_snapshot"]["reqd"] == 1


def test_sotrama_settings_are_a_singleton_with_review_defaults():
    settings = load_doctype("sotrama/sotrama_core/doctype/sotrama_settings/sotrama_settings.json")
    fields = {field["fieldname"]: field for field in settings["fields"]}

    assert settings["name"] == "Sotrama Settings"
    assert settings["issingle"] == 1
    assert fields["country"]["default"] == "Algeria"
    assert fields["payroll_review_required"]["default"] == "1"
    assert fields["legal_rules_review_required"]["default"] == "1"


def test_role_fixtures_define_permission_roles():
    roles = json.loads((ROOT / "sotrama/fixtures/role.json").read_text(encoding="utf-8"))
    names = {role["role_name"] for role in roles}
    assert "Sotrama Payroll Manager" in names
    assert "Sotrama Compliance Manager" in names
