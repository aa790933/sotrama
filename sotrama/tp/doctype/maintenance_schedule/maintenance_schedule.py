import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_months, today


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
        if not self.vehicle or not self.job_type:
            return

        # Only auto-generate if this schedule was just completed
        if self.status != "Completed":
            return

        next_sched = frappe.new_doc("Maintenance Schedule")
        next_sched.vehicle = self.vehicle
        next_sched.schedule_type = self.schedule_type
        next_sched.job_type = self.job_type
        next_sched.interval_months = self.interval_months
        next_sched.interval_km = self.interval_km
        next_sched.last_service_date = self.last_service_date
        next_sched.last_service_odometer = self.last_service_odometer

        if self.schedule_type == "Calendar" and self.interval_months:
            next_sched.next_due_date = add_months(
                self.last_service_date or today(), self.interval_months
            )
        elif self.schedule_type == "Mileage" and self.interval_km and self.last_service_odometer:
            next_sched.next_due_odometer = self.last_service_odometer + self.interval_km

        next_sched.insert(ignore_permissions=True)