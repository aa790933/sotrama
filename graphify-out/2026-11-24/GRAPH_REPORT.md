# Graph Report - sotrama  (2026-11-24)

## Corpus Check
- 162 files · ~74,521 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 4 file(s) not represented in the graph (top: (none) 2, .in 1, .po 1)

## Summary
- 1175 nodes · 2130 edges · 125 communities (21 shown, 104 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e998afb1`
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
- TestDriverFileMetadataPrivacy
- execute
- install.py
- test_driver.py
- .test_french_catalog_covers_custom_doctype_labels_options_and_ui_messages
- upcoming_document_expiries.py
- breakdown_incident.py
- CompanyClassification
- TPSettings
- frappe_utils
- search_workshop_employees
- TestMaintenanceScheduleWorkflow
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
- TestFleetSystemManagedFields
- migrate_fleet_attachments_private
- VehicleModel
- migrate_legacy_company_nif
- TestCompanyClassification
- TestDriverStatusWorkflow
- prevent_submitted_fleet_record_deletion

## God Nodes (most connected - your core abstractions)
1. `TestSotramaSetup` - 57 edges
2. `validate_company_access()` - 43 edges
3. `TestVehicle` - 37 edges
4. `_delete_test_record()` - 36 edges
5. `validate_linked_document_read_permission()` - 32 edges
6. `_sotrama_package_path()` - 27 edges
7. `TestFleetPermissionsIntegration` - 26 edges
8. `MaintenanceJobCard` - 25 edges
9. `get_tp_setting()` - 24 edges
10. `TestFleetSchedulerPrivacy` - 23 edges

## Surprising Connections (you probably didn't know these)
- `TestDriverFileMetadataPrivacy` --uses--> `DriverPrivateFileMixin`  [INFERRED]
  sotrama/tests/test_driver.py → sotrama/overrides/file.py
- `TestDriverIntegration` --uses--> `DriverPrivateFileMixin`  [INFERRED]
  sotrama/tests/test_driver.py → sotrama/overrides/file.py
- `TestMaintenanceIntegration` --uses--> `Vehicle`  [INFERRED]
  sotrama/tests/test_maintenance.py → sotrama/tp/doctype/vehicle/vehicle.py
- `TestFleetPermissionsIntegration` --uses--> `Vehicle`  [INFERRED]
  sotrama/tests/test_permissions.py → sotrama/tp/doctype/vehicle/vehicle.py
- `migrate_legacy_company_nif()` --calls--> `_is_managed_company_field()`  [EXTRACTED]
  sotrama/migrations/company.py → sotrama/setup/company.py

## Import Cycles
- None detected.

## Communities (125 total, 104 thin omitted)

### Community 0 - "TestFleetSchedulerPrivacy"
Cohesion: 0.07
Nodes (14): remediate_fleet_alert_todo_assignments(), TestFleetSchedulerPrivacy, get_vehicle_document_status(), refresh_vehicle_document_statuses(), _user_for_role(), check_document_expiries(), check_driver_license_expiry(), _driver_alert_kind() (+6 more)

### Community 1 - "TestVehicle"
Cohesion: 0.10
Nodes (4): migrate_fleet_document_options(), _delete_test_record(), TestVehicle, get_vehicle_model_name()

### Community 2 - "steps"
Cohesion: 0.05
Nodes (43): MARIADB_ROOT_PASSWORD, name, runs-on, services, steps, timeout-minutes, jobs, frappe-integration (+35 more)

### Community 5 - "TestFleetPermissionsIntegration"
Cohesion: 0.07
Nodes (9): TestFleetPermissionsIntegration, _get_accessible_company_default(), get_tp_company_defaults(), get_tp_default_company(), search_company_classification_companies(), _search_company_names(), search_driver_companies(), search_fleet_report_companies() (+1 more)

### Community 7 - "TestDriverIntegration"
Cohesion: 0.06
Nodes (3): TestDriver, TestDriverIntegration, Driver

### Community 9 - "TestFleetChildTableAndAttachmentSecurity"
Cohesion: 0.07
Nodes (13): DriverPrivateFileMixin, can_access_company_scoped_fleet_attachment(), can_access_driver_private_attachment(), file_has_permission(), _get_file_attachment_company(), is_company_scoped_fleet_attachment(), is_direct_company_scoped_fleet_attachment(), is_driver_private_attachment() (+5 more)

### Community 10 - "permissions.py"
Cohesion: 0.11
Nodes (15): _can_read_driver_attachment_parent(), _file_belongs_to_parent(), _filter_driver_attachment_metadata(), _filter_fleet_attachment_metadata(), get_docinfo_with_driver_attachment_filter(), _get_driver_private_attachment_names(), get_filtered_attachments_with_driver_attachment_filter(), _get_unrelated_fleet_attachment_names() (+7 more)

### Community 11 - "test_permissions.py"
Cohesion: 0.10
Nodes (9): enforce_fleet_company_user_permissions(), get_single_value_with_tp_settings_field_permissions(), prevent_unsafe_fleet_docsharing(), remove_unsafe_fleet_docshares(), remove_unsafe_fleet_docshares_for_document(), remove_unsafe_fleet_docshares_for_user(), tp_company_defaults_query_conditions(), tp_settings_query_conditions() (+1 more)

### Community 14 - "setup/company.py"
Cohesion: 0.09
Nodes (10): preserve_fleet_file_privacy_on_uninstall(), _detach_legacy_module_fields(), enable_algerian_company_fields(), get_custom_fields(), _is_managed_company_field(), _set_company_fields_hidden(), sync_company_fields(), preserve_company_fields_on_uninstall() (+2 more)

### Community 15 - "test_fleet_form_permissions.js"
Cohesion: 0.09
Nodes (16): assert, driverSource, fs, inspectionChildren, inspectionDialogs, jobCardChildren, loadHandlers(), makeForm() (+8 more)

### Community 16 - "security.py"
Cohesion: 0.15
Nodes (13): migrate_driver_private_attachments(), _migrate_fleet_attachments_private(), _clear_attached_file_field(), _ensure_file_privacy_field(), _ensure_fleet_file_privacy_field(), _is_remote_file(), preserve_driver_file_privacy_on_uninstall(), _redact_driver_attachment_comments() (+5 more)

### Community 18 - "TestFleetReports"
Cohesion: 0.12
Nodes (7): TestFleetReports, _date_filters(), _estimate_depreciation(), execute(), get_columns(), get_data(), validate_filters()

### Community 19 - "masters.py"
Cohesion: 0.18
Nodes (4): _designation_name_key(), ensure_default_masters(), ensure_public_works_designations(), setup()

### Community 23 - "validate_company_access"
Cohesion: 0.16
Nodes (8): get_tp_company_setting(), get_tp_setting(), validate_company_access(), get_open_vehicle_safety_holds(), validate_active_driver(), validate_linked_document_read_permission(), validate_professional_transport_certificate(), validate_submitted_vehicle()

### Community 24 - "steps"
Cohesion: 0.10
Nodes (19): runs-on, steps, RELEASE_TAG, jobs, build-and-release, name, on, push (+11 more)

### Community 26 - "execute"
Cohesion: 0.14
Nodes (5): hide_managed_legacy_company_nif(), normalize_fleet_master_names(), simplify_fleet_reference_masters(), remove_legacy_algerian_localization_workspace(), execute()

### Community 27 - "install.py"
Cohesion: 0.11
Nodes (6): _ensure_driver_file_privacy_field(), ensure_roles(), initialize_app(), prepare_before_install(), recover_incomplete_install(), repair_orphaned_module_definitions()

### Community 28 - "test_driver.py"
Cohesion: 0.15
Nodes (9): _check_driver_compliance_child_rpc_access(), _check_sotrama_child_table_rpc_access(), _check_tp_company_defaults_child_access(), _check_tp_settings_field_read_permission(), driver_compliance_record_query_conditions(), get_list_with_tp_settings_permissions(), get_value_with_tp_settings_field_permissions(), sotrama_child_table_query_conditions() (+1 more)

### Community 31 - ".test_french_catalog_covers_custom_doctype_labels_options_and_ui_messages"
Cohesion: 0.83
Nodes (3): assert_translated(), check_print_format_content(), check_workspace_and_report_labels()

### Community 32 - "upcoming_document_expiries.py"
Cohesion: 0.47
Nodes (3): execute(), get_columns(), get_data()

### Community 39 - "search_workshop_employees"
Cohesion: 0.29
Nodes (3): get_workshop_employee_name(), search_workshop_employees(), _validate_workshop_employee_lookup_access()

## Knowledge Gaps
- **1 isolated node(s):** `sotrama`
  These have ≤1 connection - possible missing edges. (Counts symbols only; 524 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **104 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `validate_company_access()` connect `validate_company_access` to `breakdown_incident.py`, `CompanyClassification`, `MaintenanceJobCard`, `TestFleetPermissionsIntegration`, `frappe_utils`, `TestDriverIntegration`, `search_workshop_employees`, `OperationalTask`, `permissions.py`, `test_permissions.py`, `MaintenanceSchedule`, `VehicleInspection`, `Vehicle`, `frappe`?**
  _High betweenness centrality (0.060) - this node is a cross-community bridge._
- **What connects `sotrama` to the rest of the system?**
  _1 weakly-connected nodes found - possible missing edges._
- **Should `TestFleetSchedulerPrivacy` be split into smaller, more focused modules?**
  _Cohesion score 0.07259528130671507 - nodes in this community are weakly interconnected._
- **Why does `TestFleetChildTableAndAttachmentSecurity` connect `TestFleetChildTableAndAttachmentSecurity` to `.test_file_controller_mixin_sets_privacy_before_storage_insert`, `.test_file_controller_mixin_blocks_reuse_of_fleet_file_content`, `test_permissions.py`, `TestDriverFileMetadataPrivacy`, `test_driver.py`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Should `TestVehicle` be split into smaller, more focused modules?**
  _Cohesion score 0.0953058321479374 - nodes in this community are weakly interconnected._
- **Why does `_sotrama_package_path()` connect `TestSotramaSetup` to `VehicleInspection`, `TestFleetPermissionsIntegration`, `TestDriverIntegration`, `OperationalTask`, `test_permissions.py`, `security.py`, `test_setup.py`, `TestFleetReports`, `frappe`, `.test_french_catalog_covers_custom_doctype_labels_options_and_ui_messages`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Should `steps` be split into smaller, more focused modules?**
  _Cohesion score 0.049682875264270614 - nodes in this community are weakly interconnected._