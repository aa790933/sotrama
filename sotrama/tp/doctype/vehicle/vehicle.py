import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Vehicle(Document):
    """
    Fleet Vehicle — core record for every vehicle in the Algerian
    public works company fleet. Extends the base Vehicle concept with
    Algerian regulatory fields, Grade 8 classification linkage, and
    full fleet management capabilities.
    """

    def validate(self):
        self._validate_license_plate()
        self._set_defaults()
        from sotrama.tp.settings import validate_company_access

        validate_company_access(self.company, "Vehicle")
        self._validate_classification()
        self._validate_chassis()
        self._validate_company_links()
        self._validate_company_ownership()
        self._validate_safety_hold()

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
        if not self.license_plate:
            frappe.throw(_("License Plate is required"))

    def _validate_classification(self):
        if not self.company_classification:
            frappe.throw(
                _(
                    "Company Classification is required — "
                    "this links the vehicle to the company's Grade level"
                )
            )
            return

        from sotrama.tp.validation import validate_linked_document_read_permission

        validate_linked_document_read_permission(
            "Company Classification", self.company_classification
        )
        classification = frappe.db.get_value(
            "Company Classification",
            self.company_classification,
            ["company", "active", "docstatus", "expiry_date"],
            as_dict=True,
        )
        if not classification or not classification.active:
            frappe.throw(_("Select an active Company Classification."))
        if classification.company:
            from sotrama.tp.settings import validate_company_access

            validate_company_access(classification.company, "Company Classification")
        if classification.docstatus != 1:
            frappe.throw(
                _(
                    "Submit the Company Classification certificate before assigning it to a Vehicle."
                )
            )
        if classification.expiry_date and getdate(classification.expiry_date) < getdate(
            today()
        ):
            frappe.throw(
                _("The selected Company Classification certificate has expired.")
            )
        if not classification.company:
            frappe.throw(
                _(
                    "Assign the Company Classification to a Company before using it on a Vehicle."
                )
            )
        if self.company and classification.company != self.company:
            frappe.throw(
                _("Company Classification must belong to the Vehicle Company.")
            )

    def _validate_chassis(self):
        if self.chassis_no and len(str(self.chassis_no)) < 10:
            frappe.throw(_("Chassis Number seems too short — please verify"))

    def _set_defaults(self):
        from sotrama.tp.settings import get_tp_company_setting, get_tp_setting

        if not self.vehicle_status:
            self.vehicle_status = "Active"
        if not self.fuel_type:
            self.fuel_type = "Diesel"

        if not self.company:
            self.company = get_tp_setting("default_company")
        if not self.company_classification:
            self.company_classification = get_tp_company_setting(
                self.company, "default_company_classification", "Vehicle"
            )
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
        """When a vehicle is cancelled, mark it out of service."""
        frappe.db.set_value("Vehicle", self.name, "vehicle_status", "Out of Service")
