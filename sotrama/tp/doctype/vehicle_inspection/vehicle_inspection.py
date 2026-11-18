import frappe
from frappe import _
from frappe.model.document import Document


class VehicleInspection(Document):
    """
    Vehicle Inspection — structured checklist for pre-use, periodic,
    and post-incident inspections. Each inspection item has a status
    (Okay/Defective), remarks, and optional photo proof.
    """

    def validate(self):
        self._set_company_from_vehicle()
        self._validate_items()
        self._calculate_defects()
        self._validate_follow_up()

    def _set_company_from_vehicle(self):
        if not self.vehicle:
            return

        vehicle_company = frappe.db.get_value("Vehicle", self.vehicle, "company")
        if self.company and vehicle_company and self.company != vehicle_company:
            frappe.throw(_("Inspection Company must match the Vehicle Company."))
        self.company = vehicle_company or self.company

        if self.driver:
            driver_company = frappe.db.get_value("Driver", self.driver, "company")
            if driver_company and self.company and driver_company != self.company:
                frappe.throw(_("Inspection Driver must belong to the Vehicle Company."))

    def on_submit(self):
        self._create_defect_issues()
        self._clear_followed_up_inspection()
        self._update_vehicle_status()
        if self.follow_up_of and not self.has_critical_defect:
            self._restore_vehicle_status()

    def before_submit(self):
        if self.vehicle:
            from sotrama.tp.validation import get_vehicle_status_before_out_of_service

            self.previous_vehicle_status = get_vehicle_status_before_out_of_service(self.vehicle)

    def on_cancel(self):
        if self._reopen_followed_up_inspection():
            return
        self._restore_vehicle_status()

    def _validate_follow_up(self):
        if not self.follow_up_of:
            return
        if self.follow_up_of == self.name:
            frappe.throw(_("An inspection cannot be a follow-up of itself."))

        previous = frappe.get_doc("Vehicle Inspection", self.follow_up_of)
        if previous.docstatus != 1 or not previous.has_critical_defect:
            frappe.throw(_("Select a submitted inspection with an unresolved safety-critical defect."))
        if previous.vehicle != self.vehicle:
            frappe.throw(_("Follow-up Inspection and original Inspection must use the same Vehicle."))
        if previous.critical_defect_cleared_by and previous.critical_defect_cleared_by != self.name:
            frappe.throw(_("The selected critical inspection has already been cleared by another follow-up."))
        if self.has_critical_defect or self.overall_status != "Pass":
            frappe.throw(_("A follow-up can clear a critical defect only when its overall result is Pass and it has no critical defects."))

    def _clear_followed_up_inspection(self):
        if self.follow_up_of and not self.has_critical_defect:
            frappe.db.set_value(
                "Vehicle Inspection",
                self.follow_up_of,
                "critical_defect_cleared_by",
                self.name,
            )

    def _reopen_followed_up_inspection(self):
        if not self.follow_up_of or not frappe.db.exists("Vehicle Inspection", self.follow_up_of):
            return False

        previous = frappe.get_doc("Vehicle Inspection", self.follow_up_of)
        if (
            previous.docstatus == 1
            and previous.has_critical_defect
            and previous.critical_defect_cleared_by == self.name
        ):
            previous.db_set("critical_defect_cleared_by", None)
            frappe.db.set_value("Vehicle", self.vehicle, "vehicle_status", "Out of Service")
            return True
        return False

    def _validate_items(self):
        for row in self.inspection_items or []:
            if row.status == "Defective" and not row.remarks:
                frappe.throw(
                    _("Remarks required for defective item: {0}").format(row.category)
                )

    def _calculate_defects(self):
        self.total_defects = sum(
            1 for row in (self.inspection_items or [])
            if row.status == "Defective"
        )
        critical_terms = (
            "mechanical", "brak", "steer", "tyre", "tire", "chassis",
            "technical inspection", "frein", "direction", "pneumatique",
            "moteur", "hydraulique", "structure",
        )
        self.has_critical_defect = int(any(
            row.status == "Defective"
            and (
                row.is_safety_critical
                or any(term in (row.category or "").casefold() for term in critical_terms)
            )
            for row in (self.inspection_items or [])
        ))

    def _create_defect_issues(self):
        """For each defective item, auto-create an ERPNext Issue."""
        for row in self.inspection_items or []:
            if row.status == "Defective" and not row.linked_issue:
                issue = frappe.new_doc("Issue")
                issue.subject = _("[Vehicle Inspection] {0} — {1}").format(
                    self.vehicle, row.category
                )
                issue.description = _(
                    "Created from Vehicle Inspection {0}.\n\n{1}"
                ).format(self.name, row.remarks)
                if self.company:
                    issue.company = self.company
                issue.insert(ignore_permissions=True)
                row.db_set("linked_issue", issue.name)

    def _update_vehicle_status(self):
        """If critical defects found, mark vehicle Out of Service."""
        if self.has_critical_defect and self.vehicle:
            frappe.db.set_value(
                "Vehicle", self.vehicle, "vehicle_status", "Out of Service"
            )

    def _restore_vehicle_status(self):
        from sotrama.tp.validation import restore_vehicle_status_when_clear

        restore_vehicle_status_when_clear(
            self.vehicle,
            self.previous_vehicle_status,
            "Vehicle Inspection",
            self.name,
        )
