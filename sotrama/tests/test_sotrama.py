"""
Test suite for Sotrama — Algerian Localization & TP Fleet Management.

Run with: bench --site your-site run-tests --app sotrama
"""


import json
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate, today


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
            module_path = app_path.joinpath(*dotted_path.split(".")[1:]).with_suffix(".py")
            self.assertTrue(module_path.is_file(), f"Patch module does not exist: {dotted_path}")

    def test_default_fleet_masters_are_created_for_a_fresh_install(self):
        self.assertTrue(frappe.db.exists("Vehicle Make", {"make_name": "Mercedes-Benz"}))
        self.assertTrue(frappe.db.exists("Vehicle Make", {"make_name": "Volvo"}))
        self.assertTrue(frappe.db.exists("Maintenance Job Type", {"job_type_name": "Oil Change"}))

    def test_sotrama_settings_doctype_is_inside_its_declared_module(self):
        module_path = Path(frappe.get_module_path("Sotrama"))
        self.assertTrue(
            (module_path / "doctype" / "sotrama_settings" / "sotrama_settings.json").is_file()
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
        importable_doctypes = frappe.get_hooks("importable_doctypes", app_name="sotrama")
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
            any("/assets/sotrama/js/sotrama.js" in path for path in hooks["app_include_js"])
        )
        self.assertIsInstance(hooks.get("filters_config"), list)

    def test_app_lifecycle_hooks_are_import_paths(self):
        app_hooks = frappe.get_hooks(app_name="sotrama")
        self.assertEqual(app_hooks["before_install"][0], "sotrama.hooks.prepare_before_install")
        self.assertEqual(app_hooks["after_install"][0], "sotrama.hooks.initialize_app")
        self.assertFalse(
            app_hooks.get("after_migrate"),
            "Migrations must not create or alter optional Company custom fields.",
        )
        self.assertEqual(
            app_hooks["before_uninstall"][0],
            "sotrama.hooks.preserve_company_fields_on_uninstall",
        )

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
        self.assertEqual(app_entry["has_permission"], "sotrama.permissions.has_app_permission")

    def test_standard_desktop_navigation_includes_the_overview_module(self):
        from sotrama.config.desktop import get_data

        modules = {entry["module_name"] for entry in get_data()}
        self.assertEqual(modules, {"Sotrama", "TP", "Algerian Localization"})
        module = frappe.get_doc("Module Def", "Sotrama")
        self.assertEqual(module.app_name, "sotrama")
        self.assertFalse(module.custom)
        sidebar = frappe.get_doc("Sidebar", "Sotrama")
        self.assertTrue(any(item.link_to == "Sotrama Settings" for item in sidebar.items))
        dock = frappe.get_doc("Dock", {"app": "sotrama", "standard": 1})
        self.assertEqual(
            {item.link_to for item in dock.items if item.link_type == "Sidebar"},
            {"Sotrama", "TP", "Algerian Localization"},
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
        self.assertEqual(_designation_name_key("Gérant"), _designation_name_key("GERANT"))

        created = ensure_public_works_designations()
        try:
            self.assertTrue(all(frappe.db.exists("Designation", name) for name in created))
            if frappe.get_meta("Designation").has_field("description"):
                self.assertTrue(
                    all(not frappe.db.get_value("Designation", name, "description") for name in created)
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
            {"Sotrama Fleet", "Algerian Localization", "Sotrama Settings"},
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
            self.assertTrue(frappe.db.exists("Number Card", card_name), f"Missing Number Card: {card_name}")

        sidebar = frappe.get_doc("Sidebar", "TP")
        self.assertTrue(any(item.link_to == "TP Settings" for item in sidebar.items))
        self.assertTrue(any(item.link_to == "TP Settings" for item in workspace.links))
        self.assertIn("HR Manager", {row.role for row in workspace.roles})

        app_dock = frappe.get_doc("Dock", {"app": "sotrama", "standard": 1})
        self.assertEqual(
            {item.link_to for item in app_dock.items if item.link_type == "Sidebar"},
            {"Sotrama", "TP", "Algerian Localization"},
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
            self.assertIsNotNone(meta.get_field(fieldname), f"Missing TP setting: {fieldname}")

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
            permission for permission in meta.permissions
            if permission.role == "HR Manager" and permission.permlevel == 1
        ]
        self.assertTrue(hr_permissions)
        self.assertTrue(hr_permissions[0].read)
        self.assertTrue(hr_permissions[0].write)

        system_permissions = [
            permission for permission in meta.permissions
            if permission.role == "System Manager" and permission.permlevel == 1
        ]
        self.assertTrue(system_permissions)
        self.assertTrue(system_permissions[0].read)
        self.assertTrue(system_permissions[0].write)

        fleet_permissions = [
            permission for permission in meta.permissions
            if permission.role == "Fleet Manager" and permission.permlevel == 1
        ]
        self.assertFalse(fleet_permissions)

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
            "filters: { company: frm.doc.company || '' }",
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

    def test_workshop_employee_lookup_is_limited_to_accessible_company_and_safe_fields(self):
        from sotrama.tp.doctype.maintenance_job_card.maintenance_job_card import (
            get_workshop_employee_name,
            search_workshop_employees,
        )

        module = "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card"
        with (
            patch(f"{module}.frappe.only_for") as only_for,
            patch(f"{module}.frappe.has_permission", return_value=True),
            patch(f"{module}.frappe.get_list", return_value=[{"name": "VEH-001"}]),
            patch(
                f"{module}.frappe.get_all",
                return_value=[("EMP-001", "Ali Mechanic", "Mécanicien")],
            ) as get_all,
        ):
            result = search_workshop_employees(
                "Employee", "Ali", "name", 0, 10, {"company": "SOTRAMA"}
            )

        self.assertEqual(result, [("EMP-001", "Ali Mechanic", "Mécanicien")])
        only_for.assert_called_once_with(["System Manager", "Fleet Manager", "Workshop"])
        query = get_all.call_args.kwargs
        self.assertEqual(query["fields"], ["name", "employee_name", "designation"])
        self.assertEqual(query["filters"], {"company": "SOTRAMA", "status": "Active"})
        self.assertTrue(query["as_list"])

        with (
            patch(f"{module}.frappe.only_for"),
            patch(f"{module}.frappe.has_permission", return_value=True),
            patch(f"{module}.frappe.get_list", return_value=[{"name": "VEH-001"}]),
            patch(f"{module}.frappe.db.get_value", return_value="Ali Mechanic"),
        ):
            self.assertEqual(
                get_workshop_employee_name("EMP-001", "SOTRAMA"), "Ali Mechanic"
            )

        with (
            patch(f"{module}.frappe.only_for"),
            patch(f"{module}.frappe.has_permission", return_value=True),
            patch(f"{module}.frappe.get_list", return_value=[]),
            self.assertRaises(frappe.PermissionError),
        ):
            get_workshop_employee_name("EMP-001", "OTHER-COMPANY")

        with (
            patch(f"{module}.frappe.only_for"),
            patch(f"{module}.frappe.has_permission", return_value=False),
            patch(f"{module}.frappe.get_list") as get_vehicles,
            self.assertRaises(frappe.PermissionError),
        ):
            get_workshop_employee_name("EMP-001", "SOTRAMA")
        get_vehicles.assert_not_called()

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

        inspection.inspection_items[0].status = "Okay"
        inspection.before_submit()

        inspection.inspection_items[0].status = "Defective"
        with self.assertRaises(frappe.ValidationError):
            inspection.before_submit()
        inspection.inspection_items[0].remarks = "Brake hose damaged"
        inspection.before_submit()

    def test_follow_up_inspection_can_be_saved_as_draft_before_checks_are_complete(self):
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
            patch("sotrama.tp.settings.get_tp_setting", side_effect=lambda key, default=None: default),
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
            patch("sotrama.tp.settings.get_tp_setting", side_effect=lambda key, default=None: default),
        ):
            driver._validate_employee_link()
        only_for.assert_called_once_with(["System Manager", "HR Manager"])

    def test_driver_licence_categories_include_the_2025_decree_categories(self):
        driver_meta = frappe.get_meta("Driver", cached=False)
        licence_field = driver_meta.get_field("license_class")
        categories = set((licence_field.options or "").splitlines())
        for category in ("A1", "A", "B", "B(E)", "C1", "C1(E)", "C", "C(E)", "D", "D(E)", "F"):
            self.assertIn(category, categories)
        for fieldname in ("license_number", "license_class", "license_expiry", "license_issue_date"):
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
            permission for permission in driver_meta.permissions
            if permission.role == "HR Manager" and permission.permlevel == 1
        ]
        self.assertTrue(hr_permissions)
        self.assertTrue(hr_permissions[0].read)
        self.assertTrue(hr_permissions[0].write)

        system_manager_permissions = [
            permission for permission in driver_meta.permissions
            if permission.role == "System Manager" and permission.permlevel == 1
        ]
        self.assertTrue(system_manager_permissions)
        self.assertTrue(system_manager_permissions[0].read)
        self.assertTrue(system_manager_permissions[0].write)

        fleet_permissions = [
            permission for permission in driver_meta.permissions
            if permission.role == "Fleet Manager" and permission.permlevel == 1
        ]
        workshop_permissions = [
            permission for permission in driver_meta.permissions
            if permission.role == "Workshop" and permission.permlevel == 1
        ]
        self.assertFalse(fleet_permissions)
        self.assertFalse(workshop_permissions)

        record_meta = frappe.get_meta("Driver Compliance Record", cached=False)
        self.assertTrue(record_meta.istable)
        self.assertIsNotNone(record_meta.get_field("valid_until"))

    def test_transport_activity_options_follow_road_code_articles_79_80(self):
        field = frappe.get_meta("Operational Task", cached=False).get_field("transport_kind")
        activities = set((field.options or "").splitlines())
        for activity in (
            "Transport collectif de personnes",
            "Transport scolaire",
            "Transport de marchandises",
            "Transport de matières dangereuses",
            "Transport par taxi",
        ):
            self.assertIn(activity, activities)

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
        for fieldname in ("status", "resolution_date", "resolution_notes", "downtime_hours"):
            self.assertTrue(meta.get_field(fieldname).read_only)
            self.assertFalse(meta.get_field(fieldname).allow_on_submit)

        vehicle_meta = frappe.get_meta("Vehicle", cached=False)
        self.assertTrue(vehicle_meta.get_field("primary_driver").allow_on_submit)

    def test_fleet_reports_have_reference_doctypes(self):
        self.assertEqual(frappe.get_value("Report", "Fleet Cost Analysis", "ref_doctype"), "Vehicle")
        self.assertEqual(
            frappe.get_value("Report", "Upcoming Document Expiries", "ref_doctype"),
            "Vehicle",
        )

    def test_fleet_cost_report_uses_site_default_currency_for_cost_fields(self):
        from sotrama.tp.report.fleet_cost_analysis.fleet_cost_analysis import (
            get_columns,
            get_data,
        )

        self.assertFalse(frappe.get_value("Report", "Fleet Cost Analysis", "add_total_row"))
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
            self.assertIn(layout.get("page", {}).get("size"), {"A4", "Letter", "Legal", "A3"})
            meta = frappe.get_meta(doctype, cached=False)

            custom_names = set()
            zones = [layout.get("header", {}), *layout["sections"], layout.get("footer", {})]
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
                                child_field = child_meta.get_field(table_column["fieldname"])
                                self.assertIsNotNone(
                                    child_field,
                                    f"{name}: unknown child field {docfield.options}.{table_column['fieldname']}",
                                )
                                self.assertEqual(table_column.get("fieldtype"), child_field.fieldtype)
                                if child_field.options:
                                    self.assertEqual(table_column.get("options"), child_field.options)

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
            all(hooks.COMPANY_FIELD_OWNERSHIP_MARKER in field["description"] for field in definitions)
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

    def test_migration_does_not_create_company_fields_when_settings_doctype_is_missing(self):
        from sotrama import hooks

        with (
            patch.object(hooks.frappe.db, "exists", return_value=False),
            patch.object(hooks, "enable_algerian_company_fields") as enable_fields,
            patch.object(hooks, "_set_company_fields_hidden") as hide_fields,
        ):
            hooks.sync_company_fields()

        enable_fields.assert_not_called()
        hide_fields.assert_not_called()

    def test_enabling_creates_only_missing_fields_without_overwriting_existing_fields(self):
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
        self.assertTrue(all(call.kwargs["update_modified"] is False for call in set_value.call_args_list))
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
            return legacy_field if filters.get("fieldname") == "custom_capital_social" else None

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

    def test_enabling_recognizes_system_generated_fields_preserved_in_custom_module(self):
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
        from sotrama import hooks

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
            patch.object(hooks.frappe.db, "table_exists", return_value=True) as table_exists,
            patch.object(hooks.frappe, "get_all", return_value=fields) as get_all,
            patch.object(hooks.frappe.db, "set_value") as set_value,
            patch.object(hooks.frappe, "clear_cache") as clear_cache,
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
                self.assertIn(hooks.COMPANY_FIELD_OWNERSHIP_MARKER, values["description"])
        self.assertTrue(all(call.kwargs["update_modified"] is False for call in set_value.call_args_list))
        clear_cache.assert_called_once_with(doctype="Company")


