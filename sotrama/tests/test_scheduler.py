# Frappe integration tests for Sotrama scheduler behavior.

import unittest
from unittest.mock import Mock, patch
from unittest.mock import call as mock_call

import frappe
from frappe.utils import add_days, today


class TestFleetSchedulerPrivacy(unittest.TestCase):
    """Scheduler alerts must respect document access and field privacy."""

    def test_vehicle_document_status_uses_the_configured_expiry_window(self):
        from sotrama.tp.doctype.vehicle_document.vehicle_document import (
            get_vehicle_document_status,
        )

        reference_date = today()
        self.assertEqual(
            get_vehicle_document_status(None, 30, reference_date), "Pending"
        )
        self.assertEqual(
            get_vehicle_document_status(
                add_days(reference_date, -1), 30, reference_date
            ),
            "Expired",
        )
        self.assertEqual(
            get_vehicle_document_status(reference_date, 30, reference_date),
            "Expiring Soon",
        )
        self.assertEqual(
            get_vehicle_document_status(
                add_days(reference_date, 30), 30, reference_date
            ),
            "Expiring Soon",
        )
        self.assertEqual(
            get_vehicle_document_status(
                add_days(reference_date, 31), 30, reference_date
            ),
            "Valid",
        )

    def test_vehicle_document_status_backfill_updates_only_changed_rows(self):
        from sotrama.tp.doctype.vehicle_document.vehicle_document import (
            refresh_vehicle_document_statuses,
        )

        documents = [
            frappe._dict(
                name="ROW-STATUS-CHANGED",
                expiry_date=add_days(today(), 5),
                status="Valid",
            ),
            frappe._dict(
                name="ROW-STATUS-UNCHANGED",
                expiry_date=add_days(today(), 365),
                status="Valid",
            ),
        ]
        with (
            patch("frappe.db.table_exists", return_value=True),
            patch("frappe.get_all", return_value=documents),
            patch("sotrama.tp.settings.get_tp_setting", return_value=30),
            patch("frappe.db.set_value") as set_value,
        ):
            changed = refresh_vehicle_document_statuses()

        self.assertEqual(changed, 1)
        set_value.assert_called_once_with(
            "Vehicle Document",
            "ROW-STATUS-CHANGED",
            "status",
            "Expiring Soon",
            update_modified=False,
        )

    def test_document_expiry_scheduler_batches_documents_for_submitted_vehicles(self):
        from sotrama.tp.scheduler import check_document_expiries

        vehicle = frappe._dict(
            name="VEH-EXPIRY-001",
            license_plate="EXPIRY-001",
            vehicle_status="Active",
        )
        document = frappe._dict(
            name="ROW-EXPIRY-001",
            parent=vehicle.name,
            document_type="Insurance Certificate",
            expiry_date=add_days(today(), 5),
            status="Valid",
        )
        todo = Mock(name="TODO-EXPIRY-001")
        todo.name = "TODO-EXPIRY-001"
        with (
            patch("sotrama.tp.scheduler.documents.get_tp_setting", return_value=30),
            patch(
                "frappe.get_all",
                side_effect=[[vehicle], [document], []],
            ) as get_all,
            patch(
                "sotrama.tp.scheduler.documents._user_for_role",
                return_value="fleet@example.invalid",
            ),
            patch("frappe.db.get_value", return_value="en"),
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc", return_value=todo),
        ):
            check_document_expiries()

        fleet_reads = [
            call
            for call in get_all.call_args_list
            if call.args and call.args[0] in {"Vehicle", "Vehicle Document", "ToDo"}
        ]
        self.assertEqual(len(fleet_reads), 3)
        self.assertEqual(get_all.call_args_list[0].args[0], "Vehicle")
        self.assertEqual(get_all.call_args_list[0].kwargs["filters"]["docstatus"], 1)
        self.assertEqual(get_all.call_args_list[1].args[0], "Vehicle Document")
        self.assertIn("name", get_all.call_args_list[1].kwargs["fields"])
        self.assertEqual(
            get_all.call_args_list[1].kwargs["filters"]["parent"],
            ["in", [vehicle.name]],
        )
        self.assertEqual(
            get_all.call_args_list[1].kwargs["filters"]["parentfield"],
            "vehicle_documents",
        )
        self.assertEqual(get_all.call_args_list[2].args[0], "ToDo")
        self.assertEqual(
            get_all.call_args_list[2].kwargs["filters"]["reference_name"],
            ["in", [vehicle.name]],
        )
        self.assertIn("Vehicle Document Expiring", todo.description)
        self.assertIn("Insurance Certificate", todo.description)
        self.assertIn("Vehicle Document Row: ROW-EXPIRY-001", todo.description)
        self.assertEqual(todo.priority, "Medium")
        self.assertEqual(document.status, "Expiring Soon")
        set_value.assert_any_call(
            "Vehicle Document",
            "ROW-EXPIRY-001",
            "status",
            "Expiring Soon",
            update_modified=False,
        )
        todo.insert.assert_called_once_with(ignore_permissions=True)

    def test_document_expiry_scheduler_keeps_same_type_renewals_separate(self):
        from sotrama.tp.scheduler import check_document_expiries

        vehicle = frappe._dict(
            name="VEH-EXPIRY-RENEWALS",
            license_plate="RENEWALS-001",
            vehicle_status="Active",
        )
        documents = [
            frappe._dict(
                name="ROW-INSURANCE-OLD",
                parent=vehicle.name,
                document_type="Insurance Certificate",
                expiry_date=add_days(today(), 5),
                status="Valid",
            ),
            frappe._dict(
                name="ROW-INSURANCE-RENEWAL",
                parent=vehicle.name,
                document_type="Insurance Certificate",
                expiry_date=add_days(today(), 365),
                status="Valid",
            ),
        ]
        todos = []
        for name in ("TODO-INSURANCE-OLD", "TODO-INSURANCE-RENEWAL"):
            todo = Mock()
            todo.name = name
            todo.status = "Open"
            todos.append(todo)

        todo_read_count = {"count": 0}

        def get_all(doctype, **kwargs):
            if doctype == "Vehicle":
                return [vehicle]
            if doctype == "Vehicle Document":
                return documents
            if doctype == "ToDo":
                todo_read_count["count"] += 1
                if todo_read_count["count"] == 1:
                    return []
                return [
                    frappe._dict(
                        name=todo.name,
                        reference_name=vehicle.name,
                        description=todo.description,
                        status=todo.status,
                    )
                    for todo in todos
                ]
            self.fail(f"Unexpected scheduler query: {doctype}")

        with (
            patch("sotrama.tp.scheduler.documents.get_tp_setting", return_value=400),
            patch(
                "frappe.get_all",
                side_effect=get_all,
            ),
            patch(
                "sotrama.tp.scheduler.documents._user_for_role",
                return_value="fleet@example.invalid",
            ),
            patch("frappe.db.get_value", return_value="en"),
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc", side_effect=todos) as new_doc,
        ):
            check_document_expiries()
            check_document_expiries()

        self.assertEqual(new_doc.call_count, 2)
        self.assertEqual(set_value.call_count, 4)
        descriptions = [todo.description for todo in todos]
        self.assertIn("Vehicle Document Row: ROW-INSURANCE-OLD", descriptions[0])
        self.assertIn("Vehicle Document Row: ROW-INSURANCE-RENEWAL", descriptions[1])
        self.assertNotEqual(descriptions[0], descriptions[1])

    def test_document_expiry_scheduler_closes_alert_after_document_renewal(self):
        from sotrama.tp.scheduler import check_document_expiries

        vehicle = frappe._dict(
            name="VEH-EXPIRY-RENEWED",
            license_plate="RENEWED-001",
            vehicle_status="Active",
        )
        renewed_expiry = add_days(today(), 365)
        document = frappe._dict(
            name="ROW-INSURANCE-RENEWED",
            parent=vehicle.name,
            document_type="Insurance Certificate",
            expiry_date=renewed_expiry,
            status="Expiring Soon",
        )
        old_todo = frappe._dict(
            name="TODO-INSURANCE-RENEWED",
            reference_name=vehicle.name,
            description=(
                "Vehicle Document Expiring: Insurance Certificate\n"
                "Document expires on the old date\n"
                f"Vehicle Document Row: {document.name} | Expiry: {add_days(today(), 5)}"
            ),
            status="Open",
        )
        legacy_french_todo = frappe._dict(
            name="TODO-INSURANCE-LEGACY-FR",
            reference_name=vehicle.name,
            description=(
                "Expiration d'un document du véhicule : Assurance "
                f"(véhicule : {vehicle.license_plate})\n"
                f"Ancienne échéance : {add_days(today(), 5)}"
            ),
            status="Open",
        )
        unrelated_todo = frappe._dict(
            name="TODO-MAINTENANCE-UNRELATED",
            reference_name=vehicle.name,
            description="Maintenance due for this vehicle",
            status="Open",
        )
        with (
            patch("sotrama.tp.scheduler.documents.get_tp_setting", return_value=30),
            patch(
                "frappe.get_all",
                side_effect=[
                    [vehicle],
                    [document],
                    [old_todo, legacy_french_todo, unrelated_todo],
                ],
            ),
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc") as new_doc,
        ):
            check_document_expiries()

        self.assertEqual(document.status, "Valid")
        set_value.assert_any_call(
            "Vehicle Document",
            document.name,
            "status",
            "Valid",
            update_modified=False,
        )
        set_value.assert_any_call(
            "ToDo",
            old_todo.name,
            "status",
            "Closed",
            update_modified=False,
        )
        set_value.assert_any_call(
            "ToDo",
            legacy_french_todo.name,
            "status",
            "Closed",
            update_modified=False,
        )
        self.assertNotIn(
            mock_call(
                "ToDo",
                unrelated_todo.name,
                "status",
                "Closed",
                update_modified=False,
            ),
            set_value.call_args_list,
        )
        new_doc.assert_not_called()

    def test_document_expiry_scheduler_does_not_reopen_closed_or_cancelled_alerts(self):
        from sotrama.tp.scheduler import check_document_expiries

        vehicle = frappe._dict(
            name="VEH-EXPIRY-DISMISSED",
            license_plate="DISMISSED-001",
            vehicle_status="Active",
        )
        documents = [
            frappe._dict(
                name="ROW-EXPIRY-CLOSED",
                parent=vehicle.name,
                document_type="Insurance Certificate",
                expiry_date=add_days(today(), 5),
                status="Valid",
            ),
            frappe._dict(
                name="ROW-EXPIRY-CANCELLED",
                parent=vehicle.name,
                document_type="Technical Inspection",
                expiry_date=add_days(today(), 5),
                status="Valid",
            ),
        ]
        todos = [
            frappe._dict(
                name="TODO-EXPIRY-CLOSED",
                reference_name=vehicle.name,
                description=(
                    f"Vehicle Document Row: {documents[0].name} | Expiry: {documents[0].expiry_date}"
                ),
                status="Closed",
            ),
            frappe._dict(
                name="TODO-EXPIRY-CANCELLED",
                reference_name=vehicle.name,
                description=(
                    f"Vehicle Document Row: {documents[1].name} | Expiry: {documents[1].expiry_date}"
                ),
                status="Cancelled",
            ),
        ]
        with (
            patch("sotrama.tp.scheduler.documents.get_tp_setting", return_value=30),
            patch(
                "frappe.get_all",
                side_effect=[[vehicle], documents, todos],
            ),
            patch(
                "sotrama.tp.scheduler.documents._user_for_role",
                return_value="fleet@example.invalid",
            ),
            patch("frappe.db.get_value", return_value="en"),
            patch("frappe.db.set_value"),
            patch("frappe.new_doc") as new_doc,
        ):
            check_document_expiries()

        new_doc.assert_not_called()

    def test_role_assignment_requires_read_permission_for_the_exact_document(self):
        from sotrama.tp.scheduler import _user_for_role

        with (
            patch(
                "frappe.get_all",
                side_effect=[
                    ["fleet-a@example.invalid", "fleet-b@example.invalid"],
                    ["fleet-a@example.invalid", "fleet-b@example.invalid"],
                ],
            ) as get_all,
            patch("frappe.db.exists", return_value=True),
            patch(
                "frappe.has_permission",
                side_effect=[False, True],
            ) as has_permission,
        ):
            assigned = _user_for_role("Fleet Manager", "Vehicle", "VEHICLE-B")

        self.assertEqual(assigned, "fleet-b@example.invalid")
        self.assertEqual(has_permission.call_count, 2)
        self.assertEqual(has_permission.call_args_list[0].kwargs["doc"], "VEHICLE-B")
        self.assertEqual(get_all.call_count, 2)

    def test_role_assignment_reuses_enabled_role_users_within_one_scheduler_run(self):
        from sotrama.tp.scheduler import _user_for_role

        role_users_cache = {}
        with (
            patch(
                "frappe.get_all",
                side_effect=[["fleet@example.invalid"], ["fleet@example.invalid"]],
            ) as get_all,
            patch("frappe.db.exists") as exists,
            patch("frappe.has_permission", return_value=True) as has_permission,
        ):
            first = _user_for_role(
                "Fleet Manager",
                "Vehicle",
                "VEH-001",
                role_users_cache=role_users_cache,
                known_existing=True,
            )
            second = _user_for_role(
                "Fleet Manager",
                "Vehicle",
                "VEH-002",
                role_users_cache=role_users_cache,
                known_existing=True,
            )

        self.assertEqual(first, "fleet@example.invalid")
        self.assertEqual(second, "fleet@example.invalid")
        self.assertEqual(
            get_all.call_count,
            2,
            "Role membership and enabled users should be fetched once per role",
        )
        self.assertEqual(
            has_permission.call_count,
            2,
            "Read permission must still be checked for every exact document",
        )
        exists.assert_not_called()

    def test_role_assignment_falls_back_if_a_batched_document_was_deleted(self):
        from sotrama.tp.scheduler import _user_for_role

        with (
            patch(
                "frappe.get_all",
                side_effect=[["fleet@example.invalid"], ["fleet@example.invalid"]],
            ),
            patch(
                "frappe.has_permission",
                side_effect=frappe.DoesNotExistError,
            ),
        ):
            assigned = _user_for_role(
                "Fleet Manager", "Vehicle", "VEH-DELETED", known_existing=True
            )

        self.assertEqual(assigned, "Administrator")

    def test_maintenance_due_scheduler_batches_vehicle_odometer_and_open_todos(self):
        from sotrama.tp.scheduler import check_maintenance_due

        schedules = [
            frappe._dict(
                name="SCH-DATE",
                vehicle="VEH-DATE",
                next_due_date=add_days(today(), 2),
                next_due_odometer=500,
                job_type="Oil Change",
            ),
            frappe._dict(
                name="SCH-ODO",
                vehicle="VEH-ODO",
                next_due_date=None,
                next_due_odometer=1000,
                job_type="Inspection",
            ),
        ]
        vehicles = [
            frappe._dict(
                name="VEH-DATE",
                current_odometer=450,
                docstatus=1,
                vehicle_status="Active",
            ),
            frappe._dict(
                name="VEH-ODO",
                current_odometer=1200,
                docstatus=1,
                vehicle_status="Active",
            ),
        ]
        existing_todo = frappe._dict(
            name="TODO-DATE",
            reference_name="SCH-DATE",
            description="Maintenance Due: Oil Change (Vehicle: VEH-DATE)",
            status="Open",
        )
        created_todo = Mock(name="TODO-ODO")
        created_todo.name = "TODO-ODO"
        with (
            patch("sotrama.tp.scheduler.maintenance.get_tp_setting", return_value=14),
            patch(
                "frappe.get_all",
                side_effect=[schedules, vehicles, [existing_todo]],
            ) as get_all,
            patch(
                "sotrama.tp.scheduler.maintenance._user_for_role",
                return_value="fleet@example.invalid",
            ),
            patch("frappe.db.get_value") as get_value,
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc", return_value=created_todo),
        ):
            check_maintenance_due()

        self.assertEqual(get_all.call_count, 3)
        self.assertEqual(get_all.call_args_list[1].args[0], "Vehicle")
        self.assertEqual(get_all.call_args_list[2].args[0], "ToDo")
        self.assertEqual(
            get_all.call_args_list[2].kwargs["filters"],
            {"reference_type": "Maintenance Schedule"},
        )
        self.assertTrue(get_all.call_args_list[2].kwargs["or_filters"])
        get_value.assert_not_called()
        set_value.assert_called_once()
        self.assertEqual(set_value.call_args.args[:2], ("ToDo", "TODO-DATE"))
        self.assertIn(
            str(schedules[0].next_due_date), set_value.call_args.args[2]["description"]
        )
        self.assertIn("1200", created_todo.description)
        self.assertIn("1000", created_todo.description)
        created_todo.insert.assert_called_once_with(ignore_permissions=True)

    def test_maintenance_due_scheduler_closes_obsolete_and_cancelled_vehicle_alerts(
        self,
    ):
        from sotrama.tp.scheduler import check_maintenance_due

        schedules = [
            frappe._dict(
                name="SCH-NOT-DUE",
                vehicle="VEH-ACTIVE",
                next_due_date=add_days(today(), 90),
                next_due_odometer=5000,
                job_type="Oil Change",
            ),
            frappe._dict(
                name="SCH-CANCELLED-VEHICLE",
                vehicle="VEH-CANCELLED",
                next_due_date=add_days(today(), 1),
                next_due_odometer=None,
                job_type="Inspection",
            ),
        ]
        vehicles = [
            frappe._dict(
                name="VEH-ACTIVE",
                current_odometer=1000,
                docstatus=1,
                vehicle_status="Active",
            ),
            frappe._dict(
                name="VEH-CANCELLED",
                current_odometer=1000,
                docstatus=2,
                vehicle_status="Out of Service",
            ),
        ]
        todos = [
            frappe._dict(
                name="TODO-NOT-DUE",
                reference_name="SCH-NOT-DUE",
                description="Maintenance Due: Oil Change (Vehicle: VEH-ACTIVE)",
                status="Open",
            ),
            frappe._dict(
                name="TODO-CANCELLED-VEHICLE",
                reference_name="SCH-CANCELLED-VEHICLE",
                description="Maintenance Due: Inspection (Vehicle: VEH-CANCELLED)",
                status="Open",
            ),
            frappe._dict(
                name="TODO-PAUSED-SCHEDULE",
                reference_name="SCH-PAUSED",
                description="Maintenance à effectuer : Inspection (véhicule : VEH-PAUSED)",
                status="Open",
            ),
        ]

        with (
            patch("sotrama.tp.scheduler.maintenance.get_tp_setting", return_value=14),
            patch(
                "frappe.get_all",
                side_effect=[schedules, vehicles, todos],
            ),
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc") as new_doc,
        ):
            check_maintenance_due()

        for todo in todos:
            set_value.assert_any_call(
                "ToDo", todo.name, "status", "Closed", update_modified=False
            )
        new_doc.assert_not_called()

    def test_maintenance_due_scheduler_respects_manual_close_per_schedule_cycle(self):
        from sotrama.tp.scheduler import (
            _maintenance_alert_signature,
            check_maintenance_due,
        )

        same_cycle = frappe._dict(
            name="SCH-MANUALLY-CLOSED",
            vehicle="VEH-CLOSED",
            next_due_date=add_days(today(), 2),
            next_due_odometer=1000,
            job_type="Oil Change",
        )
        new_cycle = frappe._dict(
            name="SCH-RESCHEDULED",
            vehicle="VEH-RESCHEDULED",
            next_due_date=add_days(today(), 3),
            next_due_odometer=2000,
            job_type="Inspection",
        )
        previous_cycle = frappe._dict(
            name=new_cycle.name,
            next_due_date=add_days(today(), 90),
            next_due_odometer=new_cycle.next_due_odometer,
        )
        vehicles = [
            frappe._dict(
                name="VEH-CLOSED",
                current_odometer=500,
                docstatus=1,
                vehicle_status="Active",
            ),
            frappe._dict(
                name="VEH-RESCHEDULED",
                current_odometer=1500,
                docstatus=1,
                vehicle_status="Active",
            ),
        ]
        todos = [
            frappe._dict(
                name="TODO-CLOSED-SAME-CYCLE",
                reference_name=same_cycle.name,
                description=f"Maintenance Due: Oil Change\n{_maintenance_alert_signature(same_cycle)}",
                status="Closed",
            ),
            frappe._dict(
                name="TODO-OPEN-DUPLICATE-SAME-CYCLE",
                reference_name=same_cycle.name,
                description=f"Maintenance Due: Oil Change\n{_maintenance_alert_signature(same_cycle)}",
                status="Open",
            ),
            frappe._dict(
                name="TODO-CLOSED-OLD-CYCLE",
                reference_name=new_cycle.name,
                description=f"Maintenance Due: Inspection\n{_maintenance_alert_signature(previous_cycle)}",
                status="Closed",
            ),
        ]
        created_todo = Mock()
        created_todo.name = "TODO-NEW-CYCLE"

        with (
            patch("sotrama.tp.scheduler.maintenance.get_tp_setting", return_value=14),
            patch(
                "frappe.get_all",
                side_effect=[[same_cycle, new_cycle], vehicles, todos],
            ),
            patch(
                "sotrama.tp.scheduler.maintenance._user_for_role",
                return_value="fleet@example.invalid",
            ),
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc", return_value=created_todo) as new_doc,
        ):
            check_maintenance_due()

        new_doc.assert_called_once_with("ToDo")
        created_todo.insert.assert_called_once_with(ignore_permissions=True)
        self.assertIn(_maintenance_alert_signature(new_cycle), created_todo.description)
        set_value.assert_called_once_with(
            "ToDo",
            "TODO-OPEN-DUPLICATE-SAME-CYCLE",
            "status",
            "Closed",
            update_modified=False,
        )

    def test_legacy_driver_alerts_are_sanitized_and_routed_to_the_right_role(self):
        from sotrama.migrations.security import remediate_fleet_alert_todo_assignments

        todos = [
            frappe._dict(
                name="TODO-LICENSE",
                reference_type="Driver",
                reference_name="DRV-TEST-001",
                allocated_to="fleet@example.invalid",
                description="Driver Test Driver license expires on tomorrow; SECRET-LICENSE-NUMBER",
            ),
            frappe._dict(
                name="TODO-SAFETY",
                reference_type="Driver",
                reference_name="DRV-TEST-001",
                allocated_to="fleet@example.invalid",
                description="Driver Test Driver safety training expires on tomorrow; HR-only date",
            ),
            frappe._dict(
                name="TODO-COMPLIANCE",
                reference_type="Driver",
                reference_name="DRV-TEST-001",
                allocated_to="fleet@example.invalid",
                description="Review the restricted professional-driver compliance records. Medical result: POSITIVE",
            ),
        ]
        driver = frappe._dict(
            name="DRV-TEST-001",
            driver_name="Test Driver",
            license_expiry=add_days(today(), 1),
            safety_training_expiry=add_days(today(), 2),
        )
        with (
            patch(
                "sotrama.migrations.security.frappe.get_all",
                side_effect=[todos, [driver]],
            ) as get_all,
            patch(
                "sotrama.migrations.security._user_for_role",
                side_effect=[
                    "fleet@example.invalid",
                    "hr@example.invalid",
                    "hr@example.invalid",
                ],
            ),
            patch("sotrama.migrations.security.frappe.db.set_value") as set_value,
        ):
            remediate_fleet_alert_todo_assignments()

        self.assertEqual(get_all.call_count, 2)
        self.assertEqual(get_all.call_args_list[1].args[0], "Driver")
        license_update = set_value.call_args_list[0].args[2]
        safety_update = set_value.call_args_list[1].args[2]
        compliance_update = set_value.call_args_list[2].args[2]
        self.assertNotIn("allocated_to", license_update)
        self.assertEqual(todos[0].allocated_to, "fleet@example.invalid")
        self.assertNotIn("SECRET-LICENSE-NUMBER", license_update["description"])
        self.assertEqual(safety_update["allocated_to"], "hr@example.invalid")
        self.assertIn("safety training", safety_update["description"])
        self.assertEqual(compliance_update["allocated_to"], "hr@example.invalid")
        self.assertNotIn("POSITIVE", compliance_update["description"])

    def test_french_legacy_driver_alerts_are_sanitized_and_routed_to_the_right_role(
        self,
    ):
        from sotrama.migrations.security import remediate_fleet_alert_todo_assignments

        driver = frappe._dict(
            name="DRV-LEGACY-FR",
            driver_name="Conducteur historique",
            license_expiry="2026-12-01",
            safety_training_expiry="2026-12-15",
        )
        todos = [
            frappe._dict(
                name="TODO-LICENSE-FR-LEGACY",
                reference_type="Driver",
                reference_name=driver.name,
                allocated_to="fleet@example.invalid",
                description="Expiration du permis du conducteur : Conducteur historique\nLe permis du conducteur Conducteur historique expire le 2026-12-01 ; SECRET-LICENSE-NUMBER",
            ),
            frappe._dict(
                name="TODO-SAFETY-FR-LEGACY",
                reference_type="Driver",
                reference_name=driver.name,
                allocated_to="fleet@example.invalid",
                description="Expiration de la formation sécurité : Conducteur historique\nLa formation sécurité du conducteur Conducteur historique expire le 2026-12-15.",
            ),
            frappe._dict(
                name="TODO-COMPLIANCE-FR-LEGACY",
                reference_type="Driver",
                reference_name=driver.name,
                allocated_to="fleet@example.invalid",
                description="Contrôle restreint de conformité du conducteur\nRésultat médical : POSITIF ; date : 2026-11-01. Consultez les dossiers de conformité professionnelle à accès restreint.",
            ),
        ]

        with (
            patch(
                "sotrama.migrations.security.frappe.get_all",
                side_effect=[todos, [driver]],
            ) as get_all,
            patch(
                "sotrama.migrations.security._user_for_role",
                side_effect=[
                    "fleet@example.invalid",
                    "hr@example.invalid",
                    "hr@example.invalid",
                ],
            ),
            patch("sotrama.migrations.security.frappe.db.set_value") as set_value,
        ):
            remediate_fleet_alert_todo_assignments()

        self.assertTrue(get_all.call_args_list[0].kwargs["or_filters"])
        updates = {call.args[1]: call.args[2] for call in set_value.call_args_list}
        self.assertEqual(len(updates), 3)
        self.assertNotIn("SECRET-LICENSE-NUMBER", updates[todos[0].name]["description"])
        self.assertNotIn("allocated_to", updates[todos[0].name])
        self.assertEqual(todos[0].allocated_to, "fleet@example.invalid")
        self.assertEqual(updates[todos[1].name]["allocated_to"], "hr@example.invalid")
        self.assertTrue(
            any(
                phrase in updates[todos[1].name]["description"].lower()
                for phrase in ("safety training", "formation sécurité")
            )
        )
        self.assertEqual(updates[todos[2].name]["allocated_to"], "hr@example.invalid")
        self.assertNotIn("POSITIF", updates[todos[2].name]["description"])
        self.assertNotIn("2026-11-01", updates[todos[2].name]["description"])

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
            patch("sotrama.tp.scheduler.drivers.get_tp_setting", return_value=60),
            patch(
                "frappe.get_all",
                side_effect=[[], [driver], []],
            ) as get_all,
            patch("frappe.db.exists", return_value=False),
            patch(
                "frappe.new_doc",
                side_effect=[license_todo, safety_todo],
            ),
            patch(
                "sotrama.tp.scheduler.drivers._user_for_role",
                side_effect=["fleet@example.invalid", "hr@example.invalid"],
            ),
        ):
            check_driver_license_expiry()

        self.assertEqual(license_todo.allocated_to, "fleet@example.invalid")
        self.assertNotIn("SECRET-LICENSE-NUMBER", license_todo.description)
        self.assertEqual(safety_todo.allocated_to, "hr@example.invalid")
        self.assertEqual(
            get_all.call_args_list[0].kwargs["filters"]["transport_regulatory_status"],
            "Regulated",
        )
        self.assertEqual(get_all.call_args_list[2].args[0], "ToDo")
        self.assertEqual(
            get_all.call_args_list[2].kwargs["filters"],
            {"reference_type": "Driver"},
        )

    def test_driver_scheduler_closes_renewed_cleared_and_inactive_alerts_in_french(
        self,
    ):
        from sotrama.tp.scheduler import check_driver_license_expiry

        active_driver = frappe._dict(
            name="DRV-RENEWED",
            driver_name="Conducteur renouvelé",
            status="Active",
            license_expiry=add_days(today(), 365),
            safety_training_expiry=None,
        )
        compliant_driver = frappe._dict(
            name="DRV-COMPLIANT",
            driver_name="Conducteur conforme",
            status="Active",
            license_expiry=None,
            safety_training_expiry=None,
        )
        compliance_records = [
            frappe._dict(
                name="COMPLIANCE-MEDICAL-001",
                modified="2026-11-20 10:00:00",
                parent=compliant_driver.name,
                check_type="Medical Fitness Examination",
                result="Fit",
                valid_until=add_days(today(), 365),
            ),
            frappe._dict(
                name="COMPLIANCE-DRUG-001",
                modified="2026-11-20 10:00:00",
                parent=compliant_driver.name,
                check_type="Drug Screening",
                result="Negative",
                valid_until=add_days(today(), 365),
            ),
        ]
        todos = [
            frappe._dict(
                name="TODO-LICENSE-FR",
                reference_name=active_driver.name,
                description="Expiration du permis du conducteur : Conducteur renouvelé\nLe permis du conducteur expire le 2026-12-01.",
                status="Open",
            ),
            frappe._dict(
                name="TODO-SAFETY-FR",
                reference_name=active_driver.name,
                description="Expiration de la formation sécurité : Conducteur renouvelé\nLa formation sécurité du conducteur expire le 2026-12-01.",
                status="Open",
            ),
            frappe._dict(
                name="TODO-COMPLIANCE-FR",
                reference_name=active_driver.name,
                description="Contrôle restreint de conformité du conducteur\nConsultez les dossiers de conformité professionnelle à accès restreint des conducteurs.",
                status="Open",
            ),
            frappe._dict(
                name="TODO-INACTIVE-DRIVER",
                reference_name="DRV-INACTIVE",
                description="Driver Former Driver license expires on 2026-12-01.",
                status="Open",
            ),
            frappe._dict(
                name="TODO-COMPLIANCE-COMPLETED",
                reference_name=compliant_driver.name,
                description="Review the restricted professional-driver compliance records. This task intentionally contains no medical result or date.",
                status="Open",
            ),
        ]

        with (
            patch("sotrama.tp.scheduler.drivers.get_tp_setting", return_value=60),
            patch(
                "frappe.get_all",
                side_effect=[
                    [compliant_driver.name],
                    [active_driver, compliant_driver],
                    compliance_records,
                    todos,
                ],
            ),
            patch("frappe.db.exists", return_value=True),
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc") as new_doc,
        ):
            check_driver_license_expiry()

        for todo in todos:
            set_value.assert_any_call(
                "ToDo", todo.name, "status", "Closed", update_modified=False
            )
        new_doc.assert_not_called()

    def test_driver_scheduler_respects_manual_close_for_same_expiry_only(self):
        from sotrama.tp.scheduler import check_driver_license_expiry

        same_expiry_driver = frappe._dict(
            name="DRV-CLOSED-SAME-EXPIRY",
            driver_name="Driver Same Expiry",
            license_expiry=add_days(today(), 10),
            safety_training_expiry=None,
        )
        renewed_driver = frappe._dict(
            name="DRV-NEW-EXPIRY",
            driver_name="Driver New Expiry",
            license_expiry=add_days(today(), 11),
            safety_training_expiry=None,
        )
        safety_driver = frappe._dict(
            name="DRV-CLOSED-SAFETY",
            driver_name="Driver Safety Same Expiry",
            license_expiry=None,
            safety_training_expiry=add_days(today(), 12),
        )
        old_expiry = add_days(today(), -10)
        todos = [
            frappe._dict(
                name="TODO-CLOSED-SAME-EXPIRY",
                reference_name=same_expiry_driver.name,
                description=f"Driver License Expiring: Driver Same Expiry\nDriver Driver Same Expiry license expires on {same_expiry_driver.license_expiry}.",
                status="Closed",
            ),
            frappe._dict(
                name="TODO-OPEN-DUPLICATE-CLOSED-EXPIRY",
                reference_name=same_expiry_driver.name,
                description=f"Driver License Expiring: Driver Same Expiry\nDriver Driver Same Expiry license expires on {same_expiry_driver.license_expiry}.",
                status="Open",
            ),
            frappe._dict(
                name="TODO-CLOSED-OLD-EXPIRY",
                reference_name=renewed_driver.name,
                description=f"Driver License Expiring: Driver New Expiry\nDriver Driver New Expiry license expires on {old_expiry}.",
                status="Closed",
            ),
            frappe._dict(
                name="TODO-CLOSED-SAFETY-EXPIRY",
                reference_name=safety_driver.name,
                description=f"Safety Training Expiring: Driver Safety Same Expiry\nDriver Driver Safety Same Expiry safety training expires on {safety_driver.safety_training_expiry}.",
                status="Closed",
            ),
        ]
        created_todo = Mock()
        created_todo.name = "TODO-NEW-EXPIRY"

        with (
            patch("sotrama.tp.scheduler.drivers.get_tp_setting", return_value=60),
            patch(
                "frappe.get_all",
                side_effect=[
                    [],
                    [same_expiry_driver, renewed_driver, safety_driver],
                    todos,
                ],
            ),
            patch(
                "sotrama.tp.scheduler.drivers._user_for_role",
                side_effect=[
                    "fleet@example.invalid",
                    "fleet@example.invalid",
                    "hr@example.invalid",
                ],
            ),
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc", return_value=created_todo) as new_doc,
        ):
            check_driver_license_expiry()

        new_doc.assert_called_once_with("ToDo")
        created_todo.insert.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(created_todo.reference_name, renewed_driver.name)
        self.assertIn(str(renewed_driver.license_expiry), created_todo.description)
        set_value.assert_called_once_with(
            "ToDo",
            "TODO-OPEN-DUPLICATE-CLOSED-EXPIRY",
            "status",
            "Closed",
            update_modified=False,
        )

    def test_driver_scheduler_keeps_one_open_alert_and_closes_duplicates(self):
        from sotrama.tp.scheduler import check_driver_license_expiry

        driver = frappe._dict(
            name="DRV-DUPLICATE-ALERT",
            driver_name="Driver Duplicate",
            license_expiry=add_days(today(), 10),
            safety_training_expiry=None,
        )
        todos = [
            frappe._dict(
                name="TODO-KEEP",
                reference_name=driver.name,
                description=f"Driver License Expiring: Driver Duplicate\nDriver Driver Duplicate license expires on {driver.license_expiry}.",
                status="Open",
            ),
            frappe._dict(
                name="TODO-CLOSE-DUPLICATE",
                reference_name=driver.name,
                description=f"Driver License Expiring: Driver Duplicate\nDriver Driver Duplicate license expires on {driver.license_expiry}.",
                status="Open",
            ),
        ]

        with (
            patch("sotrama.tp.scheduler.drivers.get_tp_setting", return_value=60),
            patch(
                "frappe.get_all",
                side_effect=[[], [driver], todos],
            ),
            patch(
                "sotrama.tp.scheduler.drivers._user_for_role",
                return_value="fleet@example.invalid",
            ),
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc") as new_doc,
        ):
            check_driver_license_expiry()

        new_doc.assert_not_called()
        set_value.assert_any_call(
            "ToDo",
            "TODO-CLOSE-DUPLICATE",
            "status",
            "Closed",
            update_modified=False,
        )
        self.assertNotIn(
            ("ToDo", "TODO-KEEP", "status", "Closed"),
            [call.args for call in set_value.call_args_list],
        )

    def test_driver_compliance_signature_tracks_record_revision_without_medical_values(
        self,
    ):
        from sotrama.tp.scheduler import _driver_compliance_signature

        original = {
            "Medical Fitness Examination": frappe._dict(
                name="COMPLIANCE-MEDICAL-001",
                modified="2026-11-20 10:00:00",
                result="Fit",
                valid_until="2026-12-01",
            ),
            "Drug Screening": frappe._dict(
                name="COMPLIANCE-DRUG-001",
                modified="2026-11-20 10:00:00",
                result="Negative",
                valid_until="2026-12-01",
            ),
        }
        changed_medical_values = {
            "Medical Fitness Examination": frappe._dict(
                name="COMPLIANCE-MEDICAL-001",
                modified="2026-11-20 10:00:00",
                result="Unfit",
                valid_until="2027-01-01",
            ),
            "Drug Screening": original["Drug Screening"],
        }
        revised_record = {
            **original,
            "Medical Fitness Examination": frappe._dict(
                name="COMPLIANCE-MEDICAL-001",
                modified="2026-11-21 10:00:00",
                result="Fit",
                valid_until="2026-12-01",
            ),
        }

        signature = _driver_compliance_signature(original)
        self.assertEqual(len(signature), 16)
        self.assertEqual(
            signature, _driver_compliance_signature(changed_medical_values)
        )
        self.assertNotEqual(signature, _driver_compliance_signature(revised_record))
        self.assertNotIn("Fit", signature)
        self.assertNotIn("2026-12-01", signature)

    def test_driver_scheduler_suppresses_manually_closed_compliance_snapshot(self):
        from sotrama.tp.scheduler import (
            _driver_compliance_description,
            _driver_compliance_signature,
            check_driver_license_expiry,
        )

        same_snapshot_driver = frappe._dict(
            name="DRV-CLOSED-COMPLIANCE",
            driver_name="Driver Compliance",
            license_expiry=None,
            safety_training_expiry=None,
        )
        changed_snapshot_driver = frappe._dict(
            name="DRV-CHANGED-COMPLIANCE",
            driver_name="Driver Updated Compliance",
            license_expiry=None,
            safety_training_expiry=None,
        )
        old_signature = _driver_compliance_signature({})
        changed_records = [
            frappe._dict(
                name="COMPLIANCE-MEDICAL-UPDATED",
                modified="2026-11-22 10:00:00",
                parent=changed_snapshot_driver.name,
                check_type="Medical Fitness Examination",
                test_date=today(),
                result="Fit",
                valid_until=add_days(today(), 365),
            )
        ]
        todos = [
            frappe._dict(
                name="TODO-CLOSED-SAME-COMPLIANCE-SNAPSHOT",
                reference_name=same_snapshot_driver.name,
                description=_driver_compliance_description(
                    same_snapshot_driver.driver_name, old_signature
                ),
                status="Closed",
            ),
            frappe._dict(
                name="TODO-CLOSED-OLD-COMPLIANCE-SNAPSHOT",
                reference_name=changed_snapshot_driver.name,
                description=_driver_compliance_description(
                    changed_snapshot_driver.driver_name, old_signature
                ),
                status="Closed",
            ),
        ]
        created_todo = Mock()
        created_todo.name = "TODO-NEW-COMPLIANCE-SNAPSHOT"

        with (
            patch("sotrama.tp.scheduler.drivers.get_tp_setting", return_value=60),
            patch(
                "frappe.get_all",
                side_effect=[
                    [same_snapshot_driver.name, changed_snapshot_driver.name],
                    [same_snapshot_driver, changed_snapshot_driver],
                    changed_records,
                    todos,
                ],
            ),
            patch("frappe.db.exists", return_value=True),
            patch(
                "sotrama.tp.scheduler.drivers._user_for_role",
                return_value="hr@example.invalid",
            ),
            patch("frappe.db.set_value") as set_value,
            patch("frappe.new_doc", return_value=created_todo) as new_doc,
        ):
            check_driver_license_expiry()

        new_doc.assert_called_once_with("ToDo")
        created_todo.insert.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(created_todo.reference_name, changed_snapshot_driver.name)
        self.assertIn("[SOTRAMA-DRIVER-COMPLIANCE:", created_todo.description)
        self.assertNotIn("Fit", created_todo.description)
        self.assertNotIn(str(changed_records[0].valid_until), created_todo.description)
        set_value.assert_not_called()

    def test_driver_compliance_scheduler_reads_only_active_regulated_drivers(self):
        from sotrama.tp.scheduler import check_driver_license_expiry

        active_driver = frappe._dict(
            name="DRV-ACTIVE-REGULATED",
            status="Active",
            driver_name="Active Driver",
            license_expiry=None,
            safety_training_expiry=None,
        )
        inactive_driver = frappe._dict(
            name="DRV-INACTIVE-REGULATED",
            status="Inactive",
            driver_name="Inactive Driver",
            license_expiry=None,
            safety_training_expiry=None,
        )
        tasks = [active_driver.name, inactive_driver.name]
        compliance_todo = frappe._dict(
            name="TODO-RESTRICTED-COMPLIANCE",
            insert=Mock(),
        )
        with (
            patch("sotrama.tp.scheduler.drivers.get_tp_setting", return_value=60),
            patch(
                "frappe.get_all",
                side_effect=[tasks, [active_driver], [], [], []],
            ) as get_all,
            patch("frappe.db.exists", return_value=True),
            patch(
                "frappe.new_doc",
                return_value=compliance_todo,
            ),
        ):
            check_driver_license_expiry()

        compliance_query = get_all.call_args_list[2]
        self.assertEqual(compliance_query.args[0], "Driver Compliance Record")
        self.assertEqual(
            compliance_query.kwargs["filters"]["parent"],
            ["in", [active_driver.name]],
        )
        self.assertEqual(get_all.call_args_list[4].args[0], "Has Role")
        compliance_todo.insert.assert_called_once_with(ignore_permissions=True)
        self.assertIn("[SOTRAMA-DRIVER-COMPLIANCE:", compliance_todo.description)
        self.assertNotIn("Medical Fitness", compliance_todo.description)
        self.assertNotIn("Fit", compliance_todo.description)
