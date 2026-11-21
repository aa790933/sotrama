"""
Test suite for Sotrama — Algerian Localization & TP Fleet Management.

Run with: bench --site your-site run-tests --app sotrama
"""

import json
import unittest
import uuid
from pathlib import Path
from unittest.mock import Mock, patch

import frappe
from frappe.utils import add_days, getdate, today


def _get_test_company():
    company = (
        frappe.db.get_single_value("TP Settings", "default_company")
        if frappe.db.exists("DocType", "TP Settings")
        else None
    )
    if not company or not frappe.db.exists("Company", company):
        company = frappe.db.get_value("Company", {}, "name")
    if not company:
        raise AssertionError(
            "The Sotrama test suite requires at least one ERPNext Company."
        )
    return company


class TestSotramaHooks(unittest.TestCase):
    """Protect against incompatible hook value shapes across installed apps."""

    def test_app_install_does_not_trigger_an_unnecessary_yarn_install(self):
        app_path = Path(frappe.get_app_path("sotrama")).parent
        self.assertFalse(
            (app_path / "package.json").exists(),
            "Sotrama has no Node dependencies; package.json makes Bench run Yarn and can dirty the Git checkout.",
        )

    def test_declared_patches_resolve_to_real_python_modules(self):
        app_path = Path(frappe.get_app_path("sotrama")).parent
        patch_file = app_path / "patches.txt"
        for line in patch_file.read_text(encoding="utf-8").splitlines():
            dotted_path = line.strip()
            if not dotted_path or dotted_path.startswith("#"):
                continue
            module_path = app_path.joinpath(*dotted_path.split(".")[1:]).with_suffix(
                ".py"
            )
            self.assertTrue(
                module_path.is_file(), f"Patch module does not exist: {dotted_path}"
            )

    def test_default_fleet_masters_are_created_for_a_fresh_install(self):
        self.assertTrue(
            frappe.db.exists("Vehicle Make", {"make_name": "Mercedes-Benz"})
        )
        self.assertTrue(frappe.db.exists("Vehicle Make", {"make_name": "Volvo"}))
        self.assertTrue(
            frappe.db.exists("Maintenance Job Type", {"job_type_name": "Oil Change"})
        )

    def test_sotrama_settings_doctype_is_inside_its_declared_module(self):
        module_path = Path(frappe.get_module_path("Sotrama"))
        self.assertTrue(
            (
                module_path / "doctype" / "sotrama_settings" / "sotrama_settings.json"
            ).is_file()
        )

    def test_standard_workspace_exports_have_importable_names(self):
        app_path = Path(frappe.get_app_path("sotrama")).parent
        workspace_files = {
            app_path / "sotrama" / "workspace" / "sotrama" / "sotrama.json": "Sotrama",
            app_path
            / "algerian_localization"
            / "workspace"
            / "algerian_localization"
            / "algerian_localization.json": "Algerian Localization",
        }

        for path, expected_name in workspace_files.items():
            workspace = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(workspace.get("doctype"), "Workspace")
            self.assertTrue(workspace.get("name"), f"Missing import name in {path}")
            self.assertEqual(workspace["name"], expected_name)

    def test_role_profiles_use_frappe_importable_doctype_sync(self):
        importable_doctypes = frappe.get_hooks(
            "importable_doctypes", app_name="sotrama"
        )
        self.assertIn("Role Profile", importable_doctypes)
        for profile in ("Fleet Manager", "Workshop", "Driver"):
            self.assertTrue(frappe.db.exists("Role Profile", profile))

    def test_app_metadata_is_complete_for_desk_boot(self):
        from frappe.utils.change_log import get_versions

        app_hooks = frappe.get_hooks(app_name="sotrama")
        self.assertTrue(app_hooks.get("app_name"))
        self.assertTrue(app_hooks.get("app_title"))
        self.assertTrue(app_hooks.get("app_description"))
        self.assertTrue(app_hooks.get("app_version"))

        # Reproduce the metadata lookup used by Desk boot and install-app.
        versions = get_versions()
        self.assertIn("sotrama", versions)
        self.assertEqual(versions["sotrama"]["title"], "Sotrama")
        self.assertTrue(versions["sotrama"]["description"])
        self.assertEqual(versions["sotrama"]["version"], app_hooks["app_version"][0])

    def test_global_hook_merge(self):
        hooks = frappe.get_hooks()
        self.assertIsInstance(hooks.get("app_include_js"), list)
        self.assertTrue(
            any(
                "/assets/sotrama/js/sotrama.js" in path
                for path in hooks["app_include_js"]
            )
        )
        self.assertIsInstance(hooks.get("filters_config"), list)

    def test_app_lifecycle_hooks_are_import_paths(self):
        app_hooks = frappe.get_hooks(app_name="sotrama")
        self.assertEqual(
            app_hooks["before_install"][0], "sotrama.hooks.prepare_before_install"
        )
        self.assertEqual(app_hooks["after_install"][0], "sotrama.hooks.initialize_app")
        self.assertEqual(
            app_hooks["after_migrate"][0],
            "sotrama.hooks.run_after_migrate",
            "Migrations must backfill standard NIF safely and secure existing Driver files without creating optional Company fields.",
        )
        self.assertEqual(
            app_hooks["before_uninstall"][0],
            "sotrama.hooks.preserve_company_fields_on_uninstall",
        )

    def test_after_migrate_runs_security_migrations_before_optional_company_nif(self):
        from sotrama import hooks

        calls = []
        with (
            patch.object(
                hooks,
                "migrate_legacy_company_nif",
                side_effect=lambda: (
                    calls.append("company_nif")
                    or {"copied": 1, "conflicts": 0, "skipped": 0}
                ),
            ) as migrate_nif,
            patch.object(
                hooks,
                "hide_managed_legacy_company_nif",
                side_effect=lambda result: calls.append("company_nif_hidden"),
            ) as hide_legacy_nif,
            patch(
                "sotrama.permissions.migrate_driver_private_attachments",
                side_effect=lambda: calls.append("driver_files"),
            ) as migrate_driver_files,
            patch(
                "sotrama.permissions.remove_unsafe_fleet_docshares",
                side_effect=lambda: calls.append("unsafe_fleet_docshares"),
            ) as remove_settings_shares,
            patch(
                "sotrama.tp.scheduler.remediate_fleet_alert_todo_assignments",
                side_effect=lambda: calls.append("fleet_todos"),
            ) as remediate_todos,
        ):
            hooks.run_after_migrate()

        migrate_nif.assert_called_once_with()
        hide_legacy_nif.assert_called_once_with(
            {"copied": 1, "conflicts": 0, "skipped": 0}
        )
        migrate_driver_files.assert_called_once_with()
        remove_settings_shares.assert_called_once_with()
        remediate_todos.assert_called_once_with()
        self.assertEqual(
            calls,
            [
                "driver_files",
                "unsafe_fleet_docshares",
                "fleet_todos",
                "company_nif",
                "company_nif_hidden",
            ],
        )

    def test_after_migrate_fails_closed_if_fleet_alert_privacy_remediation_fails(self):
        from sotrama import hooks

        with (
            patch("sotrama.permissions.remove_unsafe_fleet_docshares"),
            patch("sotrama.permissions.migrate_driver_private_attachments"),
            patch(
                "sotrama.tp.scheduler.remediate_fleet_alert_todo_assignments",
                side_effect=frappe.ValidationError,
            ),
            patch.object(hooks, "migrate_legacy_company_nif") as migrate_nif,
            self.assertRaises(frappe.ValidationError),
        ):
            hooks.run_after_migrate()

        migrate_nif.assert_not_called()

    def test_legacy_company_nif_migration_preserves_conflicts_and_existing_tax_id(self):
        from sotrama.hooks import migrate_legacy_company_nif

        rows = [
            frappe._dict(name="SOTRAMA", custom_nif=" 123456789 ", tax_id=None),
            frappe._dict(name="OTHER", custom_nif="987654321", tax_id="111111111"),
            frappe._dict(name="MATCH", custom_nif="222222222", tax_id="222222222"),
        ]
        with (
            patch("sotrama.hooks.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.hooks.frappe.db.get_value",
                side_effect=[
                    frappe._dict(
                        name="Company-custom_nif",
                        module="Sotrama",
                        is_system_generated=1,
                        description="",
                        fieldtype="Data",
                    ),
                    frappe._dict(tax_id="123456789", custom_nif=" 123456789 "),
                ],
            ),
            patch("sotrama.hooks.frappe.db.has_column", return_value=True),
            patch("sotrama.hooks.frappe.db.sql", side_effect=[rows, None]) as sql,
            patch("sotrama.hooks.frappe.db.set_value") as set_value,
            patch("sotrama.hooks.frappe.clear_cache") as clear_cache,
            patch("sotrama.hooks.frappe.log_error") as log_error,
        ):
            result = migrate_legacy_company_nif()

        self.assertEqual(result, {"copied": 1, "conflicts": 1, "skipped": 0})
        set_value.assert_not_called()
        self.assertEqual(sql.call_count, 2)
        self.assertIn("TRIM(COALESCE(`tax_id`, '')) = ''", sql.call_args.args[0])
        self.assertEqual(sql.call_args.args[1], ("123456789", "SOTRAMA", " 123456789 "))
        clear_cache.assert_called_once_with(doctype="Company")
        log_error.assert_called_once()
        self.assertIn("OTHER", log_error.call_args.kwargs["message"])
        self.assertIn("987654321", log_error.call_args.kwargs["message"])

    def test_legacy_company_nif_migration_does_not_claim_unowned_custom_field(self):
        from sotrama.hooks import migrate_legacy_company_nif

        with (
            patch("sotrama.hooks.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.hooks.frappe.db.get_value",
                return_value=frappe._dict(
                    name="Company-custom_nif",
                    module="Custom",
                    is_system_generated=0,
                    description="User-created NIF field",
                    fieldtype="Data",
                ),
            ),
            patch("sotrama.hooks.frappe.db.has_column", return_value=True),
            patch("sotrama.hooks.frappe.db.sql") as sql,
            patch("sotrama.hooks.frappe.db.set_value") as set_value,
            patch("sotrama.hooks.frappe.log_error") as log_error,
        ):
            result = migrate_legacy_company_nif()

        self.assertEqual(result, {"copied": 0, "conflicts": 0, "skipped": 1})
        sql.assert_not_called()
        set_value.assert_not_called()
        log_error.assert_called_once()

    def test_legacy_company_nif_guarded_update_does_not_overwrite_concurrent_tax_id(
        self,
    ):
        from sotrama.hooks import migrate_legacy_company_nif

        rows = [frappe._dict(name="SOTRAMA", custom_nif="123456789", tax_id=None)]
        with (
            patch("sotrama.hooks.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.hooks.frappe.db.get_value",
                side_effect=[
                    frappe._dict(
                        name="Company-custom_nif",
                        module="Sotrama",
                        is_system_generated=1,
                        description="",
                        fieldtype="Data",
                    ),
                    frappe._dict(tax_id="999999999", custom_nif="123456789"),
                ],
            ),
            patch("sotrama.hooks.frappe.db.has_column", return_value=True),
            patch("sotrama.hooks.frappe.db.sql", side_effect=[rows, None]) as sql,
            patch("sotrama.hooks.frappe.db.set_value") as set_value,
            patch("sotrama.hooks.frappe.log_error") as log_error,
        ):
            result = migrate_legacy_company_nif()

        self.assertEqual(result, {"copied": 0, "conflicts": 1, "skipped": 0})
        self.assertEqual(sql.call_count, 2)
        self.assertIn("TRIM(COALESCE(`tax_id`, '')) = ''", sql.call_args.args[0])
        set_value.assert_not_called()
        log_error.assert_called_once()
        self.assertIn("999999999", log_error.call_args.kwargs["message"])

    def test_legacy_company_nif_does_not_hide_when_legacy_value_changes_concurrently(
        self,
    ):
        from sotrama.hooks import migrate_legacy_company_nif

        rows = [frappe._dict(name="SOTRAMA", custom_nif="123456789", tax_id=None)]
        with (
            patch("sotrama.hooks.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.hooks.frappe.db.get_value",
                side_effect=[
                    frappe._dict(
                        name="Company-custom_nif",
                        module="Sotrama",
                        is_system_generated=1,
                        description="",
                        fieldtype="Data",
                    ),
                    frappe._dict(tax_id=None, custom_nif="987654321"),
                ],
            ),
            patch("sotrama.hooks.frappe.db.has_column", return_value=True),
            patch("sotrama.hooks.frappe.db.sql", side_effect=[rows, None]),
            patch("sotrama.hooks.frappe.log_error") as log_error,
        ):
            result = migrate_legacy_company_nif()

        self.assertEqual(result, {"copied": 0, "conflicts": 0, "skipped": 1})
        log_error.assert_not_called()

    def test_legacy_company_nif_is_hidden_only_after_conflict_free_owned_migration(
        self,
    ):
        from sotrama.hooks import hide_managed_legacy_company_nif

        with (
            patch("sotrama.hooks.frappe.db.table_exists", return_value=True),
            patch("sotrama.hooks.frappe.db.has_column", return_value=True),
            patch(
                "sotrama.hooks.frappe.db.get_value",
                return_value=frappe._dict(
                    name="Company-custom_nif",
                    module="Sotrama",
                    is_system_generated=1,
                    description="",
                    fieldtype="Data",
                    hidden=0,
                ),
            ),
            patch("sotrama.hooks.frappe.db.set_value") as set_value,
            patch("sotrama.hooks.frappe.clear_cache") as clear_cache,
        ):
            hidden = hide_managed_legacy_company_nif(
                {"copied": 1, "conflicts": 0, "skipped": 0}
            )

        self.assertTrue(hidden)
        set_value.assert_called_once_with(
            "Custom Field", "Company-custom_nif", "hidden", 1, update_modified=False
        )
        clear_cache.assert_called_once_with(doctype="Company")

        with patch("sotrama.hooks.frappe.db.set_value") as set_value:
            self.assertFalse(
                hide_managed_legacy_company_nif(
                    {"copied": 0, "conflicts": 1, "skipped": 0}
                )
            )
            self.assertFalse(
                hide_managed_legacy_company_nif(
                    {"copied": 0, "conflicts": 0, "skipped": 1}
                )
            )
        set_value.assert_not_called()

    def test_optional_company_fields_are_not_imported_as_fixtures(self):
        fixtures = frappe.get_hooks("fixtures", app_name="sotrama")
        self.assertFalse(
            any(
                (fixture.get("dt") if isinstance(fixture, dict) else fixture)
                in {"Custom Field", "Property Setter"}
                for fixture in fixtures
            ),
            "Company Custom Fields and standard DocType Property Setters must not be imported as fixtures.",
        )

    def test_company_form_does_not_load_legacy_nif_alias_script(self):
        doctype_js = frappe.get_hooks("doctype_js", app_name="sotrama")
        self.assertNotIn("Company", doctype_js)

    def test_app_is_registered_on_the_apps_screen(self):
        app_entry = frappe.get_hooks("add_to_apps_screen", app_name="sotrama")[0]
        self.assertEqual(app_entry["name"], "sotrama")
        self.assertEqual(app_entry["title"], "Sotrama")
        self.assertEqual(app_entry["route"], "/desk/sotrama")
        self.assertEqual(
            app_entry["has_permission"], "sotrama.permissions.has_app_permission"
        )

    def test_standard_desktop_navigation_includes_the_overview_module(self):
        from sotrama.config.desktop import get_data

        modules = {entry["module_name"] for entry in get_data()}
        self.assertEqual(modules, {"Sotrama", "TP", "Algerian Localization"})
        module = frappe.get_doc("Module Def", "Sotrama")
        self.assertEqual(module.app_name, "sotrama")
        self.assertFalse(module.custom)
        sidebar = frappe.get_doc("Sidebar", "Sotrama")
        self.assertTrue(
            any(item.link_to == "Sotrama Settings" for item in sidebar.items)
        )
        dock = frappe.get_doc("Dock", {"app": "sotrama", "standard": 1})
        self.assertEqual(
            {(item.link_type, item.link_to) for item in dock.items},
            {
                ("Workspace", "Sotrama"),
                ("Workspace", "Sotrama Fleet"),
                ("Workspace", "Algerian Localization"),
            },
        )

    def test_before_install_repairs_only_unplaced_sotrama_modules(self):
        from sotrama.hooks import repair_orphaned_module_definitions

        with (
            patch("sotrama.hooks.frappe.get_module_list", return_value=["Sotrama"]),
            patch("sotrama.hooks.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.hooks.frappe.db.get_value",
                return_value=frappe._dict(app_name=None, custom=None),
            ),
            patch("sotrama.hooks.frappe.db.set_value") as set_value,
        ):
            repair_orphaned_module_definitions()

        set_value.assert_called_once_with(
            "Module Def",
            "Sotrama",
            {"app_name": "sotrama", "custom": 0},
            update_modified=False,
        )

    def test_before_install_normalizes_a_null_custom_flag(self):
        from sotrama.hooks import repair_orphaned_module_definitions

        with (
            patch("sotrama.hooks.frappe.get_module_list", return_value=["Sotrama"]),
            patch("sotrama.hooks.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.hooks.frappe.db.get_value",
                return_value=frappe._dict(app_name="sotrama", custom=None),
            ),
            patch("sotrama.hooks.frappe.db.set_value") as set_value,
        ):
            repair_orphaned_module_definitions()

        set_value.assert_called_once_with(
            "Module Def", "Sotrama", {"custom": 0}, update_modified=False
        )

    def test_before_install_does_not_claim_another_apps_module(self):
        from sotrama.hooks import repair_orphaned_module_definitions

        with (
            patch("sotrama.hooks.frappe.get_module_list", return_value=["Sotrama"]),
            patch("sotrama.hooks.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.hooks.frappe.db.get_value",
                return_value=frappe._dict(app_name="erpnext", custom=0),
            ),
            patch("sotrama.hooks.frappe.db.set_value") as set_value,
            self.assertRaises(frappe.ValidationError),
        ):
            repair_orphaned_module_definitions()

        set_value.assert_not_called()

    def test_before_install_leaves_custom_module_definitions_for_frappe(self):
        from sotrama.hooks import repair_orphaned_module_definitions

        with (
            patch("sotrama.hooks.frappe.get_module_list", return_value=["Sotrama"]),
            patch("sotrama.hooks.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.hooks.frappe.db.get_value",
                return_value=frappe._dict(app_name=None, custom=1),
            ),
            patch("sotrama.hooks.frappe.db.set_value") as set_value,
        ):
            repair_orphaned_module_definitions()

        set_value.assert_not_called()

    def test_public_works_designations_are_unique_and_use_standard_hrms_master(self):
        from sotrama.setup import (
            PUBLIC_WORKS_DESIGNATIONS,
            _designation_name_key,
            ensure_public_works_designations,
        )

        names = list(PUBLIC_WORKS_DESIGNATIONS)
        self.assertEqual(len(names), len(set(names)))
        self.assertEqual(len(names), 202)
        self.assertTrue(all(name == name.strip() and name for name in names))
        self.assertEqual(
            _designation_name_key("Gérant"), _designation_name_key("GERANT")
        )

        created = ensure_public_works_designations()
        try:
            self.assertTrue(
                all(frappe.db.exists("Designation", name) for name in created)
            )
            if frappe.get_meta("Designation").has_field("description"):
                self.assertTrue(
                    all(
                        not frappe.db.get_value("Designation", name, "description")
                        for name in created
                    )
                )
            self.assertEqual(ensure_public_works_designations(), [])
        finally:
            for name in created:
                if frappe.db.exists("Designation", name):
                    frappe.delete_doc("Designation", name, ignore_permissions=True)

    def test_designation_seed_respects_existing_case_and_accent_variants(self):
        from sotrama.setup import ensure_public_works_designations

        with (
            patch("sotrama.setup.PUBLIC_WORKS_DESIGNATIONS", ("Gérant",)),
            patch("frappe.get_all", return_value=["GERANT"]),
            patch("frappe.new_doc") as new_doc,
        ):
            self.assertEqual(ensure_public_works_designations(), [])
        new_doc.assert_not_called()

    def test_fleet_dock_sidebar_and_workspace_are_installed(self):
        self.assertTrue(frappe.db.exists("Dock", {"app": "sotrama", "standard": 1}))
        self.assertTrue(frappe.db.exists("Sidebar", "TP"))
        self.assertTrue(frappe.db.exists("Workspace", "Sotrama Fleet"))
        self.assertTrue(frappe.db.exists("Module Def", "Algerian Localization"))
        self.assertTrue(frappe.db.exists("Sidebar", "Algerian Localization"))
        self.assertTrue(frappe.db.exists("Workspace", "Algerian Localization"))
        self.assertTrue(frappe.db.exists("Workspace", "Sotrama"))
        localization_module = frappe.get_doc("Module Def", "Algerian Localization")
        self.assertEqual(localization_module.app_name, "sotrama")
        self.assertFalse(localization_module.custom)
        localization_workspace = frappe.get_doc("Workspace", "Algerian Localization")
        self.assertEqual(
            {row.role for row in localization_workspace.roles},
            {"System Manager", "Accounts Manager"},
        )
        app_workspace = frappe.get_doc("Workspace", "Sotrama")
        self.assertEqual(
            {item.link_to for item in app_workspace.links if item.type == "Link"},
            {"Algerian Localization", "Sotrama Settings"},
            "Frappe filters child workspaces and DocType links by their own permissions.",
        )
        workspace = frappe.get_doc("Workspace", "Sotrama Fleet")
        import json

        blocks = json.loads(workspace.content or "[]")
        card_names = {
            block.get("data", {}).get("number_card_name")
            for block in blocks
            if block.get("type") == "number_card"
        }
        self.assertEqual(
            card_names,
            {"Active Vehicles", "Vehicles Out of Service", "Active Maintenance Plans"},
        )
        for card_name in card_names:
            self.assertTrue(
                frappe.db.exists("Number Card", card_name),
                f"Missing Number Card: {card_name}",
            )

        sidebar = frappe.get_doc("Sidebar", "TP")
        self.assertTrue(any(item.link_to == "TP Settings" for item in sidebar.items))
        self.assertTrue(any(item.link_to == "TP Settings" for item in workspace.links))
        self.assertEqual(
            {row.role for row in workspace.roles},
            {"System Manager", "Fleet Manager", "Workshop"},
        )

        app_dock = frappe.get_doc("Dock", {"app": "sotrama", "standard": 1})
        self.assertEqual(
            {(item.link_type, item.link_to) for item in app_dock.items},
            {
                ("Workspace", "Sotrama"),
                ("Workspace", "Sotrama Fleet"),
                ("Workspace", "Algerian Localization"),
            },
        )

    def test_sotrama_settings_expose_optional_hr_designation_seed(self):
        meta = frappe.get_meta("Sotrama Settings", cached=False)
        field = meta.get_field("add_public_works_designations")
        self.assertIsNotNone(field)
        self.assertEqual(field.fieldtype, "Check")
        self.assertEqual(field.default, "0")
        self.assertEqual(field.permlevel, 1)

        hr_permissions = [
            permission
            for permission in meta.permissions
            if permission.role == "HR Manager" and permission.permlevel == 1
        ]
        self.assertTrue(hr_permissions)
        self.assertTrue(hr_permissions[0].read)
        self.assertTrue(hr_permissions[0].write)

        company_field = meta.get_field("enable_algerian_company_fields")
        self.assertEqual(company_field.permlevel, 0)

        doctype_js = frappe.get_hooks("doctype_js", app_name="sotrama")
        self.assertIn("Sotrama Settings", doctype_js)
        self.assertTrue(
            (
                Path(frappe.get_app_path("sotrama")).parent
                / "public/js/sotrama_settings.js"
            ).is_file()
        )

    def test_explicit_btph_job_title_action_requires_enabled_setting_and_permission(
        self,
    ):
        from sotrama.sotrama.doctype.sotrama_settings.sotrama_settings import (
            create_missing_public_works_designations,
        )

        with (
            patch(
                "sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.frappe.only_for"
            ) as only_for,
            patch(
                "sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.frappe.get_single",
                return_value=frappe._dict(add_public_works_designations=1),
            ),
            patch(
                "sotrama.setup.ensure_public_works_designations",
                return_value=["TITLE-001"],
            ) as seed,
        ):
            result = create_missing_public_works_designations()

        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["created"], ["TITLE-001"])
        only_for.assert_called_once_with(["System Manager", "HR Manager"])
        seed.assert_called_once_with()

        with (
            patch(
                "sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.frappe.only_for"
            ),
            patch(
                "sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.frappe.get_single",
                return_value=frappe._dict(add_public_works_designations=0),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            create_missing_public_works_designations()

    def test_fleet_manager_role_profile_does_not_escalate_to_system_manager(self):
        profile = frappe.get_doc("Role Profile", "Fleet Manager")
        roles = {row.role for row in profile.roles}
        self.assertIn("Fleet Manager", roles)
        self.assertNotIn("System Manager", roles)

    def test_tp_settings_is_a_single_central_configuration(self):
        meta = frappe.get_meta("TP Settings", cached=False)
        self.assertTrue(meta.issingle)
        for fieldname in (
            "default_company",
            "default_company_classification",
            "default_department",
            "default_cost_center",
            "default_parts_warehouse",
            "require_employee_link",
            "require_active_employee_for_active_driver",
            "block_expired_driver_license",
            "block_expired_medical_certificate",
            "block_expired_safety_training",
            "require_professional_certificate_for_transport",
            "driver_document_alert_days",
            "vehicle_document_alert_days",
            "maintenance_due_alert_days",
            "company_defaults",
        ):
            self.assertIsNotNone(
                meta.get_field(fieldname), f"Missing TP setting: {fieldname}"
            )
        self.assertEqual(meta.get_field("block_expired_driver_license").default, "0")

        company_scoped_settings = (
            "default_company",
            "default_company_classification",
            "default_department",
            "default_cost_center",
            "default_parts_warehouse",
            "company_defaults",
        )
        for fieldname in company_scoped_settings:
            self.assertEqual(meta.get_field(fieldname).permlevel, 2)

        restricted_settings = (
            "require_employee_link",
            "require_active_employee_for_active_driver",
            "block_expired_medical_certificate",
            "block_expired_safety_training",
            "require_professional_certificate_for_transport",
        )
        for fieldname in restricted_settings:
            self.assertEqual(meta.get_field(fieldname).permlevel, 1)

        hr_permissions = [
            permission
            for permission in meta.permissions
            if permission.role == "HR Manager" and permission.permlevel == 1
        ]
        self.assertTrue(hr_permissions)
        self.assertTrue(hr_permissions[0].read)
        self.assertTrue(hr_permissions[0].write)

        system_permissions = [
            permission
            for permission in meta.permissions
            if permission.role == "System Manager" and permission.permlevel == 1
        ]
        self.assertTrue(system_permissions)
        self.assertTrue(system_permissions[0].read)
        self.assertTrue(system_permissions[0].write)

        system_level_two = [
            permission
            for permission in meta.permissions
            if permission.role == "System Manager" and permission.permlevel == 2
        ]
        self.assertTrue(system_level_two)
        self.assertTrue(system_level_two[0].read)
        self.assertTrue(system_level_two[0].write)

        fleet_permissions = [
            permission
            for permission in meta.permissions
            if permission.role == "Fleet Manager" and permission.permlevel == 1
        ]
        self.assertFalse(fleet_permissions)

        for role in ("Fleet Manager", "HR Manager", "Workshop"):
            self.assertFalse(
                any(
                    permission.role == role and permission.permlevel == 2
                    for permission in meta.permissions
                ),
                f"{role} must not read or write global per-Company defaults.",
            )

        company_defaults = frappe.get_meta("TP Company Defaults", cached=False)
        self.assertTrue(company_defaults.istable)
        for fieldname in (
            "company",
            "company_classification",
            "default_department",
            "default_cost_center",
            "default_parts_warehouse",
            "active",
        ):
            self.assertIsNotNone(company_defaults.get_field(fieldname))

    def test_maintenance_job_card_can_select_a_specific_plan(self):
        card_meta = frappe.get_meta("Maintenance Job Card", cached=False)
        schedule_field = card_meta.get_field("maintenance_schedule")
        self.assertIsNotNone(schedule_field)
        self.assertEqual(schedule_field.fieldtype, "Link")
        self.assertEqual(schedule_field.options, "Maintenance Schedule")
        schedule_meta = frappe.get_meta("Maintenance Schedule", cached=False)
        last_job_card = schedule_meta.get_field("last_service_job_card")
        self.assertIsNotNone(last_job_card)
        self.assertEqual(last_job_card.options, "Maintenance Job Card")
        self.assertTrue(schedule_meta.get_field("status").read_only)
        self.assertFalse(schedule_meta.get_field("status").allow_on_submit)
        next_schedule = schedule_meta.get_field("next_schedule")
        self.assertEqual(next_schedule.fieldtype, "Link")
        self.assertEqual(next_schedule.options, "Maintenance Schedule")
        self.assertTrue(next_schedule.read_only)
        self.assertFalse(next_schedule.allow_on_submit)

    def test_job_card_child_tables_explain_item_and_employee_sources(self):
        card_meta = frappe.get_meta("Maintenance Job Card", cached=False)
        parts = card_meta.get_field("parts_used")
        labour = card_meta.get_field("labour_lines")
        other_costs = card_meta.get_field("other_costs")
        self.assertEqual(parts.options, "Job Card Part")
        self.assertIn("ERPNext Item", parts.description)
        self.assertIn("configured parts warehouse", parts.description)
        self.assertEqual(labour.options, "Job Card Labour")
        self.assertIn("Frappe HR Employee", labour.description)
        self.assertIn("hourly rate", labour.description)
        self.assertIn("additional maintenance expenses", other_costs.description)

        print_format = frappe.get_doc("Print Format", "Maintenance Job Card Report")
        self.assertTrue(print_format.print_format_builder_beta)
        print_layout = json.loads(print_format.format_data)
        print_sections = {section["label"] for section in print_layout["sections"]}
        self.assertIn("Spare Parts (Stock Items)", print_sections)
        self.assertIn("Labour (Employees / Mechanics)", print_sections)
        inspection_print = frappe.get_doc("Print Format", "Vehicle Inspection Report")
        self.assertTrue(inspection_print.print_format_builder_beta)
        json.loads(inspection_print.format_data)

        labour_meta = frappe.get_meta("Job Card Labour", cached=False)
        self.assertEqual(labour_meta.get_field("mechanic").options, "Employee")
        self.assertEqual(labour_meta.get_field("mechanic").label, "Employee (Mechanic)")
        self.assertFalse(labour_meta.get_field("mechanic").in_list_view)
        self.assertTrue(labour_meta.get_field("mechanic_name").in_list_view)

        script = (
            Path(frappe.get_app_path("sotrama")).parent / "public/js/job_card.js"
        ).read_text(encoding="utf-8")
        for action in (
            "Add Spare Part (Item)",
            "Add Mechanic (Employee)",
            "Add Other Cost",
            "frm.set_query('mechanic', 'labour_lines'",
            "search_workshop_employees",
            "get_workshop_employee_name",
            "target_doctype: 'Maintenance Job Card'",
            "frappe.call({",
            "total_parts_cost: totalParts",
            "total_labour_cost: totalLabour",
            "parts_used_delete",
            "labour_lines_delete",
            "other_costs_delete",
        ):
            self.assertIn(action, script)
        self.assertIn("frm.is_new() ? permission.create : permission.write", script)
        self.assertNotIn("frappe.db.get_value('Employee'", script)

        inspection_script = (
            Path(frappe.get_app_path("sotrama")).parent / "public/js/inspection.js"
        ).read_text(encoding="utf-8")
        self.assertIn("target_doctype: 'Vehicle Inspection'", inspection_script)
        task_script = (
            Path(frappe.get_app_path("sotrama")).parent
            / "public/js/operational_task.js"
        ).read_text(encoding="utf-8")
        self.assertIn("target_doctype: 'Operational Task'", task_script)

    def test_workshop_employee_lookup_is_limited_to_accessible_company_and_safe_fields(
        self,
    ):
        from sotrama.tp.doctype.maintenance_job_card.maintenance_job_card import (
            get_workshop_employee_name,
            search_workshop_employees,
        )

        module = "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card"
        with (
            patch(f"{module}.frappe.only_for") as only_for,
            patch(f"{module}.frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
            patch(
                f"{module}.frappe.get_all",
                return_value=[("EMP-001", "Ali Mechanic", "Mécanicien")],
            ) as get_all,
        ):
            result = search_workshop_employees(
                "Employee",
                "Ali",
                "name",
                0,
                10,
                {"company": "SOTRAMA", "target_doctype": "Maintenance Job Card"},
            )

        self.assertEqual(result, [("EMP-001", "Ali Mechanic", "Mécanicien")])
        only_for.assert_called_once_with(
            ["System Manager", "Fleet Manager", "Workshop"]
        )
        query = get_all.call_args.kwargs
        self.assertEqual(query["fields"], ["name", "employee_name", "designation"])
        self.assertEqual(query["filters"], {"company": "SOTRAMA", "status": "Active"})
        self.assertTrue(query["as_list"])
        self.assertEqual(
            [call.args for call in validate_company.call_args_list],
            [
                ("SOTRAMA", "Maintenance Job Card"),
                ("SOTRAMA", "Employee"),
                ("SOTRAMA", "Vehicle"),
            ],
        )

        with (
            patch(f"{module}.frappe.only_for"),
            patch(f"{module}.frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
            patch(f"{module}.frappe.db.get_value", return_value="Ali Mechanic"),
        ):
            self.assertEqual(
                get_workshop_employee_name("EMP-001", "SOTRAMA"), "Ali Mechanic"
            )

        with (
            patch(f"{module}.frappe.only_for"),
            patch(f"{module}.frappe.has_permission", return_value=True),
            patch(
                "sotrama.tp.settings.validate_company_access",
                side_effect=frappe.PermissionError,
            ),
            self.assertRaises(frappe.PermissionError),
        ):
            get_workshop_employee_name("EMP-001", "OTHER-COMPANY")

        with (
            patch(f"{module}.frappe.only_for"),
            patch(f"{module}.frappe.has_permission", return_value=False),
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
            self.assertRaises(frappe.PermissionError),
        ):
            get_workshop_employee_name("EMP-001", "SOTRAMA")
        validate_company.assert_not_called()

        with (
            patch(f"{module}.frappe.only_for"),
            self.assertRaises(frappe.PermissionError),
        ):
            get_workshop_employee_name("EMP-001", "SOTRAMA", "TP Settings")

    def test_inspection_checklist_has_an_explicit_add_action(self):
        inspection_meta = frappe.get_meta("Vehicle Inspection", cached=False)
        checklist = inspection_meta.get_field("inspection_items")
        self.assertEqual(checklist.options, "Inspection Item")
        self.assertIn("standard checklist", checklist.description)
        self.assertTrue(inspection_meta.get_field("overall_status").read_only)

        item_meta = frappe.get_meta("Inspection Item", cached=False)
        status = item_meta.get_field("status")
        self.assertEqual(status.default, "Not Checked")
        self.assertIn("Not Checked", status.options.splitlines())
        self.assertIn("Okay", status.options.splitlines())
        self.assertIn("Defective", status.options.splitlines())

        script = (
            Path(frappe.get_app_path("sotrama")).parent / "public/js/inspection.js"
        ).read_text(encoding="utf-8")
        self.assertIn("Add Inspection Check", script)
        self.assertIn("row.status = 'Not Checked'", script)
        self.assertIn("inspection_items_add", script)
        self.assertIn("inspection_items_delete", script)
        self.assertIn("frm.is_new() ? permission.create : permission.write", script)

    def test_inspection_cannot_be_submitted_with_unchecked_items(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.append(
            "inspection_items",
            {
                "category": "Freinage et direction",
                "item_details": "Brake system",
                "status": "Not Checked",
            },
        )
        inspection.validate()
        with self.assertRaises(frappe.ValidationError):
            inspection.before_submit()

        for row in inspection.inspection_items:
            row.status = "Okay"
        inspection.before_submit()

        inspection.inspection_items[0].status = "Defective"
        with self.assertRaises(frappe.ValidationError):
            inspection.before_submit()
        inspection.inspection_items[0].remarks = "Brake hose damaged"
        inspection.before_submit()

    def test_follow_up_inspection_can_be_saved_as_draft_before_checks_are_complete(
        self,
    ):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.vehicle = "VEH-TEST-001"
        inspection.follow_up_of = "INSP-CRITICAL-001"
        inspection.append(
            "inspection_items",
            {
                "category": "Freinage et direction",
                "item_details": "Brake system",
                "status": "Not Checked",
                "is_safety_critical": 1,
            },
        )
        previous = frappe._dict(
            docstatus=1,
            has_critical_defect=1,
            vehicle="VEH-TEST-001",
            critical_defect_cleared_by=None,
        )
        with (
            patch("frappe.db.get_value", return_value="SOTRAMA-TEST-COMPANY"),
            patch("frappe.has_permission", return_value=True),
            patch("frappe.get_doc", return_value=previous),
        ):
            inspection.validate()
            self.assertIsNone(inspection.overall_status)
            with self.assertRaises(frappe.ValidationError):
                inspection.before_submit()

    def test_inspection_overall_status_is_derived_from_checked_items(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.append(
            "inspection_items",
            {
                "category": "Documents réglementaires",
                "item_details": "Registration documents",
                "status": "Not Checked",
                "is_safety_critical": 0,
            },
        )
        inspection._calculate_defects()
        self.assertIsNone(inspection.overall_status)

        inspection.inspection_items[0].status = "Okay"
        inspection._calculate_defects()
        self.assertEqual(inspection.overall_status, "Pass")

        inspection.inspection_items[0].status = "Defective"
        inspection.inspection_items[0].is_safety_critical = 0
        inspection.inspection_items[0].remarks = "Minor documentation defect"
        inspection._calculate_defects()
        self.assertEqual(inspection.overall_status, "Conditional Pass")

        inspection.inspection_items[0].is_safety_critical = 1
        inspection._calculate_defects()
        self.assertEqual(inspection.overall_status, "Fail")

    def test_company_classification_can_be_assigned_to_a_legal_entity(self):
        meta = frappe.get_meta("Company Classification", cached=False)
        company = meta.get_field("company")
        self.assertIsNotNone(company)
        self.assertEqual(company.fieldtype, "Link")
        self.assertEqual(company.options, "Company")

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

        script = (
            Path(frappe.get_app_path("sotrama")).parent / "public/js/driver.js"
        ).read_text(encoding="utf-8")
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
            "Transport collectif de personnes",
            "Transport scolaire",
            "Transport de marchandises",
            "Transport de matières dangereuses",
            "Transport par taxi",
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
                "DRV-TEST-001", "Transport de marchandises"
            )

        driver.license_number = "LIC-001"
        driver.license_class = None
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Transport de marchandises"
            )

        driver.license_class = "C"
        driver.license_expiry = "2020-01-01"
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Transport de marchandises"
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
                "DRV-TEST-001", "Transport de marchandises"
            )

        driver.license_number = "12345678"
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=0),
            patch("frappe.get_doc", return_value=driver),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Transport de marchandises"
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
                "DRV-TEST-001", "Transport de marchandises"
            )

        driver.professional_certificate_number = "BP-TEST-001"
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Transport de marchandises"
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
                "DRV-TEST-001", "Transport de marchandises"
            )

        driver.compliance_records[0].test_date = add_days(today(), 1)
        with (
            patch("sotrama.tp.validation.get_tp_setting", return_value=1),
            patch("frappe.get_doc", return_value=driver),
            self.assertRaises(frappe.ValidationError),
        ):
            validate_professional_transport_certificate(
                "DRV-TEST-001", "Transport de marchandises"
            )

    def test_inspection_child_records_safety_and_issue_links(self):
        meta = frappe.get_meta("Inspection Item", cached=False)
        self.assertIsNotNone(meta.get_field("is_safety_critical"))
        linked_issue = meta.get_field("linked_issue")
        self.assertIsNotNone(linked_issue)
        self.assertEqual(linked_issue.fieldtype, "Link")
        self.assertEqual(linked_issue.options, "Issue")

        inspection_meta = frappe.get_meta("Vehicle Inspection", cached=False)
        follow_up = inspection_meta.get_field("follow_up_of")
        cleared_by = inspection_meta.get_field("critical_defect_cleared_by")
        self.assertEqual(follow_up.options, "Vehicle Inspection")
        self.assertEqual(cleared_by.options, "Vehicle Inspection")
        self.assertTrue(cleared_by.read_only)
        self.assertFalse(cleared_by.allow_on_submit)

    def test_breakdown_workflow_fields_are_locked_after_submit(self):
        meta = frappe.get_meta("Breakdown Incident", cached=False)
        for fieldname in (
            "status",
            "resolution_date",
            "resolution_notes",
            "downtime_hours",
        ):
            self.assertTrue(meta.get_field(fieldname).read_only)
            self.assertFalse(meta.get_field(fieldname).allow_on_submit)

        vehicle_meta = frappe.get_meta("Vehicle", cached=False)
        self.assertTrue(vehicle_meta.get_field("primary_driver").allow_on_submit)

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
            license_plate="REPORT-A",
            company="COMPANY-A",
        )
        visible_document = frappe._dict(
            parent="VEH-REPORT-A",
            document_type="Insurance",
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
        ):
            rows = get_data(frappe._dict(company="COMPANY-A", vehicle="VEH-REPORT-A"))

        self.assertEqual(len(rows), 1)
        vehicle_filters = get_list.call_args.kwargs["filters"]
        self.assertIn(["company", "=", "COMPANY-A"], vehicle_filters)
        self.assertIn(["name", "=", "VEH-REPORT-A"], vehicle_filters)
        self.assertEqual(
            get_all.call_args.kwargs["filters"]["parent"],
            ["in", ["VEH-REPORT-A"]],
        )

    def test_fleet_cost_report_scopes_aggregates_to_permission_visible_vehicles(self):
        from sotrama.tp.report.fleet_cost_analysis.fleet_cost_analysis import get_data

        visible_vehicle = frappe._dict(
            name="VEH-COST-A",
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
        self.assertIn(["company", "=", "COMPANY-A"], calls[0].kwargs["filters"])
        for call in calls[1:]:
            self.assertIn(["vehicle", "in", ["VEH-COST-A"]], call.kwargs["filters"])

    def test_fleet_print_formats_use_the_frappe_16_builder(self):
        import json

        formats = (
            ("Maintenance Job Card Report", "Maintenance Job Card"),
            ("Vehicle Inspection Report", "Vehicle Inspection"),
        )
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
                        if docfield.options:
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
                                if child_field.options:
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

    def test_fleet_doctypes_have_distinct_icons(self):
        doctypes = frappe.get_all(
            "DocType",
            filters={"module": "TP", "istable": 0},
            fields=["name", "icon"],
        )
        icons = {doctype.name: doctype.icon for doctype in doctypes}
        self.assertTrue(all(icons.values()), icons)
        self.assertEqual(len(set(icons.values())), len(icons), icons)

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

        inspection_item = frappe.get_meta("Inspection Item", cached=False)
        self.assertEqual(inspection_item.get_field("is_safety_critical").permlevel, 1)

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

    def test_inspection_supervisor_must_be_active_and_match_company(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            VehicleInspection,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.company = "SOTRAMA-TEST-COMPANY"
        inspection.supervisor = "EMP-TEST-001"
        module = "sotrama.tp.doctype.vehicle_inspection.vehicle_inspection"
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
            VehicleInspection._validate_supervisor(inspection)
        employee_lookup.assert_called_once_with(
            "SOTRAMA-TEST-COMPANY", "Vehicle Inspection"
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
            VehicleInspection._validate_supervisor(inspection)
        employee_lookup.assert_called_once_with(
            "SOTRAMA-TEST-COMPANY", "Vehicle Inspection"
        )

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
                    "SOTRAMA-TEST-COMPANY",
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
                    "SOTRAMA-TEST-COMPANY",
                    frappe._dict(company="SOTRAMA-TEST-COMPANY", status="Suspended"),
                ],
            ),
            patch("frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
        ):
            inspection._set_company_from_vehicle()

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

    def test_workshop_cannot_downgrade_custom_inspection_safety_checks(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        row = inspection.append(
            "inspection_items",
            {
                "category": "Custom hydraulic hose",
                "status": "Not Checked",
                "is_safety_critical": 0,
            },
        )
        with (
            patch("frappe.get_roles", return_value=["Workshop"]),
            patch.object(inspection, "get_doc_before_save", return_value=None),
        ):
            inspection._enforce_safety_critical_flags()
        self.assertEqual(row.is_safety_critical, 1)

        row.is_safety_critical = 0
        row.category = "Documents réglementaires"
        previous = frappe._dict(
            inspection_items=[frappe._dict(name=row.name, is_safety_critical=1)]
        )
        with (
            patch("frappe.get_roles", return_value=["Workshop"]),
            patch.object(inspection, "get_doc_before_save", return_value=previous),
        ):
            inspection._enforce_safety_critical_flags()
        self.assertEqual(row.is_safety_critical, 1)

    def test_workshop_cannot_hide_custom_checks_in_noncritical_categories(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            STANDARD_INSPECTION_CHECKS,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        custom = inspection.append(
            "inspection_items",
            {
                "category": "Documents réglementaires",
                "item_details": "Freins défectueux à contrôler",
                "status": "Defective",
                "is_safety_critical": 0,
            },
        )
        standard = next(
            check
            for check in STANDARD_INSPECTION_CHECKS
            if not check["is_safety_critical"]
        )
        standard_row = inspection.append(
            "inspection_items", {**standard, "status": "Not Checked"}
        )
        duplicate_standard_row = inspection.append(
            "inspection_items", {**standard, "status": "Not Checked"}
        )
        with (
            patch("frappe.get_roles", return_value=["Workshop"]),
            patch.object(inspection, "get_doc_before_save", return_value=None),
        ):
            inspection._enforce_safety_critical_flags()

        self.assertEqual(custom.is_safety_critical, 1)
        self.assertEqual(standard_row.is_safety_critical, 0)
        self.assertEqual(duplicate_standard_row.is_safety_critical, 1)

    def test_inspection_server_restores_every_required_standard_check(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            STANDARD_INSPECTION_CHECKS,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.append(
            "inspection_items",
            {
                "category": "Custom check",
                "item_details": "Custom item",
                "status": "Not Checked",
            },
        )
        inspection._ensure_standard_checklist()
        categories = {row.category for row in inspection.inspection_items}
        expected = {check["category"] for check in STANDARD_INSPECTION_CHECKS}
        self.assertTrue(expected.issubset(categories))
        self.assertEqual(len(expected), 9)
        self.assertTrue(
            all(
                row.status == "Not Checked"
                for row in inspection.inspection_items
                if row.category in expected
            )
        )

    def test_negative_other_costs_are_rejected(self):
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.append("other_costs", {"description": "Credit", "amount": -100})
        with self.assertRaises(frappe.ValidationError):
            job_card._validate_other_costs()

    def test_vehicle_cannot_return_to_service_with_an_open_safety_hold(self):
        from sotrama.tp.doctype.vehicle.vehicle import Vehicle

        vehicle = frappe.new_doc("Vehicle")
        vehicle.name = "VEH-TEST-001"
        vehicle.vehicle_status = "Active"
        with (
            patch(
                "sotrama.tp.validation.get_open_vehicle_safety_holds",
                return_value={"breakdown": "BI-OPEN", "critical_inspection": None},
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            Vehicle._validate_safety_hold(vehicle)

        with (
            patch(
                "sotrama.tp.validation.get_open_vehicle_safety_holds",
                return_value={"breakdown": None, "critical_inspection": "INSP-OPEN"},
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            Vehicle._validate_safety_hold(vehicle)

        with (
            patch(
                "sotrama.tp.validation.get_open_vehicle_safety_holds",
                return_value={"breakdown": "BI-OPEN", "critical_inspection": None},
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            Vehicle.before_cancel(vehicle)

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

    def test_critical_inspection_cannot_be_cancelled(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            VehicleInspection,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.has_critical_defect = 1
        with self.assertRaises(frappe.ValidationError):
            VehicleInspection.before_cancel(inspection)

        inspection.has_critical_defect = 0
        VehicleInspection.before_cancel(inspection)

    def test_inspection_workflow_fields_cannot_be_forged_after_submission(self):
        from sotrama.tp.doctype.vehicle_inspection.vehicle_inspection import (
            VehicleInspection,
        )

        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.critical_defect_cleared_by = "INSP-FAKE"
        inspection.previous_vehicle_status = "Active"
        with (
            patch.object(
                inspection,
                "get_doc_before_save",
                return_value=frappe._dict(
                    docstatus=1,
                    critical_defect_cleared_by=None,
                    previous_vehicle_status="Out of Service",
                ),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            VehicleInspection._validate_system_managed_fields(inspection)

    def test_breakdown_previous_vehicle_status_cannot_be_forged(self):
        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            BreakdownIncident,
        )

        incident = frappe.new_doc("Breakdown Incident")
        incident.previous_vehicle_status = "Active"
        with (
            patch.object(
                incident,
                "get_doc_before_save",
                return_value=frappe._dict(
                    docstatus=1, previous_vehicle_status="Out of Service"
                ),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            BreakdownIncident._validate_system_managed_fields(incident)

    def test_unresolved_breakdown_cannot_be_cancelled(self):
        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            BreakdownIncident,
        )

        incident = frappe.new_doc("Breakdown Incident")
        incident.status = "In Progress"
        with self.assertRaises(frappe.ValidationError):
            BreakdownIncident.before_cancel(incident)

        incident.status = "Resolved"
        with patch.object(incident, "_restore_vehicle_status"):
            BreakdownIncident.before_cancel(incident)

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

    def test_breakdown_resolution_requires_audit_notes(self):
        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            BreakdownIncident,
        )

        incident = frappe.new_doc("Breakdown Incident")
        incident.status = "Resolved"
        incident.resolution_date = "2026-11-19"
        with self.assertRaises(frappe.ValidationError):
            BreakdownIncident._validate_dates(incident)

    def test_completed_mileage_schedule_requires_last_service_odometer(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            MaintenanceSchedule,
        )

        schedule = frappe.new_doc("Maintenance Schedule")
        schedule.schedule_type = "Mileage"
        schedule.interval_km = 10000
        schedule.status = "Completed"
        with self.assertRaises(frappe.ValidationError):
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
            patch("frappe.session.user", "fleet@example.com"),
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
        with patch("frappe.get_roles", return_value=["Workshop"]):
            self.assertFalse(
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
            patch("frappe.session.user", "fleet@example.com"),
        ):
            self.assertFalse(file_doc.is_downloadable())
        with (
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.session.user", "hr@example.com"),
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
            patch("frappe.session.user", "workshop@example.com"),
        ):
            self.assertFalse(file_doc.is_downloadable())

    def test_driver_private_attachment_migration_converts_local_files(self):
        from sotrama.permissions import migrate_driver_private_attachments

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
            patch("sotrama.permissions._ensure_driver_file_privacy_field"),
            patch("sotrama.permissions._remove_private_driver_file_shares"),
        ):
            migrate_driver_private_attachments()
        self.assertEqual(file_doc.is_private, 1)
        self.assertEqual(file_doc.sotrama_private_driver_attachment, 1)
        file_doc.save.assert_called_once_with(ignore_permissions=True)

    def test_driver_attachment_migration_supports_file_schema_without_remote_flag(self):
        from sotrama.permissions import migrate_driver_private_attachments

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
            patch("sotrama.permissions._ensure_driver_file_privacy_field"),
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
            patch("sotrama.permissions._validate_driver_private_file_paths"),
            patch("sotrama.permissions._remove_private_driver_file_shares"),
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
            patch("sotrama.permissions._ensure_driver_file_privacy_field"),
            patch(
                "sotrama.permissions.frappe.get_meta",
                return_value=frappe._dict(has_field=Mock(return_value=False)),
            ),
            patch("sotrama.permissions._remove_private_driver_file_shares"),
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
        self.assertIn(
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

        parent = frappe.get_doc("Workspace", "Sotrama")
        self.assertNotIn("Sotrama Fleet", {row.link_to for row in parent.links})

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

        accounting_user_workspaces = {"Sotrama", "Algerian Localization"}
        with patch(
            "frappe.desk.doctype.dock.dock.permitted_workspaces",
            return_value=accounting_user_workspaces,
        ):
            self.assertFalse(
                is_reachable({"link_type": "Workspace", "link_to": "Sotrama Fleet"})
            )
            self.assertTrue(
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
            patch("frappe.session.user", "hr@example.invalid"),
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
            allowed_workspaces=["Sotrama", "Algerian Localization"],
            can_read=[],
            restricted_doctypes=[],
            allowed_pages={},
            restricted_pages=[],
            allowed_reports={},
            allowed_dashboards={},
        )
        with (
            patch("frappe.session.user", "accounts@example.invalid"),
            patch("frappe.has_permission", return_value=False),
        ):
            self.assertFalse(is_item_allowed("Driver", "DocType", accounts_context))
            self.assertFalse(
                is_item_allowed("TP Settings", "DocType", accounts_context)
            )
            self.assertTrue(
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
        self.assertEqual(validate_company.call_count, 5)
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
                side_effect=[True, True, False, True, True, True],
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

        self.assertIsNone(result["default_company_classification"])
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


class TestSotramaCustomFields(unittest.TestCase):
    """Verify optional Company fields are opt-in and never overwrite site fields."""

    def test_company_fields_are_opt_in_and_reuse_erpnext_tax_id(self):
        from sotrama import hooks

        settings_meta = frappe.get_meta("Sotrama Settings", cached=False)
        self.assertTrue(settings_meta.issingle)
        self.assertIsNotNone(settings_meta.get_field("enable_algerian_company_fields"))
        permissions = {row.role: row for row in settings_meta.permissions}
        self.assertTrue(permissions["System Manager"].write)
        self.assertTrue(permissions["Accounts Manager"].read)
        self.assertFalse(permissions["Accounts Manager"].write)

        definitions = hooks.get_custom_fields()["Company"]
        fieldnames = {field["fieldname"] for field in definitions}
        self.assertIn("custom_article_imposition", fieldnames)
        self.assertIn("custom_nis", fieldnames)
        self.assertIn("custom_rc", fieldnames)
        self.assertIn("custom_capital_social", fieldnames)
        self.assertNotIn("custom_nif", fieldnames)
        self.assertTrue(all(field.get("depends_on") for field in definitions))
        self.assertTrue(all(field["module"] == "Custom" for field in definitions))
        self.assertTrue(
            all(
                hooks.COMPANY_FIELD_OWNERSHIP_MARKER in field["description"]
                for field in definitions
            )
        )

    def test_migration_does_not_create_company_fields_when_setting_is_disabled(self):
        from sotrama import hooks

        with (
            patch.object(hooks.frappe.db, "exists", return_value=True),
            patch.object(hooks.frappe.db, "get_single_value", return_value=0),
            patch.object(hooks, "_set_company_fields_hidden") as hide_fields,
            patch.object(hooks, "enable_algerian_company_fields") as enable_fields,
        ):
            hooks.sync_company_fields()

        hide_fields.assert_called_once_with(True)
        enable_fields.assert_not_called()

    def test_migration_does_not_create_company_fields_when_settings_doctype_is_missing(
        self,
    ):
        from sotrama import hooks

        with (
            patch.object(hooks.frappe.db, "exists", return_value=False),
            patch.object(hooks, "enable_algerian_company_fields") as enable_fields,
            patch.object(hooks, "_set_company_fields_hidden") as hide_fields,
        ):
            hooks.sync_company_fields()

        enable_fields.assert_not_called()
        hide_fields.assert_not_called()

    def test_enabling_creates_only_missing_fields_without_overwriting_existing_fields(
        self,
    ):
        from sotrama import hooks

        with (
            patch.object(hooks.frappe.db, "get_value", return_value=None),
            patch.object(hooks.frappe, "get_all", return_value=[]),
            patch.object(hooks, "create_custom_fields") as create_fields,
            patch.object(hooks, "_set_company_fields_hidden") as reveal_fields,
        ):
            hooks.enable_algerian_company_fields()

        create_fields.assert_called_once_with(hooks.get_custom_fields(), update=False)
        reveal_fields.assert_called_once_with(False)

    def test_legacy_generated_fields_receive_only_missing_country_metadata(self):
        from sotrama import hooks

        fields = [
            frappe._dict(
                {
                    "name": "Company-custom_article_imposition",
                    "fieldname": "custom_article_imposition",
                    "module": "Sotrama",
                    "description": "Fiscal article",
                    "is_system_generated": 1,
                    "depends_on": None,
                    "insert_after": "custom_nif",
                }
            ),
            frappe._dict(
                {
                    "name": "Company-custom_nis",
                    "fieldname": "custom_nis",
                    "module": "Custom",
                    "description": hooks.COMPANY_FIELD_OWNERSHIP_MARKER,
                    "is_system_generated": 1,
                    "depends_on": "eval:doc.country == 'Algeria'",
                    "insert_after": "custom_algerian_registration_column_break",
                }
            ),
        ]
        with (
            patch.object(hooks.frappe, "get_all", return_value=fields) as get_all,
            patch.object(hooks.frappe.db, "set_value") as set_value,
            patch.object(hooks.frappe, "clear_cache") as clear_cache,
        ):
            hooks._detach_legacy_module_fields()

        self.assertEqual(get_all.call_args.kwargs["filters"]["dt"], "Company")
        updates = {call.args[1]: call.args[2] for call in set_value.call_args_list}
        self.assertEqual(
            updates["Company-custom_article_imposition"],
            {
                "module": "Custom",
                "description": f"Fiscal article {hooks.COMPANY_FIELD_OWNERSHIP_MARKER}",
                "depends_on": 'eval:doc.country=="Algeria"',
                "insert_after": "custom_sotrama_algerian_registration_section",
            },
        )
        self.assertNotIn("Company-custom_nis", updates)
        self.assertTrue(
            all(
                call.kwargs["update_modified"] is False
                for call in set_value.call_args_list
            )
        )
        clear_cache.assert_called_once_with(doctype="Company")

    def test_enabling_refuses_to_change_a_legacy_fieldtype(self):
        from sotrama import hooks

        legacy_field = frappe._dict(
            {
                "name": "Company-custom_capital_social",
                "fieldtype": "Data",
                "module": "Sotrama",
                "is_system_generated": 1,
            }
        )

        def get_value(doctype, filters, *args, **kwargs):
            return (
                legacy_field
                if filters.get("fieldname") == "custom_capital_social"
                else None
            )

        with (
            patch.object(hooks.frappe.db, "get_value", side_effect=get_value),
            patch.object(hooks, "create_custom_fields") as create_fields,
            self.assertRaises(frappe.ValidationError),
        ):
            hooks.enable_algerian_company_fields()

        create_fields.assert_not_called()

    def test_enabling_refuses_to_take_over_a_field_owned_by_another_module(self):
        from sotrama import hooks

        foreign_field = frappe._dict(
            {
                "name": "Company-custom_nis",
                "fieldtype": "Data",
                "module": "Accounts",
            }
        )

        def get_value(doctype, filters, *args, **kwargs):
            return foreign_field if filters.get("fieldname") == "custom_nis" else None

        with (
            patch.object(hooks.frappe.db, "get_value", side_effect=get_value),
            patch.object(hooks, "create_custom_fields") as create_fields,
            self.assertRaises(frappe.ValidationError),
        ):
            hooks.enable_algerian_company_fields()

        create_fields.assert_not_called()

    def test_enabling_refuses_to_take_over_a_manually_created_sotrama_field(self):
        from sotrama import hooks

        manual_field = frappe._dict(
            {
                "name": "Company-custom_nis",
                "fieldtype": "Data",
                "module": "Sotrama",
                "is_system_generated": 0,
            }
        )

        def get_value(doctype, filters, *args, **kwargs):
            return manual_field if filters.get("fieldname") == "custom_nis" else None

        with (
            patch.object(hooks.frappe.db, "get_value", side_effect=get_value),
            patch.object(hooks, "create_custom_fields") as create_fields,
            self.assertRaises(frappe.ValidationError),
        ):
            hooks.enable_algerian_company_fields()

        create_fields.assert_not_called()

    def test_enabling_recognizes_system_generated_fields_preserved_in_custom_module(
        self,
    ):
        from sotrama import hooks

        preserved_field = frappe._dict(
            {
                "name": "Company-custom_nis",
                "fieldtype": "Data",
                "module": "Custom",
                "is_system_generated": 1,
                "description": hooks.COMPANY_FIELD_OWNERSHIP_MARKER,
            }
        )

        def get_value(doctype, filters, *args, **kwargs):
            if filters.get("module") == "Sotrama":
                return None
            return preserved_field if filters.get("fieldname") == "custom_nis" else None

        with (
            patch.object(hooks.frappe.db, "get_value", side_effect=get_value),
            patch.object(hooks.frappe, "get_all", return_value=[]),
            patch.object(hooks, "create_custom_fields") as create_fields,
            patch.object(hooks, "_set_company_fields_hidden") as reveal_fields,
        ):
            hooks.enable_algerian_company_fields()

        create_fields.assert_called_once_with(hooks.get_custom_fields(), update=False)
        reveal_fields.assert_called_once_with(False)

    def test_enabling_does_not_claim_an_unmarked_generated_custom_field(self):
        from sotrama import hooks

        foreign_field = frappe._dict(
            {
                "name": "Company-custom_nis",
                "fieldtype": "Data",
                "module": "Custom",
                "is_system_generated": 1,
                "description": "Generated by another app.",
            }
        )

        def get_value(doctype, filters, *args, **kwargs):
            return foreign_field if filters.get("fieldname") == "custom_nis" else None

        with (
            patch.object(hooks.frappe.db, "get_value", side_effect=get_value),
            patch.object(hooks, "create_custom_fields") as create_fields,
            self.assertRaises(frappe.ValidationError),
        ):
            hooks.enable_algerian_company_fields()

        create_fields.assert_not_called()

    def test_enabling_refuses_unowned_legacy_nif_field(self):
        from sotrama import hooks

        manual_nif = frappe._dict(
            {
                "name": "Company-custom_nif",
                "fieldtype": "Data",
                "module": "Custom",
                "is_system_generated": 0,
                "description": "Created manually.",
            }
        )

        def get_value(doctype, filters, *args, **kwargs):
            return manual_nif if filters.get("fieldname") == "custom_nif" else None

        with (
            patch.object(hooks.frappe.db, "get_value", side_effect=get_value),
            patch.object(hooks, "create_custom_fields") as create_fields,
            self.assertRaises(frappe.ValidationError),
        ):
            hooks.enable_algerian_company_fields()

        create_fields.assert_not_called()

    def test_uninstall_detaches_company_fields_instead_of_deleting_them(self):
        from sotrama import hooks, permissions

        fields = [
            frappe._dict(
                {
                    "name": "Company-custom_nif",
                    "fieldname": "custom_nif",
                    "module": "Sotrama",
                    "description": "Legacy NIF",
                    "is_system_generated": 1,
                }
            ),
            frappe._dict(
                {
                    "name": "Company-custom_algerian_registration_section",
                    "fieldname": "custom_algerian_registration_section",
                    "module": "Sotrama",
                    "description": "Legacy section",
                    "is_system_generated": 1,
                }
            ),
            frappe._dict(
                {
                    "name": "Company-custom_nis",
                    "fieldname": "custom_nis",
                    "module": "Sotrama",
                    "description": "NIS field",
                    "is_system_generated": 1,
                }
            ),
            frappe._dict(
                {
                    "name": "Company-custom_capital_social",
                    "fieldname": "custom_capital_social",
                    "module": "Sotrama",
                    "description": "Capital field",
                    "is_system_generated": 1,
                }
            ),
            frappe._dict(
                {
                    "name": "Company-custom_rc",
                    "fieldname": "custom_rc",
                    "module": "Sotrama",
                    "description": "User-managed RC field",
                    "is_system_generated": 0,
                }
            ),
        ]
        with (
            patch.object(
                hooks.frappe.db, "table_exists", return_value=True
            ) as table_exists,
            patch.object(hooks.frappe, "get_all", return_value=fields) as get_all,
            patch.object(hooks.frappe.db, "set_value") as set_value,
            patch.object(hooks.frappe, "clear_cache") as clear_cache,
            patch.object(
                permissions, "preserve_driver_file_privacy_on_uninstall"
            ) as preserve_driver_files,
        ):
            hooks.preserve_company_fields_on_uninstall()

        self.assertEqual(
            get_all.call_args.kwargs["filters"],
            {
                "dt": "Company",
                "fieldname": [
                    field["fieldname"] for field in hooks.get_custom_fields()["Company"]
                ]
                + ["custom_nif", "custom_algerian_registration_section"],
            },
        )
        self.assertEqual(set_value.call_count, 5)
        table_exists.assert_called_once_with("Custom Field")
        for call in set_value.call_args_list:
            self.assertEqual(call.args[0], "Custom Field")
            name = call.args[1]
            values = call.args[2]
            self.assertEqual(values["module"], "Custom")
            if name == "Company-custom_rc":
                self.assertNotIn("hidden", values)
                self.assertNotIn("description", values)
            else:
                self.assertEqual(values["hidden"], 1)
                self.assertIn(
                    hooks.COMPANY_FIELD_OWNERSHIP_MARKER, values["description"]
                )
        self.assertTrue(
            all(
                call.kwargs["update_modified"] is False
                for call in set_value.call_args_list
            )
        )
        clear_cache.assert_called_once_with(doctype="Company")
        preserve_driver_files.assert_called_once_with()


class TestVehicle(unittest.TestCase):
    """Test Vehicle doctype validation and lifecycle."""

    def setUp(self):
        """Create test dependencies."""
        self.company = _get_test_company()
        # Create a Company Classification
        self.classification = frappe.new_doc("Company Classification")
        self.classification.company = self.company
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = "TEST-CLAS-001"
        self.classification.insert(ignore_permissions=True)
        self.classification.submit()

        # Create a Vehicle Make
        self.make = frappe.new_doc("Vehicle Make")
        self.make.make_name = "Test Make"
        self.make.insert(ignore_permissions=True)

        # Create a Vehicle Model
        self.model = frappe.new_doc("Vehicle Model")
        self.model.vehicle_make = self.make.name
        self.model.model_name = "Test Model"
        self.model.insert(ignore_permissions=True)

    def tearDown(self):
        """Clean up test data."""
        if getattr(self, "created_vehicle", None) and frappe.db.exists(
            "Vehicle", self.created_vehicle
        ):
            frappe.delete_doc("Vehicle", self.created_vehicle, ignore_permissions=True)
        for doctype in ["Vehicle Model", "Vehicle Make"]:
            for name in frappe.get_all(doctype, pluck="name"):
                if name.startswith("Test"):
                    frappe.delete_doc(doctype, name, ignore_on_trash=True)
        if frappe.db.exists("Company Classification", self.classification.name):
            frappe.get_doc("Company Classification", self.classification.name).cancel()
            frappe.delete_doc(
                "Company Classification",
                self.classification.name,
                ignore_permissions=True,
            )

    def test_vehicle_creation_with_required_fields(self):
        """Test that a Vehicle can be created with all required fields."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = "TEST-001"
        vehicle.vehicle_make = self.make.name
        vehicle.model = self.model.name
        vehicle.year_of_manufacture = 2020
        vehicle.chassis_no = "TEST1234567890"
        vehicle.vehicle_category = "Truck"
        vehicle.vehicle_class = "Heavy"
        vehicle.tonnage = 15.0
        vehicle.number_of_axles = 3
        vehicle.fuel_type = "Diesel"
        vehicle.current_odometer = 50000.0
        vehicle.acquisition_date = today()
        vehicle.acquisition_value = 2000000
        vehicle.company_classification = self.classification.name
        vehicle.insert()
        self.created_vehicle = vehicle.name

        self.assertEqual(vehicle.vehicle_status, "Active")
        self.assertEqual(vehicle.fuel_type, "Diesel")
        self.assertEqual(vehicle.license_plate, "TEST-001")

        # Cleanup
        frappe.delete_doc("Vehicle", vehicle.name, ignore_on_trash=True)

    def test_vehicle_license_plate_required(self):
        """Test that License Plate is required."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.vehicle_category = "Truck"
        vehicle.company_classification = self.classification.name
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert()

    def test_vehicle_chassis_too_short(self):
        """Test that Chassis Number must be at least 10 characters."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.company = self.company
        vehicle.license_plate = "TEST-002"
        vehicle.vehicle_category = "Truck"
        vehicle.company_classification = self.classification.name
        vehicle.chassis_no = "SHORT"
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert()


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


class TestMaintenanceJobCard(unittest.TestCase):
    """Test Maintenance Job Card cost calculations."""

    def setUp(self):
        """Create test dependencies."""
        self.company = _get_test_company()
        self.classification = frappe.new_doc("Company Classification")
        self.classification.company = self.company
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = "TEST-CLAS-002"
        self.classification.insert(ignore_permissions=True)
        self.classification.submit()

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.company = self.company
        self.vehicle.license_plate = "TEST-MAIN-001"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert()

        item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        stock_uom = (
            "Nos"
            if frappe.db.exists("UOM", "Nos")
            else frappe.db.get_value("UOM", {}, "name")
        )
        self.item = frappe.get_doc(
            {
                "doctype": "Item",
                "item_code": f"SOTRAMA-TEST-{uuid.uuid4().hex[:8].upper()}",
                "item_name": "Sotrama Test Spare Part",
                "item_group": item_group,
                "stock_uom": stock_uom,
                "is_stock_item": 1,
            }
        ).insert(ignore_permissions=True)

    def test_automatic_schedule_lookup_uses_read_permission_and_company_scope(self):
        from sotrama.tp.doctype.maintenance_job_card.maintenance_job_card import (
            MaintenanceJobCard,
        )

        job_card = frappe._dict(
            job_nature="Scheduled Service",
            vehicle=self.vehicle.name,
            company=self.company,
            job_type="JT-TEST",
            maintenance_schedule=None,
        )
        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.get_list",
                return_value=[frappe._dict(name="MS-TEST", company=self.company)],
            ) as get_schedules,
            patch("frappe.has_permission", return_value=True) as has_permission,
            patch("sotrama.tp.settings.validate_company_access") as validate_company,
        ):
            MaintenanceJobCard._validate_maintenance_schedule(job_card)

        self.assertEqual(job_card.maintenance_schedule, "MS-TEST")
        self.assertEqual(
            get_schedules.call_args.kwargs["filters"],
            {
                "vehicle": self.vehicle.name,
                "company": self.company,
                "job_type": "JT-TEST",
                "status": "Active",
                "docstatus": 1,
            },
        )
        has_permission.assert_called_once_with(
            "Maintenance Schedule", "read", doc="MS-TEST", throw=True
        )
        validate_company.assert_called_once_with(self.company, "Maintenance Schedule")

    def test_automatic_schedule_lookup_rejects_other_company(self):
        from sotrama.tp.doctype.maintenance_job_card.maintenance_job_card import (
            MaintenanceJobCard,
        )

        job_card = frappe._dict(
            job_nature="Scheduled Service",
            vehicle=self.vehicle.name,
            company=self.company,
            job_type="JT-TEST",
            maintenance_schedule=None,
        )
        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.get_list",
                return_value=[frappe._dict(name="MS-OTHER", company="OTHER-COMPANY")],
            ),
            patch("frappe.has_permission", return_value=True),
            patch("sotrama.tp.settings.validate_company_access"),
            self.assertRaises(frappe.ValidationError),
        ):
            MaintenanceJobCard._validate_maintenance_schedule(job_card)

    def tearDown(self):
        if frappe.db.exists("Vehicle", self.vehicle.name):
            frappe.delete_doc("Vehicle", self.vehicle.name, ignore_permissions=True)
        if frappe.db.exists("Company Classification", self.classification.name):
            frappe.get_doc("Company Classification", self.classification.name).cancel()
            frappe.delete_doc(
                "Company Classification",
                self.classification.name,
                ignore_permissions=True,
            )
        if frappe.db.exists("Item", self.item.name):
            frappe.delete_doc("Item", self.item.name, ignore_permissions=True)

    def test_job_card_cost_calculation(self):
        """Test that parts, labour, and other costs are summed correctly."""
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.vehicle = self.vehicle.name
        job_card.job_date = today()
        job_card.job_nature = "Repair"
        job_card.status = "Draft"

        # Add a part
        job_card.append(
            "parts_used",
            {
                "item": self.item.name,
                "quantity": 2,
                "rate": 500,
            },
        )

        # Add labour
        job_card.append(
            "labour_lines",
            {
                "mechanic": "Test Mechanic",
                "hours": 3,
                "rate": 1000,
            },
        )

        # Add other cost
        job_card.append(
            "other_costs",
            {
                "description": "Towing",
                "amount": 2000,
            },
        )

        job_card.validate()

        self.assertEqual(job_card.total_parts_cost, 1000)
        self.assertEqual(job_card.total_labour_cost, 3000)
        self.assertEqual(job_card.total_other_cost, 2000)
        self.assertEqual(job_card.total_cost, 6000)

        # Cleanup
        # The document was never inserted; there is no database record to clean up.

    def test_job_card_labour_employee_must_belong_to_the_job_company(self):
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.company = "SOTRAMA-TEST-COMPANY"
        job_card.append(
            "labour_lines",
            {"mechanic": "EMP-TEST-001", "hours": 2, "rate": 500},
        )

        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
            ),
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.db.get_value",
                return_value=None,
            ) as employee_get_value,
            self.assertRaises(frappe.ValidationError),
        ):
            job_card._validate_labour_lines()
        employee_get_value.assert_called_once_with(
            "Employee",
            {"name": "EMP-TEST-001", "company": "SOTRAMA-TEST-COMPANY"},
            ["company", "employee_name"],
            as_dict=True,
        )

        with (
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
            ),
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.db.get_value",
                return_value=frappe._dict(
                    company="SOTRAMA-TEST-COMPANY", employee_name="Test Mechanic"
                ),
            ),
        ):
            job_card._validate_labour_lines()
        self.assertEqual(job_card.labour_lines[0].mechanic_name, "Test Mechanic")

        job_card.labour_lines[0].mechanic = None
        job_card.labour_lines[0].mechanic_name = "Forged Employee Name"
        with patch(
            "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card._validate_workshop_employee_lookup_access"
        ) as employee_lookup:
            job_card._validate_labour_lines()
        employee_lookup.assert_not_called()
        self.assertIsNone(job_card.labour_lines[0].mechanic_name)

    def test_job_card_rejects_disabled_stock_items_server_side(self):
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.append(
            "parts_used", {"item": self.item.name, "quantity": 1, "rate": 10}
        )
        with (
            patch("sotrama.tp.validation.validate_linked_document_read_permission"),
            patch(
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.db.get_value",
                return_value=frappe._dict(is_stock_item=1, disabled=1),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            job_card._check_parts_available()

    def test_job_card_odometer_validation(self):
        """Test that Odometer After cannot be less than Odometer Before."""
        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.vehicle = self.vehicle.name
        job_card.job_date = today()
        job_card.job_nature = "Repair"
        job_card.status = "Draft"
        job_card.odometer_before = 50000
        job_card.odometer_after = 40000  # Less than before
        with self.assertRaises(frappe.ValidationError):
            job_card.validate()

        # The invalid document was never inserted; there is no database record to clean up.


class TestCompanyClassification(unittest.TestCase):
    """Test Company Classification score calculation."""

    def test_grade_8_score_range(self):
        """Test that Grade 8 falls in the correct score range (63.0 - 72.8)."""
        classification = frappe.new_doc("Company Classification")
        classification.company = _get_test_company()
        classification.grade = 8
        classification.category = "TP (Travaux Publics)"
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

        # The validation-only document was never inserted.


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
            frappe.delete_doc(
                "Driver",
                self.driver.name,
                ignore_permissions=True,
                force=True,
                ignore_on_trash=True,
            )

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


class TestMaintenanceScheduleWorkflow(unittest.TestCase):
    def setUp(self):
        self.company = _get_test_company()
        self.classification = frappe.new_doc("Company Classification")
        self.classification.company = self.company
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = f"TEST-SCH-{uuid.uuid4().hex[:6]}"
        self.classification.insert(ignore_permissions=True)
        self.classification.submit()

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.company = self.company
        self.vehicle.license_plate = f"TEST-SCH-{uuid.uuid4().hex[:6]}"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert(ignore_permissions=True)
        self.vehicle.submit()

        self.job_type = frappe.new_doc("Maintenance Job Type")
        self.job_type.job_category = "General"
        self.job_type.job_type_name = f"Test Service {uuid.uuid4().hex[:8]}"
        self.job_type.insert(ignore_permissions=True)
        self.job_type.submit()
        self.created_schedules = []
        self.created_job_cards = []

        self.schedule = frappe.new_doc("Maintenance Schedule")
        self.schedule.vehicle = self.vehicle.name
        self.schedule.job_type = self.job_type.name
        self.schedule.schedule_type = "Calendar"
        self.schedule.interval_months = 6
        self.schedule.last_service_date = today()
        self.schedule.insert(ignore_permissions=True)
        self.schedule.submit()
        self.created_schedules.append(self.schedule.name)

    def tearDown(self):
        for name in self.created_job_cards:
            if frappe.db.exists("Maintenance Job Card", name):
                frappe.delete_doc(
                    "Maintenance Job Card",
                    name,
                    ignore_permissions=True,
                    force=True,
                    ignore_on_trash=True,
                )
        for name in self.created_schedules:
            if frappe.db.exists("Maintenance Schedule", name):
                frappe.delete_doc(
                    "Maintenance Schedule",
                    name,
                    ignore_permissions=True,
                    force=True,
                    ignore_on_trash=True,
                )
        for doctype, name in (
            ("Maintenance Job Type", self.job_type.name),
            ("Vehicle", self.vehicle.name),
            ("Company Classification", self.classification.name),
        ):
            if frappe.db.exists(doctype, name):
                doc = frappe.get_doc(doctype, name)
                if doctype == "Company Classification" and doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(
                    doctype,
                    name,
                    ignore_permissions=True,
                    force=True,
                    ignore_on_trash=True,
                )

    def test_completion_creates_one_linked_successor_and_is_idempotent(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            update_maintenance_schedule_status,
        )

        update_maintenance_schedule_status(self.schedule.name, "Paused")
        update_maintenance_schedule_status(self.schedule.name, "Active")
        result = update_maintenance_schedule_status(self.schedule.name, "Completed")
        self.assertEqual(result["status"], "Completed")
        self.assertTrue(result["next_schedule"])
        self.created_schedules.append(result["next_schedule"])

        successor = frappe.get_doc("Maintenance Schedule", result["next_schedule"])
        self.assertEqual(successor.docstatus, 1)
        self.assertEqual(successor.status, "Active")
        self.assertEqual(successor.vehicle, self.vehicle.name)
        self.assertEqual(successor.job_type, self.job_type.name)
        self.assertTrue(successor.next_due_date)

        repeated = update_maintenance_schedule_status(self.schedule.name, "Completed")
        self.assertEqual(repeated["next_schedule"], successor.name)

    def test_completed_schedule_cannot_be_cancelled_while_successor_is_active(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            update_maintenance_schedule_status,
        )

        result = update_maintenance_schedule_status(self.schedule.name, "Completed")
        successor_name = result["next_schedule"]
        self.created_schedules.append(successor_name)
        self.schedule.reload()

        with self.assertRaises(frappe.ValidationError):
            self.schedule.before_cancel()

        successor = frappe.get_doc("Maintenance Schedule", successor_name)
        successor.cancel()
        self.schedule.reload()
        self.schedule.before_cancel()

    def test_mileage_plan_cannot_complete_without_a_last_service_reading(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            update_maintenance_schedule_status,
        )

        self.schedule.db_set(
            {"schedule_type": "Mileage", "interval_months": None, "interval_km": 10000}
        )
        with self.assertRaises(frappe.ValidationError):
            update_maintenance_schedule_status(self.schedule.name, "Completed")

    def test_completed_scheduled_job_card_advances_same_plan_and_cancel_restores_it(
        self,
    ):
        from frappe.utils import add_days, add_months

        original_due_date = add_days(today(), 30)
        self.schedule.db_set(
            {
                "last_service_date": add_days(today(), -30),
                "next_due_date": original_due_date,
                "last_service_job_card": None,
            }
        )

        job_card = frappe.new_doc("Maintenance Job Card")
        job_card.job_date = today()
        job_card.completion_date = today()
        job_card.vehicle = self.vehicle.name
        job_card.job_nature = "Scheduled Service"
        job_card.job_type = self.job_type.name
        job_card.maintenance_schedule = self.schedule.name
        job_card.status = "Completed"
        job_card.insert(ignore_permissions=True)
        self.created_job_cards.append(job_card.name)
        job_card.submit()

        updated_schedule = frappe.get_doc("Maintenance Schedule", self.schedule.name)
        self.assertEqual(updated_schedule.status, "Active")
        self.assertEqual(updated_schedule.last_service_job_card, job_card.name)
        self.assertEqual(getdate(updated_schedule.last_service_date), getdate(today()))
        self.assertEqual(
            getdate(updated_schedule.next_due_date), getdate(add_months(today(), 6))
        )
        self.assertEqual(updated_schedule.next_schedule, None)

        job_card.cancel()
        restored_schedule = frappe.get_doc("Maintenance Schedule", self.schedule.name)
        self.assertIsNone(restored_schedule.last_service_job_card)
        self.assertEqual(
            getdate(restored_schedule.last_service_date),
            getdate(add_days(today(), -30)),
        )
        self.assertEqual(
            getdate(restored_schedule.next_due_date), getdate(original_due_date)
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
                "sotrama.overrides.file.is_driver_private_attachment",
                return_value=True,
            ),
            patch(
                "sotrama.overrides.file.can_access_driver_private_attachment",
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
            print_logs=False,
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
            print_logs=False,
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
            self.assertRaises(frappe.ValidationError),
        ) as raised:
            _validate_driver_private_file_paths([file_doc])
        self.assertIn("FILE-COLLISION", str(raised.exception))

    def test_migration_repairs_private_flag_with_public_file_url(self):
        from sotrama.permissions import migrate_driver_private_attachments

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
            patch("sotrama.permissions._ensure_driver_file_privacy_field"),
            patch(
                "frappe.get_meta",
                return_value=frappe._dict(has_field=Mock(return_value=False)),
            ),
            patch("frappe.get_all", return_value=[frappe._dict(name=file_doc.name)]),
            patch("frappe.get_doc", return_value=file_doc),
            patch("sotrama.permissions._validate_driver_private_file_paths"),
            patch("sotrama.permissions._remove_private_driver_file_shares"),
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
            patch("frappe.session.user", "hr@example.invalid"),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            _check_driver_compliance_child_rpc_access("Driver Compliance Record")
        with (
            patch("frappe.session.user", "hr@example.invalid"),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            get_value_with_tp_settings_field_permissions(
                "Driver Compliance Record", ["result"], filters={"name": "DCR-001"}
            )
        with (
            patch("frappe.session.user", "hr@example.invalid"),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            get_list_with_tp_settings_permissions("Driver Compliance Record")

        from sotrama.permissions import (
            validate_link_and_fetch_without_tp_settings_singleton,
        )

        with (
            patch("frappe.session.user", "hr@example.invalid"),
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
            print_logs=False,
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
            print_logs=False,
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
            ),
            patch("sotrama.permissions._has_hr_file_access", return_value=False),
        ):
            get_docinfo_with_driver_attachment_filter(
                doc=frappe._dict(doctype="Driver Compliance Record", name="DCR-001")
            )
        self.assertEqual(child_docinfo.attachments, [])
        self.assertEqual(child_docinfo.attachment_logs, [])

    def test_separate_driver_docinfo_endpoint_checks_parent_read_permission(self):
        from sotrama.permissions import get_docinfo_with_driver_attachment_filter

        with (
            patch("frappe.session.user", "fleet@example.invalid"),
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
            print_logs=False,
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
        ):
            result = get_filtered_attachments_with_driver_attachment_filter(
                "Driver", "DRV-001", "[]"
            )
        self.assertEqual(result, [])

        with (
            patch(
                "frappe.desk.form.load.get_filtered_attachments",
                return_value=[frappe._dict(file_name="private-certificate.pdf")],
            ),
            patch("sotrama.permissions._has_hr_file_access", return_value=False),
        ):
            result = get_filtered_attachments_with_driver_attachment_filter(
                "Driver Compliance Record", "DCR-001", "[]"
            )
        self.assertEqual(result, [])


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
            patch("frappe.session.user", "fleet@example.invalid"),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch("frappe.has_permission", return_value=True),
            self.assertRaises(frappe.PermissionError),
        ):
            get_single_value_with_tp_settings_field_permissions(
                "TP Settings", "require_employee_link"
            )

        with (
            patch("frappe.session.user", "hr@example.invalid"),
            patch("frappe.get_roles", return_value=["HR Manager"]),
            patch("frappe.has_permission", return_value=True),
            self.assertRaises(frappe.PermissionError),
        ):
            get_single_value_with_tp_settings_field_permissions(
                "TP Settings", "default_company"
            )

        with (
            patch("frappe.session.user", "fleet@example.invalid"),
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
            patch("frappe.session.user", "fleet@example.invalid"),
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
            patch("frappe.session.user", "fleet@example.invalid"),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            get_list_with_tp_settings_permissions(
                "TP Settings", fields=["default_company"]
            )

        with (
            patch("frappe.session.user", "fleet@example.invalid"),
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
            patch("frappe.session.user", "fleet@example.invalid"),
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
            patch("frappe.session.user", "fleet@example.invalid"),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
        ):
            self.assertEqual(tp_company_defaults_query_conditions(), "1=0")
            self.assertEqual(tp_settings_query_conditions(), "1=0")

        with (
            patch("frappe.session.user", "system@example.invalid"),
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
            patch("frappe.session.user", "fleet@example.invalid"),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(fleet_share)

        target = frappe._dict(doctype="Vehicle", name="VEH-001")
        with (
            patch("frappe.session.user", "system@example.invalid"),
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
            print_logs=False,
        )

        with (
            patch("frappe.session.user", "system@example.invalid"),
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
            patch("frappe.session.user", "system@example.invalid"),
            patch("frappe.get_roles", return_value=["System Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(everyone_share)

        with (
            patch("frappe.session.user", "system@example.invalid"),
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
            patch("frappe.session.user", "hr@example.invalid"),
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
            patch("frappe.session.user", "fleet@example.invalid"),
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
            patch("frappe.session.user", "fleet@example.invalid"),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            patch.object(current, "get_doc_before_save", return_value=previous),
        ):
            current._validate_company_defaults_permissions()

        self.assertEqual(current.default_company, "COMPANY-A")
        self.assertEqual(current.company_defaults[0].company, "COMPANY-A")

        new_settings = frappe.new_doc("TP Settings")
        new_settings.default_company = "COMPANY-B"
        with (
            patch("frappe.session.user", "fleet@example.invalid"),
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
            patch("frappe.session.user", "fleet@example.invalid"),
            patch("frappe.get_roles", return_value=["Fleet Manager"]),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(share)

        with (
            patch("frappe.session.user", "system@example.invalid"),
            patch("frappe.get_roles", return_value=["System Manager"]),
            patch("frappe.get_doc", return_value=frappe._dict(name="VEH-001")),
            patch("frappe.has_permission", return_value=False),
            self.assertRaises(frappe.PermissionError),
        ):
            prevent_unsafe_fleet_docsharing(share)


class TestFleetSchedulerPrivacy(unittest.TestCase):
    """Scheduler alerts must respect document access and field privacy."""

    def test_role_assignment_requires_read_permission_for_the_exact_document(self):
        from sotrama.tp.scheduler import _user_for_role

        with (
            patch(
                "sotrama.tp.scheduler.frappe.get_all",
                return_value=["fleet-a@example.invalid", "fleet-b@example.invalid"],
            ),
            patch("sotrama.tp.scheduler.frappe.db.get_value", return_value=1),
            patch("sotrama.tp.scheduler.frappe.db.exists", return_value=True),
            patch(
                "sotrama.tp.scheduler.frappe.has_permission",
                side_effect=[False, True],
            ) as has_permission,
        ):
            assigned = _user_for_role("Fleet Manager", "Vehicle", "VEHICLE-B")

        self.assertEqual(assigned, "fleet-b@example.invalid")
        self.assertEqual(has_permission.call_count, 2)
        self.assertEqual(has_permission.call_args_list[0].kwargs["doc"], "VEHICLE-B")

    def test_legacy_driver_alerts_are_sanitized_and_routed_to_the_right_role(self):
        from sotrama.tp.scheduler import remediate_fleet_alert_todo_assignments

        todos = [
            frappe._dict(
                name="TODO-LICENSE",
                title="Driver License Expiring: Test Driver",
                reference_type="Driver",
                reference_name="DRV-TEST-001",
                allocated_to="fleet@example.invalid",
                description="Old alert exposed licence SECRET-LICENSE-NUMBER",
            ),
            frappe._dict(
                name="TODO-SAFETY",
                title="Safety Training Expiring: Test Driver",
                reference_type="Driver",
                reference_name="DRV-TEST-001",
                allocated_to="fleet@example.invalid",
                description="Old safety alert with HR-only training date",
            ),
            frappe._dict(
                name="TODO-COMPLIANCE",
                title="Restricted Driver Compliance Review",
                reference_type="Driver",
                reference_name="DRV-TEST-001",
                allocated_to="fleet@example.invalid",
                description="Old alert contained medical result: POSITIVE",
            ),
        ]
        driver_license = frappe._dict(
            driver_name="Test Driver", license_expiry=add_days(today(), 1)
        )
        driver_safety = frappe._dict(
            driver_name="Test Driver", safety_training_expiry=add_days(today(), 2)
        )
        with (
            patch("sotrama.tp.scheduler.frappe.get_all", return_value=todos),
            patch(
                "sotrama.tp.scheduler._user_for_role",
                side_effect=[
                    "fleet@example.invalid",
                    "hr@example.invalid",
                    "hr@example.invalid",
                ],
            ),
            patch(
                "sotrama.tp.scheduler.frappe.db.get_value",
                side_effect=[driver_license, driver_safety],
            ),
            patch("sotrama.tp.scheduler.frappe.db.set_value") as set_value,
        ):
            remediate_fleet_alert_todo_assignments()

        license_update = set_value.call_args_list[0].args[2]
        safety_update = set_value.call_args_list[1].args[2]
        compliance_update = set_value.call_args_list[2].args[2]
        self.assertEqual(license_update["allocated_to"], "fleet@example.invalid")
        self.assertNotIn("SECRET-LICENSE-NUMBER", license_update["description"])
        self.assertEqual(safety_update["allocated_to"], "hr@example.invalid")
        self.assertIn("safety training", safety_update["description"])
        self.assertEqual(compliance_update["allocated_to"], "hr@example.invalid")
        self.assertNotIn("POSITIVE", compliance_update["description"])

    def test_driver_alerts_do_not_disclose_licence_number_or_safety_expiry_to_fleet(
        self,
    ):
        from sotrama.tp.scheduler import check_driver_license_expiry

        driver = frappe._dict(
            name="DRV-TEST-PRIVACY",
            driver_name="Test Driver",
            license_number="SECRET-LICENSE-NUMBER",
            license_expiry=add_days(today(), 1),
            safety_training_expiry=add_days(today(), 2),
        )
        license_todo = Mock()
        safety_todo = Mock()
        with (
            patch("sotrama.tp.scheduler.get_tp_setting", return_value=60),
            patch("sotrama.tp.scheduler.frappe.get_all", side_effect=[[], [driver]]),
            patch("sotrama.tp.scheduler.frappe.db.exists", return_value=False),
            patch(
                "sotrama.tp.scheduler.frappe.new_doc",
                side_effect=[license_todo, safety_todo],
            ),
            patch(
                "sotrama.tp.scheduler._user_for_role",
                side_effect=["fleet@example.invalid", "hr@example.invalid"],
            ),
        ):
            check_driver_license_expiry()

        self.assertEqual(license_todo.allocated_to, "fleet@example.invalid")
        self.assertNotIn("SECRET-LICENSE-NUMBER", license_todo.description)
        self.assertEqual(safety_todo.allocated_to, "hr@example.invalid")


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
            transport_kind="Transport de marchandises",
            project=None,
        )
        with (
            patch("frappe.has_permission", return_value=True),
            patch(
                "frappe.db.get_value",
                return_value=frappe._dict(vehicle_status="Active", company="COMPANY-A"),
            ),
            patch("sotrama.tp.settings.validate_company_access"),
            self.assertRaises(frappe.ValidationError),
        ):
            OperationalTask._validate_vehicle(task)

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
                return_value=frappe._dict(vehicle_status="Active", company="COMPANY-A"),
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
            transport_kind="Transport de marchandises",
            transport_basis="Compte propre",
            transport_regulatory_status="À confirmer",
        )
        with self.assertRaises(frappe.ValidationError):
            OperationalTask._validate_transport_regulatory_applicability(task)

    def test_own_account_transport_requires_authority_evidence_before_regulated_submission(
        self,
    ):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        task = frappe._dict(
            name="OT-EVIDENCE-001",
            doctype="Operational Task",
            task_type="Transport",
            transport_kind="Transport de marchandises",
            transport_basis="Compte propre",
            transport_regulatory_status="Réglementé",
            driver="DRV-001",
            transport_authority_reference="DECISION-001",
            transport_authority_decision_date="2026-10-01",
            transport_authority_evidence="/private/files/authority-decision.pdf",
        )
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
        validate_certificate.assert_called_once_with(
            "DRV-001", "Transport de marchandises"
        )

    def test_nonregulated_transport_requires_official_authority_evidence(self):
        from sotrama.tp.doctype.operational_task.operational_task import OperationalTask

        incomplete_task = frappe._dict(
            task_type="Transport",
            transport_kind="Transport de marchandises",
            transport_basis="Compte propre",
            transport_regulatory_status="Non soumis (confirmation officielle)",
            transport_authority_reference="DECISION-002",
            transport_authority_decision_date="2026-10-01",
            transport_authority_evidence=None,
        )
        with self.assertRaises(frappe.ValidationError):
            OperationalTask._validate_transport_regulatory_applicability(
                incomplete_task
            )

        task = frappe._dict(
            name="OT-EVIDENCE-002",
            doctype="Operational Task",
            task_type="Transport",
            transport_kind="Transport de marchandises",
            transport_basis="Compte propre",
            transport_regulatory_status="Non soumis (confirmation officielle)",
            transport_authority_reference="DECISION-002",
            transport_authority_decision_date="2026-10-01",
            transport_authority_evidence="/private/files/authority-decision.pdf",
        )
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

        task = frappe._dict(
            name="OT-EVIDENCE-003",
            doctype="Operational Task",
            task_type="Transport",
            transport_kind="Transport de marchandises",
            transport_basis="Compte propre",
            transport_regulatory_status="Non soumis (confirmation officielle)",
            transport_authority_reference="DECISION-003",
            transport_authority_decision_date="2026-10-01",
            transport_authority_evidence="/private/files/authority-decision.pdf",
        )
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
                return_value=frappe._dict(vehicle_status="Active", company="COMPANY-A"),
            ),
            patch("sotrama.tp.settings.validate_company_access"),
            patch("sotrama.tp.validation.validate_active_driver") as validate_driver,
        ):
            OperationalTask._validate_vehicle(task)

        validate_driver.assert_called_once_with("DRIVER-A", "COMPANY-A")


class TestBreakdownIncident(unittest.TestCase):
    """Test Breakdown Incident validation and workflow."""

    def setUp(self):
        self.company = _get_test_company()
        self.classification = frappe.new_doc("Company Classification")
        self.classification.company = self.company
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = "TEST-BRK-001"
        self.classification.insert(ignore_permissions=True)
        self.classification.submit()

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.company = self.company
        self.vehicle.license_plate = "TEST-BRK-VEH-001"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert()
        self.created_breakdowns = []
        self.created_inspections = []
        self.created_drivers = []

    def tearDown(self):
        for name in reversed(self.created_inspections):
            if frappe.db.exists("Vehicle Inspection", name):
                frappe.delete_doc(
                    "Vehicle Inspection",
                    name,
                    ignore_permissions=True,
                    force=True,
                    ignore_on_trash=True,
                )
        for name in self.created_breakdowns:
            if frappe.db.exists("Breakdown Incident", name):
                frappe.delete_doc(
                    "Breakdown Incident",
                    name,
                    ignore_permissions=True,
                    force=True,
                    ignore_on_trash=True,
                )
        for name in self.created_drivers:
            if frappe.db.exists("Driver", name):
                frappe.delete_doc(
                    "Driver",
                    name,
                    ignore_permissions=True,
                    force=True,
                    ignore_on_trash=True,
                )
        for doctype, name in (
            ("Vehicle", self.vehicle.name),
            ("Company Classification", self.classification.name),
        ):
            if frappe.db.exists(doctype, name):
                if doctype == "Company Classification":
                    frappe.get_doc(doctype, name).cancel()
                frappe.delete_doc(
                    doctype,
                    name,
                    ignore_permissions=True,
                    force=True,
                    ignore_on_trash=True,
                )

    def test_breakdown_date_validation(self):
        """Test that Resolution Date cannot be before Incident Date."""
        from frappe.utils import add_days

        breakdown = frappe.new_doc("Breakdown Incident")
        breakdown.vehicle = self.vehicle.name
        breakdown.incident_date = today()
        breakdown.resolution_date = add_days(today(), -1)  # Before incident
        breakdown.description = "Test breakdown"
        with self.assertRaises(frappe.ValidationError):
            breakdown.validate()

        # The invalid document was never inserted; there is no database record to clean up.

    def test_breakdown_can_record_a_historical_incident_for_a_suspended_driver(self):
        from frappe.utils import add_days, now_datetime

        from sotrama.tp.doctype.driver.driver import update_driver_status

        driver = frappe.new_doc("Driver")
        driver.driver_name = f"Suspended Driver {uuid.uuid4().hex[:8]}"
        driver.company = self.company
        driver.license_number = f"TEST-{uuid.uuid4().hex[:8]}"
        driver.license_expiry = add_days(today(), 365)
        driver.insert(ignore_permissions=True)
        driver.submit()
        self.created_drivers.append(driver.name)
        update_driver_status(driver.name, "Suspended")

        breakdown = frappe.new_doc("Breakdown Incident")
        breakdown.vehicle = self.vehicle.name
        breakdown.driver = driver.name
        breakdown.incident_date = now_datetime()
        breakdown.description = "Historical incident attributed to a suspended driver"
        breakdown.insert(ignore_permissions=True)
        self.created_breakdowns.append(breakdown.name)
        with patch(
            "sotrama.tp.doctype.breakdown_incident.breakdown_incident.BreakdownIncident._create_job_card"
        ):
            breakdown.submit()

        self.assertEqual(breakdown.driver, driver.name)

    def _submit_breakdown(self):
        from frappe.utils import now_datetime

        breakdown = frappe.new_doc("Breakdown Incident")
        breakdown.vehicle = self.vehicle.name
        breakdown.incident_date = now_datetime()
        breakdown.description = "Test vehicle breakdown"
        breakdown.insert(ignore_permissions=True)
        self.created_breakdowns.append(breakdown.name)
        # Job-card creation has its own workflow; isolate the vehicle-status
        # lifecycle here so the test does not create a cross-linked work order.
        with patch(
            "sotrama.tp.doctype.breakdown_incident.breakdown_incident.BreakdownIncident._create_job_card"
        ):
            breakdown.submit()
        return frappe.get_doc("Breakdown Incident", breakdown.name)

    def _set_breakdown_status(self, name, status):
        from frappe.utils import now_datetime

        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            update_breakdown_status,
        )

        values = {}
        if status == "Resolved":
            values = {
                "resolution_date": now_datetime(),
                "resolution_notes": "Test repair completed",
            }
        update_breakdown_status(name, status, **values)
        return frappe.get_doc("Breakdown Incident", name)

    def _submit_critical_inspection(self):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.vehicle = self.vehicle.name
        inspection.inspection_type = "Periodic"
        inspection.inspection_date = today()
        inspection._ensure_standard_checklist()
        for row in inspection.inspection_items:
            row.status = "Okay"
        brake_check = next(
            row
            for row in inspection.inspection_items
            if row.category == "Freinage et direction"
        )
        brake_check.item_details = "Brake system check"
        brake_check.status = "Defective"
        brake_check.remarks = "Test brake defect"
        brake_check.is_safety_critical = 1
        inspection.insert(ignore_permissions=True)
        self.created_inspections.append(inspection.name)
        with patch(
            "sotrama.tp.doctype.vehicle_inspection.vehicle_inspection.VehicleInspection._create_defect_issues"
        ):
            inspection.submit()
        return inspection

    def _submit_follow_up_inspection(self, previous_inspection):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.vehicle = self.vehicle.name
        inspection.inspection_type = "Post-Incident"
        inspection.inspection_date = today()
        inspection.overall_status = "Pass"
        inspection.follow_up_of = previous_inspection.name
        inspection._ensure_standard_checklist()
        for row in inspection.inspection_items:
            row.status = "Okay"
        brake_check = next(
            row
            for row in inspection.inspection_items
            if row.category == "Freinage et direction"
        )
        brake_check.item_details = "Brake system reinspection"
        brake_check.is_safety_critical = 1
        inspection.insert(ignore_permissions=True)
        self.created_inspections.append(inspection.name)
        with patch(
            "sotrama.tp.doctype.vehicle_inspection.vehicle_inspection.VehicleInspection._create_defect_issues"
        ):
            inspection.submit()
        return inspection

    def test_resolving_breakdown_restores_vehicle_status(self):
        breakdown = self._submit_breakdown()
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )
        self.assertEqual(breakdown.previous_vehicle_status, "Active")

        self._set_breakdown_status(breakdown.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )

    def test_reopening_resolved_breakdown_marks_vehicle_out_of_service_again(self):
        breakdown = self._submit_breakdown()
        self._set_breakdown_status(breakdown.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )

        self._set_breakdown_status(breakdown.name, "In Progress")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )
        self.assertEqual(
            frappe.db.get_value(
                "Breakdown Incident", breakdown.name, "previous_vehicle_status"
            ),
            "Active",
        )
        self.assertFalse(
            frappe.db.get_value("Breakdown Incident", breakdown.name, "resolution_date")
        )
        self.assertEqual(
            frappe.db.get_value("Breakdown Incident", breakdown.name, "downtime_hours"),
            0,
        )

    def test_resolved_breakdown_requires_a_resolution_date(self):
        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            update_breakdown_status,
        )

        breakdown = self._submit_breakdown()
        with self.assertRaises(frappe.ValidationError):
            update_breakdown_status(breakdown.name, "Resolved")

    def test_breakdown_status_transition_is_audited_and_disallows_invalid_jumps(self):
        from frappe.utils import now_datetime

        from sotrama.tp.doctype.breakdown_incident.breakdown_incident import (
            update_breakdown_status,
        )

        breakdown = self._submit_breakdown()
        with self.assertRaises(frappe.ValidationError):
            update_breakdown_status(breakdown.name, "Closed")

        self._set_breakdown_status(breakdown.name, "Acknowledged")
        self._set_breakdown_status(breakdown.name, "In Progress")
        update_breakdown_status(
            breakdown.name,
            "Resolved",
            resolution_date=now_datetime(),
            resolution_notes="Resolved in test",
        )

        comments = frappe.get_all(
            "Comment",
            filters={
                "reference_doctype": "Breakdown Incident",
                "reference_name": breakdown.name,
            },
            fields=["content"],
            order_by="creation asc",
        )
        self.assertTrue(
            any("Resolved" in (comment.content or "") for comment in comments)
        )

    def test_overlapping_breakdowns_keep_vehicle_out_of_service_until_last_resolves(
        self,
    ):
        first = self._submit_breakdown()
        second = self._submit_breakdown()

        self._set_breakdown_status(first.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )

        self._set_breakdown_status(second.name, "Resolved")
        self._set_breakdown_status(second.name, "Closed")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )

    def test_resolving_breakdown_preserves_preexisting_manual_out_of_service(self):
        frappe.db.set_value(
            "Vehicle", self.vehicle.name, "vehicle_status", "Out of Service"
        )
        breakdown = self._submit_breakdown()
        self.assertEqual(breakdown.previous_vehicle_status, "Out of Service")

        self._set_breakdown_status(breakdown.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )

    def test_resolving_breakdown_does_not_override_critical_inspection(self):
        breakdown = self._submit_breakdown()
        inspection = self._submit_critical_inspection()

        self._set_breakdown_status(breakdown.name, "Resolved")
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )

        with self.assertRaises(frappe.ValidationError):
            inspection.cancel()
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )

    def test_successful_follow_up_clears_critical_inspection_and_cancel_reinstates_hold(
        self,
    ):
        critical = self._submit_critical_inspection()
        follow_up = self._submit_follow_up_inspection(critical)

        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )
        self.assertEqual(
            frappe.db.get_value(
                "Vehicle Inspection", critical.name, "critical_defect_cleared_by"
            ),
            follow_up.name,
        )

        follow_up.cancel()
        self.assertFalse(
            frappe.db.get_value(
                "Vehicle Inspection", critical.name, "critical_defect_cleared_by"
            )
        )
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Out of Service",
        )