class TestVehicle(unittest.TestCase):
    """Test Vehicle doctype validation and lifecycle."""

    def setUp(self):
        """Create test dependencies."""
        # Create a Company Classification
        self.classification = frappe.new_doc("Company Classification")
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
            frappe.delete_doc("Company Classification", self.classification.name, ignore_permissions=True)

    def test_vehicle_creation_with_required_fields(self):
        """Test that a Vehicle can be created with all required fields."""
        vehicle = frappe.new_doc("Vehicle")
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
        vehicle.vehicle_category = "Truck"
        vehicle.company_classification = self.classification.name
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert()

    def test_vehicle_chassis_too_short(self):
        """Test that Chassis Number must be at least 10 characters."""
        vehicle = frappe.new_doc("Vehicle")
        vehicle.license_plate = "TEST-002"
        vehicle.vehicle_category = "Truck"
        vehicle.company_classification = self.classification.name
        vehicle.chassis_no = "SHORT"
        with self.assertRaises(frappe.ValidationError):
            vehicle.insert()


class TestDriver(unittest.TestCase):
    """Test Driver doctype validation."""

    def test_driver_license_required(self):
        """Test that License Number is required."""
        driver = frappe.new_doc("Driver")
        driver.driver_name = "Test Driver"
        with self.assertRaises(frappe.ValidationError):
            driver.insert()

    def test_driver_license_expiry_warning(self):
        """Test that expired license shows warning."""
        driver = frappe.new_doc("Driver")
        driver.driver_name = "Test Driver"
        driver.license_number = "LIC-001"
        driver.license_expiry = add_days(today(), -1)  # expired yesterday
        driver.insert()  # Should not throw, just msgprint
        frappe.delete_doc("Driver", driver.name, ignore_on_trash=True)


