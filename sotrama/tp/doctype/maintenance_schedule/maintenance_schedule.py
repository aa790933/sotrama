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
        self._set_company_from_vehicle()
        self._validate_interval()

    def _set_company_from_vehicle(self):
        if not self.vehicle:
            return

        vehicle_company = frappe.db.get_value("Vehicle", self.vehicle, "company")
        if self.company and vehicle_company and self.company != vehicle_company:
            frappe.throw(_("Maintenance Schedule Company must match the Vehicle Company."))
        self.company = vehicle_company or self.company

    def on_submit(self):
        self._create_next_occurrence()

    def _validate_interval(self):
        if not self.schedule_type:
            frappe.throw(_("Schedule Type is required"))
        if self.schedule_type == "Calendar" and (
            self.interval_months is None or self.interval_months <= 0
        ):
            frappe.throw(_("Interval Months must be greater than zero for a Calendar schedule."))
        if self.schedule_type == "Mileage" and (
            self.interval_km is None or self.interval_km <= 0
        ):
            frappe.throw(_("Interval KM must be greater than zero for a Mileage schedule."))

    def _create_next_occurrence(self):
        """Generate the next Maintenance Schedule based on interval."""
        if not self.vehicle or not self.job_type:
            return

        # Only auto-generate if this schedule was just completed
        if self.status != "Completed":
            return

        if self.next_schedule and frappe.db.exists("Maintenance Schedule", self.next_schedule):
            return

        next_sched = frappe.new_doc("Maintenance Schedule")
        next_sched.vehicle = self.vehicle
        next_sched.company = self.company
        next_sched.schedule_type = self.schedule_type
        next_sched.job_type = self.job_type
        next_sched.interval_months = self.interval_months
        next_sched.interval_km = self.interval_km
        next_sched.last_service_date = self.last_service_date
        next_sched.last_service_odometer = self.last_service_odometer
        next_sched.last_service_job_card = self.last_service_job_card

        if self.schedule_type == "Calendar" and self.interval_months:
            next_sched.next_due_date = add_months(
                self.last_service_date or today(), self.interval_months
            )
        elif (
            self.schedule_type == "Mileage"
            and self.interval_km
            and self.last_service_odometer is not None
        ):
            next_sched.next_due_odometer = self.last_service_odometer + self.interval_km

        next_sched.status = "Active"
        next_sched.insert(ignore_permissions=True)
        next_sched.submit()
        self.db_set("next_schedule", next_sched.name)


@frappe.whitelist()
def update_maintenance_schedule_status(name, status):
    """Apply a permission-checked operational transition to a submitted plan."""
    transitions = {
        "Active": {"Paused", "Completed"},
        "Paused": {"Active", "Completed"},
        "Completed": set(),
    }
    schedule = frappe.get_doc("Maintenance Schedule", name)
    schedule.check_permission("write")
    if schedule.docstatus != 1:
        frappe.throw(_("Only submitted Maintenance Schedules can change operational status."))
    if schedule.status == status:
        return {"status": status, "next_schedule": schedule.next_schedule}
    if status not in transitions.get(schedule.status, set()):
        frappe.throw(
            _("Maintenance Schedule cannot change from {0} to {1}.").format(
                schedule.status, status
            )
        )

    previous_status = schedule.status
    if (
        status == "Completed"
        and schedule.schedule_type == "Mileage"
        and schedule.last_service_odometer is None
    ):
        frappe.throw(
            _("Record the last service odometer before completing a mileage-based schedule.")
        )

    schedule.db_set("status", status)
    schedule.reload()
    if status == "Completed":
        schedule._create_next_occurrence()
    schedule.add_comment(
        "Edit",
        _("Maintenance Schedule status changed from {0} to {1}.").format(
            previous_status, status
        ),
    )
    return {"status": status, "next_schedule": schedule.next_schedule}
