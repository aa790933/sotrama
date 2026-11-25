import json
import unittest
from unittest.mock import Mock, patch

import frappe

from sotrama.tests.helpers import _sotrama_package_path

# Frappe integration tests for Sotrama permissions behavior.


class TestTpSettingsFieldPermissions(unittest.TestCase):
    """Single-value RPCs must not bypass TP Settings field permlevels."""

    def test_single_value_and_value_endpoints_enforce_tp_settings_permlevels(self):
        from sotrama.permissions import (
            COMPANY_SCOPED_FLEET_DOCTYPES,
            get_list_with_tp_settings_permissions,
            get_single_value_with_tp_settings_field_permissions,
            get_value_with_tp_settings_field_permissions,
            prevent_unsafe_fleet_docsharing,
            remove_unsafe_fleet_docshares,
            tp_company_defaults_query_conditions,
            tp_settings_query_conditions,
            validate_link_and_fetch_without_tp_settings_singleton,
        )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("frappe.has_permission", return_value=True),
            self.assertRaises(frappe.PermissionError),
        ):
            get_single_value_with_tp_settings_field_permissions(
                "TP Settings", "require_employee_link"
            )

        with (
            patch.dict(frappe.session, {"user": "hr@example.invalid"}),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.has_permission", return_value=True),
            self.assertRaises(frappe.PermissionError),
        ):
            get_single_value_with_tp_settings_field_permissions(
                "TP Settings", "default_company"
            )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("frappe.has_permission", return_value=True),
            self.assertRaises(frappe.PermissionError),
        ):
            get_value_with_tp_settings_field_permissions(
                "TP Settings",
                "driver_document_alert_days",
                filters={"name": "TP Settings"},
            )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("frappe.has_permission", return_value=True),
            self.assertRaises(frappe.PermissionError),
        ):
            get_value_with_tp_settings_field_permissions(
                "TP Settings", "driver_document_alert_days", filters={}
            )

        for doctype in ("TP Settings", "TP Company Defaults"):
            with self.assertRaises(frappe.PermissionError):
                validate_link_and_fetch_without_tp_settings_singleton(
                    doctype, "TP Settings", ["default_company"]
                )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            get_list_with_tp_settings_permissions(
                "TP Settings", fields=["default_company"]
            )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            get_list_with_tp_settings_permissions(
                "TP Company Defaults",
                fields=["company", "default_cost_center"],
                filters={"parent": "TP Settings"},
                parent="TP Settings",
            )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            get_value_with_tp_settings_field_permissions(
                "TP Company Defaults",
                "company",
                filters={"parent": "TP Settings"},
                parent="TP Settings",
            )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
        ):
            self.assertEqual(tp_company_defaults_query_conditions(), "1=0")
            self.assertEqual(tp_settings_query_conditions(), "1=0")

        with (
            patch.dict(frappe.session, {"user": "system@example.invalid"}),
            patch("frappe.get_roles", return_value=["System Manager"]),
        ):
            self.assertIsNone(tp_company_defaults_query_conditions())
            self.assertIsNone(tp_settings_query_conditions())

        for doctype in ("TP Settings", "TP Company Defaults"):
            with self.assertRaises(frappe.PermissionError):
                prevent_unsafe_fleet_docsharing(
                    frappe._dict(share_doctype=doctype, read=1)
                )

        fleet_share = frappe._dict(
            share_doctype="Vehicle",
            share_name="VEH-001",
            user="recipient@example.invalid",
            everyone=0,
            read=1,
        )
        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(fleet_share)

        target = frappe._dict(doctype="Vehicle", name="VEH-001")
        with (
            patch.dict(frappe.session, {"user": "system@example.invalid"}),
            patch("frappe.get_roles", return_value=["System Manager"]),
            patch("frappe.get_doc", return_value=target),
            patch("frappe.has_permission", return_value=True) as has_permission,
        ):
            prevent_unsafe_fleet_docsharing(fleet_share)
        has_permission.assert_called_once_with(
            "Vehicle",
            "read",
            doc=target,
            user="recipient@example.invalid",
            ignore_share_permissions=True,
        )

        with (
            patch.dict(frappe.session, {"user": "system@example.invalid"}),
            patch("frappe.get_roles", return_value=["System Manager"]),
            patch(
                "frappe.get_doc",
                return_value=frappe._dict(doctype="Vehicle", name="VEH-001"),
            ),
            patch("frappe.has_permission", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(fleet_share)

        everyone_share = frappe._dict(
            share_doctype="Vehicle",
            share_name="VEH-001",
            user=None,
            everyone=1,
            read=1,
        )
        with (
            patch.dict(frappe.session, {"user": "system@example.invalid"}),
            patch("frappe.get_roles", return_value=["System Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(everyone_share)

        with (
            patch.dict(frappe.session, {"user": "system@example.invalid"}),
            patch("frappe.get_roles", return_value=["System Manager"]),
        ):
            prevent_unsafe_fleet_docsharing(
                frappe._dict(
                    share_doctype="Vehicle", read=0, write=0, submit=0, share=0
                )
            )

        prevent_unsafe_fleet_docsharing(frappe._dict(share_doctype="Vehicle Make"))

        with (
            patch(
                "frappe.get_doc",
                return_value=frappe._dict(
                    name="FILE-PRIVATE", sotrama_private_driver_attachment=1
                ),
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(
                frappe._dict(share_doctype="File", share_name="FILE-PRIVATE", read=1)
            )

        for doctype in ("TP Settings", "TP Company Defaults"):
            prevent_unsafe_fleet_docsharing(
                frappe._dict(share_doctype=doctype, read=0, write=0, submit=0, share=0)
            )
        with patch(
            "frappe.get_doc",
            return_value=frappe._dict(
                name="FILE-PRIVATE", sotrama_private_driver_attachment=1
            ),
        ):
            prevent_unsafe_fleet_docsharing(
                frappe._dict(
                    share_doctype="File",
                    share_name="FILE-PRIVATE",
                    read=0,
                    write=0,
                    submit=0,
                    share=0,
                )
            )

        shares = [
            frappe._dict(
                name="safe-share",
                owner="system@example.invalid",
                share_doctype="Vehicle",
                share_name="VEH-001",
                user="allowed@example.invalid",
                everyone=0,
                read=1,
                write=0,
                submit=0,
                share=0,
            ),
            frappe._dict(
                name="unsafe-share",
                owner="fleet@example.invalid",
                share_doctype="Vehicle",
                share_name="VEH-002",
                user="denied@example.invalid",
                everyone=0,
                read=1,
                write=0,
                submit=0,
                share=0,
            ),
            frappe._dict(
                name="everyone-share",
                owner="system@example.invalid",
                share_doctype="Vehicle",
                share_name="VEH-003",
                user=None,
                everyone=1,
                read=1,
                write=0,
                submit=0,
                share=0,
            ),
            frappe._dict(
                name="unauthorized-share",
                owner="system@example.invalid",
                share_doctype="Vehicle",
                share_name="VEH-004",
                user="restricted@example.invalid",
                everyone=0,
                read=1,
                write=0,
                submit=0,
                share=0,
            ),
        ]
        with (
            patch("frappe.db.delete") as delete,
            patch(
                "frappe.get_all",
                side_effect=[
                    [],
                    shares,
                    [frappe._dict(name="private-file-share", share_name="FILE-001")],
                ],
            ) as get_all,
            patch(
                "frappe.get_doc",
                side_effect=lambda doctype, name: (
                    frappe._dict(
                        name=name,
                        sotrama_private_driver_attachment=1,
                    )
                    if doctype == "File"
                    else frappe._dict(name=name)
                ),
            ),
            patch("frappe.has_permission", side_effect=[True, False]) as has_permission,
            patch(
                "frappe.get_roles",
                side_effect=lambda user: (
                    ["System Manager"]
                    if user.startswith("system")
                    else ["Fleet Manager"]
                ),
            ),
        ):
            remove_unsafe_fleet_docshares()
        self.assertEqual(get_all.call_args_list[0].args, ("DocShare",))
        self.assertEqual(
            get_all.call_args_list[0].kwargs,
            {
                "filters": {
                    "share_doctype": ["in", ["TP Settings", "TP Company Defaults"]]
                },
                "or_filters": None,
                "fields": ["name"],
            },
        )
        self.assertEqual(
            get_all.call_args_list[1].args,
            ("DocShare",),
        )
        self.assertEqual(
            get_all.call_args_list[1].kwargs,
            {
                "filters": {
                    "share_doctype": ["in", sorted(COMPANY_SCOPED_FLEET_DOCTYPES)]
                },
                "or_filters": None,
                "fields": [
                    "name",
                    "owner",
                    "share_doctype",
                    "share_name",
                    "user",
                    "everyone",
                    "read",
                    "write",
                    "submit",
                    "share",
                ],
            },
        )
        self.assertEqual(
            get_all.call_args_list[2].args,
            ("DocShare",),
        )
        self.assertEqual(
            get_all.call_args_list[2].kwargs,
            {
                "filters": {"share_doctype": "File"},
                "or_filters": None,
                "fields": ["name", "share_name"],
            },
        )
        self.assertEqual(has_permission.call_count, 2)
        delete.assert_any_call("DocShare", {"name": "private-file-share"})
        delete.assert_any_call("DocShare", {"name": "unsafe-share"})
        delete.assert_any_call("DocShare", {"name": "everyone-share"})
        delete.assert_any_call("DocShare", {"name": "unauthorized-share"})
        deleted_names = [
            call.args[1].get("name")
            for call in delete.call_args_list
            if len(call.args) > 1 and isinstance(call.args[1], dict)
        ]
        self.assertNotIn("safe-share", deleted_names)

        with (
            patch.dict(frappe.session, {"user": "hr@example.invalid"}),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.has_permission", return_value=True),
            patch("frappe.client.get_single_value", return_value="1"),
        ):
            self.assertEqual(
                get_single_value_with_tp_settings_field_permissions(
                    "TP Settings", "require_employee_link"
                ),
                "1",
            )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("frappe.has_permission", return_value=True),
            self.assertRaises(frappe.PermissionError),
        ):
            get_value_with_tp_settings_field_permissions(
                "TP Settings", "default_company"
            )

    def test_fleet_docshare_cannot_override_company_user_permissions(self):
        from sotrama.permissions import enforce_fleet_company_user_permissions

        vehicle = frappe._dict(doctype="Vehicle", name="VEH-001", company="COMPANY-B")
        with (
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch(
                "sotrama.tp.settings.validate_company_access",
                side_effect=frappe.PermissionError,
            ) as validate_company,
            self.assertRaises(frappe.PermissionError),
        ):
            enforce_fleet_company_user_permissions(
                vehicle, user="fleet@example.invalid", ptype="read"
            )
        validate_company.assert_called_once_with(
            "COMPANY-B", "Vehicle", user="fleet@example.invalid"
        )

        with (
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("sotrama.tp.settings.validate_company_access"),
            patch("frappe.permissions.has_user_permission", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            enforce_fleet_company_user_permissions(
                vehicle, user="fleet@example.invalid", ptype="read"
            )

        with (
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("sotrama.tp.settings.validate_company_access"),
            patch("frappe.permissions.has_user_permission", return_value=True),
        ):
            self.assertTrue(
                enforce_fleet_company_user_permissions(
                    vehicle, user="fleet@example.invalid", ptype="read"
                )
            )

    def test_share_cleanup_runs_after_user_permission_and_fleet_company_changes(self):
        from sotrama.permissions import (
            remove_unsafe_fleet_docshares_for_document,
            remove_unsafe_fleet_docshares_for_user,
        )

        with patch("sotrama.permissions.remove_unsafe_fleet_docshares") as cleanup:
            remove_unsafe_fleet_docshares_for_user(
                frappe._dict(doctype="User Permission", user="fleet@example.invalid")
            )
            cleanup.assert_called_once_with(user="fleet@example.invalid")

        with patch("sotrama.permissions.remove_unsafe_fleet_docshares") as cleanup:
            remove_unsafe_fleet_docshares_for_user(
                frappe._dict(doctype="User", name="fleet@example.invalid")
            )
            cleanup.assert_called_once_with(
                user="fleet@example.invalid", owner="fleet@example.invalid"
            )

        with patch("sotrama.permissions.remove_unsafe_fleet_docshares") as cleanup:
            remove_unsafe_fleet_docshares_for_user(
                frappe._dict(
                    doctype="Has Role",
                    parenttype="User",
                    parent="fleet@example.invalid",
                )
            )
            cleanup.assert_called_once_with(
                user="fleet@example.invalid", owner="fleet@example.invalid"
            )

        with patch("sotrama.permissions.remove_unsafe_fleet_docshares") as cleanup:
            remove_unsafe_fleet_docshares_for_document(
                frappe._dict(doctype="Vehicle", name="VEH-001")
            )
            cleanup.assert_called_once_with(doctype="Vehicle", name="VEH-001")

    def test_deleted_fleet_record_cannot_leave_a_stale_docshare(self):
        from sotrama.permissions import remove_unsafe_fleet_docshares

        share = frappe._dict(
            name="SHARE-STALE",
            owner="system@example.invalid",
            share_doctype="Vehicle",
            share_name="VEH-DELETED",
            user="fleet@example.invalid",
            everyone=0,
            read=1,
            write=0,
            submit=0,
            share=0,
        )
        with (
            patch("frappe.get_all", return_value=[share]),
            patch("frappe.get_roles", return_value=["System Manager"]),
            patch("frappe.get_doc", side_effect=frappe.DoesNotExistError),
            patch("frappe.db.delete") as delete,
        ):
            remove_unsafe_fleet_docshares(doctype="Vehicle", name="VEH-DELETED")
        delete.assert_called_once_with("DocShare", {"name": "SHARE-STALE"})

    def test_role_demotion_removes_shares_owned_by_former_system_manager(self):
        from sotrama.permissions import remove_unsafe_fleet_docshares

        share = frappe._dict(
            name="SHARE-OWNED",
            owner="former-manager@example.invalid",
            share_doctype="Vehicle",
            share_name="VEH-001",
            user="recipient@example.invalid",
            everyone=0,
            read=1,
            write=0,
            submit=0,
            share=0,
        )
        with (
            patch("frappe.get_all", side_effect=[[], [share], []]) as get_all,
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("frappe.db.delete") as delete,
        ):
            remove_unsafe_fleet_docshares(
                user="former-manager@example.invalid",
                owner="former-manager@example.invalid",
            )
        delete.assert_called_once_with("DocShare", {"name": "SHARE-OWNED"})
        self.assertEqual(
            get_all.call_args_list[1].kwargs["or_filters"],
            [
                ["DocShare", "user", "=", "former-manager@example.invalid"],
                ["DocShare", "owner", "=", "former-manager@example.invalid"],
            ],
        )

    def test_share_cleanup_preserves_original_owner_filter_for_file_shares(self):
        from sotrama.permissions import remove_unsafe_fleet_docshares

        share = frappe._dict(
            name="SHARE-RECEIVED",
            owner="system@example.invalid",
            share_doctype="Vehicle",
            share_name="VEH-001",
            user="former-manager@example.invalid",
            everyone=0,
            read=1,
            write=0,
            submit=0,
            share=0,
        )
        with (
            patch("frappe.get_all", side_effect=[[], [share], []]) as get_all,
            patch("frappe.get_roles", return_value=["System Manager"]),
            patch("frappe.get_doc", return_value=frappe._dict(name="VEH-001")),
            patch("frappe.has_permission", return_value=True),
        ):
            remove_unsafe_fleet_docshares(
                user="former-manager@example.invalid",
                owner="former-manager@example.invalid",
            )

        self.assertEqual(
            get_all.call_args_list[2].kwargs["or_filters"],
            [
                ["DocShare", "user", "=", "former-manager@example.invalid"],
                ["DocShare", "owner", "=", "former-manager@example.invalid"],
            ],
        )

    def test_non_system_manager_cannot_change_company_defaults_but_can_save_other_settings(
        self,
    ):
        previous = frappe.new_doc("TP Settings")
        previous.default_company = "COMPANY-A"
        previous.append("company_defaults", {"company": "COMPANY-A", "active": 1})
        current = frappe.new_doc("TP Settings")
        current.default_company = "COMPANY-B"
        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch.object(current, "get_doc_before_save", return_value=previous),
        ):
            current._validate_company_defaults_permissions()

        self.assertEqual(current.default_company, "COMPANY-A")
        self.assertEqual(current.company_defaults[0].company, "COMPANY-A")

        new_settings = frappe.new_doc("TP Settings")
        new_settings.default_company = "COMPANY-B"
        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            new_settings._validate_company_defaults_permissions()

    def test_docshare_allows_only_system_manager_with_recipient_company_scope(self):
        from sotrama.permissions import prevent_unsafe_fleet_docsharing

        share = frappe._dict(
            share_doctype="Vehicle",
            share_name="VEH-001",
            user="recipient@example.invalid",
            everyone=0,
            read=1,
        )
        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(share)

        with (
            patch.dict(frappe.session, {"user": "system@example.invalid"}),
            patch("frappe.get_roles", return_value=["System Manager"]),
            patch("frappe.get_doc", return_value=frappe._dict(name="VEH-001")),
            patch("frappe.has_permission", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(share)


class TestFleetLinkedDocumentPermissions(unittest.TestCase):
    def test_linked_document_access_checks_the_exact_target_record(self):
        from sotrama.tp.validation import validate_linked_document_read_permission

        with (
            patch("frappe.has_permission", side_effect=frappe.PermissionError) as check,
            self.assertRaises(frappe.PermissionError),
        ):
            validate_linked_document_read_permission("Vehicle", "VEH-COMPANY-B")

        check.assert_called_once_with(
            "Vehicle", "read", doc="VEH-COMPANY-B", throw=True
        )

        with patch("frappe.has_permission", return_value=True) as check:
            validate_linked_document_read_permission("Vehicle", None)
        check.assert_not_called()

    def test_active_driver_projection_checks_employee_company_scope(self):
        from sotrama.tp.validation import validate_active_driver

        driver = frappe._dict(
            company="COMPANY-A",
            status="Active",
            docstatus=1,
            employee="EMP-001",
            license_expiry=None,
            medical_expiry=None,
            safety_training_expiry=None,
        )
        employee = frappe._dict(company="COMPANY-A", status="Active")
        with (
            patch("frappe.has_permission", return_value=True),
            patch("frappe.db.get_value", side_effect=[driver, employee]) as get_value,
            patch(
                "sotrama.tp.validation.get_tp_setting",
                side_effect=lambda key, default=0: (
                    1 if key == "require_active_employee_for_active_driver" else 0
                ),
            ),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
        ):
            validate_active_driver("DRV-001", "COMPANY-A")

        validate_company.assert_any_call("COMPANY-A", "Driver")
        validate_company.assert_any_call("COMPANY-A", "Employee")
        self.assertEqual(
            get_value.call_args_list[1].args[:2],
            ("Employee", {"name": "EMP-001", "company": "COMPANY-A"}),
        )

    def test_transport_activity_cannot_be_used_to_bypass_task_type(self):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        task = frappe._dict(
            vehicle="VEH-COMPANY-A",
            company="COMPANY-A",
            task_type="Earthmoving",
            transport_kind="Goods Transport",
            project=None,
        )
        with (
            patch("frappe.has_permission", return_value=True),
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(
                    vehicle_status="Active", company="COMPANY-A", docstatus=1
                ),
            ),
            patch("sotrama.tp.settings.validate_company_access"),
            self.assertRaises(frappe.ValidationError),
        ):
            OperationalTask._validate_vehicle(task)

    def test_vehicle_availability_only_blocks_new_or_changed_operational_tasks(self):
        task = frappe.new_doc("Operational Task")
        task.vehicle = "VEHICLE-A"
        task.company = "COMPANY-A"
        task.task_type = "Earthmoving"
        unavailable_vehicle = frappe._dict(
            vehicle_status="Out of Service", company="COMPANY-A", docstatus=1
        )
        with (
            patch("frappe.has_permission", return_value=True),
            patch("frappe.db.get_value", return_value=unavailable_vehicle),
            patch("sotrama.tp.settings.validate_company_access"),
            self.assertRaises(frappe.ValidationError),
        ):
            task._validate_vehicle()

        with (
            patch.object(
                task,
                "get_doc_before_save",
                return_value=frappe._dict(vehicle=task.vehicle),
            ),
            patch("frappe.has_permission", return_value=True),
            patch("frappe.db.get_value", return_value=unavailable_vehicle),
            patch("sotrama.tp.settings.validate_company_access"),
        ):
            task._validate_vehicle()

    def test_transport_task_requires_an_explicit_activity(self):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        task = frappe._dict(
            vehicle="VEH-COMPANY-A",
            company="COMPANY-A",
            task_type="Transport",
            transport_kind=None,
            project=None,
        )
        with (
            patch("frappe.has_permission", return_value=True),
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(
                    vehicle_status="Active", company="COMPANY-A", docstatus=1
                ),
            ),
            patch("sotrama.tp.settings.validate_company_access"),
            self.assertRaises(frappe.ValidationError),
        ):
            OperationalTask._validate_vehicle(task)

    def test_transport_submission_waits_for_regulatory_confirmation(self):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        task = frappe._dict(
            name="OT-EVIDENCE-001",
            task_type="Transport",
            transport_kind="Goods Transport",
            transport_basis="Own-Account Transport",
            transport_regulatory_status="To Be Confirmed",
        )
        with self.assertRaises(frappe.ValidationError):
            OperationalTask._validate_transport_regulatory_applicability(task)

    def test_own_account_transport_requires_authority_evidence_before_regulated_submission(
        self,
    ):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        task = frappe.new_doc("Operational Task")
        task.task_type = "Transport"
        task.transport_kind = "Goods Transport"
        task.transport_basis = "Own-Account Transport"
        task.transport_regulatory_status = "Regulated"
        task.driver = "DRV-001"
        task.transport_authority_reference = "DECISION-001"
        task.transport_authority_decision_date = "2026-10-01"
        task.transport_authority_evidence = "/private/files/authority-decision.pdf"
        with (
            patch(
                "sotrama.tp.validation.validate_professional_transport_certificate"
            ) as validate_certificate,
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(name="FILE-AUTHORITY-001", is_remote_file=0),
            ),
            patch("frappe.has_permission", return_value=True),
        ):
            OperationalTask._validate_transport_regulatory_applicability(task)
        validate_certificate.assert_called_once_with("DRV-001", "Goods Transport")

    def test_nonregulated_transport_requires_official_authority_evidence(self):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        incomplete_task = frappe.new_doc("Operational Task")
        incomplete_task.task_type = "Transport"
        incomplete_task.transport_kind = "Goods Transport"
        incomplete_task.transport_basis = "Own-Account Transport"
        incomplete_task.transport_regulatory_status = "Officially Confirmed Not Subject"
        incomplete_task.transport_authority_reference = "DECISION-002"
        incomplete_task.transport_authority_decision_date = "2026-10-01"
        incomplete_task.transport_authority_evidence = None
        with self.assertRaises(frappe.ValidationError):
            OperationalTask._validate_transport_regulatory_applicability(
                incomplete_task
            )

        task = frappe.new_doc("Operational Task")
        task.task_type = "Transport"
        task.transport_kind = "Goods Transport"
        task.transport_basis = "Own-Account Transport"
        task.transport_regulatory_status = "Officially Confirmed Not Subject"
        task.transport_authority_reference = "DECISION-002"
        task.transport_authority_decision_date = "2026-10-01"
        task.transport_authority_evidence = "/private/files/authority-decision.pdf"
        with (
            patch(
                "sotrama.tp.validation.validate_professional_transport_certificate"
            ) as validate_certificate,
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(name="FILE-AUTHORITY-002", is_remote_file=0),
            ),
            patch("frappe.has_permission", return_value=True),
        ):
            OperationalTask._validate_transport_regulatory_applicability(task)
        validate_certificate.assert_not_called()

        task.transport_authority_decision_date = "2099-01-01"
        with self.assertRaises(frappe.ValidationError):
            OperationalTask._validate_transport_regulatory_applicability(task)

    def test_authority_evidence_must_be_a_local_file_attached_to_the_task_field(self):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        task = frappe.new_doc("Operational Task")
        task.task_type = "Transport"
        task.transport_kind = "Goods Transport"
        task.transport_basis = "Own-Account Transport"
        task.transport_regulatory_status = "Officially Confirmed Not Subject"
        task.transport_authority_reference = "DECISION-003"
        task.transport_authority_decision_date = "2026-10-01"
        task.transport_authority_evidence = "/private/files/authority-decision.pdf"
        with (
            patch("frappe.db.get_value", return_value=None),
            self.assertRaises(frappe.ValidationError),
        ):
            OperationalTask._validate_transport_regulatory_applicability(task)

        with (
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(name="FILE-REMOTE", is_remote_file=1),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            OperationalTask._validate_transport_regulatory_applicability(task)

    def test_operational_task_driver_is_conditional_for_regulated_transport(self):
        driver_field = frappe.get_meta("Operational Task", cached=False).get_field(
            "driver"
        )
        self.assertEqual(driver_field.label, "Driver / Operator")
        self.assertFalse(driver_field.reqd)
        self.assertEqual(
            driver_field.mandatory_depends_on,
            "eval:doc.task_type == 'Transport' && doc.transport_regulatory_status == 'Regulated'",
        )
        task_js = (
            _sotrama_package_path() / "public" / "js" / "operational_task.js"
        ).read_text(encoding="utf-8")
        self.assertIn("docstatus: 1", task_js)


class TestFleetSystemManagedFields(unittest.TestCase):
    """Protect controller-owned values from direct document/API writes."""

    def test_driver_incident_count_cannot_be_set_or_changed_by_users(self):
        driver = frappe.new_doc("Driver")
        driver.total_incidents = 3
        with self.assertRaises(frappe.ValidationError):
            driver._validate_system_managed_fields()

        driver.total_incidents = 4
        with (
            patch.object(
                driver,
                "get_doc_before_save",
                return_value=frappe._dict(total_incidents=2),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            driver._validate_system_managed_fields()

    def test_breakdown_status_and_job_card_link_are_server_managed(self):
        incident = frappe.new_doc("Breakdown Incident")
        incident.status = "Resolved"
        with self.assertRaises(frappe.ValidationError):
            incident._validate_status_transition()

        incident.status = "Reported"
        incident.linked_job_card = "JC-FORGED"
        with self.assertRaises(frappe.ValidationError):
            incident._validate_system_managed_fields()

        incident.linked_job_card = None
        incident.resolution_notes = "Forged resolution"
        with self.assertRaises(frappe.ValidationError):
            incident._validate_system_managed_fields()

    def test_inspection_issue_link_and_clearance_reference_are_server_managed(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        row = inspection.append(
            "inspection_items",
            {
                "category": "Test check",
                "item_details": "Test details",
                "status": "Okay",
                "linked_issue": "ISSUE-FORGED",
            },
        )
        with self.assertRaises(frappe.ValidationError):
            inspection._validate_system_managed_fields()

        row.linked_issue = None
        inspection.critical_defect_cleared_by = "INSP-FORGED"
        with self.assertRaises(frappe.ValidationError):
            inspection._validate_system_managed_fields()

    def test_maintenance_schedule_cannot_forge_next_schedule_or_start_paused(self):
        schedule = frappe.new_doc("Maintenance Schedule")
        schedule.next_schedule = "SCH-FORGED"
        with self.assertRaises(frappe.ValidationError):
            schedule._validate_system_managed_fields()

        schedule.next_schedule = None
        schedule.last_service_job_card = "JC-FORGED"
        with self.assertRaises(frappe.ValidationError):
            schedule._validate_system_managed_fields()

        schedule.last_service_job_card = None
        schedule.status = "Paused"
        with self.assertRaises(frappe.ValidationError):
            schedule._validate_status_transition()

        schedule.status = "Active"
        schedule.last_service_job_card = "JC-GENERATED"
        schedule.flags.from_schedule_generation = True
        with self.assertRaises(frappe.ValidationError):
            schedule._validate_system_managed_fields()
        with patch.dict(frappe.flags, {"in_maintenance_schedule_generation": True}):
            schedule._validate_system_managed_fields()

    def test_maintenance_job_card_cannot_forge_stock_or_schedule_links(self):
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.stock_entry = "MAT-STE-FORGED"
        with self.assertRaises(frappe.ValidationError):
            job_card._validate_system_managed_fields()

    def test_maintenance_job_card_breakdown_links_are_workflow_managed_and_company_scoped(
        self,
    ):
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.linked_breakdown = "BRK-FORGED"
        with self.assertRaises(frappe.ValidationError):
            job_card._validate_system_managed_fields()

        job_card.linked_breakdown = None
        job_card.linked_breakdown_incident = "BRK-TEST-001"
        with self.assertRaises(frappe.ValidationError):
            job_card._validate_system_managed_fields()

        job_card.flags.from_breakdown_incident = True
        with self.assertRaises(frappe.ValidationError):
            job_card._validate_system_managed_fields()

        job_card.company = "COMPANY-A"
        job_card.vehicle = "VEHICLE-A"
        with (
            patch.dict(frappe.flags, {"in_breakdown_job_card_creation": True}),
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(
                    company="COMPANY-A", vehicle="VEHICLE-A", docstatus=1
                ),
            ),
            patch("frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
        ):
            job_card._validate_system_managed_fields()
            job_card._validate_breakdown_links()

        for fieldname in ("linked_breakdown", "linked_breakdown_incident"):
            job_card.linked_breakdown = None
            job_card.linked_breakdown_incident = None
            setattr(job_card, fieldname, "BRK-CROSS-COMPANY")
            with (
                patch(
                    "frappe.db.get_value",
                    return_value=frappe._dict(
                        company="COMPANY-B", vehicle="VEHICLE-B", docstatus=1
                    ),
                ),
                patch("frappe.has_permission", return_value=True),
                patch("sotrama.tp.settings.validate_company_access"),
                self.assertRaises(frappe.ValidationError),
            ):
                job_card._validate_breakdown_links()

            for incident, message in (
                (
                    frappe._dict(company="COMPANY-A", vehicle="VEHICLE-B", docstatus=1),
                    "wrong Vehicle",
                ),
                (None, "missing Incident"),
                (
                    frappe._dict(company="COMPANY-A", vehicle="VEHICLE-A", docstatus=0),
                    "unsubmitted Incident",
                ),
            ):
                with (
                    self.subTest(fieldname=fieldname, message=message),
                    patch("frappe.db.get_value", return_value=incident),
                    patch("frappe.has_permission", return_value=True),
                    patch("sotrama.tp.settings.validate_company_access"),
                    self.assertRaises(frappe.ValidationError),
                ):
                    job_card._validate_breakdown_links()

        job_card.stock_entry = None
        job_card.linked_maintenance_schedule = "SCH-FORGED"
        with self.assertRaises(frappe.ValidationError):
            job_card._validate_system_managed_fields()

    def test_vehicle_revalidates_primary_driver_on_every_draft_save_and_submit(self):
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = "SOTRAMA-TEST-COMPANY"
        vehicle.primary_driver = "DRV-TEST-001"
        previous = frappe._dict(
            company=vehicle.company,
            primary_driver=vehicle.primary_driver,
            docstatus=0,
        )
        with (
            patch.object(vehicle, "get_doc_before_save", return_value=previous),
            patch("frappe.db.get_value", return_value=vehicle.company),
            patch("frappe.db.exists", return_value=True),
            patch("frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
            patch("sotrama.tp.validation.validate_active_driver") as validate_driver,
        ):
            vehicle._validate_company_links()
        validate_driver.assert_called_once_with("DRV-TEST-001", "SOTRAMA-TEST-COMPANY")

        vehicle.docstatus = 1
        vehicle._action = "submit"
        with (
            patch.object(vehicle, "get_doc_before_save", return_value=previous),
            patch("frappe.db.get_value", return_value=vehicle.company),
            patch("frappe.db.exists", return_value=True),
            patch("frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
            patch("sotrama.tp.validation.validate_active_driver") as validate_driver,
        ):
            vehicle._validate_company_links()
        validate_driver.assert_called_once_with("DRV-TEST-001", "SOTRAMA-TEST-COMPANY")

    def test_operational_task_revalidates_driver_on_submit(self):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        task = frappe.new_doc("Operational Task")
        task.vehicle = "VEHICLE-A"
        task.company = "COMPANY-A"
        task.driver = "DRIVER-A"
        task.task_type = "Earthmoving"
        task.docstatus = 1
        task._action = "submit"
        previous = frappe._dict(
            vehicle=task.vehicle,
            driver=task.driver,
            task_type=task.task_type,
            transport_kind=None,
            docstatus=0,
        )
        with (
            patch.object(task, "get_doc_before_save", return_value=previous),
            patch("frappe.has_permission", return_value=True),
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(
                    vehicle_status="Active", company="COMPANY-A", docstatus=1
                ),
            ),
            patch("sotrama.tp.settings.validate_company_access"),
            patch("sotrama.tp.validation.validate_active_driver") as validate_driver,
        ):
            OperationalTask._validate_vehicle(task)

        validate_driver.assert_called_once_with("DRIVER-A", "COMPANY-A")


class TestFleetPermissionsIntegration(unittest.TestCase):
    """Domain-focused integration coverage extracted from the former setup monolith."""

    def test_company_classification_company_link_uses_user_permission_scoped_lookup(
        self,
    ):
        source = (
            _sotrama_package_path() / "public" / "js" / "company_classification.js"
        ).read_text(encoding="utf-8")
        self.assertIn("frm.set_query('company'", source)
        self.assertIn(
            "sotrama.tp.settings.search_company_classification_companies", source
        )

        from sotrama.tp.settings import search_company_classification_companies

        with (
            patch("sotrama.tp.settings.frappe.has_permission") as has_permission,
            patch(
                "frappe.permissions.get_user_permissions",
                return_value={
                    "Company": [
                        {"doc": "SOTRAMA", "applicable_for": "Company Classification"},
                        {"doc": "SOTRAMA-QUARRY", "applicable_for": "Vehicle"},
                    ]
                },
            ),
            patch(
                "frappe.permissions.get_allowed_docs_for_doctype",
                return_value=["SOTRAMA"],
            ) as get_allowed,
            patch(
                "sotrama.tp.settings.frappe.get_all",
                return_value=[frappe._dict(name="SOTRAMA")],
            ) as get_all,
        ):
            result = search_company_classification_companies(
                "Company", "SOT", "name", 0, 20
            )

        has_permission.assert_called_once_with(
            "Company Classification", "read", throw=True
        )
        get_allowed.assert_called_once_with(
            [
                {"doc": "SOTRAMA", "applicable_for": "Company Classification"},
                {"doc": "SOTRAMA-QUARRY", "applicable_for": "Vehicle"},
            ],
            "Company Classification",
        )
        get_all.assert_called_once_with(
            "Company",
            fields=["name"],
            filters=[
                ["name", "like", "%SOT%"],
                ["name", "in", ["SOTRAMA"]],
            ],
            order_by="name asc",
            start=0,
            page_length=20,
        )
        self.assertEqual(result, [["SOTRAMA"]])

    def test_vehicle_and_driver_company_links_use_their_user_permission_scopes(self):
        package_path = _sotrama_package_path()
        vehicle_source = (package_path / "public" / "js" / "vehicle.js").read_text(
            encoding="utf-8"
        )
        driver_source = (package_path / "public" / "js" / "driver.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("search_vehicle_companies", vehicle_source)
        self.assertIn("search_driver_companies", driver_source)

        from sotrama.tp.settings import (
            search_driver_companies,
            search_vehicle_companies,
        )

        company_permissions = [
            {"doc": "SOTRAMA", "applicable_for": "Vehicle"},
            {"doc": "SOTRAMA-QUARRY", "applicable_for": "Driver"},
        ]
        for doctype, query in (
            ("Vehicle", search_vehicle_companies),
            ("Driver", search_driver_companies),
        ):
            with self.subTest(doctype=doctype):
                expected_company = (
                    "SOTRAMA" if doctype == "Vehicle" else "SOTRAMA-QUARRY"
                )
                with (
                    patch(
                        "sotrama.tp.settings.frappe.has_permission"
                    ) as has_permission,
                    patch(
                        "frappe.permissions.get_user_permissions",
                        return_value={"Company": company_permissions},
                    ),
                    patch(
                        "frappe.permissions.get_allowed_docs_for_doctype",
                        return_value=[
                            "SOTRAMA" if doctype == "Vehicle" else "SOTRAMA-QUARRY"
                        ],
                    ) as get_allowed,
                    patch(
                        "sotrama.tp.settings.frappe.get_all",
                        return_value=[frappe._dict(name=expected_company)],
                    ) as get_all,
                ):
                    result = query("Company", "SOT", "name", 0, 20)

                has_permission.assert_called_once_with(doctype, "read", throw=True)
                get_allowed.assert_called_once_with(company_permissions, doctype)
                self.assertEqual(
                    get_all.call_args.kwargs["filters"][1][2], [expected_company]
                )
                self.assertEqual(result, [[expected_company]])

    def test_fleet_list_views_keep_hr_only_and_valuation_fields_out_of_shared_lists(
        self,
    ):
        package_path = _sotrama_package_path()
        vehicle = json.loads(
            (package_path / "tp" / "doctype" / "vehicle" / "vehicle.json").read_text(
                encoding="utf-8"
            )
        )
        driver = json.loads(
            (package_path / "tp" / "doctype" / "driver" / "driver.json").read_text(
                encoding="utf-8"
            )
        )
        vehicle_list_fields = {
            field["fieldname"]
            for field in vehicle["fields"]
            if field.get("in_list_view")
        }
        driver_list_fields = {
            field["fieldname"]
            for field in driver["fields"]
            if field.get("in_list_view")
        }
        self.assertTrue(
            {"company", "current_odometer", "vehicle_status"}.issubset(
                vehicle_list_fields
            )
        )
        self.assertFalse(
            {"acquisition_date", "acquisition_value"}.intersection(vehicle_list_fields)
        )
        self.assertTrue(
            {
                "driver_name",
                "company",
                "license_class",
                "license_expiry",
                "status",
            }.issubset(driver_list_fields)
        )
        self.assertFalse(
            {"license_number", "safety_training_expiry", "hire_date"}.intersection(
                driver_list_fields
            )
        )

    def test_fleet_roles_exist(self):
        for role in ("Fleet Manager", "Workshop", "Driver"):
            self.assertTrue(frappe.db.exists("Role", role), f"Missing role: {role}")

    def test_workshop_permissions_follow_least_privilege(self):
        for doctype in (
            "Vehicle",
            "Driver",
            "Operational Task",
            "Maintenance Schedule",
            "Maintenance Job Type",
            "Vehicle Make",
            "Vehicle Model",
        ):
            permissions = [
                row
                for row in frappe.get_meta(doctype, cached=False).permissions
                if row.role == "Workshop" and row.permlevel == 0
            ]
            self.assertTrue(
                permissions, f"Workshop has no explicit {doctype} permission"
            )
            self.assertTrue(
                permissions[0].read, f"Workshop must retain read access to {doctype}"
            )
            for action in ("write", "create", "delete", "submit", "cancel", "amend"):
                self.assertFalse(
                    getattr(permissions[0], action, 0),
                    f"Workshop must not have {action} on {doctype}",
                )

        for doctype in (
            "Maintenance Job Card",
            "Vehicle Inspection",
            "Breakdown Incident",
        ):
            workshop = next(
                row
                for row in frappe.get_meta(doctype, cached=False).permissions
                if row.role == "Workshop" and row.permlevel == 0
            )
            self.assertTrue(workshop.write)
            self.assertTrue(workshop.create)
            self.assertTrue(workshop.submit)
            self.assertFalse(workshop.cancel, f"Workshop must not cancel {doctype}")

    def test_sensitive_fleet_fields_have_explicit_permission_levels(self):
        vehicle_meta = frappe.get_meta("Vehicle", cached=False)
        for fieldname in (
            "acquisition_date",
            "acquisition_value",
            "current_value",
            "depreciation_rate",
            "salvage_value",
            "insurance_value",
            "asset",
        ):
            self.assertEqual(vehicle_meta.get_field(fieldname).permlevel, 1)

        driver_meta = frappe.get_meta("Driver", cached=False)
        self.assertEqual(driver_meta.get_field("employee").permlevel, 3)
        self.assertFalse(driver_meta.get_field("employee").in_list_view)
        for fieldname in ("phone", "email"):
            self.assertEqual(driver_meta.get_field(fieldname).permlevel, 2)
        for fieldname in (
            "address",
            "hire_date",
            "license_number",
            "license_issue_date",
            "medical_expiry",
            "safety_training_expiry",
            "professional_certificate",
            "professional_certificate_number",
            "compliance_records",
            "date_of_birth",
            "national_id",
        ):
            self.assertEqual(driver_meta.get_field(fieldname).permlevel, 1)
        for fieldname in (
            "license_class",
            "license_expiry",
            "total_incidents",
            "notes",
        ):
            self.assertEqual(driver_meta.get_field(fieldname).permlevel, 2)

        fleet_level_one = [
            row
            for row in driver_meta.permissions
            if row.role == "Fleet Manager" and row.permlevel == 1
        ]
        self.assertFalse(
            fleet_level_one, "Fleet Manager must not inherit HR-only level-1 fields"
        )
        fleet_level_two = [
            row
            for row in driver_meta.permissions
            if row.role == "Fleet Manager" and row.permlevel == 2
        ]
        self.assertTrue(fleet_level_two)
        self.assertFalse(
            [
                row
                for row in driver_meta.permissions
                if row.role == "Fleet Manager" and row.permlevel == 3
            ]
        )
        self.assertFalse(
            [
                row
                for row in driver_meta.permissions
                if row.role == "Workshop" and row.permlevel > 0
            ]
        )
        hr_level_two = [
            row
            for row in driver_meta.permissions
            if row.role == "HR Manager" and row.permlevel == 2
        ]
        self.assertTrue(hr_level_two)
        self.assertTrue(hr_level_two[0].read)
        self.assertTrue(hr_level_two[0].write)

        inspection_item = frappe.get_meta("Inspection Item", cached=False)
        self.assertEqual(inspection_item.get_field("is_safety_critical").permlevel, 1)

    def test_operational_task_supervisor_must_be_active_and_match_company(self):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        task = frappe.new_doc("Operational Task")
        task.company = "SOTRAMA-TEST-COMPANY"
        task.supervisor = "EMP-TEST-001"
        module = "sotrama.tp.doctype.operational_task.operational_task"
        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
            ) as employee_lookup,
            patch(
                f"{module}.frappe.db.get_value",
                return_value=None,
            ) as employee_get_value,
            self.assertRaises(frappe.ValidationError),
        ):
            OperationalTask._validate_supervisor(task)
        employee_lookup.assert_called_once_with(
            "SOTRAMA-TEST-COMPANY", "Operational Task"
        )
        employee_get_value.assert_called_once_with(
            "Employee",
            {"name": "EMP-TEST-001", "company": "SOTRAMA-TEST-COMPANY"},
            ["company", "status"],
            as_dict=True,
        )

        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
            ) as employee_lookup,
            patch(
                f"{module}.frappe.db.get_value",
                return_value=frappe._dict(
                    company="SOTRAMA-TEST-COMPANY", status="Inactive"
                ),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            OperationalTask._validate_supervisor(task)
        employee_lookup.assert_called_once_with(
            "SOTRAMA-TEST-COMPANY", "Operational Task"
        )

    def test_submitted_vehicle_and_driver_company_ownership_is_immutable(self):
        from sotrama.tp.doctype.driver.driver import Driver
        from sotrama.tp.doctype.vehicle.vehicle import Vehicle

        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = "COMPANY-B"
        with (
            patch.object(
                vehicle,
                "get_doc_before_save",
                return_value=frappe._dict(docstatus=1, company="COMPANY-A"),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            Vehicle._validate_company_ownership(vehicle)

        driver = frappe.new_doc("Driver")
        driver.company = "COMPANY-B"
        with (
            patch.object(
                driver,
                "get_doc_before_save",
                return_value=frappe._dict(docstatus=1, company="COMPANY-A"),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            Driver._validate_company_ownership(driver)

        with patch(
            "sotrama.tp.validation.get_open_vehicle_safety_holds",
            return_value={"breakdown": None, "critical_inspection": None},
        ):
            Vehicle._validate_safety_hold(vehicle)

    def test_submitted_fleet_status_transitions_are_enforced_server_side(self):
        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            BreakdownIncident,
        )
        from sotrama.tp.doctype.driver.driver import Driver
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            MaintenanceSchedule,
        )

        driver = frappe.new_doc("Driver")
        driver.status = "Active"
        with (
            patch.object(
                driver,
                "get_doc_before_save",
                return_value=frappe._dict(docstatus=1, status="Terminated"),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            Driver._validate_status_transition(driver)

        incident = frappe.new_doc("Breakdown Incident")
        incident.status = "Closed"
        with (
            patch.object(
                incident,
                "get_doc_before_save",
                return_value=frappe._dict(docstatus=1, status="Reported"),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            BreakdownIncident._validate_status_transition(incident)

        schedule = frappe.new_doc("Maintenance Schedule")
        schedule.status = "Active"
        with (
            patch.object(
                schedule,
                "get_doc_before_save",
                return_value=frappe._dict(docstatus=1, status="Completed"),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            MaintenanceSchedule._validate_status_transition(schedule)

    def test_submitted_fleet_records_are_preserved_for_audit(self):
        from sotrama.tp.validation import prevent_submitted_fleet_record_deletion

        submitted = frappe._dict(docstatus=1)
        with self.assertRaises(frappe.ValidationError):
            prevent_submitted_fleet_record_deletion(submitted)
        cancelled = frappe._dict(docstatus=2)
        with self.assertRaises(frappe.ValidationError):
            prevent_submitted_fleet_record_deletion(cancelled)
        draft = frappe._dict(docstatus=0)
        prevent_submitted_fleet_record_deletion(draft)

    def test_fleet_workspace_links_match_role_permissions(self):
        fleet = frappe.get_doc("Workspace", "Sotrama Fleet")
        fleet_roles = {row.role for row in fleet.roles}
        self.assertNotIn("HR Manager", fleet_roles)
        self.assertNotIn("Fleet Cost Analysis", {row.link_to for row in fleet.links})
        expiry_roles = {
            row.role
            for row in frappe.get_doc("Report", "Upcoming Document Expiries").roles
        }
        self.assertIn("Workshop", expiry_roles)

        manager_workspace = frappe.get_doc("Workspace", "Fleet Management Reports")
        self.assertEqual(
            {row.role for row in manager_workspace.roles},
            {"Fleet Manager", "System Manager"},
        )
        self.assertIn(
            "Fleet Cost Analysis", {row.link_to for row in manager_workspace.links}
        )
        self.assertNotIn(
            "Company Classification", {row.link_to for row in manager_workspace.links}
        )
        sidebar = frappe.get_doc("Sidebar", "TP")
        self.assertNotIn("Fleet Cost Analysis", {row.link_to for row in sidebar.items})
        self.assertNotIn(
            "Upcoming Document Expiries", {row.link_to for row in sidebar.items}
        )
        self.assertNotIn(
            "Company Classification", {row.link_to for row in sidebar.items}
        )
        self.assertNotIn("TP Settings", {row.link_to for row in sidebar.items})

        parent = frappe.get_doc("Workspace", "Sotrama")
        self.assertNotIn("Sotrama Fleet", {row.link_to for row in parent.links})
        dock = frappe.get_doc("Dock", {"app": "sotrama", "standard": 1})
        self.assertIn("Sotrama Fleet", {row.link_to for row in dock.items})

    def test_dock_workspace_entries_are_gated_by_workspace_permissions(self):
        from frappe.desk.doctype.dock.dock import is_reachable

        fleet_user_workspaces = {"Sotrama", "Sotrama Fleet"}
        with patch(
            "frappe.desk.doctype.dock.dock.permitted_workspaces",
            return_value=fleet_user_workspaces,
        ):
            self.assertTrue(
                is_reachable({"link_type": "Workspace", "link_to": "Sotrama Fleet"})
            )
            self.assertFalse(
                is_reachable(
                    {"link_type": "Workspace", "link_to": "Algerian Localization"}
                )
            )

        accounting_user_workspaces = {"Sotrama"}
        with patch(
            "frappe.desk.doctype.dock.dock.permitted_workspaces",
            return_value=accounting_user_workspaces,
        ):
            self.assertFalse(
                is_reachable({"link_type": "Workspace", "link_to": "Sotrama Fleet"})
            )
            self.assertFalse(
                is_reachable(
                    {"link_type": "Workspace", "link_to": "Algerian Localization"}
                )
            )

    def test_tp_sidebar_and_parent_workspace_links_are_filtered_by_frappe_permissions(
        self,
    ):
        from frappe.desk.utils import is_item_allowed

        hr_context = frappe._dict(
            allowed_workspaces=["Sotrama"],
            can_read=["Driver", "TP Settings"],
            restricted_doctypes=["Driver", "TP Settings"],
            allowed_pages={},
            restricted_pages=[],
            allowed_reports={},
            allowed_dashboards={},
        )
        with (
            patch.dict(frappe.session, {"user": "hr@example.invalid"}),
            patch(
                "frappe.has_permission",
                side_effect=lambda doctype: doctype in {"Driver", "TP Settings"},
            ),
        ):
            self.assertTrue(is_item_allowed("Driver", "DocType", hr_context))
            self.assertTrue(is_item_allowed("TP Settings", "DocType", hr_context))
            self.assertFalse(is_item_allowed("Vehicle", "DocType", hr_context))
            self.assertFalse(is_item_allowed("Sotrama Fleet", "Workspace", hr_context))
            self.assertFalse(
                is_item_allowed("Algerian Localization", "Workspace", hr_context)
            )

        accounts_context = frappe._dict(
            allowed_workspaces=["Sotrama"],
            can_read=[],
            restricted_doctypes=[],
            allowed_pages={},
            restricted_pages=[],
            allowed_reports={},
            allowed_dashboards={},
        )
        with (
            patch.dict(frappe.session, {"user": "accounts@example.invalid"}),
            patch("frappe.has_permission", return_value=False),
        ):
            self.assertFalse(is_item_allowed("Driver", "DocType", accounts_context))
            self.assertFalse(
                is_item_allowed("TP Settings", "DocType", accounts_context)
            )
            self.assertFalse(
                is_item_allowed("Algerian Localization", "Workspace", accounts_context)
            )

    def test_company_defaults_api_respects_company_user_permissions(self):
        from sotrama.tp import settings

        with (
            patch.object(settings.frappe, "has_permission"),
            patch(
                "sotrama.tp.settings.validate_company_access",
                side_effect=frappe.PermissionError,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            settings.get_tp_company_defaults("OTHER-COMPANY")

        with (
            patch.object(settings.frappe, "has_permission"),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
            patch.object(
                settings,
                "get_tp_company_setting",
                side_effect=lambda company, fieldname, applicable_for, **kwargs: (
                    fieldname
                ),
            ),
            patch("sotrama.tp.settings.frappe.db.get_value", return_value="SOTRAMA"),
        ):
            result = settings.get_tp_company_defaults("SOTRAMA")
        self.assertEqual(result["default_parts_warehouse"], "default_parts_warehouse")
        self.assertEqual(validate_company.call_count, 4)
        validate_company.assert_any_call("SOTRAMA", "Vehicle")

    def test_primary_company_api_enforces_the_requested_company_scope(self):
        from sotrama.tp import settings

        with (
            patch.object(settings.frappe, "has_permission"),
            patch.object(settings, "get_tp_setting", return_value="OTHER-COMPANY"),
            patch(
                "sotrama.tp.settings.validate_company_access",
                side_effect=frappe.PermissionError,
            ) as validate_company,
            self.assertRaises(frappe.PermissionError),
        ):
            settings.get_tp_default_company("Vehicle")
        validate_company.assert_called_once_with("OTHER-COMPANY", "Vehicle")

    def test_primary_company_api_returns_only_for_supported_create_contexts(self):
        from sotrama.tp import settings

        with (
            patch.object(settings.frappe, "has_permission"),
            patch.object(settings, "get_tp_setting", return_value="COMPANY-A"),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
        ):
            self.assertEqual(settings.get_tp_default_company("Vehicle"), "COMPANY-A")
        validate_company.assert_called_once_with("COMPANY-A", "Vehicle")

        with (
            patch.object(settings.frappe, "has_permission"),
            patch.object(settings, "get_tp_setting", return_value="COMPANY-A"),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
        ):
            self.assertEqual(settings.get_tp_default_company("Driver"), "COMPANY-A")
        validate_company.assert_called_once_with("COMPANY-A", "Driver")

        with self.assertRaises(frappe.PermissionError):
            settings.get_tp_default_company("TP Settings")

    def test_company_default_projection_rejects_wrong_missing_or_unscoped_targets(self):
        from sotrama.tp.settings import _get_accessible_company_default

        with (
            patch(
                "sotrama.tp.settings.get_tp_company_setting",
                return_value="COST-CENTER-B",
            ),
            patch("sotrama.tp.settings.frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.frappe.db.get_value", return_value="COMPANY-B"),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
        ):
            self.assertIsNone(
                _get_accessible_company_default(
                    "COMPANY-A", "default_cost_center", "Cost Center"
                )
            )
        validate_company.assert_not_called()

        with (
            patch(
                "sotrama.tp.settings.get_tp_company_setting",
                return_value="COST-CENTER-A",
            ),
            patch("sotrama.tp.settings.frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.frappe.db.get_value", return_value=None),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
        ):
            self.assertIsNone(
                _get_accessible_company_default(
                    "COMPANY-A", "default_cost_center", "Cost Center"
                )
            )
        validate_company.assert_not_called()

        with (
            patch(
                "sotrama.tp.settings.get_tp_company_setting",
                return_value="COST-CENTER-A",
            ),
            patch("sotrama.tp.settings.frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.frappe.db.get_value", return_value="COMPANY-A"),
            patch(
                "sotrama.tp.settings.validate_company_access",
                side_effect=frappe.PermissionError,
            ),
        ):
            self.assertIsNone(
                _get_accessible_company_default(
                    "COMPANY-A", "default_cost_center", "Cost Center"
                )
            )

    def test_company_setting_lookup_checks_context_and_only_uses_primary_fallback(self):
        from sotrama.tp.settings import get_tp_company_setting

        with (
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
            patch("sotrama.tp.settings.frappe.db.exists", return_value=True),
            patch(
                "sotrama.tp.settings.frappe.db.get_value", return_value="COST-CENTER-A"
            ) as get_value,
        ):
            result = get_tp_company_setting(
                "COMPANY-A", "default_cost_center", "Maintenance Job Card"
            )
        self.assertEqual(result, "COST-CENTER-A")
        validate_company.assert_called_once_with("COMPANY-A", "Maintenance Job Card")
        self.assertEqual(
            get_value.call_args.args[1],
            {
                "parent": "TP Settings",
                "parenttype": "TP Settings",
                "parentfield": "company_defaults",
                "company": "COMPANY-A",
                "active": 1,
            },
        )
        self.assertEqual(get_value.call_args.args[2], "default_cost_center")

    def test_company_defaults_projection_requires_the_target_doctype_create_permission(
        self,
    ):
        from sotrama.tp import settings

        with (
            patch.object(
                settings.frappe,
                "has_permission",
                side_effect=[None, frappe.PermissionError],
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            settings.get_tp_company_defaults("SOTRAMA")

        with (
            patch.object(
                settings.frappe,
                "has_permission",
                side_effect=[None, frappe.PermissionError],
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            settings.get_tp_default_company("Company Classification")

    def test_company_defaults_projection_omits_unreadable_link_targets(self):
        from sotrama.tp import settings

        with (
            patch.object(
                settings.frappe,
                "has_permission",
                side_effect=[True, True, True, True, True],
            ),
            patch.object(
                settings,
                "get_tp_company_setting",
                side_effect=lambda company, fieldname, applicable_for, **kwargs: (
                    fieldname
                ),
            ),
            patch("sotrama.tp.settings.frappe.db.get_value", return_value="SOTRAMA"),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
        ):
            result = settings.get_tp_company_defaults("SOTRAMA")

        self.assertNotIn("default_company_classification", result)
        self.assertEqual(result["default_department"], "default_department")
        self.assertEqual(result["default_cost_center"], "default_cost_center")
        self.assertEqual(result["default_parts_warehouse"], "default_parts_warehouse")
        self.assertEqual(validate_company.call_count, 4)

    def test_validate_company_access_uses_user_permissions_without_company_read_permission(
        self,
    ):
        from sotrama.tp.settings import validate_company_access

        with (
            patch("sotrama.tp.settings.frappe.db.exists", return_value=True),
            patch(
                "frappe.permissions.get_user_permissions",
                return_value={
                    "Company": [
                        frappe._dict(doc="ALLOWED-COMPANY", applicable_for="Vehicle")
                    ]
                },
            ),
            patch(
                "frappe.has_permission",
                side_effect=AssertionError(
                    "Company read permission must not be required"
                ),
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            validate_company_access("OTHER-COMPANY", "Vehicle")

    def test_company_user_permission_applicable_for_scope_matches_frappe(self):
        from sotrama.tp.settings import validate_company_access

        scoped_permission = frappe._dict(
            doc="VEHICLE-COMPANY", applicable_for="Vehicle"
        )
        with (
            patch("sotrama.tp.settings.frappe.db.exists", return_value=True),
            patch(
                "frappe.permissions.get_user_permissions",
                return_value={"Company": [scoped_permission]},
            ),
        ):
            validate_company_access("OTHER-COMPANY", "Driver")

        with (
            patch("sotrama.tp.settings.frappe.db.exists", return_value=True),
            patch(
                "frappe.permissions.get_user_permissions",
                return_value={"Company": [scoped_permission]},
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            validate_company_access("OTHER-COMPANY", "Vehicle")

    def test_company_link_is_required_on_all_company_scoped_fleet_records(self):
        for doctype in (
            "Vehicle",
            "Driver",
            "Operational Task",
            "Maintenance Job Card",
            "Vehicle Inspection",
            "Breakdown Incident",
            "Maintenance Schedule",
            "Company Classification",
        ):
            with self.subTest(doctype=doctype):
                self.assertTrue(
                    frappe.get_meta(doctype, cached=False).get_field("company").reqd,
                    f"{doctype}.company must be mandatory for company isolation",
                )


class TestFleetChildTableAndAttachmentSecurity(unittest.TestCase):
    def test_child_tables_are_only_queryable_through_parent_forms(self):
        from sotrama import hooks as app_hooks
        from sotrama.permissions import (
            COMPANY_SCOPED_FLEET_CHILD_TABLES,
            SOTRAMA_CHILD_TABLE_DOCTYPES,
            _check_sotrama_child_table_rpc_access,
            sotrama_child_table_query_conditions,
        )

        expected_hooks = {
            **{
                doctype: "sotrama.permissions.sotrama_child_table_query_conditions"
                for doctype in COMPANY_SCOPED_FLEET_CHILD_TABLES
            },
            "Driver Compliance Record": "sotrama.permissions.driver_compliance_record_query_conditions",
            "TP Company Defaults": "sotrama.permissions.tp_company_defaults_query_conditions",
        }
        self.assertEqual(set(SOTRAMA_CHILD_TABLE_DOCTYPES), set(expected_hooks))
        for doctype, hook in expected_hooks.items():
            with self.subTest(doctype=doctype):
                self.assertTrue(frappe.get_meta(doctype, cached=False).istable)
                self.assertEqual(app_hooks.permission_query_conditions[doctype], hook)

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
        ):
            for doctype in SOTRAMA_CHILD_TABLE_DOCTYPES:
                with self.subTest(doctype=doctype):
                    self.assertEqual(
                        sotrama_child_table_query_conditions(
                            "fleet@example.invalid", doctype=doctype
                        ),
                        "1=0",
                    )
                    with self.assertRaises(frappe.PermissionError):
                        _check_sotrama_child_table_rpc_access(doctype)

        with (
            patch.dict(frappe.session, {"user": "system@example.invalid"}),
            patch("frappe.get_roles", return_value=["System Manager"]),
        ):
            for doctype in SOTRAMA_CHILD_TABLE_DOCTYPES:
                self.assertIsNone(
                    sotrama_child_table_query_conditions(
                        "system@example.invalid", doctype=doctype
                    )
                )
                _check_sotrama_child_table_rpc_access(doctype)

    def test_generic_child_table_rpc_wrappers_reject_company_scoped_rows(self):
        from sotrama.permissions import (
            get_list_with_tp_settings_permissions,
            get_value_with_tp_settings_field_permissions,
            validate_link_and_fetch_without_tp_settings_singleton,
        )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
        ):
            with self.assertRaises(frappe.PermissionError):
                get_list_with_tp_settings_permissions(
                    "Vehicle Document", parent="Vehicle"
                )
            with self.assertRaises(frappe.PermissionError):
                get_value_with_tp_settings_field_permissions(
                    "Vehicle Document", "attachment", parent="Vehicle"
                )
            with self.assertRaises(frappe.PermissionError):
                validate_link_and_fetch_without_tp_settings_singleton(
                    "Vehicle Document", "VEH-DOC-001"
                )

    def test_fleet_and_driver_file_shares_are_rejected(self):
        from sotrama.permissions import (
            COMPANY_SCOPED_FLEET_CHILD_TABLES,
            COMPANY_SCOPED_FLEET_DOCTYPES,
            PRIVATE_DRIVER_ATTACHMENT_DOCTYPES,
            prevent_unsafe_fleet_docsharing,
        )

        attached_doctypes = (
            COMPANY_SCOPED_FLEET_DOCTYPES
            | set(COMPANY_SCOPED_FLEET_CHILD_TABLES)
            | PRIVATE_DRIVER_ATTACHMENT_DOCTYPES
        )
        for doctype in attached_doctypes:
            file_doc = frappe._dict(
                name="FILE-FLEET-001",
                attached_to_doctype=doctype,
                attached_to_name="PARENT-001",
            )
            with (
                self.subTest(attached_doctype=doctype),
                patch("frappe.get_doc", return_value=file_doc),
                self.assertRaises(frappe.PermissionError),
            ):
                prevent_unsafe_fleet_docsharing(
                    frappe._dict(
                        share_doctype="File",
                        share_name="FILE-FLEET-001",
                        user="recipient@example.invalid",
                        everyone=0,
                        read=1,
                    )
                )

        with patch(
            "frappe.get_doc",
            return_value=frappe._dict(
                name="FILE-COMMUNICATION", attached_to_doctype="Communication"
            ),
        ):
            prevent_unsafe_fleet_docsharing(
                frappe._dict(
                    share_doctype="File",
                    share_name="FILE-COMMUNICATION",
                    user="recipient@example.invalid",
                    everyone=0,
                    read=1,
                )
            )

    def test_legacy_fleet_file_shares_are_removed_during_migration_cleanup(self):
        from sotrama.permissions import remove_unsafe_fleet_docshares

        fleet_share = frappe._dict(name="SHARE-FLEET-FILE", share_name="FILE-FLEET")
        non_fleet_share = frappe._dict(name="SHARE-NON-FLEET", share_name="FILE-NON-FLEET")
        fleet_file_doc = frappe._dict(
            name="FILE-FLEET", attached_to_doctype="Vehicle Document", attached_to_name="VD-001"
        )
        non_fleet_file_doc = frappe._dict(
            name="FILE-NON-FLEET", attached_to_doctype="Communication", attached_to_name="COMM-001"
        )

        # Mutable share list to model database state transitions.
        shares = [fleet_share]

        def get_all_side_effect(doctype, filters=None, **kwargs):
            return list(shares)

        # First run: Fleet file share exists and is removed.
        with (
            patch("frappe.get_all", side_effect=get_all_side_effect),
            patch("frappe.get_doc", return_value=fleet_file_doc),
            patch("frappe.db.delete") as delete,
        ):
            remove_unsafe_fleet_docshares(doctype="File", name="FILE-FLEET")
            delete.assert_called_once_with("DocShare", {"name": "SHARE-FLEET-FILE"})

        # Simulate the deletion persisting in the database.
        shares.clear()

        # Second run: share is gone, no deletion attempted (idempotent).
        with (
            patch("frappe.get_all", side_effect=get_all_side_effect),
            patch("frappe.get_doc", return_value=fleet_file_doc),
            patch("frappe.db.delete") as delete_again,
        ):
            remove_unsafe_fleet_docshares(doctype="File", name="FILE-FLEET")
            delete_again.assert_not_called()

        # Non-fleet file shares are preserved across both runs.
        shares.append(non_fleet_share)
        with (
            patch("frappe.get_all", side_effect=get_all_side_effect),
            patch("frappe.get_doc", return_value=non_fleet_file_doc),
            patch("frappe.db.delete") as delete_non_fleet,
        ):
            remove_unsafe_fleet_docshares(doctype="File", name="FILE-NON-FLEET")
            delete_non_fleet.assert_not_called()

    def test_file_updates_remove_shares_when_attached_to_or_detached_from_fleet(self):
        from sotrama import hooks as app_hooks
        from sotrama.permissions import remove_unsafe_fleet_docshares_for_file

        # A File becoming attached to a Fleet document triggers share cleanup.
        # No previous attachment (new file); current doc has fleet metadata.
        attached_file = frappe._dict(
            name="FILE-ATTACHED",
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-001",
            get_doc_before_save=lambda: None,
        )
        with patch("frappe.db.delete") as delete:
            remove_unsafe_fleet_docshares_for_file(attached_file)
            delete.assert_called_once_with(
                "DocShare",
                {"share_doctype": "File", "share_name": "FILE-ATTACHED"},
            )

        # A File detaching from a Fleet document: previous doc carries the
        # old attachment metadata; current doc is detached.
        detached_file = frappe._dict(
            name="FILE-DETACHED",
            attached_to_doctype=None,
            attached_to_name=None,
            get_doc_before_save=lambda: frappe._dict(
                attached_to_doctype="Vehicle Document",
                attached_to_name="VD-001",
            ),
        )
        with patch("frappe.db.delete") as delete:
            remove_unsafe_fleet_docshares_for_file(detached_file)
            delete.assert_called_once_with(
                "DocShare",
                {"share_doctype": "File", "share_name": "FILE-DETACHED"},
            )

        # A File moving between Fleet documents: previous fleet metadata
        # triggers cleanup even though current doc is also fleet-scoped.
        moved_file = frappe._dict(
            name="FILE-MOVED",
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-002",
            get_doc_before_save=lambda: frappe._dict(
                attached_to_doctype="Vehicle",
                attached_to_name="VEH-001",
            ),
        )
        with patch("frappe.db.delete") as delete:
            remove_unsafe_fleet_docshares_for_file(moved_file)
            delete.assert_called_once_with(
                "DocShare",
                {"share_doctype": "File", "share_name": "FILE-MOVED"},
            )

        # An unrelated file (not fleet-scoped) must not have its shares deleted.
        unrelated_file = frappe._dict(
            name="FILE-UNRELATED",
            attached_to_doctype="Communication",
            attached_to_name="COMM-001",
            get_doc_before_save=lambda: None,
        )
        with patch("frappe.db.delete") as delete:
            remove_unsafe_fleet_docshares_for_file(unrelated_file)
            delete.assert_not_called()

        self.assertEqual(
            app_hooks.doc_events["File"]["before_validate"],
            "sotrama.permissions.secure_company_scoped_fleet_attachment",
        )
        self.assertEqual(
            app_hooks.doc_events["File"]["before_insert"],
            "sotrama.permissions.secure_driver_private_attachment",
        )
        self.assertEqual(
            app_hooks.doc_events["File"]["before_save"],
            "sotrama.permissions.secure_driver_private_attachment",
        )
        self.assertEqual(
            app_hooks.doc_events["File"]["on_update"],
            [
                "sotrama.permissions.secure_driver_private_attachment",
                "sotrama.permissions.remove_unsafe_fleet_docshares_for_file",
            ],
        )

    def test_company_scoped_fleet_attachments_are_always_private(self):
        from sotrama.permissions import (
            COMPANY_SCOPED_FLEET_DOCTYPES,
            SOTRAMA_CHILD_TABLE_DOCTYPES,
            file_has_permission,
            secure_company_scoped_fleet_attachment,
        )

        for doctype in COMPANY_SCOPED_FLEET_DOCTYPES | SOTRAMA_CHILD_TABLE_DOCTYPES:
            file_doc = frappe._dict(
                attached_to_doctype=doctype,
                attached_to_name="PARENT-001",
                is_private=0,
            )
            with self.subTest(attached_to_doctype=doctype):
                secure_company_scoped_fleet_attachment(file_doc)
                self.assertEqual(file_doc.is_private, 1)

        unrelated_file = frappe._dict(
            attached_to_doctype="Communication",
            is_private=0,
        )
        secure_company_scoped_fleet_attachment(unrelated_file)
        self.assertEqual(unrelated_file.is_private, 0)

        detached_file = frappe._dict(
            attached_to_doctype=None,
            is_private=0,
            get_doc_before_save=lambda: frappe._dict(
                attached_to_doctype="Vehicle Document",
                attached_to_name="VEH-001",
            ),
        )
        with (
            patch("sotrama.permissions._redact_driver_attachment_comments"),
            patch("sotrama.permissions._clear_attached_file_field"),
        ):
            secure_company_scoped_fleet_attachment(detached_file)
        self.assertEqual(detached_file.is_private, 1)
        self.assertEqual(detached_file.sotrama_private_fleet_attachment, 1)
        self.assertEqual(detached_file.owner, "Administrator")
        self.assertFalse(
            file_has_permission(
                detached_file, user="fleet@example.invalid", ptype="read"
            )
        )

    def test_company_scoped_fleet_attachments_reject_remote_urls(self):
        from sotrama.permissions import secure_company_scoped_fleet_attachment

        remote_file = frappe._dict(
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-001",
            file_url="https://files.example.invalid/vehicle.pdf",
            is_private=0,
        )
        with self.assertRaises(frappe.ValidationError):
            secure_company_scoped_fleet_attachment(remote_file)

        # A file with only a doctype (no attached document name) is not yet
        # attached to a specific company-scoped record, so this hook does not
        # apply the remote-URL rejection.
        partial_file = frappe._dict(
            attached_to_doctype="Vehicle",
            file_url="https://files.example.invalid/vehicle.pdf",
            is_private=0,
        )
        secure_company_scoped_fleet_attachment(partial_file)

        # An unattached file is not company-scoped either.
        unattached_file = frappe._dict(
            file_url="https://files.example.invalid/file.pdf",
            is_private=0,
        )
        secure_company_scoped_fleet_attachment(unattached_file)

        # A local private file attached to a company-scoped Fleet record is
        # accepted (not rejected): it has no remote URL to block.
        local_private_file = frappe._dict(
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-001",
            file_url="/private/files/fleet.pdf",
            is_private=1,
        )
        secure_company_scoped_fleet_attachment(local_private_file)
        self.assertEqual(local_private_file.is_private, 1)

    def test_fleet_file_download_checks_parent_scope_before_owner_shortcut(self):
        from sotrama.overrides.file import DriverPrivateFileMixin

        class FileBase:
            def is_downloadable(self):
                # Frappe's File.has_permission grants the owner access before
                # checking the attached parent document.
                return True

        class TestFile(DriverPrivateFileMixin, FileBase):
            pass

        file_doc = TestFile()
        with (
            patch.dict(frappe.session, {"user": "former-owner@example.invalid"}),
            patch(
                "sotrama.permissions.is_driver_private_attachment", return_value=False
            ),
            patch(
                "sotrama.permissions.is_company_scoped_fleet_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.permissions.can_access_company_scoped_fleet_attachment",
                return_value=False,
            ) as can_access_parent,
        ):
            self.assertFalse(file_doc.is_downloadable())

        can_access_parent.assert_called_once_with(
            file_doc, "former-owner@example.invalid", ptype="read"
        )

        with (
            patch.dict(frappe.session, {"user": "authorized@example.invalid"}),
            patch(
                "sotrama.permissions.is_driver_private_attachment", return_value=False
            ),
            patch(
                "sotrama.permissions.is_company_scoped_fleet_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.permissions.can_access_company_scoped_fleet_attachment",
                return_value=True,
            ) as can_access_parent,
        ):
            self.assertTrue(file_doc.is_downloadable())

        can_access_parent.assert_called_once_with(
            file_doc, "authorized@example.invalid", ptype="read"
        )

    def test_file_controller_mixin_sets_privacy_before_storage_insert(self):
        from sotrama.overrides.file import DriverPrivateFileMixin
        from sotrama.permissions import (
            DRIVER_FILE_PRIVACY_FIELD,
            FLEET_FILE_PRIVACY_FIELD,
        )

        class FileBase:
            def before_insert(self):
                self.private_when_stored = self.is_private
                if getattr(self, "copy_existing", False):
                    self.file_url = "/files/copied.pdf"
                return "stored"

            def save_file(self, content=None, **kwargs):
                self.saved_content = content
                return "saved"

            def after_insert(self):
                self.base_after_insert_called = True
                return "after"

            def on_update(self):
                self.base_on_update_called = True
                return "updated"

        class TestFile(DriverPrivateFileMixin, FileBase):
            def __init__(self, attached_to_doctype, copy_existing=False):
                self.name = "FILE-TEST"
                self.attached_to_doctype = attached_to_doctype
                self.attached_to_name = "PARENT-001"
                self.file_url = None
                self.is_private = 0
                self.copy_existing = copy_existing

            def get(self, fieldname):
                return getattr(self, fieldname, None)

            def handle_is_private_changed(self):
                self.file_url = self.file_url.replace("/files/", "/private/files/")

        fleet_file = TestFile("Vehicle")
        self.assertEqual(fleet_file.before_insert(), "stored")
        self.assertEqual(fleet_file.private_when_stored, 1)
        self.assertEqual(getattr(fleet_file, FLEET_FILE_PRIVACY_FIELD), 1)

        copied_fleet_file = TestFile("Vehicle", copy_existing=True)
        copied_fleet_file.before_insert()
        self.assertEqual(copied_fleet_file.file_url, "/private/files/copied.pdf")

        with (
            patch(
                "sotrama.permissions.secure_duplicate_fleet_file_rows",
                return_value=True,
            ) as secure_duplicates,
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(
                    file_url="/private/files/fleet.pdf", is_private=1
                ),
            ) as get_file_values,
        ):
            self.assertEqual(fleet_file.after_insert(), "after")
        secure_duplicates.assert_called_once_with(fleet_file)
        get_file_values.assert_called_once_with(
            "File", "FILE-TEST", ["file_url", "is_private"], as_dict=True
        )
        self.assertEqual(fleet_file.file_url, "/private/files/fleet.pdf")
        with (
            patch(
                "sotrama.permissions.secure_duplicate_fleet_file_rows",
                return_value=True,
            ) as secure_duplicates,
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(
                    file_url="/private/files/fleet.pdf", is_private=1
                ),
            ),
        ):
            self.assertEqual(fleet_file.on_update(), "updated")
        secure_duplicates.assert_called_once_with(fleet_file)

        driver_file = TestFile("Driver Compliance Record")
        driver_file.before_insert()
        self.assertEqual(driver_file.private_when_stored, 1)
        self.assertEqual(getattr(driver_file, DRIVER_FILE_PRIVACY_FIELD), 1)
        self.assertEqual(getattr(driver_file, FLEET_FILE_PRIVACY_FIELD), 1)
        with patch(
            "sotrama.permissions.secure_duplicate_fleet_file_rows"
        ) as secure_duplicates:
            driver_file.after_insert()
            driver_file.on_update()
        secure_duplicates.assert_not_called()

        ordinary_file = TestFile("Communication")
        ordinary_file.before_insert()
        self.assertEqual(ordinary_file.private_when_stored, 0)

    def test_file_controller_mixin_blocks_reuse_of_fleet_file_content(self):
        from sotrama.overrides.file import DriverPrivateFileMixin

        class FileBase:
            def before_insert(self):
                self.base_insert_called = True

            def save_file(self, content=None, **kwargs):
                self.base_save_called = True

            def get_content(self):
                return b"decoded fleet content"

        class TestFile(DriverPrivateFileMixin, FileBase):
            def __init__(self):
                self.name = "FILE-TEST"
                self.attached_to_doctype = "Communication"
                self.content_hash = "existing-fleet-hash"
                self.is_private = 0

            def get(self, fieldname):
                return getattr(self, fieldname, None)

        copied_file = TestFile()
        with (
            patch("frappe.db.exists", return_value=True),
            self.assertRaises(frappe.PermissionError),
        ):
            copied_file.before_insert()
        self.assertFalse(getattr(copied_file, "base_insert_called", False))

        uploaded_file = TestFile()
        with (
            patch(
                "frappe.core.doctype.file.utils.get_content_hash",
                return_value="existing-fleet-hash",
            ) as get_content_hash,
            patch("frappe.db.exists", return_value=True),
            self.assertRaises(frappe.PermissionError),
        ):
            uploaded_file.save_file(content="base64-payload", decode=True)
        self.assertFalse(getattr(uploaded_file, "base_save_called", False))
        get_content_hash.assert_called_once_with(b"decoded fleet content")

    def test_duplicate_fleet_file_rows_do_not_create_an_unrelated_access_path(self):
        from sotrama.permissions import (
            file_has_permission,
            is_company_scoped_fleet_attachment,
            prevent_unsafe_fleet_docsharing,
        )

        duplicate_file = frappe._dict(
            name="FILE-DUPLICATE",
            attached_to_doctype="Communication",
            content_hash="fleet-hash",
            is_private=1,
            sotrama_private_fleet_attachment=1,
        )
        with (
            patch(
                "sotrama.permissions.is_driver_private_attachment", return_value=False
            ),
        ):
            self.assertTrue(is_company_scoped_fleet_attachment(duplicate_file))
            self.assertFalse(
                file_has_permission(
                    duplicate_file, user="fleet@example.invalid", ptype="read"
                )
            )
            with (
                patch("frappe.get_doc", return_value=duplicate_file),
                patch.dict(frappe.session, {"user": "system@example.invalid"}),
                self.assertRaises(frappe.PermissionError),
            ):
                prevent_unsafe_fleet_docsharing(
                    frappe._dict(
                        share_doctype="File",
                        share_name="FILE-DUPLICATE",
                        user="recipient@example.invalid",
                        everyone=0,
                        read=1,
                    )
                )

    def test_fleet_file_owner_must_still_have_parent_company_permission(self):
        from sotrama.permissions import file_has_permission

        file_doc = frappe._dict(
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-001",
            owner="fleet@example.invalid",
            is_private=1,
            sotrama_private_fleet_attachment=1,
        )
        with (
            patch(
                "sotrama.permissions.is_driver_private_attachment", return_value=False
            ),
            patch("frappe.has_permission", return_value=False) as has_permission,
        ):
            self.assertFalse(
                file_has_permission(
                    file_doc, user="fleet@example.invalid", ptype="read"
                )
            )
        has_permission.assert_called_once_with(
            "Vehicle",
            "read",
            doc="VEH-001",
            user="fleet@example.invalid",
            ignore_share_permissions=True,
        )

        with (
            patch(
                "sotrama.permissions.is_driver_private_attachment", return_value=False
            ),
            patch("frappe.has_permission", return_value=True),
        ):
            self.assertTrue(
                file_has_permission(
                    file_doc, user="fleet@example.invalid", ptype="read"
                )
            )
            self.assertFalse(
                file_has_permission(
                    file_doc, user="fleet@example.invalid", ptype="share"
                )
            )

    def test_child_fleet_file_ignores_parent_docshare_without_bypassing_permlevel(self):
        from sotrama.permissions import file_has_permission

        file_doc = frappe._dict(
            attached_to_doctype="Vehicle Document",
            attached_to_name="VD-001",
            sotrama_private_fleet_attachment=1,
        )
        parent = frappe._dict(parenttype="Vehicle", parent="VEH-001")
        with (
            patch(
                "sotrama.permissions.is_driver_private_attachment", return_value=False
            ),
            patch("frappe.db.get_value", return_value=parent),
            patch("frappe.has_permission", side_effect=[True, False]) as has_permission,
        ):
            self.assertFalse(
                file_has_permission(
                    file_doc, user="fleet@example.invalid", ptype="read"
                )
            )
        self.assertEqual(has_permission.call_count, 2)
        has_permission.assert_any_call(
            "Vehicle Document",
            "read",
            doc="VD-001",
            user="fleet@example.invalid",
        )
        has_permission.assert_any_call(
            "Vehicle",
            "read",
            doc="VEH-001",
            user="fleet@example.invalid",
            ignore_share_permissions=True,
        )

    def test_driver_and_general_fleet_attachment_content_cannot_cross_privacy_scopes(
        self,
    ):
        from sotrama.permissions import prevent_fleet_attachment_content_reuse

        meta = Mock()
        meta.has_field.return_value = True
        vehicle_file = frappe._dict(
            name="VEH-FILE-001",
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-001",
            content_hash="driver-hash",
            is_new=lambda: False,
        )
        with (
            patch("frappe.get_meta", return_value=meta),
            patch("frappe.get_all", return_value=[]),
            patch(
                "frappe.db.exists",
                side_effect=lambda doctype, filters: (
                    filters.get("sotrama_private_driver_attachment") == 1
                ),
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_fleet_attachment_content_reuse(vehicle_file)

        driver_file = frappe._dict(
            name="DRV-FILE-001",
            attached_to_doctype="Driver",
            attached_to_name="DRV-001",
            content_hash="fleet-hash",
            is_new=lambda: False,
        )
        with (
            patch("frappe.get_meta", return_value=meta),
            patch("frappe.get_all", return_value=[]),
            patch(
                "frappe.db.exists",
                side_effect=lambda doctype, filters: (
                    filters.get("attached_to_doctype", [None, []])[1]
                    and "Vehicle" in filters["attached_to_doctype"][1]
                ),
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_fleet_attachment_content_reuse(driver_file)

    def test_private_file_content_cannot_be_reused_across_companies_through_child_rows(
        self,
    ):
        from sotrama.permissions import prevent_fleet_attachment_content_reuse

        file_meta = Mock()
        file_meta.has_field.side_effect = lambda field: (
            field
            in {
                "sotrama_private_fleet_attachment",
                "sotrama_private_driver_attachment",
            }
        )
        child_meta = Mock()
        child_meta.has_field.return_value = False
        vehicle_meta = Mock()
        vehicle_meta.has_field.side_effect = lambda field: field == "company"
        target = frappe._dict(
            name="FILE-TARGET",
            attached_to_doctype="Vehicle Document",
            attached_to_name="VD-A",
            content_hash="shared-fleet-content",
            is_new=lambda: False,
        )
        duplicate = frappe._dict(
            name="FILE-OTHER-COMPANY",
            attached_to_doctype="Vehicle Document",
            attached_to_name="VD-B",
            sotrama_private_fleet_attachment=1,
            sotrama_private_driver_attachment=0,
        )

        def get_meta(doctype):
            return {
                "File": file_meta,
                "Vehicle Document": child_meta,
                "Vehicle": vehicle_meta,
            }[doctype]

        def get_value(doctype, name, fields, as_dict=False):
            if doctype == "Vehicle Document":
                return frappe._dict(
                    parenttype="Vehicle",
                    parent="VEH-A" if name == "VD-A" else "VEH-B",
                )
            if doctype == "Vehicle":
                return "COMP-A" if name == "VEH-A" else "COMP-B"
            raise AssertionError(f"Unexpected lookup: {doctype} {name}")

        with (
            patch("frappe.get_meta", side_effect=get_meta),
            patch("frappe.get_all", return_value=[duplicate]),
            patch("frappe.db.get_value", side_effect=get_value),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_fleet_attachment_content_reuse(target)

        detached_duplicate = frappe._dict(
            name="FILE-DETACHED",
            attached_to_doctype=None,
            attached_to_name=None,
            sotrama_private_fleet_attachment=1,
            sotrama_private_driver_attachment=0,
        )
        with (
            patch("frappe.get_meta", side_effect=get_meta),
            patch("frappe.get_all", return_value=[detached_duplicate]),
            patch(
                "frappe.db.get_value",
                side_effect=lambda doctype, name, fields, as_dict=False: (
                    frappe._dict(parenttype="Vehicle", parent="VEH-A")
                    if doctype == "Vehicle Document"
                    else "COMP-A"
                ),
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_fleet_attachment_content_reuse(target)

        with (
            patch("frappe.get_meta", side_effect=get_meta),
            patch("frappe.get_all", return_value=[duplicate]),
            patch(
                "frappe.db.get_value",
                side_effect=lambda doctype, name, fields, as_dict=False: (
                    frappe._dict(parenttype="Vehicle", parent="VEH-A")
                    if doctype == "Vehicle Document"
                    else "COMP-A"
                ),
            ),
            patch("frappe.db.exists", return_value=False),
        ):
            prevent_fleet_attachment_content_reuse(target)

        target.file_url = "/files/protected.pdf"
        private_source = frappe._dict(
            name="FILE-PRIVATE-SOURCE",
            attached_to_doctype="Vehicle Document",
            attached_to_name="VD-B",
            file_url="/files/protected.pdf",
            is_private=1,
            sotrama_private_fleet_attachment=1,
            sotrama_private_driver_attachment=0,
        )
        with (
            patch.dict(frappe.session, {"user": "former-owner@example.invalid"}),
            patch("frappe.get_meta", side_effect=get_meta),
            patch("frappe.get_all", return_value=[private_source]),
            patch(
                "frappe.db.get_value",
                side_effect=lambda doctype, name, fields, as_dict=False: (
                    frappe._dict(parenttype="Vehicle", parent="VEH-A")
                    if doctype == "Vehicle Document"
                    else "COMP-A"
                ),
            ),
            patch(
                "sotrama.permissions.can_access_company_scoped_fleet_attachment",
                return_value=False,
            ) as can_access_source,
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_fleet_attachment_content_reuse(target)

        can_access_source.assert_called_once_with(
            private_source, "former-owner@example.invalid", ptype="read"
        )

        target.file_url = "/private/files/orphan.pdf"
        target.is_new = lambda: True
        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("frappe.get_meta", side_effect=get_meta),
            patch("frappe.get_all", return_value=[]),
            patch(
                "frappe.db.get_value",
                side_effect=lambda doctype, name, fields, as_dict=False: (
                    frappe._dict(parenttype="Vehicle", parent="VEH-A")
                    if doctype == "Vehicle Document"
                    else "COMP-A"
                ),
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_fleet_attachment_content_reuse(target)

        target.is_new = lambda: False
        target.get_doc_before_save = lambda: frappe._dict(
            file_url="/private/files/previous.pdf"
        )
        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("frappe.get_meta", side_effect=get_meta),
            patch("frappe.get_all", return_value=[]),
            patch(
                "frappe.db.get_value",
                side_effect=lambda doctype, name, fields, as_dict=False: (
                    frappe._dict(parenttype="Vehicle", parent="VEH-A")
                    if doctype == "Vehicle Document"
                    else "COMP-A"
                ),
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_fleet_attachment_content_reuse(target)

    def test_fleet_attachment_moves_require_old_parent_and_same_company(self):
        from sotrama.permissions import secure_company_scoped_fleet_attachment

        previous = frappe._dict(
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-B",
        )
        file_doc = frappe._dict(
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-A",
            file_url="/private/files/fleet.pdf",
            is_private=0,
        )
        file_doc.get_doc_before_save = lambda: previous

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch(
                "sotrama.permissions.is_direct_company_scoped_fleet_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.permissions.is_company_scoped_fleet_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.permissions._get_file_attachment_company",
                side_effect=["COMP-B", "COMP-A"],
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            secure_company_scoped_fleet_attachment(file_doc)

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch(
                "sotrama.permissions.is_direct_company_scoped_fleet_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.permissions.is_company_scoped_fleet_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.permissions._get_file_attachment_company",
                side_effect=["COMP-A", "COMP-A"],
            ),
            patch(
                "sotrama.permissions.can_access_company_scoped_fleet_attachment",
                return_value=False,
            ) as can_access_previous,
            self.assertRaises(frappe.PermissionError),
        ):
            secure_company_scoped_fleet_attachment(file_doc)

        can_access_previous.assert_called_once_with(
            previous, "fleet@example.invalid", ptype="write"
        )

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch(
                "sotrama.permissions.is_direct_company_scoped_fleet_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.permissions.is_company_scoped_fleet_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.permissions._get_file_attachment_company",
                side_effect=["COMP-A", "COMP-A"],
            ),
            patch(
                "sotrama.permissions.can_access_company_scoped_fleet_attachment",
                return_value=True,
            ),
            patch("sotrama.permissions.prevent_fleet_attachment_content_reuse"),
        ):
            secure_company_scoped_fleet_attachment(file_doc)

        self.assertEqual(file_doc.is_private, 1)

    def test_detached_fleet_protected_file_cannot_be_reattached_by_regular_user(self):
        from sotrama.permissions import secure_company_scoped_fleet_attachment

        previous = frappe._dict(
            attached_to_doctype=None,
            attached_to_name=None,
            sotrama_private_fleet_attachment=1,
        )
        file_doc = frappe._dict(
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-NEW",
            file_url="/private/files/detached.pdf",
            is_private=1,
        )
        file_doc.get_doc_before_save = lambda: previous

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch(
                "sotrama.permissions.is_direct_company_scoped_fleet_attachment",
                side_effect=[True, False],
            ),
            patch(
                "sotrama.permissions.is_company_scoped_fleet_attachment",
                return_value=True,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            secure_company_scoped_fleet_attachment(file_doc)

    def test_file_query_conditions_hide_detached_fleet_provenance_rows(self):
        from sotrama.permissions import file_query_conditions

        meta = Mock()
        meta.has_field.return_value = True
        with patch("frappe.get_meta", return_value=meta):
            conditions = file_query_conditions("fleet@example.invalid")

        self.assertIn("fleet_private_file", conditions)
        self.assertIn("sotrama_private_fleet_attachment", conditions)
        self.assertIn("Vehicle", conditions)
        self.assertIn("NOT IN", conditions)
        self.assertIn(
            "COALESCE(`tabFile`.`sotrama_private_fleet_attachment`, 0) = 0",
            conditions,
        )
        self.assertIsNone(file_query_conditions("Administrator"))

    def test_fleet_attachment_docinfo_hides_unrelated_duplicate_rows(self):
        from sotrama.permissions import _filter_fleet_attachment_metadata

        docinfo = frappe._dict(
            attachments=[
                frappe._dict(name="FILE-DUPLICATE"),
                frappe._dict(name="FILE-DIRECT"),
            ],
            attachment_logs=[frappe._dict(content="Attachment added")],
        )
        response = frappe._dict(docinfo=docinfo)
        with (
            patch("sotrama.permissions.frappe.response", response),
            patch(
                "sotrama.permissions._get_unrelated_fleet_attachment_names",
                return_value={"FILE-DUPLICATE"},
            ),
        ):
            _filter_fleet_attachment_metadata("Vehicle", "VEH-001")

        self.assertEqual(
            [attachment.name for attachment in docinfo.attachments],
            ["FILE-DIRECT"],
        )
        self.assertEqual(docinfo.attachment_logs, [])