class TestMaintenanceJobCard(unittest.TestCase):
    """Test Maintenance Job Card cost calculations."""

    def setUp(self):
        """Create test dependencies."""
        self.classification = frappe.new_doc("Company Classification")
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = "TEST-CLAS-002"
        self.classification.insert(ignore_permissions=True)
        self.classification.submit()

        self.vehicle = frappe.new_doc("Vehicle")
        self.vehicle.license_plate = "TEST-MAIN-001"
        self.vehicle.vehicle_category = "Truck"
        self.vehicle.company_classification = self.classification.name
        self.vehicle.insert()

        item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name")
        stock_uom = "Nos" if frappe.db.exists("UOM", "Nos") else frappe.db.get_value(
            "UOM", {}, "name"
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

    def tearDown(self):
        if frappe.db.exists("Vehicle", self.vehicle.name):
            frappe.delete_doc("Vehicle", self.vehicle.name, ignore_permissions=True)
        if frappe.db.exists("Company Classification", self.classification.name):
            frappe.get_doc("Company Classification", self.classification.name).cancel()
            frappe.delete_doc("Company Classification", self.classification.name, ignore_permissions=True)
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
        job_card.append("parts_used", {
            "item": self.item.name,
            "quantity": 2,
            "rate": 500,
        })

        # Add labour
        job_card.append("labour_lines", {
            "mechanic": "Test Mechanic",
            "hours": 3,
            "rate": 1000,
        })

        # Add other cost
        job_card.append("other_costs", {
            "description": "Towing",
            "amount": 2000,
        })

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
                "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.db.get_value",
                return_value=frappe._dict(company="ANOTHER-COMPANY"),
            ),
            self.assertRaises(frappe.ValidationError),
        ):
            job_card._validate_labour_lines()

        with patch(
            "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.frappe.db.get_value",
            return_value=frappe._dict(
                company="SOTRAMA-TEST-COMPANY", employee_name="Test Mechanic"
            ),
        ):
            job_card._validate_labour_lines()
        self.assertEqual(job_card.labour_lines[0].mechanic_name, "Test Mechanic")

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
        self.driver = frappe.new_doc("Driver")
        self.driver.driver_name = f"Test Driver {uuid.uuid4().hex[:8]}"
        self.driver.license_number = f"TEST-{uuid.uuid4().hex[:8]}"
        self.driver.license_expiry = add_days(today(), 365)
        self.driver.insert(ignore_permissions=True)
        self.driver.submit()

    def tearDown(self):
        if frappe.db.exists("Driver", self.driver.name):
            driver = frappe.get_doc("Driver", self.driver.name)
            if driver.docstatus == 1:
                driver.cancel()
            frappe.delete_doc("Driver", self.driver.name, ignore_permissions=True)

    def test_driver_status_uses_audited_transitions_and_revalidates_on_reactivation(self):
        from sotrama.tp.doctype.driver.driver import update_driver_status

        update_driver_status(self.driver.name, "Suspended")
        self.assertEqual(frappe.db.get_value("Driver", self.driver.name, "status"), "Suspended")

        update_driver_status(self.driver.name, "Active")
        self.assertEqual(frappe.db.get_value("Driver", self.driver.name, "status"), "Active")

        update_driver_status(self.driver.name, "Terminated")
        with self.assertRaises(frappe.ValidationError):
            update_driver_status(self.driver.name, "Active")

        comments = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Driver", "reference_name": self.driver.name},
            fields=["content"],
            order_by="creation asc",
        )
        self.assertTrue(any("Terminated" in (comment.content or "") for comment in comments))


