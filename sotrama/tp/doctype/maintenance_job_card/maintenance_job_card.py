from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class MaintenanceJobCard(Document):
    """
    Maintenance Job Card — the core work order for every repair,
    service, or maintenance event on a fleet vehicle.
    Tracks parts, labour, vendor, costs, and links to breakdowns.
    """

    def validate(self):
        self._validate_dates()
        self._validate_odometer()
        self._calculate_totals()

    def on_submit(self):
        self._post_stock_entries()
        self._update_vehicle_odometer()
        self._generate_next_schedule()

    def before_submit(self):
        self._check_parts_available()

    # ------------------------------------------------------------------

    def _validate_dates(self):
        if self.job_date and self.completion_date:
            if self.completion_date < self.job_date:
                frappe.throw(_("Completion Date cannot be before Job Date"))

    def _validate_odometer(self):
        if self.odometer_before and self.odometer_after:
            if self.odometer_after < self.odometer_before:
                frappe.throw(
                    _("Odometer After ({0}) cannot be less than Odometer Before ({1})").format(
                        self.odometer_after, self.odometer_before
                    )
                )

    def _calculate_totals(self):
        total_parts = 0
        for row in self.parts_used or []:
            total_parts += (row.quantity or 0) * (row.rate or 0)

        total_labour = 0
        for row in self.labour_lines or []:
            total_labour += (row.hours or 0) * (row.rate or 0)

        total_other = 0
        for row in self.other_costs or []:
            total_other += row.amount or 0

        self.total_parts_cost = total_parts
        self.total_labour_cost = total_labour
        self.total_other_cost = total_other
        self.total_cost = total_parts + total_labour + total_other

    def _check_parts_available(self):
        for row in self.parts_used or []:
            if row.item and not frappe.db.exists(
                "Item", row.item
            ):
                frappe.msgprint(
                    title=_("Warning"),
                    indicator="orange",
                    message=_("Item {0} not found in ERPNext Item master").format(row.item),
                )

    def _post_stock_entries(self):
        """Auto-post consumed parts as a Stock Entry on submit."""
        if not self.parts_used:
            return
        # Placeholder — full implementation creates a Stock Entry
        # with warehouse, item, qty, and serial/batch tracking.
        pass

    def _update_vehicle_odometer(self):
        """Update the linked Vehicle's current odometer."""
        if self.vehicle and self.odometer_after:
            frappe.db.set_value(
                "Vehicle", self.vehicle, "current_odometer", self.odometer_after
            )

    def _generate_next_schedule(self):
        """If this job is a scheduled service, create the next Maintenance Schedule."""
        if self.job_type and self.vehicle:
            # Logic to find/create next schedule based on job_type interval
            pass