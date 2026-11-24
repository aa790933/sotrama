import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Vehicle(Document):
    """
    Fleet Vehicle — core record for every vehicle in the Algerian
    public works company fleet. Company classification certificates are
    maintained at legal-entity level and are optional references, not a
    prerequisite for registering an individual fleet asset.
    """

    def validate(self):
        self._validate_license_plate()
        self._set_defaults()
        self._update_vehicle_document_statuses()
        self._validate_unique_fleet_number()
        from sotrama.tp.settings import validate_company_access

        validate_company_access(self.company, "Vehicle")
        self._validate_chassis()
        self._validate_asset_values()
        self._validate_make_model()
        self._validate_company_links()
        self._validate_asset_link()
        self._validate_company_ownership()
        self._validate_safety_hold()

    def _update_vehicle_document_statuses(self):
        from sotrama.tp.doctype.vehicle_document.vehicle_document import (
            get_vehicle_document_status,
        )
        from sotrama.tp.settings import get_tp_setting

        alert_days = get_tp_setting("vehicle_document_alert_days", 30)
        for row in self.get("vehicle_documents") or []:
            row.status = get_vehicle_document_status(row.expiry_date, alert_days)

    def before_cancel(self):
        from sotrama.tp.validation import get_open_vehicle_safety_holds

        holds = get_open_vehicle_safety_holds(self.name)
        if any(holds.values()):
            frappe.throw(
                _(
                    "Resolve all open breakdowns and safety-critical inspections before cancelling this Vehicle."
                )
            )

    def on_cancel(self):
        self._cancel_related_records()

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_license_plate(self):
        # Normalize in the controller as well as the form script so imports and
        # API-created records use the same company-level uniqueness key.
        self.license_plate = (self.license_plate or "").strip().upper()
        if not self.license_plate:
            frappe.throw(_("Registration / Fleet Number is required."))

    def _validate_unique_fleet_number(self):
        if not self.company or not self.license_plate:
            return
        duplicate = frappe.db.get_value(
            "Vehicle",
            {
                "company": self.company,
                "license_plate": self.license_plate,
                "name": ["!=", self.name],
            },
            "name",
        )
        if duplicate:
            frappe.throw(
                _("Registration / Fleet Number must be unique within the Company.")
            )

    def _validate_chassis(self):
        if self.chassis_no and len(str(self.chassis_no)) < 10:
            frappe.throw(_("Chassis Number seems too short — please verify"))

    def _validate_asset_values(self):
        """Keep acquisition, salvage and annual depreciation inputs coherent."""
        previous = self.get_doc_before_save()
        fields = ("acquisition_value", "depreciation_rate", "salvage_value")
        if previous and all(
            flt(previous.get(field)) == flt(self.get(field)) for field in fields
        ):
            return

        acquisition_value = flt(self.acquisition_value)
        depreciation_rate = flt(self.depreciation_rate)
        salvage_value = flt(self.salvage_value)

        if acquisition_value < 0:
            frappe.throw(_("Acquisition Value cannot be negative."))
        if salvage_value < 0:
            frappe.throw(_("Salvage Value cannot be negative."))
        if salvage_value > acquisition_value:
            frappe.throw(_("Salvage Value cannot exceed Acquisition Value."))
        if not 0 <= depreciation_rate <= 100:
            frappe.throw(_("Depreciation Rate must be between 0 and 100 percent."))

    def _validate_make_model(self):
        from sotrama.tp.validation import validate_linked_document_read_permission

        previous = self.get_doc_before_save()
        make_changed = (
            not previous
            or getattr(self, "_action", None) == "submit"
            or previous.vehicle_make != self.vehicle_make
        )
        model_changed = (
            not previous
            or getattr(self, "_action", None) == "submit"
            or previous.model != self.model
            or previous.vehicle_make != self.vehicle_make
        )

        if self.vehicle_make and (make_changed or model_changed):
            validate_linked_document_read_permission("Vehicle Make", self.vehicle_make)
            make = frappe.db.get_value(
                "Vehicle Make",
                self.vehicle_make,
                ["active"],
                as_dict=True,
            )
            if not make or not make.active:
                frappe.throw(_("Select an active Vehicle Make."))

        if self.model and model_changed:
            if not self.vehicle_make:
                frappe.throw(_("Select a Vehicle Make before selecting a Model."))

            validate_linked_document_read_permission("Vehicle Model", self.model)
            model = frappe.db.get_value(
                "Vehicle Model",
                self.model,
                ["vehicle_make", "active"],
                as_dict=True,
            )
            if not model or not model.active:
                frappe.throw(_("Select an active Vehicle Model."))
            if model.vehicle_make != self.vehicle_make:
                frappe.throw(
                    _("Vehicle Model must belong to the selected Vehicle Make.")
                )

    def _set_defaults(self):
        from sotrama.tp.settings import get_tp_company_setting, get_tp_setting

        if not self.vehicle_status:
            self.vehicle_status = "Active"
        if not self.fuel_type:
            self.fuel_type = "Diesel"

        if not self.company:
            self.company = get_tp_setting("default_company")
        if not self.department:
            default_department = get_tp_company_setting(
                self.company, "default_department", "Vehicle"
            )
            department_company = (
                frappe.db.get_value("Department", default_department, "company")
                if default_department
                else None
            )
            if (
                not self.company
                or not department_company
                or department_company == self.company
            ):
                self.department = default_department

        if self.company and not self.cost_center:
            default_cost_center = get_tp_company_setting(
                self.company, "default_cost_center", "Vehicle"
            )
            if (
                default_cost_center
                and frappe.db.get_value("Cost Center", default_cost_center, "company")
                == self.company
            ):
                self.cost_center = default_cost_center

        if self.company and not self.parts_warehouse:
            default_warehouse = get_tp_company_setting(
                self.company, "default_parts_warehouse", "Vehicle"
            )
            if (
                default_warehouse
                and frappe.db.get_value("Warehouse", default_warehouse, "company")
                == self.company
            ):
                self.parts_warehouse = default_warehouse

    def _validate_company_links(self):
        if self.parts_warehouse:
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission("Warehouse", self.parts_warehouse)
            warehouse = frappe.db.get_value(
                "Warehouse",
                self.parts_warehouse,
                ["company", "is_group", "disabled"],
                as_dict=True,
            )
            if not warehouse:
                frappe.throw(_("Parts Warehouse does not exist."))
            if warehouse.company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(warehouse.company, "Warehouse")
            if not self.company or warehouse.company != self.company:
                frappe.throw(_("Parts Warehouse must belong to the Vehicle Company."))
            if warehouse.is_group or warehouse.disabled:
                frappe.throw(_("Parts Warehouse must be an enabled leaf Warehouse."))

        if self.cost_center:
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission("Cost Center", self.cost_center)
            cost_center = frappe.db.get_value(
                "Cost Center",
                self.cost_center,
                ["company", "is_group", "disabled"],
                as_dict=True,
            )
            if not cost_center:
                frappe.throw(_("Cost Center does not exist."))
            if cost_center.company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(cost_center.company, "Cost Center")
            if not self.company or cost_center.company != self.company:
                frappe.throw(_("Cost Center must belong to the Vehicle Company."))
            if cost_center.is_group or cost_center.disabled:
                frappe.throw(_("Cost Center must be an enabled leaf Cost Center."))

        if self.department and self.company:
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission("Department", self.department)
            department_company = frappe.db.get_value(
                "Department", self.department, "company"
            )
            if department_company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(department_company, "Department")
            if department_company and department_company != self.company:
                frappe.throw(_("Department must belong to the Vehicle Company."))

        if self.primary_driver:
            previous = self.get_doc_before_save()
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission("Driver", self.primary_driver)
            driver_company = frappe.db.get_value(
                "Driver", self.primary_driver, "company"
            )
            if not frappe.db.exists("Driver", self.primary_driver):
                frappe.throw(_("Selected Primary Driver does not exist."))
            if driver_company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(driver_company, "Driver")
            if driver_company and self.company and driver_company != self.company:
                frappe.throw(_("Primary Driver must belong to the Vehicle Company."))

            assignment_changed = (
                not previous
                or self.docstatus == 0
                or getattr(self, "_action", None) == "submit"
                or previous.primary_driver != self.primary_driver
                or previous.company != self.company
            )
            if assignment_changed:
                from sotrama.tp.validation import validate_active_driver

                validate_active_driver(self.primary_driver, self.company)

    def _validate_asset_link(self):
        if not self.asset:
            return

        previous = self.get_doc_before_save()
        asset_changed = (
            not previous
            or getattr(self, "_action", None) == "submit"
            or previous.asset != self.asset
            or previous.company != self.company
        )
        if not asset_changed:
            return

        from sotrama.tp.settings import validate_company_access
        from sotrama.tp.validation import validate_linked_document_read_permission

        validate_linked_document_read_permission("Asset", self.asset)
        asset = frappe.db.get_value(
            "Asset",
            self.asset,
            ["company", "status", "docstatus"],
            as_dict=True,
        )
        if not asset or asset.docstatus != 1:
            frappe.throw(_("Select a submitted Asset."))
        if asset.status in {"Sold", "Scrapped"}:
            frappe.throw(_("A sold or scrapped Asset cannot be linked to a Vehicle."))
        if not asset.company:
            frappe.throw(_("The linked Asset must have a Company."))

        validate_company_access(asset.company, "Asset")
        if not self.company or asset.company != self.company:
            frappe.throw(_("Asset must belong to the Vehicle Company."))

    def _validate_company_ownership(self):
        previous = self.get_doc_before_save()
        if (
            previous
            and previous.docstatus == 1
            and previous.company
            and previous.company != self.company
        ):
            frappe.throw(
                _(
                    "Vehicle Company cannot be changed after submission. Use a controlled inter-company transfer process to preserve Fleet history."
                )
            )

    def _validate_safety_hold(self):
        if not self.name or self.vehicle_status not in {"Active", "In Service"}:
            return
        from sotrama.tp.validation import get_open_vehicle_safety_holds

        holds = get_open_vehicle_safety_holds(self.name)
        if holds["breakdown"] or holds["critical_inspection"]:
            reasons = []
            if holds["breakdown"]:
                reasons.append(_("an unresolved Breakdown Incident"))
            if holds["critical_inspection"]:
                reasons.append(_("an unresolved safety-critical Inspection"))
            frappe.throw(
                _(
                    "Vehicle cannot be set to Active or In Service while {0} exists."
                ).format(_(" and ").join(reasons))
            )

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def _cancel_related_records(self):
        """Take the vehicle out of service and close its document-expiry alerts."""
        frappe.db.set_value("Vehicle", self.name, "vehicle_status", "Out of Service")

        open_todos = frappe.get_all(
            "ToDo",
            filters={
                "reference_type": "Vehicle",
                "reference_name": self.name,
                "status": "Open",
            },
            fields=["name", "description"],
            limit_page_length=0,
        )
        legacy_alert_prefixes = {
            _("Vehicle Document Expiring: {0} (Vehicle: {1})", lang="en").split(
                "{0}", 1
            )[0],
            _("Vehicle Document Expiring: {0} (Vehicle: {1})", lang="fr").split(
                "{0}", 1
            )[0],
        }
        for todo in open_todos:
            description = todo.description or ""
            if "Vehicle Document Row:" in description or any(
                prefix and prefix in description for prefix in legacy_alert_prefixes
            ):
                frappe.db.set_value(
                    "ToDo", todo.name, "status", "Closed", update_modified=False
                )
