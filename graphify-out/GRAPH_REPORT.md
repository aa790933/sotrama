# Graph Report - sotrama  (2026-11-24)

## Corpus Check
- 162 files · ~74,521 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .in 1, .po 1)

## Summary
- 1174 nodes · 2144 edges · 113 communities (26 shown, 87 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 33 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `d70c3a31`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- TestFleetSchedulerPrivacy
- TestVehicle
- steps
- MaintenanceJobCard
- VehicleInspection
- TestFleetPermissionsIntegration
- TestSotramaSetup
- TestDriverIntegration
- OperationalTask
- TestFleetChildTableAndAttachmentSecurity
- permissions.py
- test_permissions.py
- MaintenanceSchedule
- BreakdownIncident
- setup/company.py
- test_fleet_form_permissions.js
- security.py
- test_setup.py
- TestFleetReports
- masters.py
- TestBreakdownIncident
- Vehicle
- TestSotramaCustomFields
- validate_company_access
- steps
- is_driver_private_attachment
- execute
- install.py
- test_driver.py
- _sotrama_package_path
- get_tp_setting
- validation.py
- CompanyClassification
- TPSettings
- validate_active_driver
- search_workshop_employees
- get_tp_company_setting
- get_data
- MaintenanceJobType
- VehicleMake
- docs.py
- TestCompanyClassificationIntegration
- BreakdownPhoto
- DriverComplianceRecord
- InspectionItem
- JobCardLabour
- JobCardOtherCost
- JobCardPart
- JobCardPhoto
- TPCompanyDefaults
- sotrama

## God Nodes (most connected - your core abstractions)
1. `TestSotramaSetup` - 58 edges
2. `validate_company_access()` - 43 edges
3. `TestVehicle` - 37 edges
4. `_delete_test_record()` - 36 edges
5. `validate_linked_document_read_permission()` - 32 edges
6. `TestFleetPermissionsIntegration` - 30 edges
7. `_sotrama_package_path()` - 27 edges
8. `MaintenanceJobCard` - 26 edges
9. `VehicleInspection` - 24 edges
10. `get_tp_setting()` - 24 edges

## Surprising Connections (you probably didn't know these)
- `TestDriverIntegration` --uses--> `DriverPrivateFileMixin`  [INFERRED]
  sotrama/tests/test_driver.py → sotrama/overrides/file.py
- `TestFleetChildTableAndAttachmentSecurity` --uses--> `DriverPrivateFileMixin`  [INFERRED]
  sotrama/tests/test_permissions.py → sotrama/overrides/file.py
- `TestMaintenanceIntegration` --uses--> `MaintenanceSchedule`  [INFERRED]
  sotrama/tests/test_maintenance.py → sotrama/tp/doctype/maintenance_schedule/maintenance_schedule.py
- `TestMaintenanceIntegration` --uses--> `Vehicle`  [INFERRED]
  sotrama/tests/test_maintenance.py → sotrama/tp/doctype/vehicle/vehicle.py
- `TestFleetPermissionsIntegration` --uses--> `BreakdownIncident`  [INFERRED]
  sotrama/tests/test_permissions.py → sotrama/tp/doctype/breakdown_incident/breakdown_incident.py

## Import Cycles
- None detected.

## Communities (113 total, 87 thin omitted)

### Community 0 - "TestFleetSchedulerPrivacy"
Cohesion: 0.07
Nodes (14): remediate_fleet_alert_todo_assignments(), TestFleetSchedulerPrivacy, get_vehicle_document_status(), refresh_vehicle_document_statuses(), _user_for_role(), check_document_expiries(), check_driver_license_expiry(), _driver_alert_kind() (+6 more)

### Community 1 - "TestVehicle"
Cohesion: 0.06
Nodes (6): migrate_fleet_document_options(), _delete_test_record(), TestDriverStatusWorkflow, TestVehicle, get_vehicle_model_name(), VehicleModel

### Community 2 - "steps"
Cohesion: 0.05
Nodes (43): MARIADB_ROOT_PASSWORD, name, runs-on, services, steps, timeout-minutes, jobs, frappe-integration (+35 more)

### Community 5 - "TestFleetPermissionsIntegration"
Cohesion: 0.07
Nodes (9): TestFleetPermissionsIntegration, get_tp_company_defaults(), get_tp_default_company(), search_company_classification_companies(), _search_company_names(), search_driver_companies(), search_fleet_report_companies(), search_vehicle_companies() (+1 more)

### Community 6 - "TestSotramaSetup"
Cohesion: 0.06
Nodes (4): migrate_legacy_company_nif(), migrate_fleet_attachments_private(), repair_orphaned_module_definitions(), TestSotramaSetup

### Community 7 - "TestDriverIntegration"
Cohesion: 0.07
Nodes (3): TestDriver, TestDriverIntegration, Driver

### Community 8 - "OperationalTask"
Cohesion: 0.07
Nodes (3): TestFleetLinkedDocumentPermissions, TestFleetSystemManagedFields, OperationalTask

### Community 9 - "TestFleetChildTableAndAttachmentSecurity"
Cohesion: 0.08
Nodes (9): can_access_company_scoped_fleet_attachment(), file_has_permission(), file_query_conditions(), _get_file_attachment_company(), is_direct_company_scoped_fleet_attachment(), _prevent_cross_company_file_reuse(), prevent_fleet_attachment_content_reuse(), secure_company_scoped_fleet_attachment() (+1 more)

### Community 10 - "permissions.py"
Cohesion: 0.10
Nodes (15): _can_read_driver_attachment_parent(), _check_tp_settings_field_read_permission(), _file_belongs_to_parent(), _filter_driver_attachment_metadata(), _filter_fleet_attachment_metadata(), get_docinfo_with_driver_attachment_filter(), _get_driver_private_attachment_names(), get_filtered_attachments_with_driver_attachment_filter() (+7 more)

### Community 11 - "test_permissions.py"
Cohesion: 0.08
Nodes (11): enforce_fleet_company_user_permissions(), is_company_scoped_fleet_attachment(), prevent_unsafe_fleet_docsharing(), remove_unsafe_fleet_docshares(), remove_unsafe_fleet_docshares_for_document(), remove_unsafe_fleet_docshares_for_file(), remove_unsafe_fleet_docshares_for_user(), sotrama_child_table_query_conditions() (+3 more)

### Community 12 - "MaintenanceSchedule"
Cohesion: 0.08
Nodes (3): TestMaintenanceScheduleWorkflow, MaintenanceSchedule, update_maintenance_schedule_status()

### Community 14 - "setup/company.py"
Cohesion: 0.11
Nodes (9): preserve_fleet_file_privacy_on_uninstall(), _detach_legacy_module_fields(), enable_algerian_company_fields(), get_custom_fields(), _is_managed_company_field(), _set_company_fields_hidden(), sync_company_fields(), preserve_company_fields_on_uninstall() (+1 more)

### Community 15 - "test_fleet_form_permissions.js"
Cohesion: 0.09
Nodes (16): assert, driverSource, fs, inspectionChildren, inspectionDialogs, jobCardChildren, loadHandlers(), makeForm() (+8 more)

### Community 16 - "security.py"
Cohesion: 0.14
Nodes (13): migrate_driver_private_attachments(), _migrate_fleet_attachments_private(), _clear_attached_file_field(), _is_remote_file(), _mark_duplicate_driver_file_rows(), preserve_driver_file_privacy_on_uninstall(), _redact_driver_attachment_comments(), _remove_private_driver_file_shares() (+5 more)

### Community 17 - "test_setup.py"
Cohesion: 0.14
Nodes (3): simplify_fleet_reference_masters(), _get_test_company(), TestCompanyClassification

### Community 18 - "TestFleetReports"
Cohesion: 0.12
Nodes (7): TestFleetReports, _date_filters(), _estimate_depreciation(), execute(), get_columns(), get_data(), validate_filters()

### Community 19 - "masters.py"
Cohesion: 0.13
Nodes (5): _designation_name_key(), ensure_default_masters(), ensure_public_works_designations(), setup(), create_missing_public_works_designations()

### Community 23 - "validate_company_access"
Cohesion: 0.23
Nodes (4): _validate_workshop_employee_lookup_access(), validate_company_access(), validate_linked_document_read_permission(), validate_submitted_vehicle()

### Community 24 - "steps"
Cohesion: 0.10
Nodes (19): runs-on, steps, RELEASE_TAG, jobs, build-and-release, name, on, push (+11 more)

### Community 25 - "is_driver_private_attachment"
Cohesion: 0.15
Nodes (4): DriverPrivateFileMixin, can_access_driver_private_attachment(), is_driver_private_attachment(), TestDriverFileMetadataPrivacy

### Community 26 - "execute"
Cohesion: 0.16
Nodes (4): hide_managed_legacy_company_nif(), normalize_fleet_master_names(), remove_legacy_algerian_localization_workspace(), execute()

### Community 27 - "install.py"
Cohesion: 0.14
Nodes (7): _ensure_driver_file_privacy_field(), _ensure_file_privacy_field(), _ensure_fleet_file_privacy_field(), ensure_roles(), initialize_app(), prepare_before_install(), recover_incomplete_install()

### Community 28 - "test_driver.py"
Cohesion: 0.23
Nodes (7): _check_driver_compliance_child_rpc_access(), _check_sotrama_child_table_rpc_access(), _check_tp_company_defaults_child_access(), driver_compliance_record_query_conditions(), get_list_with_tp_settings_permissions(), get_value_with_tp_settings_field_permissions(), validate_link_and_fetch_without_tp_settings_singleton()

### Community 31 - "_sotrama_package_path"
Cohesion: 0.14
Nodes (4): _sotrama_package_path(), assert_translated(), check_print_format_content(), check_workspace_and_report_labels()

### Community 32 - "get_tp_setting"
Cohesion: 0.21
Nodes (5): VehicleDocument, execute(), get_columns(), get_data(), get_tp_setting()

### Community 34 - "validation.py"
Cohesion: 0.20
Nodes (4): get_open_vehicle_safety_holds(), get_vehicle_status_before_out_of_service(), restore_vehicle_status_when_clear(), validate_professional_transport_certificate()

## Knowledge Gaps
- **1 isolated node(s):** `sotrama`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 523 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **87 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `validate_company_access()` connect `validate_company_access` to `validation.py`, `CompanyClassification`, `MaintenanceJobCard`, `TestFleetPermissionsIntegration`, `validate_active_driver`, `TestDriverIntegration`, `OperationalTask`, `VehicleInspection`, `permissions.py`, `test_permissions.py`, `get_tp_company_setting`, `MaintenanceSchedule`, `Vehicle`, `frappe`?**
  _High betweenness centrality (0.053) - this node is a cross-community bridge._
- **What connects `sotrama` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `TestFleetSchedulerPrivacy` be split into smaller, more focused modules?**
  _Cohesion score 0.07259528130671507 - nodes in this community are weakly interconnected._
- **Why does `_delete_test_record()` connect `TestVehicle` to `MaintenanceJobCard`, `MaintenanceSchedule`, `test_setup.py`, `TestBreakdownIncident`, `test_driver.py`, `frappe`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Should `TestVehicle` be split into smaller, more focused modules?**
  _Cohesion score 0.057912457912457915 - nodes in this community are weakly interconnected._
- **Why does `_sotrama_package_path()` connect `_sotrama_package_path` to `VehicleInspection`, `TestFleetPermissionsIntegration`, `TestDriverIntegration`, `OperationalTask`, `test_permissions.py`, `test_setup.py`, `TestFleetReports`, `test_driver.py`, `frappe`?**
  _High betweenness centrality (0.043) - this node is a cross-community bridge._
- **Should `steps` be split into smaller, more focused modules?**
  _Cohesion score 0.049682875264270614 - nodes in this community are weakly interconnected._