class TestMaintenanceScheduleWorkflow(unittest.TestCase):
    def setUp(self):
        self.classification = frappe.new_doc("Company Classification")
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = f"TEST-SCH-{uuid.uuid4().hex[:6]}"
        self.classification.insert(ignore_permissions=True)
        self.classification.submit()

        self.vehicle = frappe.new_doc("Vehicle")
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
                job_card = frappe.get_doc("Maintenance Job Card", name)
                if job_card.docstatus == 1:
                    job_card.cancel()
                frappe.delete_doc("Maintenance Job Card", name, ignore_permissions=True)
        for name in self.created_schedules:
            if frappe.db.exists("Maintenance Schedule", name):
                schedule = frappe.get_doc("Maintenance Schedule", name)
                if schedule.docstatus == 1:
                    schedule.cancel()
                frappe.delete_doc("Maintenance Schedule", name, ignore_permissions=True)
        for doctype, name in (
            ("Maintenance Job Type", self.job_type.name),
            ("Vehicle", self.vehicle.name),
            ("Company Classification", self.classification.name),
        ):
            if frappe.db.exists(doctype, name):
                doc = frappe.get_doc(doctype, name)
                if doc.docstatus == 1:
                    doc.cancel()
                frappe.delete_doc(doctype, name, ignore_permissions=True)

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

    def test_mileage_plan_cannot_complete_without_a_last_service_reading(self):
        from sotrama.tp.doctype.maintenance_schedule.maintenance_schedule import (
            update_maintenance_schedule_status,
        )

        self.schedule.db_set({"schedule_type": "Mileage", "interval_months": None, "interval_km": 10000})
        with self.assertRaises(frappe.ValidationError):
            update_maintenance_schedule_status(self.schedule.name, "Completed")

    def test_completed_scheduled_job_card_advances_same_plan_and_cancel_restores_it(self):
        from frappe.utils import add_days, add_months

        original_due_date = add_days(today(), 30)
        self.schedule.db_set({
            "last_service_date": add_days(today(), -30),
            "next_due_date": original_due_date,
            "last_service_job_card": None,
        })

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
        self.assertEqual(getdate(updated_schedule.next_due_date), getdate(add_months(today(), 6)))
        self.assertEqual(updated_schedule.next_schedule, None)

        job_card.cancel()
        restored_schedule = frappe.get_doc("Maintenance Schedule", self.schedule.name)
        self.assertIsNone(restored_schedule.last_service_job_card)
        self.assertEqual(getdate(restored_schedule.last_service_date), getdate(add_days(today(), -30)))
        self.assertEqual(getdate(restored_schedule.next_due_date), getdate(original_due_date))


