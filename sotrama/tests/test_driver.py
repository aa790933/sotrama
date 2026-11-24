import unittest

# Frappe integration tests for Sotrama driver behavior.
import uuid
from unittest.mock import Mock, patch

import frappe
from frappe.utils import add_days, today

from sotrama.tests.helpers import (
    _delete_test_record,
    _get_test_company,
    _sotrama_package_path,
)


class TestDriver(unittest.TestCase):
    """Test Driver doctype validation."""

    def test_off_road_operator_can_be_recorded_without_road_licence(self):
        """Road licence details are required only for regulated transport tasks."""
        from sotrama.tp.doctype.driver.driver import Driver

        driver = frappe.new_doc("Driver")
        driver.driver_name = "Test Driver"
        driver.license_number = None
        driver.license_class = None
        driver.license_expiry = None
        Driver._validate_license(driver)

    def test_driver_license_expiry_warning(self):
        """Test that expired license shows warning."""
        driver = frappe.new_doc("Driver")
        driver.driver_name = "Test Driver"
        driver.company = _get_test_company()
        driver.license_number = "LIC-001"
        driver.license_expiry = add_days(today(), -1)  # expired yesterday
        driver.insert()  # Should not throw, just msgprint
        frappe.delete_doc("Driver", driver.name, ignore_on_trash=True)


class TestDriverStatusWorkflow(unittest.TestCase):
    def setUp(self):
        self.company = _get_test_company()
        self.driver = frappe.new_doc("Driver")
        self.driver.driver_name = f"Test Driver {uuid.uuid4().hex[:8]}"
        self.driver.company = self.company
        self.driver.license_number = f"TEST-{uuid.uuid4().hex[:8]}"
        self.driver.license_expiry = add_days(today(), 365)
        self.driver.insert(ignore_permissions=True)
        self.driver.submit()

    def tearDown(self):
        if frappe.db.exists("Driver", self.driver.name):
            _delete_test_record("Driver", self.driver.name)

    def test_driver_status_uses_audited_transitions_and_revalidates_on_reactivation(
        self,
    ):
        from sotrama.tp.doctype.driver.driver import update_driver_status

        update_driver_status(self.driver.name, "Suspended")
        self.assertEqual(
            frappe.db.get_value("Driver", self.driver.name, "status"), "Suspended"
        )

        update_driver_status(self.driver.name, "Active")
        self.assertEqual(
            frappe.db.get_value("Driver", self.driver.name, "status"), "Active"
        )

        update_driver_status(self.driver.name, "Terminated")
        with self.assertRaises(frappe.ValidationError):
            update_driver_status(self.driver.name, "Active")

        comments = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Driver", "reference_name": self.driver.name},
            fields=["content"],
            order_by="creation asc",
        )
        self.assertTrue(
            any("Terminated" in (comment.content or "") for comment in comments)
        )


