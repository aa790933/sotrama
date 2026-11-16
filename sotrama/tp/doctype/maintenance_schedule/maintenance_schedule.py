from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class MaintenanceSchedule(Document):
    """
    Maintenance Schedule — defines recurring preventive maintenance
    for a vehicle. Supports both calendar-interval and mileage-interval
    rules. Auto-generates the next occurrence on completion.
    """

    def validate(self):
        self._validate_interval()

    def on_submit(self):
        self._create_next_occurrence()

    def _validate_interval(self):
        if not self.schedule_type:
            frappe.throw(_("Schedule Type is required"))
        if self.schedule_type == "Calendar" and not self.interval_months:
            frappe.throw(_("Interval Months is required for Calendar schedule"))
        if self.schedule_type == "Mileage" and not self.interval_km:
            frappe.throw(_("Interval KM is required for Mileage schedule"))

    def _create_next_occurrence(self):
        """Generate the next Maintenance Schedule based on interval."""
        if not self.vehicle:
            return
        # Logic: calculate next due date/km and create a new schedule
        # This is a placeholder — full implementation creates the next
        # schedule document with updated due_date / due_odometer.
        pass