class TestBreakdownIncident(unittest.TestCase):
    """Test Breakdown Incident validation and workflow."""

    def setUp(self):
        self.classification = frappe.new_doc("Company Classification")
        self.classification.grade = 8
        self.classification.category = "TP (Travaux Publics)"
        self.classification.registration_number = "TEST-BRK-001"
        self.classification.insert(ignore_permissions=True)
        self.classification.submit()

        self.vehicle = frappe.new_doc("Vehicle")
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
                inspection = frappe.get_doc("Vehicle Inspection", name)
                if inspection.docstatus == 1:
                    inspection.cancel()
                frappe.delete_doc("Vehicle Inspection", name, ignore_permissions=True)
        for name in self.created_breakdowns:
            if frappe.db.exists("Breakdown Incident", name):
                incident = frappe.get_doc("Breakdown Incident", name)
                if incident.docstatus == 1:
                    incident.cancel()
                frappe.delete_doc("Breakdown Incident", name, ignore_permissions=True)
        for name in self.created_drivers:
            if frappe.db.exists("Driver", name):
                driver = frappe.get_doc("Driver", name)
                if driver.docstatus == 1:
                    driver.cancel()
                frappe.delete_doc("Driver", name, ignore_permissions=True)
        for doctype, name in (
            ("Vehicle", self.vehicle.name),
            ("Company Classification", self.classification.name),
        ):
            if frappe.db.exists(doctype, name):
                if doctype == "Company Classification":
                    frappe.get_doc(doctype, name).cancel()
                frappe.delete_doc(doctype, name, ignore_permissions=True)

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
        with patch("sotrama.tp.doctype.breakdown_incident.breakdown_incident.BreakdownIncident._create_job_card"):
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
        with patch("sotrama.tp.doctype.breakdown_incident.breakdown_incident.BreakdownIncident._create_job_card"):
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
        inspection.append("inspection_items", {
            "category": "Freinage et direction",
            "item_details": "Brake system check",
            "status": "Defective",
            "remarks": "Test brake defect",
            "is_safety_critical": 1,
        })
        inspection.insert(ignore_permissions=True)
        self.created_inspections.append(inspection.name)
        with patch("sotrama.tp.doctype.vehicle_inspection.vehicle_inspection.VehicleInspection._create_defect_issues"):
            inspection.submit()
        return inspection

    def _submit_follow_up_inspection(self, previous_inspection):
        inspection = frappe.new_doc("Vehicle Inspection")
        inspection.vehicle = self.vehicle.name
        inspection.inspection_type = "Post-Incident"
        inspection.inspection_date = today()
        inspection.overall_status = "Pass"
        inspection.follow_up_of = previous_inspection.name
        inspection.append("inspection_items", {
            "category": "Freinage et direction",
            "item_details": "Brake system reinspection",
            "status": "Okay",
            "is_safety_critical": 1,
        })
        inspection.insert(ignore_permissions=True)
        self.created_inspections.append(inspection.name)
        with patch("sotrama.tp.doctype.vehicle_inspection.vehicle_inspection.VehicleInspection._create_defect_issues"):
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
            filters={"reference_doctype": "Breakdown Incident", "reference_name": breakdown.name},
            fields=["content"],
            order_by="creation asc",
        )
        self.assertTrue(any("Resolved" in (comment.content or "") for comment in comments))

    def test_overlapping_breakdowns_keep_vehicle_out_of_service_until_last_resolves(self):
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
        frappe.db.set_value("Vehicle", self.vehicle.name, "vehicle_status", "Out of Service")
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

        inspection.cancel()
        self.assertEqual(
            frappe.db.get_value("Vehicle", self.vehicle.name, "vehicle_status"),
            "Active",
        )

    def test_successful_follow_up_clears_critical_inspection_and_cancel_reinstates_hold(self):
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