class TestDriverFileMetadataPrivacy(unittest.TestCase):
    def test_duplicate_file_rows_sharing_driver_content_hash_remain_hr_only(self):
        from sotrama.permissions import (
            _secure_duplicate_driver_file_rows,
            can_access_driver_private_attachment,
            file_has_permission,
            file_query_conditions,
            is_driver_private_attachment,
        )

        duplicate = frappe._dict(
            name="FILE-DUPLICATE",
            content_hash="DRIVER-EVIDENCE-HASH",
            attached_to_doctype="Purchase Invoice",
            attached_to_name="PINV-001",
            is_private=1,
            is_remote_file=False,
            owner="fleet@example.invalid",
            sotrama_private_driver_attachment=1,
        )
        file_meta = frappe._dict(has_field=Mock(return_value=True))
        with (
            patch("frappe.get_meta", return_value=file_meta),
            patch("frappe.db.exists", return_value="FILE-DRIVER-SOURCE"),
        ):
            self.assertTrue(is_driver_private_attachment(duplicate))
            with patch("frappe.get_roles", return_value=["Fleet Manager"]):
                self.assertFalse(
                    file_has_permission(
                        duplicate, user="fleet@example.invalid", ptype="read"
                    )
                )

        from sotrama.overrides.file import DriverPrivateFileMixin

        with (
            patch(
                "sotrama.permissions.is_driver_private_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.permissions.can_access_driver_private_attachment",
                return_value=False,
            ),
        ):
            self.assertFalse(DriverPrivateFileMixin.is_downloadable(duplicate))

        with (
            patch("frappe.get_meta", return_value=file_meta),
            patch("frappe.db.exists", return_value="FILE-DRIVER-SOURCE"),
            patch("frappe.get_roles", return_value=["HR Manager"]),
        ):
            self.assertFalse(
                can_access_driver_private_attachment(duplicate, "hr@example.invalid")
            )
            self.assertFalse(
                file_has_permission(duplicate, user="hr@example.invalid", ptype="read")
            )

        source_file = frappe._dict(
            name="FILE-DRIVER-SOURCE",
            content_hash="DRIVER-EVIDENCE-HASH",
            attached_to_doctype="Driver",
            attached_to_name="DRV-PRIVATE-001",
            is_private=1,
            is_remote_file=False,
        )
        with (
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.has_permission", return_value=True) as has_permission,
        ):
            self.assertTrue(
                can_access_driver_private_attachment(source_file, "hr@example.invalid")
            )
        has_permission.assert_called_once_with(
            "Driver",
            "read",
            doc="DRV-PRIVATE-001",
            user="hr@example.invalid",
            ignore_share_permissions=True,
        )
        with (
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.has_permission", return_value=False) as has_permission,
        ):
            self.assertFalse(
                file_has_permission(
                    source_file, user="hr@example.invalid", ptype="write"
                )
            )
        has_permission.assert_called_once_with(
            "Driver",
            "write",
            doc="DRV-PRIVATE-001",
            user="hr@example.invalid",
            ignore_share_permissions=True,
        )
        with patch("frappe.get_roles", return_value=["HR Manager"]):
            self.assertFalse(
                can_access_driver_private_attachment(
                    source_file, "hr@example.invalid", ptype="share"
                )
            )
        with (
            patch("frappe.get_roles", return_value=["System Manager"]),
            patch("frappe.has_permission", return_value=True),
        ):
            self.assertTrue(
                can_access_driver_private_attachment(
                    source_file, "system@example.invalid", ptype="share"
                )
            )

        with patch("frappe.get_meta", return_value=file_meta):
            query_condition = file_query_conditions("fleet@example.invalid")
        self.assertIn("content_hash", query_condition)
        self.assertIn("driver_private_file", query_condition)

        source = frappe._dict(
            name="FILE-DRIVER-SOURCE", content_hash="DRIVER-EVIDENCE-HASH"
        )
        duplicate_to_secure = frappe._dict(
            name="FILE-DUPLICATE",
            content_hash="DRIVER-EVIDENCE-HASH",
            attached_to_doctype="Purchase Invoice",
            attached_to_name="PINV-001",
            attached_to_field="attachment",
            is_private=0,
            is_remote_file=False,
            file_url="/files/driver-evidence.pdf",
            flags=frappe._dict(),
            save=Mock(),
            handle_is_private_changed=Mock(),
        )
        with (
            patch("frappe.get_all", return_value=[frappe._dict(name="FILE-DUPLICATE")]),
            patch("frappe.get_doc", return_value=duplicate_to_secure),
            patch("sotrama.permissions._redact_driver_attachment_comments"),
            patch("sotrama.permissions._clear_attached_file_field") as clear_field,
            patch(
                "sotrama.permissions._remove_private_driver_file_shares"
            ) as remove_shares,
        ):
            _secure_duplicate_driver_file_rows(source)
        self.assertEqual(duplicate_to_secure.sotrama_private_driver_attachment, 1)
        self.assertEqual(duplicate_to_secure.is_private, 1)
        self.assertEqual(duplicate_to_secure.save.call_count, 2)
        self.assertTrue(
            all(
                call.kwargs == {"ignore_permissions": True}
                for call in duplicate_to_secure.save.call_args_list
            )
        )
        clear_field.assert_called_once_with(duplicate_to_secure)
        remove_shares.assert_called_once_with("FILE-DUPLICATE")

    def test_private_file_migration_fails_closed_on_path_collision(self):
        from sotrama.permissions import _validate_driver_private_file_paths

        file_doc = frappe._dict(
            name="FILE-COLLISION",
            file_url="/files/driver-evidence.pdf",
            is_remote_file=False,
        )
        with (
            patch(
                "frappe.get_site_path",
                side_effect=[
                    "C:/sotrama/sites/site1/public/files/driver-evidence.pdf",
                    "C:/sotrama/sites/site1/private/files/driver-evidence.pdf",
                ],
            ),
            patch("pathlib.Path.exists", side_effect=[True, True]),
            self.assertRaises(frappe.ValidationError) as raised,
        ):
            _validate_driver_private_file_paths([file_doc])
        self.assertIn("FILE-COLLISION", str(raised.exception))

    def test_migration_repairs_private_flag_with_public_file_url(self):
        from sotrama.migrations.security import migrate_driver_private_attachments

        file_doc = frappe._dict(
            name="FILE-PUBLIC-URL",
            attached_to_doctype="Driver",
            attached_to_name="DRV-001",
            file_url="/files/legacy-private-flag.pdf",
            is_private=1,
            is_remote_file=False,
            save=Mock(),
        )
        with (
            patch("sotrama.migrations.security._ensure_driver_file_privacy_field"),
            patch(
                "frappe.get_meta",
                return_value=frappe._dict(has_field=Mock(return_value=False)),
            ),
            patch("frappe.get_all", return_value=[frappe._dict(name=file_doc.name)]),
            patch("frappe.get_doc", return_value=file_doc),
            patch("sotrama.migrations.security._validate_driver_private_file_paths"),
            patch("sotrama.migrations.security._remove_private_driver_file_shares"),
        ):
            migrate_driver_private_attachments()
        file_doc.save.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(file_doc.sotrama_private_driver_attachment, 1)

    def test_driver_compliance_child_table_is_scoped_to_hr_parent_access(self):
        from sotrama.permissions import (
            _check_driver_compliance_child_rpc_access,
            driver_compliance_record_query_conditions,
            get_list_with_tp_settings_permissions,
            get_value_with_tp_settings_field_permissions,
        )

        with patch("frappe.get_roles", return_value=["Fleet Manager"]):
            self.assertEqual(
                driver_compliance_record_query_conditions("fleet@example.invalid"),
                "1=0",
            )
        with patch("frappe.get_roles", return_value=["HR Manager"]):
            self.assertEqual(
                driver_compliance_record_query_conditions("hr@example.invalid"),
                "1=0",
            )
        with patch("frappe.get_roles", return_value=["System Manager"]):
            self.assertIsNone(
                driver_compliance_record_query_conditions("system@example.invalid")
            )

        with (
            patch.dict(frappe.session, {"user": "hr@example.invalid"}),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            _check_driver_compliance_child_rpc_access("Driver Compliance Record")
        with (
            patch.dict(frappe.session, {"user": "hr@example.invalid"}),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            get_value_with_tp_settings_field_permissions(
                "Driver Compliance Record", ["result"], filters={"name": "DCR-001"}
            )
        with (
            patch.dict(frappe.session, {"user": "hr@example.invalid"}),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            get_list_with_tp_settings_permissions("Driver Compliance Record")

        from sotrama.permissions import (
            validate_link_and_fetch_without_tp_settings_singleton,
        )

        with (
            patch.dict(frappe.session, {"user": "hr@example.invalid"}),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            validate_link_and_fetch_without_tp_settings_singleton(
                "Driver Compliance Record", "DCR-001", ["result"]
            )

    def test_duplicate_driver_evidence_is_hidden_from_unrelated_attachment_views(self):
        from sotrama.permissions import (
            _filter_driver_attachment_metadata,
            get_filtered_attachments_with_driver_attachment_filter,
        )

        docinfo = frappe._dict(
            attachments=[
                frappe._dict(name="FILE-DUPLICATE", file_name="medical-evidence.pdf"),
                frappe._dict(name="FILE-ORDINARY", file_name="invoice.pdf"),
            ],
            attachment_logs=[frappe._dict(content="contains duplicate file URL")],
        )
        with (
            patch("frappe.response", frappe._dict(docinfo=docinfo)),
            patch(
                "sotrama.permissions._get_driver_private_attachment_names",
                return_value={"FILE-DUPLICATE"},
            ),
        ):
            _filter_driver_attachment_metadata("Purchase Invoice", "PINV-001")
        self.assertEqual([row.name for row in docinfo.attachments], ["FILE-ORDINARY"])
        self.assertEqual(docinfo.attachment_logs, [])

        with (
            patch(
                "frappe.desk.form.load.get_filtered_attachments",
                return_value=[
                    frappe._dict(name="FILE-DUPLICATE"),
                    frappe._dict(name="FILE-ORDINARY"),
                ],
            ),
            patch(
                "sotrama.permissions._get_driver_private_attachment_names",
                return_value={"FILE-DUPLICATE"},
            ),
        ):
            attachments = get_filtered_attachments_with_driver_attachment_filter(
                "Purchase Invoice", "PINV-001", "[]"
            )
        self.assertEqual([row.name for row in attachments], ["FILE-ORDINARY"])

    def test_file_doctype_permission_checks_and_queries_hide_driver_evidence(self):
        from sotrama.permissions import file_has_permission, file_query_conditions

        self.assertTrue(file_has_permission(None, user="workshop@example.invalid"))
        with (
            patch("sotrama.permissions.frappe.get_roles", return_value=["Workshop"]),
            patch("sotrama.permissions.frappe.get_meta") as get_meta,
        ):
            get_meta.return_value.has_field.return_value = True
            condition = file_query_conditions("workshop@example.invalid")

        self.assertIn("sotrama_private_driver_attachment", condition)
        self.assertIn("Driver Compliance Record", condition)

        with patch("sotrama.permissions.frappe.get_roles", return_value=["HR Manager"]):
            hr_condition = file_query_conditions("hr@example.invalid")
        self.assertIn("Driver", hr_condition)
        self.assertIn("NOT IN", hr_condition)

    def test_driver_attachment_access_checks_parent_company_permission(self):
        from sotrama.permissions import can_access_driver_private_attachment

        driver_file = frappe._dict(
            attached_to_doctype="Driver",
            attached_to_name="DRV-001",
        )
        with (
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.has_permission", return_value=True) as has_permission,
        ):
            self.assertTrue(
                can_access_driver_private_attachment(driver_file, "hr@example.invalid")
            )
        has_permission.assert_called_once_with(
            "Driver",
            "read",
            doc="DRV-001",
            user="hr@example.invalid",
            ignore_share_permissions=True,
        )

        with (
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.has_permission", return_value=False),
        ):
            self.assertFalse(
                can_access_driver_private_attachment(driver_file, "hr@example.invalid")
            )

        child_file = frappe._dict(
            attached_to_doctype="Driver Compliance Record",
            attached_to_name="DCR-001",
        )
        with (
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.db.get_value", return_value="DRV-CHILD-001") as get_parent,
            patch("frappe.has_permission", return_value=True) as has_permission,
        ):
            self.assertTrue(
                can_access_driver_private_attachment(child_file, "hr@example.invalid")
            )
        get_parent.assert_called_once_with(
            "Driver Compliance Record", "DCR-001", "parent"
        )
        has_permission.assert_called_once_with(
            "Driver",
            "read",
            doc="DRV-CHILD-001",
            user="hr@example.invalid",
            ignore_share_permissions=True,
        )

    def test_driver_form_and_docinfo_responses_hide_attachment_metadata_from_fleet(
        self,
    ):
        from sotrama.permissions import (
            get_docinfo_with_driver_attachment_filter,
            getdoc_with_driver_attachment_filter,
        )

        docinfo = frappe._dict(
            attachments=[frappe._dict(file_name="private-certificate.pdf")],
            attachment_logs=[frappe._dict(content="private attachment URL")],
        )

        def fake_getdoc(doctype, name):
            frappe.response["docinfo"] = docinfo
            return "loaded"

        with (
            patch("frappe.desk.form.load.getdoc", side_effect=fake_getdoc),
            patch("sotrama.permissions._has_hr_file_access", return_value=False),
            patch("frappe.has_permission", return_value=True),
        ):
            self.assertEqual(
                getdoc_with_driver_attachment_filter("Driver", "DRV-001"), "loaded"
            )
        self.assertEqual(docinfo.attachments, [])
        self.assertEqual(docinfo.attachment_logs, [])

        separate_docinfo = frappe._dict(
            attachments=[frappe._dict(file_name="private-certificate.pdf")],
            attachment_logs=[frappe._dict(content="private attachment URL")],
        )

        def fake_get_docinfo(*args, **kwargs):
            frappe.response["docinfo"] = separate_docinfo

        with (
            patch("frappe.desk.form.load.get_docinfo", side_effect=fake_get_docinfo),
            patch("sotrama.permissions._has_hr_file_access", return_value=False),
            patch("frappe.has_permission", return_value=True),
        ):
            get_docinfo_with_driver_attachment_filter(
                doc=frappe._dict(doctype="Driver", name="DRV-001")
            )
        self.assertEqual(separate_docinfo.attachments, [])
        self.assertEqual(separate_docinfo.attachment_logs, [])

        child_docinfo = frappe._dict(
            attachments=[frappe._dict(file_name="private-medical-record.pdf")],
            attachment_logs=[frappe._dict(content="private child attachment URL")],
        )

        def fake_child_get_docinfo(*args, **kwargs):
            frappe.response["docinfo"] = child_docinfo

        with (
            patch(
                "frappe.desk.form.load.get_docinfo", side_effect=fake_child_get_docinfo
            ) as child_get_docinfo,
            patch("sotrama.permissions._has_hr_file_access", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            get_docinfo_with_driver_attachment_filter(
                doc=frappe._dict(doctype="Driver Compliance Record", name="DCR-001")
            )
        child_get_docinfo.assert_not_called()

    def test_separate_driver_docinfo_endpoint_checks_parent_read_permission(self):
        from sotrama.permissions import get_docinfo_with_driver_attachment_filter

        with (
            patch.dict(frappe.session, {"user": "fleet@example.invalid"}),
            patch(
                "frappe.has_permission", side_effect=frappe.PermissionError
            ) as has_permission,
            patch("frappe.desk.form.load.get_docinfo") as get_docinfo,
            self.assertRaises(frappe.PermissionError),
        ):
            get_docinfo_with_driver_attachment_filter(
                doc=frappe._dict(doctype="Driver", name="DRV-RESTRICTED")
            )
        has_permission.assert_called_once_with(
            "Driver",
            "read",
            doc="DRV-RESTRICTED",
            user="fleet@example.invalid",
            ignore_share_permissions=True,
        )
        get_docinfo.assert_not_called()

    def test_driver_attachment_gallery_returns_no_hr_files_to_workshop(self):
        from sotrama.permissions import (
            get_filtered_attachments_with_driver_attachment_filter,
        )

        with (
            patch(
                "frappe.desk.form.load.get_filtered_attachments",
                return_value=[frappe._dict(file_name="private-certificate.pdf")],
            ),
            patch("sotrama.permissions._has_hr_file_access", return_value=False),
            patch("frappe.has_permission", return_value=True),
        ):
            result = get_filtered_attachments_with_driver_attachment_filter(
                "Driver", "DRV-001", "[]"
            )
        self.assertEqual(result, [])

        with (
            patch(
                "frappe.desk.form.load.get_filtered_attachments",
                return_value=[frappe._dict(file_name="private-certificate.pdf")],
            ) as get_attachments,
            patch("sotrama.permissions._has_hr_file_access", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            get_filtered_attachments_with_driver_attachment_filter(
                "Driver Compliance Record", "DCR-001", "[]"
            )
        get_attachments.assert_not_called()


class TestDriverIntegration(unittest.TestCase):
    """Domain-focused integration coverage extracted from the former setup monolith."""

    def test_driver_employee_link_remains_available_and_optional_by_default(self):
        meta = frappe.get_meta("Driver", cached=False)
        employee_field = meta.get_field("employee")
        status_field = meta.get_field("status")
        self.assertIsNotNone(employee_field)
        self.assertEqual(employee_field.fieldtype, "Link")
        self.assertEqual(employee_field.options, "Employee")
        self.assertFalse(employee_field.hidden)
        self.assertFalse(employee_field.reqd)
        self.assertTrue(employee_field.allow_on_submit)
        self.assertIn("Only HR Manager and System Manager", employee_field.description)
        self.assertFalse(status_field.allow_on_submit)
        self.assertEqual(status_field.read_only_depends_on, "eval:doc.docstatus == 1")

        script = (_sotrama_package_path() / "public/js/driver.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("frappe.user.has_role('HR Manager')", script)
        self.assertIn("set_df_property('employee', 'read_only'", script)

    def test_fleet_roles_cannot_remove_an_existing_hrms_employee_link(self):
        driver = frappe.new_doc("Driver")
        driver.company = "SOTRAMA-TEST-COMPANY"
        driver.employee = None
        with (
            patch.object(
                driver,
                "get_doc_before_save",
                return_value=frappe._dict(employee="EMP-TEST-001"),
            ),
            patch(
                "frappe.only_for",
                side_effect=frappe.PermissionError("HR Manager role required"),
            ),
            patch(
                "sotrama.tp.settings.get_tp_setting",
                side_effect=lambda key, default=None: default,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            driver._validate_employee_link()

        with (
            patch.object(
                driver,
                "get_doc_before_save",
                return_value=frappe._dict(employee="EMP-TEST-001"),
            ),
            patch("frappe.only_for") as only_for,
            patch(
                "sotrama.tp.settings.get_tp_setting",
                side_effect=lambda key, default=None: default,
            ),
        ):
            driver._validate_employee_link()
        only_for.assert_called_once_with(["System Manager", "HR Manager"])

    def test_driver_licence_categories_include_the_2025_decree_categories(self):
        driver_meta = frappe.get_meta("Driver", cached=False)
        licence_field = driver_meta.get_field("license_class")
        categories = set((licence_field.options or "").splitlines())
        for category in (
            "A1",
            "A",
            "B",
            "B(E)",
            "C1",
            "C1(E)",
            "C",
            "C(E)",
            "D",
            "D(E)",
            "F",
        ):
            self.assertIn(category, categories)
        for fieldname in (
            "license_number",
            "license_class",
            "license_expiry",
            "license_issue_date",
        ):
            self.assertTrue(driver_meta.get_field(fieldname).allow_on_submit)

    def test_driver_compliance_history_is_restricted_to_hr_manager(self):
        driver_meta = frappe.get_meta("Driver", cached=False)
        compliance_field = driver_meta.get_field("compliance_records")
        medical_expiry = driver_meta.get_field("medical_expiry")
        date_of_birth = driver_meta.get_field("date_of_birth")
        national_id = driver_meta.get_field("national_id")
        self.assertEqual(compliance_field.fieldtype, "Table")
        self.assertEqual(compliance_field.options, "Driver Compliance Record")
        self.assertEqual(compliance_field.permlevel, 1)
        self.assertEqual(medical_expiry.permlevel, 1)
        self.assertEqual(date_of_birth.permlevel, 1)
        self.assertEqual(national_id.permlevel, 1)
        self.assertTrue(date_of_birth.allow_on_submit)
        self.assertTrue(national_id.allow_on_submit)
        self.assertTrue(compliance_field.allow_on_submit)
        self.assertTrue(medical_expiry.allow_on_submit)

        hr_permissions = [
            permission
            for permission in driver_meta.permissions
            if permission.role == "HR Manager" and permission.permlevel == 1
        ]
        self.assertTrue(hr_permissions)
        self.assertTrue(hr_permissions[0].read)
        self.assertTrue(hr_permissions[0].write)

        system_manager_permissions = [
            permission
            for permission in driver_meta.permissions
            if permission.role == "System Manager" and permission.permlevel == 1
        ]
        self.assertTrue(system_manager_permissions)
        self.assertTrue(system_manager_permissions[0].read)
        self.assertTrue(system_manager_permissions[0].write)

        fleet_permissions = [
            permission
            for permission in driver_meta.permissions
            if permission.role == "Fleet Manager" and permission.permlevel == 1
        ]
        workshop_permissions = [
            permission
            for permission in driver_meta.permissions
            if permission.role == "Workshop" and permission.permlevel == 1
        ]
        self.assertFalse(fleet_permissions)
        self.assertFalse(workshop_permissions)

        record_meta = frappe.get_meta("Driver Compliance Record", cached=False)
        self.assertTrue(record_meta.istable)
        self.assertIsNotNone(record_meta.get_field("valid_until"))

    def test_transport_activity_options_follow_road_code_articles_79_80(self):
        field = frappe.get_meta("Operational Task", cached=False).get_field(
            "transport_kind"
        )
        activities = set((field.options or "").splitlines())
        for activity in (
            "Collective Passenger Transport",
            "School Transport",
            "Goods Transport",
            "Dangerous Goods Transport",
            "Taxi Transport",
        ):
            self.assertIn(activity, activities)

    def test_regulated_transport_requires_current_driver_licence_data(self):
        from sotrama.tp.validation import validate_professional_transport_certificate

        driver = frappe._dict(
            license_number=None,
            license_class="C",
            license_expiry="2027-12-31",
            professional_certificate="/private/files/brevet.pdf",
            professional_certificate_number="BP-001",
            compliance_records=[],
        )
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Goods Transport"
            )

        driver.license_number = "LIC-001"
        driver.license_class = None
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Goods Transport"
            )

        driver.license_class = "C"
        driver.license_expiry = "2020-01-01"
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Goods Transport"
            )

    def test_regulated_transport_always_requires_a_current_licence_when_optional_compliance_policy_is_disabled(
        self,
    ):
        from sotrama.tp.validation import validate_professional_transport_certificate

        driver = frappe._dict(
            license_number=None,
            license_class="C",
            license_expiry="2027-12-31",
            professional_certificate=None,
            professional_certificate_number=None,
            compliance_records=[],
        )
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=0),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Goods Transport"
            )

        driver.license_number = "12345678"
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=0),
            patch("frappe.get_doc", return_value=driver),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Goods Transport"
            )

    def test_regulated_transport_requires_current_certificate_and_screening_when_policy_is_enabled(
        self,
    ):
        from sotrama.tp.validation import validate_professional_transport_certificate

        driver = frappe._dict(
            license_number="12345678",
            license_class="C",
            license_expiry="2027-12-31",
            professional_certificate=None,
            professional_certificate_number=None,
            compliance_records=[],
        )
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Goods Transport"
            )

        driver.professional_certificate_number = "BP-TEST-001"
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Goods Transport"
            )

        driver.compliance_records = [
            frappe._dict(
                check_type="Medical Fitness Examination",
                test_date=today(),
                result="Fit",
                valid_until=add_days(today(), 30),
                idx=1,
            ),
            frappe._dict(
                check_type="Drug Screening",
                test_date=today(),
                result="Negative",
                valid_until=add_days(today(), 30),
                idx=2,
            ),
        ]
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Goods Transport"
            )

        driver.compliance_records[0].test_date = add_days(today(), 1)
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Goods Transport"
            )

    def test_linking_employee_does_not_copy_personal_contact_details_to_fleet_fields(
        self,
    ):
        from sotrama.tp.doctype.driver.driver import Driver

        employee = frappe._dict(
            employee_name="Mechanic Test",
            company="COMPANY-A",
            status="Active",
            cell_number="0555000000",
            company_email=None,
            personal_email="personal@example.invalid",
            date_of_joining="2020-01-15",
            check_permission=Mock(),
        )
        driver = frappe.new_doc("Driver")
        driver.employee = "EMP-TEST-001"
        with (
            patch("frappe.only_for"),
            patch("frappe.get_doc", return_value=employee),
            patch("frappe.db.exists", return_value=None),
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(company="COMPANY-A", status="Active"),
            ),
            patch(
                "sotrama.tp.settings.get_tp_setting",
                side_effect=lambda key, default=0: default,
            ),
            patch("sotrama.tp.settings.validate_company_access"),
        ):
            Driver._validate_employee_link(driver)

        self.assertEqual(driver.driver_name, "Mechanic Test")
        self.assertIsNone(driver.phone)
        self.assertIsNone(driver.email)
        self.assertEqual(str(driver.hire_date), "2020-01-15")

    def test_existing_driver_employee_projection_is_company_filtered(self):
        from sotrama.tp.doctype.driver.driver import Driver

        driver = frappe.new_doc("Driver")
        driver.employee = "EMP-TEST-001"
        driver.company = "COMPANY-A"
        driver.status = "Active"
        with (
            patch.object(
                driver,
                "get_doc_before_save",
                return_value=frappe._dict(employee="EMP-TEST-001"),
            ),
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(company="COMPANY-A", status="Active"),
            ) as get_employee,
            patch("frappe.db.exists", return_value=None),
            patch(
                "sotrama.tp.settings.get_tp_setting",
                side_effect=lambda key, default=0: default,
            ),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
        ):
            Driver._validate_employee_link(driver)

        get_employee.assert_called_once_with(
            "Employee",
            {"name": "EMP-TEST-001", "company": "COMPANY-A"},
            ["company", "status"],
            as_dict=True,
        )
        validate_company.assert_called_once_with("COMPANY-A", "Employee")

    def test_only_post_incident_inspections_can_reference_an_inactive_driver(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.vehicle = "VEH-TEST-001"
        inspection.company = "SOTRAMA-TEST-COMPANY"
        inspection.driver = "DRV-TEST-001"
        inspection.inspection_type = "Pre-Use"
        module = "sotrama.tp.doctype.vehicle_inspection.vehicle_inspection"
        with (
            patch(
                f"{module}.frappe.db.get_value",
                side_effect=[
                    frappe._dict(company="SOTRAMA-TEST-COMPANY", docstatus=1),
                    frappe._dict(company="SOTRAMA-TEST-COMPANY", status="Suspended"),
                ],
            ),
            patch("frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
            self.assertRaises(frappe.ValidationError),
        ):
            inspection._set_company_from_vehicle()

        inspection.inspection_type = "Post-Incident"
        with (
            patch(
                f"{module}.frappe.db.get_value",
                side_effect=[
                    frappe._dict(company="SOTRAMA-TEST-COMPANY", docstatus=1),
                    frappe._dict(company="SOTRAMA-TEST-COMPANY", status="Suspended"),
                ],
            ),
            patch("frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
        ):
            inspection._set_company_from_vehicle()

    def test_driver_hr_attachments_are_private_to_hr_roles(self):
        from sotrama.permissions import (
            file_has_permission,
            secure_driver_private_attachment,
        )

        file_doc = frappe._dict(
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-001",
            attached_to_field="professional_certificate",
            sotrama_private_driver_attachment=0,
        )
        with patch("frappe.get_roles", return_value=["Fleet Manager"]):
            self.assertFalse(
                file_has_permission(file_doc, user="fleet@example.com", ptype="read")
            )
        with patch("frappe.get_roles", return_value=["Workshop"]):
            self.assertFalse(
                file_has_permission(file_doc, user="workshop@example.com", ptype="read")
            )
        fleet_upload = frappe._dict(
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-001",
            attached_to_field="professional_certificate",
            is_private=0,
            is_remote_file=False,
        )
        with (
            patch.dict(frappe.session, {"user": "fleet@example.com"}),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            secure_driver_private_attachment(fleet_upload, method="before_insert")
        with (
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.has_permission", return_value=True),
        ):
            self.assertTrue(
                file_has_permission(file_doc, user="hr@example.com", ptype="read")
            )
        with (
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.has_permission", return_value=False),
        ):
            self.assertFalse(
                file_has_permission(file_doc, user="hr@example.com", ptype="read")
            )

        detached_file_doc = frappe._dict(
            attached_to_doctype=None,
            attached_to_name=None,
            attached_to_field=None,
            sotrama_private_driver_attachment=0,
        )
        # Detached, unmarked files fall back to ordinary Frappe File permissions.
        with patch("frappe.get_roles", return_value=["Workshop"]):
            self.assertTrue(
                file_has_permission(
                    detached_file_doc, user="workshop@example.com", ptype="read"
                )
            )

        local_file = frappe._dict(
            name="FILE-LOCAL",
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-001",
            attached_to_field="professional_certificate",
            is_private=0,
            is_remote_file=False,
            is_new=lambda: False,
            save=Mock(),
        )
        with patch(
            "sotrama.permissions._remove_private_driver_file_shares"
        ) as remove_shares:
            secure_driver_private_attachment(local_file)
        remove_shares.assert_called_once_with(local_file.name)
        self.assertEqual(local_file.is_private, 1)
        self.assertEqual(local_file.sotrama_private_driver_attachment, 1)
        local_file.save.assert_called_once_with(ignore_permissions=True)

        detached_file = frappe._dict(
            name="FILE-DETACHED",
            attached_to_doctype=None,
            attached_to_name=None,
            attached_to_field=None,
            is_private=0,
            is_remote_file=False,
            is_new=lambda: False,
            get_doc_before_save=Mock(
                return_value=frappe._dict(
                    attached_to_doctype="Driver",
                    attached_to_name="DRV-TEST-001",
                    attached_to_field="professional_certificate",
                )
            ),
            save=Mock(),
        )
        with patch(
            "sotrama.permissions._remove_private_driver_file_shares"
        ) as remove_shares:
            secure_driver_private_attachment(detached_file, method="on_update")
        remove_shares.assert_called_once_with(detached_file.name)
        self.assertEqual(detached_file.is_private, 1)
        self.assertEqual(detached_file.sotrama_private_driver_attachment, 1)
        detached_file.save.assert_called_once_with(ignore_permissions=True)

        update_file = frappe._dict(
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-001",
            attached_to_field="professional_certificate",
            is_private=0,
            is_remote_file=False,
            get_doc_before_save=Mock(return_value=frappe._dict(is_private=1)),
            save=Mock(),
        )
        secure_driver_private_attachment(update_file, method="before_save")
        self.assertEqual(update_file.is_private, 1)
        update_file.save.assert_not_called()

        inconsistent_private_file = frappe._dict(
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-001",
            attached_to_field="professional_certificate",
            file_url="/files/legacy-public-certificate.pdf",
            is_private=1,
            is_remote_file=False,
            get_doc_before_save=Mock(
                return_value=frappe._dict(
                    attached_to_doctype="Driver",
                    attached_to_name="DRV-TEST-001",
                )
            ),
            handle_is_private_changed=Mock(),
        )
        with patch("sotrama.permissions._validate_driver_private_file_paths"):
            secure_driver_private_attachment(
                inconsistent_private_file, method="before_save"
            )
        inconsistent_private_file.handle_is_private_changed.assert_called_once_with()

        new_file = frappe._dict(
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-001",
            attached_to_field="professional_certificate",
            file_url="/files/driver-certificate.pdf",
            is_private=0,
            is_remote_file=False,
            is_new=lambda: True,
            handle_is_private_changed=Mock(),
        )
        with patch("sotrama.permissions._validate_driver_private_file_paths"):
            secure_driver_private_attachment(new_file, method="before_insert")
        self.assertEqual(new_file.is_private, 1)
        new_file.handle_is_private_changed.assert_called_once_with()

        remote_file = frappe._dict(
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-001",
            attached_to_field="professional_certificate",
            is_private=0,
            is_remote_file=True,
            is_new=lambda: True,
            flags=frappe._dict(),
        )
        with self.assertRaises(frappe.ValidationError):
            secure_driver_private_attachment(remote_file)

    def test_driver_compliance_child_attachments_are_hr_only(self):
        from sotrama.permissions import file_has_permission

        file_doc = frappe._dict(
            attached_to_doctype="Driver Compliance Record",
            attached_to_name="DCR-TEST-001",
            attached_to_field="evidence",
        )
        with patch("frappe.get_roles", return_value=["Workshop"]):
            self.assertFalse(
                file_has_permission(file_doc, user="workshop@example.com", ptype="read")
            )

    def test_driver_file_download_mixin_denies_non_hr_even_for_public_files(self):
        from sotrama.overrides.file import DriverPrivateFileMixin

        class BaseFile:
            def is_downloadable(self):
                return True

        class TestFile(DriverPrivateFileMixin, BaseFile):
            attached_to_doctype = "Driver"
            attached_to_name = "DRV-TEST-001"
            attached_to_field = "professional_certificate"
            sotrama_private_driver_attachment = 0

            def get(self, fieldname):
                return getattr(self, fieldname, None)

        file_doc = TestFile()
        with (
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch.dict(frappe.session, {"user": "fleet@example.com"}),
        ):
            self.assertFalse(file_doc.is_downloadable())
        with (
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch.dict(frappe.session, {"user": "hr@example.com"}),
            patch(
                "sotrama.permissions.can_access_driver_private_attachment",
                return_value=True,
            ),
        ):
            self.assertTrue(file_doc.is_downloadable())

        file_doc.attached_to_doctype = None
        file_doc.sotrama_private_driver_attachment = 1
        with (
            patch("frappe.get_roles", return_value=["Workshop"]),
            patch.dict(frappe.session, {"user": "workshop@example.com"}),
        ):
            self.assertFalse(file_doc.is_downloadable())

    def test_driver_private_attachment_migration_converts_local_files(self):
        from sotrama.migrations.security import migrate_driver_private_attachments

        file_doc = frappe._dict(
            name="FILE-DRIVER-001",
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-001",
            attached_to_field="professional_certificate",
            is_private=0,
            is_remote_file=False,
            save=Mock(),
        )
        with (
            patch(
                "sotrama.permissions.frappe.get_all",
                return_value=[frappe._dict(name=file_doc.name)],
            ),
            patch("sotrama.permissions.frappe.get_doc", return_value=file_doc),
            patch("sotrama.migrations.security._ensure_driver_file_privacy_field"),
            patch("sotrama.migrations.security._remove_private_driver_file_shares"),
        ):
            migrate_driver_private_attachments()
        self.assertEqual(file_doc.is_private, 1)
        self.assertEqual(file_doc.sotrama_private_driver_attachment, 1)
        file_doc.save.assert_called_once_with(ignore_permissions=True)

    def test_driver_attachment_migration_supports_file_schema_without_remote_flag(self):
        from sotrama.migrations.security import migrate_driver_private_attachments

        file_doc = frappe._dict(
            name="FILE-DRIVER-NO-REMOTE-FLAG",
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-003",
            attached_to_field="professional_certificate",
            file_url="/private/files/driver-certificate.pdf",
            is_private=1,
            save=Mock(),
        )
        with (
            patch("sotrama.migrations.security._ensure_driver_file_privacy_field"),
            patch(
                "sotrama.permissions.frappe.get_meta",
                return_value=frappe._dict(has_field=Mock(return_value=False)),
            ),
            patch("sotrama.permissions.frappe.db.has_column", return_value=False),
            patch(
                "sotrama.permissions.frappe.get_all",
                return_value=[frappe._dict(name=file_doc.name)],
            ) as get_all,
            patch("sotrama.permissions.frappe.get_doc", return_value=file_doc),
            patch("sotrama.migrations.security._validate_driver_private_file_paths"),
            patch("sotrama.migrations.security._remove_private_driver_file_shares"),
        ):
            migrate_driver_private_attachments()

        self.assertNotIn("is_remote_file", get_all.call_args.kwargs["fields"])
        self.assertEqual(file_doc.sotrama_private_driver_attachment, 1)
        file_doc.save.assert_called_once_with(ignore_permissions=True)

        remote_file = frappe._dict(
            name="FILE-DRIVER-REMOTE",
            attached_to_doctype="Driver",
            attached_to_name="DRV-TEST-002",
            attached_to_field="professional_certificate",
            file_url="https://example.invalid/driver-certificate.pdf",
            is_private=0,
            is_remote_file=True,
            flags=frappe._dict(),
            save=Mock(),
        )
        with (
            patch(
                "sotrama.permissions.frappe.get_all",
                side_effect=[
                    [frappe._dict(name=remote_file.name)],
                    [
                        frappe._dict(
                            name="COMMENT-REMOTE-001",
                            content=f'<a href="{remote_file.file_url}">certificate</a>',
                        ),
                        frappe._dict(
                            name="COMMENT-REMOTE-002",
                            content='<a href="https%3A%2F%2Fexample.invalid%2Fdriver-certificate.pdf">certificate</a>',
                        ),
                    ],
                ],
            ),
            patch("sotrama.permissions.frappe.get_doc", return_value=remote_file),
            patch("sotrama.permissions.frappe.log_error") as log_error,
            patch("sotrama.permissions.frappe.db.set_value") as set_value,
            patch("sotrama.migrations.security._ensure_driver_file_privacy_field"),
            patch(
                "sotrama.permissions.frappe.get_meta",
                return_value=frappe._dict(has_field=Mock(return_value=False)),
            ),
            patch("sotrama.migrations.security._remove_private_driver_file_shares"),
        ):
            migrate_driver_private_attachments()
        self.assertIsNone(remote_file.attached_to_doctype)
        self.assertEqual(remote_file.is_private, 1)
        self.assertEqual(remote_file.sotrama_private_driver_attachment, 1)
        remote_file.save.assert_called_once_with(ignore_permissions=True)
        log_error.assert_called_once()
        self.assertIn(
            "[Private Driver compliance attachment]", set_value.call_args.args[3]
        )
        self.assertEqual(set_value.call_count, 2)

    def test_driver_private_files_are_detached_and_administrator_owned_on_uninstall(
        self,
    ):
        from sotrama.permissions import preserve_driver_file_privacy_on_uninstall

        remote_file = frappe._dict(
            name="FILE-DRIVER-UNINSTALL",
            attached_to_doctype="Driver Compliance Record",
            attached_to_name="DCR-TEST-001",
            attached_to_field="evidence",
            file_url="https://example.invalid/driver-evidence.pdf",
            is_private=0,
            is_remote_file=True,
            owner="hr@example.com",
            flags=frappe._dict(),
            save=Mock(),
        )
        with (
            patch(
                "sotrama.permissions.frappe.get_all",
                side_effect=[
                    [frappe._dict(name=remote_file.name)],
                    [frappe._dict(name=remote_file.name)],
                ],
            ),
            patch("sotrama.permissions.frappe.get_doc", return_value=remote_file),
            patch("sotrama.permissions._ensure_driver_file_privacy_field"),
            patch("sotrama.permissions._redact_driver_attachment_comments") as redact,
            patch("sotrama.permissions._clear_attached_file_field") as clear_field,
            patch(
                "sotrama.permissions._remove_private_driver_file_shares"
            ) as remove_shares,
        ):
            preserve_driver_file_privacy_on_uninstall()

        self.assertIsNone(remote_file.attached_to_doctype)
        self.assertIsNone(remote_file.attached_to_name)
        self.assertIsNone(remote_file.attached_to_field)
        self.assertEqual(remote_file.is_private, 1)
        self.assertEqual(remote_file.sotrama_private_driver_attachment, 1)
        self.assertEqual(remote_file.owner, "Administrator")
        self.assertTrue(remote_file.flags.allow_remote_driver_detach)
        remote_file.save.assert_called_once_with(ignore_permissions=True)
        redact.assert_called_once()
        clear_field.assert_called_once_with(remote_file)
        remove_shares.assert_called_once_with(remote_file.name)

    def test_uninstall_detaches_non_driver_file_rows_sharing_private_driver_content(
        self,
    ):
        from sotrama.permissions import preserve_driver_file_privacy_on_uninstall

        source_file = frappe._dict(
            name="FILE-DRIVER-SOURCE",
            content_hash="DRIVER-EVIDENCE-HASH",
            attached_to_doctype="Driver",
            attached_to_name="DRV-PRIVATE-001",
            attached_to_field="professional_certificate",
            file_url="/private/files/driver-evidence.pdf",
            is_private=1,
            is_remote_file=False,
            owner="hr@example.invalid",
            sotrama_private_driver_attachment=0,
            flags=frappe._dict(),
            save=Mock(),
        )
        duplicate_file = frappe._dict(
            name="FILE-UNRELATED-DUPLICATE",
            content_hash="DRIVER-EVIDENCE-HASH",
            attached_to_doctype="Purchase Invoice",
            attached_to_name="PINV-001",
            attached_to_field="attachment",
            file_url="/private/files/driver-evidence.pdf",
            is_private=1,
            is_remote_file=False,
            owner="fleet@example.invalid",
            sotrama_private_driver_attachment=1,
            flags=frappe._dict(),
            save=Mock(),
        )
        with (
            patch(
                "sotrama.permissions.frappe.get_all",
                side_effect=[
                    [
                        frappe._dict(
                            name=source_file.name, content_hash=source_file.content_hash
                        )
                    ],
                    [
                        frappe._dict(
                            name=source_file.name, content_hash=source_file.content_hash
                        )
                    ],
                    [
                        frappe._dict(name=source_file.name),
                        frappe._dict(name=duplicate_file.name),
                    ],
                ],
            ),
            patch(
                "sotrama.permissions.frappe.get_doc",
                side_effect=lambda doctype, name: {
                    source_file.name: source_file,
                    duplicate_file.name: duplicate_file,
                }[name],
            ),
            patch("sotrama.permissions._ensure_driver_file_privacy_field"),
            patch("sotrama.permissions._redact_driver_attachment_comments") as redact,
            patch("sotrama.permissions._clear_attached_file_field") as clear_field,
            patch(
                "sotrama.permissions._remove_private_driver_file_shares"
            ) as remove_shares,
        ):
            preserve_driver_file_privacy_on_uninstall()

        for file_doc in (source_file, duplicate_file):
            self.assertIsNone(file_doc.attached_to_doctype)
            self.assertIsNone(file_doc.attached_to_name)
            self.assertIsNone(file_doc.attached_to_field)
            self.assertEqual(file_doc.is_private, 1)
            self.assertEqual(file_doc.owner, "Administrator")
            file_doc.save.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(redact.call_count, 2)
        self.assertEqual(clear_field.call_count, 2)
        self.assertEqual(remove_shares.call_count, 2)
