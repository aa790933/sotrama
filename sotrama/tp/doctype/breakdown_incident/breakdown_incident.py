import frappe
from frappe import _
from frappe.model.document import Document


class BreakdownIncident(Document):
    """
    Breakdown Incident — records every unexpected vehicle failure.
    Triggers job cards, links to drivers, and feeds the reliability
    analytics dashboard.
    """

    def validate(self):
        self._validate_dates()
        self._calculate_downtime()

    def on_submit(self):
        self._create_job_card()
        self._update_driver_incident_count()
        self._set_vehicle_out_of_service()

    def before_cancel(self):
        self._restore_vehicle_status()

    # ------------------------------------------------------------------

    def _validate_dates(self):
        if self.incident_date and self.resolution_date:
            if self.resolution_date < self.incident_date:
                frappe.throw(_("Resolution Date cannot be before Incident Date"))

    def _calculate_downtime(self):
        if self.incident_date and self.resolution_date:
            delta = frappe.utils.time_diff_in_seconds(
                self.resolution_date, self.incident_date
            )
            self.downtime_hours = round(delta / 3600, 2)

    def _create_job_card(self):
        """Auto-create a maintenance job card linked to this breakdown."""
        existing = frappe.db.get_value(
            "Maintenance Job Card",
            {"linked_breakdown_incident": self.name},
        )
        if existing:
            if not self.linked_job_card:
                self.db_set("linked_job_card", existing)
            return

        if self.linked_job_card:
            return

        if self.vehicle:
            job_card = frappe.new_doc("Maintenance Job Card")
            job_card.vehicle = self.vehicle
            job_card.job_nature = "Breakdown"
            job_card.job_date = self.incident_date
            job_card.linked_breakdown_incident = self.name
            job_card.driver_at_time = self.driver
            job_card.reported_issue = self.description
            job_card.insert(ignore_permissions=True)
            self.db_set("linked_job_card", job_card.name)

    def _update_driver_incident_count(self):
        if self.driver:
            count = frappe.db.count(
                "Breakdown Incident",
                {"driver": self.driver, "docstatus": 1},
            )
            frappe.db.set_value("Driver", self.driver, "total_incidents", count)

    def _set_vehicle_out_of_service(self):
        if self.vehicle:
            current_status = frappe.db.get_value(
                "Vehicle", self.vehicle, "vehicle_status"
            )
            self.db_set("previous_vehicle_status", current_status)
            frappe.db.set_value(
                "Vehicle", self.vehicle, "vehicle_status", "Out of Service"
            )

    def _restore_vehicle_status(self):
        if self.vehicle:
            other_open_incidents = frappe.db.exists(
                "Breakdown Incident",
                {
                    "vehicle": self.vehicle,
                    "name": ["!=", self.name],
                    "docstatus": 1,
                    "status": ["not in", ["Resolved", "Closed"]],
                },
            )
            current_status = frappe.db.get_value(
                "Vehicle", self.vehicle, "vehicle_status"
            )
            if not other_open_incidents and current_status == "Out of Service":
                frappe.db.set_value(
                    "Vehicle",
                    self.vehicle,
                    "vehicle_status",
                    self.previous_vehicle_status or "Active",
                )
