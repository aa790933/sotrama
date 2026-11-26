# Frappe integration tests for Sotrama setup behavior.

import ast
import json
import re
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

import frappe

from sotrama.tests.helpers import (
    _sotrama_package_path,
)


class TestSotramaSetup(unittest.TestCase):
    """Protect against incompatible hook value shapes across installed apps."""

    def test_frappe_16_todo_schema_uses_description_not_title(self):
        todo_meta = frappe.get_meta("ToDo")
        self.assertTrue(todo_meta.has_field("description"))
        self.assertFalse(todo_meta.has_field("title"))

    def test_frappe_16_has_permission_calls_do_not_pass_removed_print_logs(self):
        offenders = []
        for path in _sotrama_package_path().rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                if not isinstance(node.func, ast.Attribute):
                    continue
                if node.func.attr != "has_permission":
                    continue
                if any(keyword.arg == "print_logs" for keyword in node.keywords):
                    offenders.append(f"{path}:{node.lineno}")
        self.assertEqual(offenders, [])

    def test_fleet_workspace_number_cards_count_only_submitted_records(self):
        number_cards = {
            "active_vehicles": "Vehicle",
            "vehicles_out_of_service": "Vehicle",
            "active_maintenance_plans": "Maintenance Schedule",
        }
        for card_name, doctype in number_cards.items():
            with self.subTest(card=card_name):
                card_path = (
                    _sotrama_package_path()
                    / "tp"
                    / "number_card"
                    / card_name
                    / f"{card_name}.json"
                )
                card = json.loads(card_path.read_text(encoding="utf-8"))
                filters = json.loads(card["filters_json"])
                self.assertIn([doctype, "docstatus", "=", 1], filters)

    def test_sotrama_home_workspace_has_central_setup_cards(self):
        workspace_path = (
            _sotrama_package_path()
            / "sotrama"
            / "workspace"
            / "sotrama"
            / "sotrama.json"
        )
        workspace = json.loads(workspace_path.read_text(encoding="utf-8"))
        card_names = {
            block.get("data", {}).get("card_name")
            for block in json.loads(workspace["content"])
            if block.get("type") == "card"
        }
        self.assertEqual(card_names, {"Company & HR Setup", "Fleet Configuration"})
        links = {
            link.get("link_to")
            for link in workspace["links"]
            if link.get("type") == "Link"
        }
        self.assertEqual(
            links,
            {"Company", "Designation", "Sotrama Settings", "TP Settings"},
        )
        self.assertTrue(
            all(
                link.get("link_type") in {"DocType", "Page", "Report"}
                for link in workspace["links"]
                if link.get("type") == "Link"
            )
        )
        workspace_roles = {row["role"] for row in workspace["roles"]}
        self.assertTrue(
            {"System Manager", "Fleet Manager", "Workshop"}.issubset(workspace_roles)
        )

    def test_app_install_does_not_trigger_an_unnecessary_yarn_install(self):
        app_path = Path(frappe.get_app_path("sotrama"))
        self.assertFalse(
            (app_path / "package.json").exists(),
            "Sotrama has no Node dependencies; package.json makes Bench run Yarn and can dirty the Git checkout.",
        )

    def test_declared_patches_resolve_to_real_python_modules(self):
        app_path = _sotrama_package_path()
        patch_file = app_path / "patches.txt"
        for line in patch_file.read_text(encoding="utf-8").splitlines():
            dotted_path = line.strip()
            if not dotted_path or dotted_path.startswith(("#", "[")):
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
        self.assertTrue(
            frappe.get_meta("File", cached=False).has_field(
                "sotrama_private_driver_attachment"
            )
        )
        self.assertTrue(
            frappe.get_meta("File", cached=False).has_field(
                "sotrama_private_fleet_attachment"
            )
        )
        self.assertTrue(
            frappe.db.get_single_value("Sotrama Settings", "setup_initialized")
        )
        setup_marker = frappe.get_meta("Sotrama Settings", cached=False).get_field(
            "setup_initialized"
        )
        self.assertTrue(setup_marker.hidden)
        self.assertTrue(setup_marker.read_only)

    def test_before_install_ensures_driver_and_fleet_attachment_privacy_metadata(self):
        from sotrama.setup import install

        with (
            patch.object(install, "ensure_roles"),
            patch.object(install, "repair_orphaned_module_definitions"),
            patch(
                "sotrama.permissions._ensure_driver_file_privacy_field"
            ) as ensure_field,
            patch(
                "sotrama.permissions._ensure_fleet_file_privacy_field"
            ) as ensure_fleet_field,
        ):
            install.prepare_before_install()

        ensure_field.assert_called_once_with()
        ensure_fleet_field.assert_called_once_with()

    def test_before_install_refuses_to_claim_an_unowned_fleet_file_privacy_field(self):
        from sotrama.permissions import _ensure_fleet_file_privacy_field

        foreign_field = frappe._dict(
            name="File-sotrama_private_fleet_attachment",
            fieldtype="Data",
            module="Custom",
            is_system_generated=1,
            description="Created by another app.",
        )
        with (
            patch(
                "sotrama.permissions.frappe.db.get_value",
                return_value=foreign_field,
            ),
            patch("sotrama.permissions.create_custom_fields") as create_fields,
            self.assertRaises(frappe.ValidationError),
        ):
            _ensure_fleet_file_privacy_field()

        create_fields.assert_not_called()

    def test_after_migrate_retries_only_an_incomplete_first_install(self):
        from sotrama.setup import install

        with (
            patch.object(install.frappe.db, "table_exists", return_value=True),
            patch.object(install.frappe.db, "get_single_value", return_value=0),
            patch.object(install, "initialize_app") as initialize,
        ):
            install.recover_incomplete_install()

        initialize.assert_called_once_with()

        with (
            patch.object(install.frappe.db, "table_exists", return_value=True),
            patch.object(install.frappe.db, "get_single_value", return_value=1),
            patch.object(install, "initialize_app") as initialize,
        ):
            install.recover_incomplete_install()

        initialize.assert_not_called()

        with (
            patch.object(install.frappe.db, "table_exists", return_value=False),
            patch.object(install, "initialize_app") as initialize,
        ):
            install.recover_incomplete_install()

        initialize.assert_not_called()

    def test_before_install_refuses_to_claim_an_unowned_file_privacy_field(self):
        from sotrama.permissions import _ensure_driver_file_privacy_field

        foreign_field = frappe._dict(
            name="File-sotrama_private_driver_attachment",
            fieldtype="Data",
            module="Custom",
            is_system_generated=1,
            description="Created by another app.",
        )
        with (
            patch(
                "sotrama.permissions.frappe.db.get_value",
                return_value=foreign_field,
            ),
            patch("sotrama.permissions.create_custom_fields") as create_fields,
            self.assertRaises(frappe.ValidationError),
        ):
            _ensure_driver_file_privacy_field()

        create_fields.assert_not_called()

    def test_regional_setup_entrypoint_remains_available(self):
        from sotrama.setup import setup

        self.assertTrue(callable(setup))
        self.assertIsNone(setup(company="SOTRAMA"))

    def test_sotrama_settings_doctype_is_inside_its_declared_module(self):
        module_path = Path(frappe.get_module_path("Sotrama"))
        self.assertTrue(
            (
                module_path / "doctype" / "sotrama_settings" / "sotrama_settings.json"
            ).is_file()
        )

    def test_standard_workspace_exports_have_importable_names(self):
        app_path = _sotrama_package_path()
        workspace_files = {
            app_path / "sotrama" / "workspace" / "sotrama" / "sotrama.json": "Sotrama",
            app_path
            / "tp"
            / "workspace"
            / "sotrama_fleet"
            / "sotrama_fleet.json": "Sotrama Fleet",
            app_path
            / "tp"
            / "workspace"
            / "fleet_management_reports"
            / "fleet_management_reports.json": "Fleet Management Reports",
        }

        for path, expected_name in workspace_files.items():
            workspace = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(workspace.get("doctype"), "Workspace")
            self.assertTrue(workspace.get("name"), f"Missing import name in {path}")
            self.assertEqual(workspace["name"], expected_name)

    def test_french_translation_catalog_is_valid_and_covers_fleet_workflows(self):
        catalog_path = _sotrama_package_path() / "locale" / "fr.po"
        catalog = catalog_path.read_text(encoding="utf-8")

        for source, expected in (
            ("Vehicle", "Véhicule"),
            ("Technical Specifications", "Caractéristiques techniques"),
            ("Driver / Operator", "Conducteur / opérateur"),
            ("Fleet Cost Analysis", "Analyse des coûts du parc"),
            (
                "Registration Certificate",
                "Certificat d'immatriculation (carte grise)",
            ),
            (
                "Enable Algerian registration fields",
                "Activer les identifiants d'immatriculation algériens",
            ),
            ("Add Custom Check", "Ajouter un contrôle personnalisé"),
            (
                "Import Missing BTPH Job Titles",
                "Importer les intitulés BTPH manquants",
            ),
            (
                "Job Type Name is required",
                "Le nom du type d'intervention est obligatoire",
            ),
            (
                "Enter the manufacturer's name. This value is also used as the readable record ID.",
                "Saisissez le nom du constructeur. Cette valeur sert également d'identifiant lisible de la fiche.",
            ),
            (
                "Enter the manufacturer's model designation. The internal record ID is generated from the selected make and model name.",
                "Saisissez la désignation du modèle du constructeur. L'identifiant interne de la fiche est généré à partir de la marque sélectionnée et du nom du modèle.",
            ),
            (
                "Officially Confirmed Not Subject",
                "Non soumis (confirmation officielle)",
            ),
        ):
            self.assertIn(f'msgid "{source}"\nmsgstr "{expected}"', catalog)

    def test_frappe_loads_compiled_french_translations_when_available(self):
        translation_paths = (
            Path(
                frappe.get_site_path(
                    "assets", "locale", "fr", "LC_MESSAGES", "sotrama.mo"
                )
            ),
            Path(
                frappe.get_site_path(
                    "..", "assets", "locale", "fr", "LC_MESSAGES", "sotrama.mo"
                )
            ).resolve(),
        )
        if not any(path.is_file() for path in translation_paths):
            self.skipTest("French translations have not been compiled on this site.")

        self.assertEqual(frappe._("Vehicle", lang="fr"), "Véhicule")
        self.assertEqual(
            frappe._("Registration Certificate", lang="fr"),
            "Certificat d'immatriculation (carte grise)",
        )
        self.assertEqual(
            frappe._("VEHICLE INSPECTION", lang="fr"), "CONTRÔLE DU VÉHICULE"
        )

    def test_french_catalog_covers_custom_doctype_labels_options_and_ui_messages(self):
        package_path = _sotrama_package_path()
        from babel.messages.pofile import read_po

        catalog_path = package_path / "locale" / "fr.po"
        with catalog_path.open("rb") as source_file:
            catalog = read_po(source_file)
        translations = {}
        msgids = set()
        for message in catalog:
            if not message.id:
                continue
            msgids.add(message.id)
            values = (
                tuple(message.string.values())
                if isinstance(message.string, dict)
                else message.string
                if isinstance(message.string, (tuple, list))
                else (message.string,)
            )
            if values and all(values):
                translations.setdefault(message.id, []).append(message.string)

        def assert_translated(message, description):
            self.assertIn(message, msgids, description)
            self.assertIn(
                message,
                translations,
                f"Empty French translation: {description}",
            )

        non_translatable_options = {
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
            "m²",
            "m³",
            "t",
            "km",
        }

        for path in package_path.rglob("*.json"):
            try:
                definition = json.loads(path.read_text(encoding="utf-8-sig"))
            except OSError, json.JSONDecodeError:
                continue
            if definition.get("doctype") == "DocType" and definition.get("description"):
                assert_translated(
                    definition["description"],
                    f"French DocType description: {path}",
                )
            for field in definition.get("fields", []):
                label = field.get("label")
                if label:
                    assert_translated(label, f"French label: {path}:{label}")
                if field.get("description"):
                    assert_translated(
                        field["description"],
                        f"French field description: {path}:{field.get('fieldname')}",
                    )
                if field.get("fieldtype") == "Select" and field.get("options"):
                    for option in field["options"].splitlines():
                        if option and option not in non_translatable_options:
                            assert_translated(option, f"French option: {path}:{option}")
            if any(
                part in {"workspace", "report", "dashboard", "notification"}
                for part in path.parts
            ):

                def check_workspace_and_report_labels(value, location, path=path):
                    if isinstance(value, dict):
                        for key, child in value.items():
                            if (
                                key in {"label", "title", "description"}
                                and isinstance(child, str)
                                and child
                            ):
                                assert_translated(
                                    child,
                                    f"French workspace/report text: {path}:{location}/{key}",
                                )
                            check_workspace_and_report_labels(
                                child, f"{location}/{key}"
                            )
                    elif isinstance(value, list):
                        for index, child in enumerate(value):
                            check_workspace_and_report_labels(
                                child, f"{location}/{index}"
                            )

                check_workspace_and_report_labels(definition, "root")
        for path in package_path.rglob("print_format/**/*.json"):
            definition = json.loads(path.read_text(encoding="utf-8-sig"))
            format_data = definition.get("format_data")
            if not format_data:
                continue
            layout = json.loads(format_data)

            def check_print_format_content(value, location, path=path):
                if isinstance(value, dict):
                    if value.get("label"):
                        assert_translated(
                            value["label"],
                            f"French print-format label: {path}:{location}",
                        )
                    if value.get("text"):
                        assert_translated(
                            value["text"],
                            f"French print-format text: {path}:{location}",
                        )
                    if value.get("fieldtype") == "Select" and value.get("options"):
                        for option in value["options"].splitlines():
                            if option and option not in non_translatable_options:
                                assert_translated(
                                    option,
                                    f"French print-format option: {path}:{location}",
                                )
                    for key, child in value.items():
                        check_print_format_content(child, f"{location}/{key}")
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        check_print_format_content(child, f"{location}/{index}")

            check_print_format_content(layout, "format_data")

        for path in package_path.rglob("*.js"):
            source = path.read_text(encoding="utf-8-sig")
            for quote, literal in re.findall(
                r"__\(\s*(['\"])(.*?)\1", source, re.DOTALL
            ):
                message = ast.literal_eval(f"{quote}{literal}{quote}")
                assert_translated(
                    message, f"French JavaScript message: {path}:{message}"
                )

        for path in package_path.rglob("*.py"):
            source = path.read_text(encoding="utf-8-sig")
            tree = ast.parse(source, filename=str(path))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                function = node.func
                is_gettext_call = (
                    isinstance(function, ast.Name) and function.id == "_"
                ) or (isinstance(function, ast.Attribute) and function.attr == "_")
                if not is_gettext_call or not node.args:
                    continue
                argument = node.args[0]
                if not isinstance(argument, ast.Constant) or not isinstance(
                    argument.value, str
                ):
                    continue
                message = argument.value
                if message == "and ":
                    continue
                assert_translated(message, f"French Python message: {path}:{message}")

    def test_primary_fleet_forms_keep_core_sections_open_and_details_collapsed(self):
        sections = {
            "Vehicle": {
                "open": ("section_vehicle_identity",),
                "collapsed": (
                    "section_specs",
                    "section_acquisition",
                    "section_assignment",
                    "section_documents",
                ),
                "single_tab": False,
                "tab_count": 3,
            },
            "Breakdown Incident": {
                "open": ("section_incident",),
                "collapsed": ("section_resolution", "section_evidence"),
                "single_tab": False,
                "tab_count": 2,
            },
            "Maintenance Job Card": {
                "open": ("section_work_order",),
                "collapsed": (
                    "section_diagnosis",
                    "section_execution",
                    "section_cost_summary",
                    "section_parts",
                    "section_attachments",
                ),
                "single_tab": False,
                "tab_count": 3,
            },
            "Maintenance Schedule": {
                "open": ("section_plan",),
                "collapsed": ("section_last_service", "section_notes"),
                "single_tab": False,
                "tab_count": 2,
            },
            "Operational Task": {
                "open": ("section_assignment",),
                "collapsed": ("section_time", "section_output"),
                "single_tab": False,
                "tab_count": 3,
            },
            "Vehicle Inspection": {
                "open": ("section_inspection", "section_inspection_results"),
                "collapsed": (),
                "single_tab": False,
                "tab_count": 2,
            },
            "Driver": {
                "open": (
                    "section_driver_identity",
                    "section_licence",
                    "section_contact",
                ),
                "collapsed": ("section_restricted_compliance",),
                "single_tab": False,
                "tab_count": 3,
            },
            "Vehicle Document": {
                "open": ("section_vehicle_document",),
                "collapsed": (),
                "single_tab": False,
            },
            "Vehicle Make": {
                "open": ("section_make",),
                "collapsed": (),
                "single_tab": False,
            },
            "Vehicle Model": {
                "open": ("section_model",),
                "collapsed": (),
                "single_tab": False,
            },
            "Company Classification": {
                "open": ("section_certificate",),
                "collapsed": (
                    "section_workforce",
                    "section_resources",
                    "section_execution",
                ),
                "single_tab": False,
            },
            "Breakdown Photo": {
                "open": ("section_breakdown_photo",),
                "collapsed": (),
                "single_tab": False,
            },
            "Inspection Item": {
                "open": ("section_checklist_item",),
                "collapsed": (),
                "single_tab": False,
            },
            "Job Card Labour": {
                "open": ("section_labour_details",),
                "collapsed": (),
                "single_tab": False,
            },
            "Job Card Other Cost": {
                "open": ("section_other_cost",),
                "collapsed": (),
                "single_tab": False,
            },
            "Job Card Part": {
                "open": ("section_part_details",),
                "collapsed": ("section_part_traceability",),
                "single_tab": False,
            },
            "Job Card Photo": {
                "open": ("section_job_photo",),
                "collapsed": (),
                "single_tab": False,
            },
            "Maintenance Job Type": {
                "open": ("section_job_type",),
                "collapsed": (),
                "single_tab": False,
            },
            "TP Settings": {
                "open": ("section_company_defaults",),
                "collapsed": (
                    "section_company_matrix",
                    "section_employee_policy",
                    "section_alert_windows",
                ),
                "single_tab": False,
            },
        }
        for doctype, expected in sections.items():
            meta = frappe.get_meta(doctype, cached=False)
            tabs = [
                field.fieldname
                for field in meta.fields
                if field.fieldtype == "Tab Break"
            ]
            if expected["single_tab"]:
                self.assertEqual(len(tabs), 1, doctype)
            if expected.get("tab_count"):
                self.assertEqual(len(tabs), expected["tab_count"], doctype)
            for fieldname in expected["open"]:
                self.assertFalse(
                    meta.get_field(fieldname).collapsible, f"{doctype}.{fieldname}"
                )
            for fieldname in expected["collapsed"]:
                self.assertTrue(
                    meta.get_field(fieldname).collapsible, f"{doctype}.{fieldname}"
                )

    def test_role_profiles_use_frappe_importable_doctype_sync(self):
        importable_doctypes = frappe.get_hooks(
            "importable_doctypes", app_name="sotrama"
        )
        self.assertIn("Role Profile", importable_doctypes)
        role_profile_meta = frappe.get_meta("Role Profile", cached=False)
        self.assertTrue(role_profile_meta.has_field("role_profile"))
        self.assertFalse(role_profile_meta.has_field("role_profile_name"))
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
        self.assertFalse(
            any(
                "/assets/sotrama/js/sotrama.js" in path
                for path in hooks["app_include_js"]
            )
        )
        self.assertIsInstance(hooks.get("filters_config"), list)

    def test_app_lifecycle_hooks_are_import_paths(self):
        app_hooks = frappe.get_hooks(app_name="sotrama")
        self.assertEqual(
            app_hooks["before_install"][0],
            "sotrama.setup.install.prepare_before_install",
        )
        self.assertEqual(
            app_hooks["after_install"][0], "sotrama.setup.install.initialize_app"
        )
        self.assertEqual(
            app_hooks["after_migrate"][0],
            "sotrama.setup.install.recover_incomplete_install",
        )
        self.assertEqual(
            app_hooks["never_skip_patches"],
            ["sotrama.patches.v1_4.initial_data_cleanup"],
        )
        patches = (
            Path(frappe.get_app_path("sotrama")).joinpath("patches.txt").read_text()
        )
        self.assertIn("[post_model_sync]", patches)
        self.assertIn("sotrama.patches.v1_4.initial_data_cleanup", patches)
        self.assertEqual(
            app_hooks["before_uninstall"][0],
            "sotrama.setup.uninstall.preserve_company_fields_on_uninstall",
        )

    def test_initial_cleanup_patch_runs_security_migrations_before_optional_company_nif(
        self,
    ):
        from sotrama.patches.v1_4.initial_data_cleanup import execute

        calls = []
        with (
            patch(
                "sotrama.setup.masters.ensure_default_masters",
                side_effect=lambda: calls.append("masters"),
            ),
            patch(
                "sotrama.migrations.fleet_documents.migrate_fleet_document_options",
                side_effect=lambda: calls.append("documents"),
            ),
            patch(
                "sotrama.migrations.fleet_reference_masters.simplify_fleet_reference_masters",
                side_effect=lambda: calls.append("reference_masters"),
            ),
            patch(
                "sotrama.migrations.navigation.remove_legacy_algerian_localization_workspace",
                side_effect=lambda: calls.append("navigation"),
            ),
            patch(
                "sotrama.migrations.fleet_master_names.normalize_fleet_master_names",
                side_effect=lambda: calls.append("master_names"),
            ),
            patch(
                "sotrama.permissions.remove_unsafe_fleet_docshares",
                side_effect=lambda: calls.append("unsafe_shares"),
            ),
            patch(
                "sotrama.migrations.security.migrate_driver_private_attachments",
                side_effect=lambda: calls.append("driver_files"),
            ),
            patch(
                "sotrama.migrations.security.migrate_fleet_attachments_private",
                side_effect=lambda: calls.append("fleet_files"),
            ),
            patch(
                "sotrama.migrations.security.remediate_fleet_alert_todo_assignments",
                side_effect=lambda: calls.append("fleet_todos"),
            ),
            patch(
                "sotrama.tp.doctype.vehicle_document.vehicle_document.refresh_vehicle_document_statuses",
                side_effect=lambda: calls.append("document_status"),
            ),
            patch(
                "sotrama.migrations.company.migrate_legacy_company_nif",
                side_effect=lambda: (
                    calls.append("company_nif")
                    or {"copied": 1, "conflicts": 0, "skipped": 0}
                ),
            ) as migrate_nif,
            patch(
                "sotrama.migrations.company.hide_managed_legacy_company_nif",
                side_effect=lambda result: calls.append("company_nif_hidden"),
            ) as hide_legacy_nif,
        ):
            execute()

        migrate_nif.assert_called_once_with()
        hide_legacy_nif.assert_called_once_with(
            {"copied": 1, "conflicts": 0, "skipped": 0}
        )
        self.assertEqual(
            calls,
            [
                "masters",
                "documents",
                "reference_masters",
                "navigation",
                "master_names",
                "unsafe_shares",
                "driver_files",
                "fleet_files",
                "fleet_todos",
                "document_status",
                "company_nif",
                "company_nif_hidden",
            ],
        )

    def test_fleet_attachment_migration_makes_existing_files_private(self):
        from sotrama.migrations.security import migrate_fleet_attachments_private
        from sotrama.permissions import (
            COMPANY_SCOPED_FLEET_DOCTYPES,
            SOTRAMA_CHILD_TABLE_DOCTYPES,
        )

        attached_doctypes = sorted(
            COMPANY_SCOPED_FLEET_DOCTYPES | SOTRAMA_CHILD_TABLE_DOCTYPES
        )
        fleet_rows = [
            frappe._dict(name="FILE-001", content_hash=None),
            frappe._dict(name="FILE-002", content_hash=None),
        ]
        with (
            patch(
                "sotrama.migrations.security.frappe.get_all",
                return_value=fleet_rows,
            ) as get_files,
            patch("sotrama.migrations.security._ensure_fleet_file_privacy_field"),
            patch("sotrama.migrations.security.frappe.get_doc") as get_doc,
        ):
            file_docs = []
            for file_url in ("/files/one.pdf", "/files/two.pdf"):
                file_doc = Mock(is_private=0, file_url=file_url)
                file_doc.get.side_effect = lambda field: (
                    False if field == "is_remote_file" else None
                )
                file_docs.append(file_doc)
            get_doc.side_effect = file_docs
            migrate_fleet_attachments_private()

        get_files.assert_called_once_with(
            "File",
            filters={"attached_to_doctype": ["in", attached_doctypes]},
            fields=["name", "content_hash"],
            limit_page_length=0,
        )
        self.assertEqual(
            get_doc.call_args_list,
            [call("File", "FILE-001"), call("File", "FILE-002")],
        )
        for file_doc in file_docs:
            self.assertEqual(file_doc.is_private, 1)
            file_doc.save.assert_called_once_with(ignore_permissions=True)

    def test_fleet_attachment_migration_validates_already_private_content_groups(self):
        from sotrama.migrations.security import migrate_fleet_attachments_private

        fleet_row = frappe._dict(name="FILE-PRIVATE", content_hash="existing-hash")
        file_doc = Mock(is_private=1, file_url="/private/files/existing.pdf")
        file_doc.get.side_effect = lambda field: {
            "is_remote_file": False,
            "content_hash": "existing-hash",
            "sotrama_private_fleet_attachment": 1,
        }.get(field)
        with (
            patch(
                "sotrama.migrations.security.frappe.get_all",
                return_value=[fleet_row],
            ),
            patch("sotrama.migrations.security._ensure_fleet_file_privacy_field"),
            patch("sotrama.migrations.security.frappe.get_doc", return_value=file_doc),
            patch(
                "sotrama.migrations.security.prevent_fleet_attachment_content_reuse",
                side_effect=frappe.PermissionError,
            ) as validate_reuse,
            self.assertRaises(frappe.PermissionError),
        ):
            migrate_fleet_attachments_private()

        validate_reuse.assert_called_once_with(file_doc)
        file_doc.save.assert_not_called()

    def test_fleet_attachment_migration_repairs_public_url_with_private_flag(self):
        from sotrama.migrations.security import migrate_fleet_attachments_private

        fleet_row = frappe._dict(name="FILE-LEGACY", content_hash=None)
        file_doc = Mock(is_private=1, file_url="/files/legacy.pdf")
        file_doc.get.side_effect = lambda field: (
            False if field == "is_remote_file" else None
        )
        with (
            patch(
                "sotrama.migrations.security.frappe.get_all",
                return_value=[fleet_row],
            ),
            patch("sotrama.migrations.security._ensure_fleet_file_privacy_field"),
            patch("sotrama.migrations.security.frappe.get_doc", return_value=file_doc),
        ):
            migrate_fleet_attachments_private()

        self.assertEqual(file_doc.is_private, 1)
        file_doc.handle_is_private_changed.assert_called_once_with()
        file_doc.save.assert_called_once_with(ignore_permissions=True)

    def test_fleet_attachment_migration_detaches_remote_urls(self):
        from sotrama.migrations.security import migrate_fleet_attachments_private

        file_doc = Mock(
            name="FILE-REMOTE",
            is_private=0,
            file_url="https://files.example.invalid/fleet.pdf",
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-001",
            attached_to_field="registration_document",
        )
        fleet_row = frappe._dict(name="FILE-REMOTE", content_hash=None)
        file_doc.get.side_effect = lambda field: field == "is_remote_file"
        with (
            patch(
                "sotrama.migrations.security.frappe.get_all",
                return_value=[fleet_row],
            ),
            patch("sotrama.migrations.security._ensure_fleet_file_privacy_field"),
            patch("sotrama.migrations.security.frappe.get_doc", return_value=file_doc),
            patch(
                "sotrama.migrations.security._redact_driver_attachment_comments"
            ) as redact,
            patch(
                "sotrama.migrations.security._clear_attached_file_field"
            ) as clear_field,
            patch("sotrama.migrations.security.frappe.log_error") as log_error,
        ):
            migrate_fleet_attachments_private()

        redact.assert_called_once_with("Vehicle", "VEH-001", file_doc)
        clear_field.assert_called_once_with(file_doc)
        self.assertIsNone(file_doc.attached_to_doctype)
        self.assertIsNone(file_doc.attached_to_name)
        self.assertIsNone(file_doc.attached_to_field)
        self.assertEqual(file_doc.owner, "Administrator")
        self.assertEqual(file_doc.is_private, 1)
        file_doc.save.assert_called_once_with(ignore_permissions=True)
        log_error.assert_called_once()

    def test_fleet_attachment_migration_detaches_unrelated_duplicate_file_rows(self):
        from sotrama.migrations.security import migrate_fleet_attachments_private

        fleet_row = frappe._dict(name="FILE-FLEET", content_hash="fleet-hash")
        duplicate_row = frappe._dict(
            name="FILE-DUPLICATE", attached_to_doctype="Communication"
        )
        fleet_file = Mock(
            name="FILE-FLEET", is_private=1, file_url="/private/files/fleet.pdf"
        )
        fleet_file.get.side_effect = lambda field, default=None: {
            "is_remote_file": False,
            "content_hash": "fleet-hash",
            "file_url": "/private/files/fleet.pdf",
        }.get(field, getattr(fleet_file, field, default))
        duplicate_file = Mock(
            name="FILE-DUPLICATE",
            is_private=1,
            file_url="/private/files/fleet.pdf",
            attached_to_doctype="Communication",
            attached_to_name="COMM-001",
            attached_to_field="attachment",
            owner="user@example.invalid",
        )
        duplicate_file.get.side_effect = lambda field, default=None: {
            "is_remote_file": False,
        }.get(field, getattr(duplicate_file, field, default))
        get_all_calls = []

        def get_all_side_effect(doctype, filters=None, fields=None, limit_page_length=0, **kwargs):
            get_all_calls.append(filters or {})
            if filters and isinstance(filters.get("attached_to_doctype"), list):
                return [fleet_row]
            if filters and filters.get("content_hash") == "fleet-hash":
                return [duplicate_row]
            return []

        with (
            patch(
                "sotrama.migrations.security.frappe.get_all",
                side_effect=get_all_side_effect,
            ),
            patch(
                "sotrama.migrations.security.frappe.get_meta",
                return_value=Mock(has_field=Mock(return_value=False)),
            ),
            # frappe.db.exists is exercised by the content-reuse check with
            # real SQL; mock it so the migration's security paths run against
            # the test doubles instead of the live database.
            patch(
                "sotrama.migrations.security.frappe.db.exists",
                return_value=False,
            ),
            patch("sotrama.migrations.security._ensure_fleet_file_privacy_field"),
            patch(
                "sotrama.migrations.security.frappe.get_doc",
                side_effect=[fleet_file, duplicate_file, fleet_file, duplicate_file],
            ) as get_doc,
            patch(
                "sotrama.migrations.security._redact_driver_attachment_comments"
            ) as redact,
            patch(
                "sotrama.migrations.security._clear_attached_file_field"
            ) as clear_field,
            patch(
                "sotrama.migrations.security._remove_private_driver_file_shares"
            ) as remove_shares,
            patch("sotrama.migrations.security.frappe.log_error") as log_error,
        ):
            migrate_fleet_attachments_private()
            migrate_fleet_attachments_private()

        # Capture state after the first migration run, then run again to
        # prove idempotency: a second execution must not change any state
        # or make additional side-effect calls.
        duplicate_state_after_run_1 = {
            "attached_to_doctype": duplicate_file.attached_to_doctype,
            "attached_to_name": duplicate_file.attached_to_name,
            "attached_to_field": duplicate_file.attached_to_field,
            "owner": duplicate_file.owner,
            "is_private": duplicate_file.is_private,
            "sotrama_private_fleet_attachment": duplicate_file.sotrama_private_fleet_attachment,
        }
        fleet_state_after_run_1 = {
            "is_private": fleet_file.is_private,
            "sotrama_private_fleet_attachment": fleet_file.sotrama_private_fleet_attachment,
        }
        redact_calls_after_run_1 = redact.call_count
        clear_field_calls_after_run_1 = clear_field.call_count
        remove_shares_calls_after_run_1 = remove_shares.call_count
        log_error_calls_after_run_1 = log_error.call_count
        duplicate_save_calls_after_run_1 = duplicate_file.save.call_count
        fleet_save_calls_after_run_1 = fleet_file.save.call_count

        # Second execution against the already-secured state.
        migrate_fleet_attachments_private()

        # Idempotency: state and side-effect call counts must be unchanged.
        self.assertEqual(
            duplicate_file.attached_to_doctype,
            duplicate_state_after_run_1["attached_to_doctype"],
        )
        self.assertEqual(
            duplicate_file.attached_to_name,
            duplicate_state_after_run_1["attached_to_name"],
        )
        self.assertEqual(
            duplicate_file.attached_to_field,
            duplicate_state_after_run_1["attached_to_field"],
        )
        self.assertEqual(duplicate_file.owner, duplicate_state_after_run_1["owner"])
        self.assertEqual(duplicate_file.is_private, duplicate_state_after_run_1["is_private"])
        self.assertEqual(
            duplicate_file.sotrama_private_fleet_attachment,
            duplicate_state_after_run_1["sotrama_private_fleet_attachment"],
        )
        self.assertEqual(fleet_file.is_private, fleet_state_after_run_1["is_private"])
        self.assertEqual(
            fleet_file.sotrama_private_fleet_attachment,
            fleet_state_after_run_1["sotrama_private_fleet_attachment"],
        )
        self.assertEqual(redact.call_count, redact_calls_after_run_1)
        self.assertEqual(clear_field.call_count, clear_field_calls_after_run_1)
        self.assertEqual(remove_shares.call_count, remove_shares_calls_after_run_1)
        self.assertEqual(log_error.call_count, log_error_calls_after_run_1)
        self.assertEqual(
            duplicate_file.save.call_count, duplicate_save_calls_after_run_1
        )
        self.assertEqual(fleet_file.save.call_count, fleet_save_calls_after_run_1)
        self.assertIsNone(frappe.flags.get("in_fleet_attachment_migration"))

        # Both migration runs enter the content-reuse check and the
        # duplicate sweep, so each run issues one hash query (4 total).
        attached_queries = [
            c
            for c in get_all_calls
            if isinstance(c.get("attached_to_doctype"), list)
        ]
        hash_queries = [
            c for c in get_all_calls if c.get("content_hash") == "fleet-hash"
        ]
        self.assertEqual(len(attached_queries), 2)  # once per migration run
        self.assertEqual(len(hash_queries), 4)  # 2 per migration run
        self.assertEqual(
            get_doc.call_args_list,
            [
                call("File", "FILE-FLEET"),
                call("File", "FILE-DUPLICATE"),
                call("File", "FILE-FLEET"),
                call("File", "FILE-DUPLICATE"),
            ],
        )
        redact.assert_called_once_with("Communication", "COMM-001", duplicate_file)
        clear_field.assert_called_once_with(duplicate_file)
        self.assertIsNone(duplicate_file.attached_to_doctype)
        self.assertIsNone(duplicate_file.attached_to_name)
        self.assertIsNone(duplicate_file.attached_to_field)
        self.assertEqual(duplicate_file.owner, "Administrator")
        self.assertEqual(duplicate_file.sotrama_private_fleet_attachment, 1)
        duplicate_file.save.assert_called_once_with(ignore_permissions=True)
        remove_shares.assert_called_once_with("FILE-DUPLICATE")
        log_error.assert_called_once()

    def test_initial_cleanup_patch_fails_closed_before_optional_company_nif(self):
        from sotrama.patches.v1_4.initial_data_cleanup import execute

        with (
            patch("sotrama.setup.masters.ensure_default_masters"),
            patch("sotrama.migrations.fleet_documents.migrate_fleet_document_options"),
            patch(
                "sotrama.migrations.fleet_reference_masters.simplify_fleet_reference_masters"
            ),
            patch(
                "sotrama.migrations.navigation.remove_legacy_algerian_localization_workspace"
            ),
            patch("sotrama.migrations.fleet_master_names.normalize_fleet_master_names"),
            patch("sotrama.permissions.remove_unsafe_fleet_docshares"),
            patch("sotrama.migrations.security.migrate_driver_private_attachments"),
            patch("sotrama.migrations.security.migrate_fleet_attachments_private"),
            patch(
                "sotrama.migrations.security.remediate_fleet_alert_todo_assignments",
                side_effect=frappe.ValidationError,
            ),
            patch(
                "sotrama.migrations.company.migrate_legacy_company_nif"
            ) as migrate_nif,
            self.assertRaises(frappe.ValidationError),
        ):
            execute()

        migrate_nif.assert_not_called()

    def test_initial_cleanup_patch_retries_when_vehicle_document_backfill_fails(self):
        from sotrama.patches.v1_4.initial_data_cleanup import execute

        with (
            patch("sotrama.setup.masters.ensure_default_masters"),
            patch("sotrama.migrations.fleet_documents.migrate_fleet_document_options"),
            patch(
                "sotrama.migrations.fleet_reference_masters.simplify_fleet_reference_masters"
            ),
            patch(
                "sotrama.migrations.navigation.remove_legacy_algerian_localization_workspace"
            ),
            patch("sotrama.migrations.fleet_master_names.normalize_fleet_master_names"),
            patch("sotrama.permissions.remove_unsafe_fleet_docshares"),
            patch("sotrama.migrations.security.migrate_driver_private_attachments"),
            patch("sotrama.migrations.security.migrate_fleet_attachments_private"),
            patch("sotrama.migrations.security.remediate_fleet_alert_todo_assignments"),
            patch(
                "sotrama.tp.doctype.vehicle_document.vehicle_document.refresh_vehicle_document_statuses",
                side_effect=RuntimeError("vehicle document backfill failed"),
            ),
            patch(
                "sotrama.migrations.company.migrate_legacy_company_nif"
            ) as migrate_nif,
            self.assertRaisesRegex(RuntimeError, "vehicle document backfill failed"),
        ):
            execute()

        migrate_nif.assert_not_called()

    def test_initial_cleanup_patch_does_not_mark_company_migration_failure_complete(
        self,
    ):
        from sotrama.patches.v1_4.initial_data_cleanup import execute

        with (
            patch("sotrama.setup.masters.ensure_default_masters"),
            patch("sotrama.migrations.fleet_documents.migrate_fleet_document_options"),
            patch(
                "sotrama.migrations.fleet_reference_masters.simplify_fleet_reference_masters"
            ),
            patch(
                "sotrama.migrations.navigation.remove_legacy_algerian_localization_workspace"
            ),
            patch("sotrama.migrations.fleet_master_names.normalize_fleet_master_names"),
            patch("sotrama.permissions.remove_unsafe_fleet_docshares"),
            patch("sotrama.migrations.security.migrate_driver_private_attachments"),
            patch("sotrama.migrations.security.migrate_fleet_attachments_private"),
            patch("sotrama.migrations.security.remediate_fleet_alert_todo_assignments"),
            patch(
                "sotrama.tp.doctype.vehicle_document.vehicle_document.refresh_vehicle_document_statuses"
            ),
            patch(
                "sotrama.migrations.company.migrate_legacy_company_nif",
                side_effect=RuntimeError("unexpected Company migration failure"),
            ),
            patch(
                "sotrama.migrations.company.hide_managed_legacy_company_nif"
            ) as hide_legacy_nif,
            self.assertRaisesRegex(
                RuntimeError, "unexpected Company migration failure"
            ),
        ):
            execute()

        hide_legacy_nif.assert_not_called()

    def test_legacy_company_nif_migration_preserves_conflicts_and_existing_tax_id(self):
        from sotrama.migrations.company import migrate_legacy_company_nif

        rows = [
            frappe._dict(name="SOTRAMA", custom_nif=" 123456789 ", tax_id=None),
            frappe._dict(name="OTHER", custom_nif="987654321", tax_id="111111111"),
            frappe._dict(name="MATCH", custom_nif="222222222", tax_id="222222222"),
        ]
        with (
            patch(
                "sotrama.migrations.company.frappe.db.table_exists", return_value=True
            ),
            patch(
                "sotrama.migrations.company.frappe.db.get_value",
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
            patch("sotrama.migrations.company.frappe.db.has_column", return_value=True),
            patch(
                "sotrama.migrations.company.frappe.db.sql", side_effect=[rows, None]
            ) as sql,
            patch("sotrama.migrations.company.frappe.db.set_value") as set_value,
            patch("sotrama.migrations.company.frappe.clear_cache") as clear_cache,
            patch("sotrama.migrations.company.frappe.log_error") as log_error,
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
        from sotrama.migrations.company import migrate_legacy_company_nif

        with (
            patch(
                "sotrama.migrations.company.frappe.db.table_exists", return_value=True
            ),
            patch(
                "sotrama.migrations.company.frappe.db.get_value",
                return_value=frappe._dict(
                    name="Company-custom_nif",
                    module="Custom",
                    is_system_generated=0,
                    description="User-created NIF field",
                    fieldtype="Data",
                ),
            ),
            patch("sotrama.migrations.company.frappe.db.has_column", return_value=True),
            patch("sotrama.migrations.company.frappe.db.sql") as sql,
            patch("sotrama.migrations.company.frappe.db.set_value") as set_value,
            patch("sotrama.migrations.company.frappe.log_error") as log_error,
        ):
            result = migrate_legacy_company_nif()

        self.assertEqual(result, {"copied": 0, "conflicts": 0, "skipped": 1})
        sql.assert_not_called()
        set_value.assert_not_called()
        log_error.assert_called_once()

    def test_legacy_company_nif_guarded_update_does_not_overwrite_concurrent_tax_id(
        self,
    ):
        from sotrama.migrations.company import migrate_legacy_company_nif

        rows = [frappe._dict(name="SOTRAMA", custom_nif="123456789", tax_id=None)]
        with (
            patch(
                "sotrama.migrations.company.frappe.db.table_exists", return_value=True
            ),
            patch(
                "sotrama.migrations.company.frappe.db.get_value",
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
            patch("sotrama.migrations.company.frappe.db.has_column", return_value=True),
            patch(
                "sotrama.migrations.company.frappe.db.sql", side_effect=[rows, None]
            ) as sql,
            patch("sotrama.migrations.company.frappe.db.set_value") as set_value,
            patch("sotrama.migrations.company.frappe.log_error") as log_error,
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
        from sotrama.migrations.company import migrate_legacy_company_nif

        rows = [frappe._dict(name="SOTRAMA", custom_nif="123456789", tax_id=None)]
        with (
            patch(
                "sotrama.migrations.company.frappe.db.table_exists", return_value=True
            ),
            patch(
                "sotrama.migrations.company.frappe.db.get_value",
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
            patch("sotrama.migrations.company.frappe.db.has_column", return_value=True),
            patch("sotrama.migrations.company.frappe.db.sql", side_effect=[rows, None]),
            patch("sotrama.migrations.company.frappe.log_error") as log_error,
        ):
            result = migrate_legacy_company_nif()

        self.assertEqual(result, {"copied": 0, "conflicts": 0, "skipped": 1})
        log_error.assert_not_called()

    def test_legacy_company_nif_is_hidden_only_after_conflict_free_owned_migration(
        self,
    ):
        from sotrama.migrations.company import hide_managed_legacy_company_nif

        with (
            patch(
                "sotrama.migrations.company.frappe.db.table_exists", return_value=True
            ),
            patch("sotrama.migrations.company.frappe.db.has_column", return_value=True),
            patch(
                "sotrama.migrations.company.frappe.db.get_value",
                return_value=frappe._dict(
                    name="Company-custom_nif",
                    module="Sotrama",
                    is_system_generated=1,
                    description="",
                    fieldtype="Data",
                    hidden=0,
                ),
            ),
            patch("sotrama.migrations.company.frappe.db.set_value") as set_value,
            patch("sotrama.migrations.company.frappe.clear_cache") as clear_cache,
        ):
            hidden = hide_managed_legacy_company_nif(
                {"copied": 1, "conflicts": 0, "skipped": 0}
            )

        self.assertTrue(hidden)
        set_value.assert_called_once_with(
            "Custom Field", "Company-custom_nif", "hidden", 1, update_modified=False
        )
        clear_cache.assert_called_once_with(doctype="Company")

        with patch("sotrama.migrations.company.frappe.db.set_value") as set_value:
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
        self.assertEqual(modules, {"Sotrama", "TP"})
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
            },
        )

    def test_before_install_repairs_only_unplaced_sotrama_modules(self):
        from sotrama.setup.install import repair_orphaned_module_definitions

        with (
            patch(
                "sotrama.setup.install.frappe.get_module_list", return_value=["Sotrama"]
            ),
            patch("sotrama.setup.install.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.setup.install.frappe.db.get_value",
                return_value=frappe._dict(app_name=None, custom=None),
            ),
            patch("sotrama.setup.install.frappe.db.delete") as delete,
        ):
            repair_orphaned_module_definitions()

        delete.assert_called_once_with("Module Def", {"name": "Sotrama"})

    def test_before_install_removes_existing_sotrama_module_for_installer_recreation(
        self,
    ):
        from sotrama.setup.install import repair_orphaned_module_definitions

        with (
            patch(
                "sotrama.setup.install.frappe.get_module_list", return_value=["Sotrama"]
            ),
            patch("sotrama.setup.install.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.setup.install.frappe.db.get_value",
                return_value=frappe._dict(app_name="sotrama", custom=0),
            ),
            patch("sotrama.setup.install.frappe.db.delete") as delete,
        ):
            repair_orphaned_module_definitions()

        delete.assert_called_once_with("Module Def", {"name": "Sotrama"})

    def test_legacy_localization_patch_deletes_only_standard_navigation(self):
        from sotrama.migrations.navigation import (
            remove_legacy_algerian_localization_workspace as execute,
        )

        workspace = Mock()
        with (
            patch("frappe.db.exists", return_value=True),
            patch(
                "frappe.db.get_value",
                side_effect=[
                    frappe._dict(module="Algerian Localization", standard=1),
                    frappe._dict(module="Algerian Localization", standard=1),
                    frappe._dict(app_name="sotrama", custom=0),
                ],
            ),
            patch("frappe.get_doc", return_value=workspace),
            patch(
                "frappe.get_all",
                side_effect=[["Algerian Localization Custom Sidebar"], []],
            ),
            patch("frappe.delete_doc") as delete_doc,
        ):
            execute()

        workspace.drop_sidebar_rows.assert_called_once_with()
        workspace.delete_desktop_icon.assert_called_once_with()
        self.assertEqual(
            [call.args[:2] for call in delete_doc.call_args_list],
            [
                ("Custom Workspace", "Algerian Localization"),
                ("Workspace", "Algerian Localization"),
                ("Sidebar", "Algerian Localization"),
                ("Custom Sidebar", "Algerian Localization Custom Sidebar"),
                ("Module Def", "Algerian Localization"),
            ],
        )
        self.assertTrue(delete_doc.call_args_list[1].kwargs["ignore_on_trash"])

        with (
            patch("frappe.db.exists", return_value=True),
            patch(
                "frappe.db.get_value",
                side_effect=[
                    frappe._dict(module="Algerian Localization", standard=0),
                    frappe._dict(module="Another Module", standard=1),
                    frappe._dict(app_name="erpnext", custom=0),
                ],
            ),
            patch("frappe.get_all", return_value=[]),
            patch("frappe.delete_doc") as delete_doc,
        ):
            execute()

        delete_doc.assert_not_called()

    def test_before_install_removes_sotrama_module_with_null_custom_flag_for_recreation(
        self,
    ):
        from sotrama.setup.install import repair_orphaned_module_definitions

        with (
            patch(
                "sotrama.setup.install.frappe.get_module_list", return_value=["Sotrama"]
            ),
            patch("sotrama.setup.install.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.setup.install.frappe.db.get_value",
                return_value=frappe._dict(app_name="sotrama", custom=None),
            ),
            patch("sotrama.setup.install.frappe.db.delete") as delete,
        ):
            repair_orphaned_module_definitions()

        delete.assert_called_once_with("Module Def", {"name": "Sotrama"})

    def test_before_install_does_not_claim_another_apps_module(self):
        from sotrama.setup.install import repair_orphaned_module_definitions

        with (
            patch(
                "sotrama.setup.install.frappe.get_module_list", return_value=["Sotrama"]
            ),
            patch("sotrama.setup.install.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.setup.install.frappe.db.get_value",
                return_value=frappe._dict(app_name="erpnext", custom=0),
            ),
            patch("sotrama.setup.install.frappe.db.delete") as delete,
            self.assertRaises(frappe.ValidationError),
        ):
            repair_orphaned_module_definitions()

        delete.assert_not_called()

    def test_before_install_leaves_custom_module_definitions_for_frappe(self):
        from sotrama.setup.install import repair_orphaned_module_definitions

        with (
            patch(
                "sotrama.setup.install.frappe.get_module_list", return_value=["Sotrama"]
            ),
            patch("sotrama.setup.install.frappe.db.table_exists", return_value=True),
            patch(
                "sotrama.setup.install.frappe.db.get_value",
                return_value=frappe._dict(app_name=None, custom=1),
            ),
            patch("sotrama.setup.install.frappe.db.delete") as delete,
        ):
            repair_orphaned_module_definitions()

        delete.assert_not_called()

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

        existing = frappe.get_doc(
            {"doctype": "Designation", "designation_name": "GERANT"}
        ).insert(ignore_permissions=True)
        try:
            with patch("sotrama.setup.masters.PUBLIC_WORKS_DESIGNATIONS", ("Gérant",)):
                self.assertEqual(ensure_public_works_designations(), [])
        finally:
            frappe.delete_doc("Designation", existing.name, ignore_permissions=True)

    def test_fleet_dock_sidebar_and_workspace_are_installed(self):
        self.assertTrue(frappe.db.exists("Dock", {"app": "sotrama", "standard": 1}))
        self.assertTrue(frappe.db.exists("Sidebar", "TP"))
        self.assertTrue(frappe.db.exists("Workspace", "Sotrama Fleet"))
        self.assertFalse(frappe.db.exists("Module Def", "Algerian Localization"))
        self.assertFalse(frappe.db.exists("Sidebar", "Algerian Localization"))
        self.assertFalse(frappe.db.exists("Workspace", "Algerian Localization"))
        self.assertFalse(frappe.db.exists("Custom Workspace", "Algerian Localization"))
        self.assertTrue(frappe.db.exists("Workspace", "Sotrama"))
        app_workspace = frappe.get_doc("Workspace", "Sotrama")
        self.assertEqual(
            {item.link_to for item in app_workspace.links if item.type == "Link"},
            {"Company", "Designation", "Sotrama Settings", "TP Settings"},
            (
                "The central workspace links only to standard DocTypes; "
                "permissions remain on each target."
            ),
        )
        self.assertTrue(
            all(
                item.link_type in {"DocType", "Page", "Report"}
                for item in app_workspace.links
                if item.type == "Link"
            )
        )
        app_blocks = json.loads(app_workspace.content or "[]")
        self.assertEqual(
            {
                block.get("data", {}).get("card_name")
                for block in app_blocks
                if block.get("type") == "card"
            },
            {"Company & HR Setup", "Fleet Configuration"},
        )
        self.assertTrue(
            all(
                row.description
                for row in app_workspace.links
                if row.type == "Card Break"
            )
        )
        workspace = frappe.get_doc("Workspace", "Sotrama Fleet")
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
        fleet_card_names = {
            block.get("data", {}).get("card_name")
            for block in blocks
            if block.get("type") == "card"
        }
        self.assertEqual(
            fleet_card_names,
            {
                "Fleet Operations",
                "Maintenance & Safety",
                "Reports & Analysis",
                "Setup & Masters",
            },
        )
        self.assertTrue(all(block.get("id") for block in blocks))
        for card_name in card_names:
            self.assertTrue(
                frappe.db.exists("Number Card", card_name),
                f"Missing Number Card: {card_name}",
            )

        sidebar = frappe.get_doc("Sidebar", "TP")
        self.assertFalse(any(item.link_to == "TP Settings" for item in sidebar.items))
        self.assertTrue(
            any(
                item.link_type == "Workspace"
                and item.link_to == "Fleet Management Reports"
                for item in sidebar.items
            )
        )
        reports_workspace = frappe.get_doc("Workspace", "Fleet Management Reports")
        reports_blocks = json.loads(reports_workspace.content or "[]")
        self.assertEqual(
            {
                block.get("data", {}).get("card_name")
                for block in reports_blocks
                if block.get("type") == "card"
            },
            {"Fleet Analysis"},
        )
        self.assertTrue(
            any(
                row.type == "Card Break" and row.description
                for row in reports_workspace.links
            )
        )
        self.assertFalse(any(item.link_to == "TP Settings" for item in workspace.links))
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
            },
        )

    def test_sotrama_settings_keep_company_toggle_and_explicit_btph_import_action(self):
        meta = frappe.get_meta("Sotrama Settings", cached=False)
        self.assertIsNone(meta.get_field("add_public_works_designations"))
        catalogue = meta.get_field("section_public_works_designations")
        self.assertIn("202-title", catalogue.description)
        self.assertIn("Only missing", catalogue.description)
        self.assertFalse(
            any(permission.permlevel == 1 for permission in meta.permissions)
        )

        company_field = meta.get_field("enable_algerian_company_fields")
        self.assertEqual(company_field.permlevel, 0)
        self.assertEqual(company_field.label, "Enable Algerian registration fields")
        self.assertIn("NIF", company_field.description)

        doctype_js = frappe.get_hooks("doctype_js", app_name="sotrama")
        self.assertIn("Sotrama Settings", doctype_js)
        self.assertTrue(
            (_sotrama_package_path() / "public/js/sotrama_settings.js").is_file()
        )

    def test_explicit_btph_job_title_action_requires_role_and_designation_create_permission(
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
                "sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.frappe.has_permission",
                return_value=True,
            ) as has_permission,
            patch(
                "sotrama.setup.ensure_public_works_designations",
                return_value=["TITLE-001"],
            ) as seed,
        ):
            result = create_missing_public_works_designations()

        self.assertEqual(result["created_count"], 1)
        self.assertEqual(result["created"], ["TITLE-001"])
        only_for.assert_called_once_with(["System Manager", "HR Manager"])
        has_permission.assert_called_once_with("Designation", "create", throw=True)
        seed.assert_called_once_with()

        with (
            patch(
                "sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.frappe.only_for"
            ),
            patch(
                "sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.frappe.has_permission",
                side_effect=frappe.PermissionError,
            ),
            patch("sotrama.setup.ensure_public_works_designations") as seed,
            self.assertRaises(frappe.PermissionError),
        ):
            create_missing_public_works_designations()
        seed.assert_not_called()

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
        company_defaults_meta = frappe.get_meta("TP Company Defaults", cached=False)
        self.assertIsNotNone(company_defaults_meta.get_field("company_classification"))
        self.assertIsNone(
            company_defaults_meta.get_field("default_company_classification")
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

    def test_hidden_legacy_company_classification_defaults_do_not_block_settings(self):
        from sotrama.tp.doctype.tp_settings.tp_settings import TPSettings

        settings = frappe.new_doc("TP Settings")
        settings.default_company_classification = "LEGACY-EXPIRED-CLASSIFICATION"
        with (
            patch.object(settings, "_validate_company_defaults_permissions"),
            patch.object(settings, "_validate_company_defaults"),
        ):
            settings.validate()

        row = frappe._dict(
            company="COMPANY-A",
            active=1,
            company_classification="LEGACY-EXPIRED-CLASSIFICATION",
            idx=1,
        )
        TPSettings._validate_company_defaults(frappe._dict(company_defaults=[row]))

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

    def test_fleet_doctypes_have_distinct_icons(self):
        doctypes = frappe.get_all(
            "DocType",
            filters={"module": "TP", "istable": 0},
            fields=["name", "icon"],
        )
        icons = {doctype.name: doctype.icon for doctype in doctypes}
        self.assertTrue(all(icons.values()), icons)
        self.assertEqual(len(set(icons.values())), len(icons), icons)


class TestSotramaCustomFields(unittest.TestCase):
    """Verify optional Company fields are opt-in and never overwrite site fields."""

    def test_company_fields_are_opt_in_and_reuse_erpnext_tax_id(self):
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama.setup import company as hooks

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
        from sotrama import permissions
        from sotrama.setup import uninstall as hooks

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
            patch.object(
                permissions, "preserve_fleet_file_privacy_on_uninstall"
            ) as preserve_fleet_files,
        ):
            hooks.preserve_company_fields_on_uninstall()

        self.assertEqual(
            get_all.call_args.kwargs["filters"],
            {
                "dt": "Company",
                "fieldname": [
                    "in",
                    [
                        field["fieldname"]
                        for field in hooks.get_custom_fields()["Company"]
                    ]
                    + ["custom_nif", "custom_algerian_registration_section"],
                ],
            },
        )
        self.assertEqual(set_value.call_count, 5)
        table_exists.assert_called_once_with("Custom Field")
        for call_item in set_value.call_args_list:
            self.assertEqual(call_item.args[0], "Custom Field")
            name = call_item.args[1]
            values = call_item.args[2]
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
        preserve_fleet_files.assert_called_once_with()

    def test_uninstall_detaches_fleet_files_and_preserves_private_storage(self):
        from sotrama.permissions import preserve_fleet_file_privacy_on_uninstall

        file_doc = frappe._dict(
            name="FILE-FLEET-UNINSTALL",
            attached_to_doctype="Vehicle",
            attached_to_name="VEH-001",
            attached_to_field="documents",
            owner="fleet@example.invalid",
            is_private=1,
            file_url="/private/files/fleet.pdf",
            sotrama_private_fleet_attachment=1,
            flags=frappe._dict(),
            save=Mock(),
        )
        original_flag = frappe.flags.get("in_fleet_attachment_migration")
        with (
            patch(
                "sotrama.migrations.security.migrate_fleet_attachments_private"
            ) as migrate,
            patch(
                "sotrama.permissions.frappe.get_all",
                return_value=[frappe._dict(name=file_doc.name)],
            ) as get_all,
            patch("sotrama.permissions.frappe.get_doc", return_value=file_doc),
            patch("sotrama.permissions._redact_driver_attachment_comments") as redact,
            patch("sotrama.permissions._clear_attached_file_field") as clear_field,
            patch(
                "sotrama.permissions._remove_private_driver_file_shares"
            ) as remove_shares,
        ):
            preserve_fleet_file_privacy_on_uninstall()

        migrate.assert_called_once_with()
        get_all.assert_called_once_with(
            "File",
            filters={"sotrama_private_fleet_attachment": 1},
            fields=["name"],
            limit_page_length=0,
        )
        redact.assert_called_once()
        clear_field.assert_called_once_with(file_doc)
        remove_shares.assert_called_once_with(file_doc.name)
        self.assertIsNone(file_doc.attached_to_doctype)
        self.assertIsNone(file_doc.attached_to_name)
        self.assertIsNone(file_doc.attached_to_field)
        self.assertEqual(file_doc.owner, "Administrator")
        self.assertEqual(file_doc.is_private, 1)
        self.assertEqual(file_doc.sotrama_private_fleet_attachment, 1)
        file_doc.save.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(
            frappe.flags.get("in_fleet_attachment_migration"), original_flag
        )
