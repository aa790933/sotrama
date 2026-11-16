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
        self._validate_items()
        self._calculate_defects()

    def on_submit(self):
        self._create_defect_issues()
        self._update_vehicle_status()

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

    def _create_defect_issues(self):
        """For each defective item, auto-create an ERPNext Issue."""
        for row in self.inspection_items or []:
            if row.status == "Defective":
                issue = frappe.new_doc("Issue")
                issue.subject = _("[Vehicle Inspection] {0} — {1}").format(
                    self.vehicle, row.category
                )
                issue.description = _(
                    "Created from Vehicle Inspection {0}.\n\n{1}"
                ).format(self.name, row.remarks)
                company = frappe.db.get_value("Vehicle", self.vehicle, "company")
                if company:
                    issue.company = company
                issue.insert(ignore_permissions=True)

    def _update_vehicle_status(self):
        """If critical defects found, mark vehicle Out of Service."""
        has_critical = any(
            row.status == "Defective"
            and any(
                term in (row.category or "").casefold()
                for term in (
                    "mechanical", "brak", "steer", "tyre", "tire",
                    "chassis", "technical inspection",
                )
            )
            for row in (self.inspection_items or [])
        )
        if has_critical and self.vehicle:
            frappe.db.set_value(
                "Vehicle", self.vehicle, "vehicle_status", "Out of Service"
            )
