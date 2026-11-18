import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime


class BreakdownIncident(Document):
    """
    Breakdown Incident — records every unexpected vehicle failure.
    Triggers job cards, links to drivers, and feeds the reliability
    analytics dashboard.
    """

    def validate(self):
        self._clear_resolution_when_reopened()
        self._validate_dates()
        self._set_company_from_vehicle()
        self._calculate_downtime()

    def on_submit(self):
        self._create_job_card()
        self._update_driver_incident_count()
        self._set_vehicle_out_of_service()

    def on_update_after_submit(self):
        """Keep vehicle availability synchronized with a submitted incident."""
        previous = self.get_doc_before_save()
        if not previous or previous.status == self.status:
            return

        self._sync_vehicle_after_status_change(previous.status)

    def _sync_vehicle_after_status_change(self, previous_status):
        """Apply status transitions to the vehicle without overwriting prior causes."""
        if previous_status == self.status:
            return

        if self.status in ("Resolved", "Closed"):
            self._restore_vehicle_status()
        else:
            # Reopening a resolved incident must reuse its original fallback
            # status, not capture the vehicle's current (possibly changed) state.
            self._set_vehicle_out_of_service(preserve_previous=True)

    def before_cancel(self):
        self._restore_vehicle_status()

    def on_cancel(self):
        self._update_driver_incident_count()

    # ------------------------------------------------------------------

    def _validate_dates(self):
        if self.status in ("Resolved", "Closed") and not self.resolution_date:
            frappe.throw(_("Set a Resolution Date before marking the breakdown Resolved or Closed."))
        if (
            self.incident_date
            and self.resolution_date
            and get_datetime(self.resolution_date) < get_datetime(self.incident_date)
        ):
            frappe.throw(_("Resolution Date cannot be before Incident Date"))

    def _clear_resolution_when_reopened(self):
        previous = self.get_doc_before_save()
        if (
            previous
            and previous.status in ("Resolved", "Closed")
            and self.status not in ("Resolved", "Closed")
        ):
            self.resolution_date = None
            self.resolution_notes = None

    def _set_company_from_vehicle(self):
        if not self.vehicle:
            return

        vehicle = frappe.db.get_value(
            "Vehicle", self.vehicle, ["company", "primary_driver"], as_dict=True
        )
        if not vehicle:
            frappe.throw(_("Selected Vehicle does not exist."))

        previous = self.get_doc_before_save()
        if self.company and vehicle.company and self.company != vehicle.company:
            frappe.throw(_("Breakdown Company must match the Vehicle Company."))
        self.company = vehicle.company or self.company
        if not previous and not self.driver:
            self.driver = vehicle.primary_driver

        if self.driver:
            driver_company = frappe.db.get_value("Driver", self.driver, "company")
            if not frappe.db.exists("Driver", self.driver):
                frappe.throw(_("Selected Driver does not exist."))
            if driver_company and self.company and driver_company != self.company:
                frappe.throw(_("Breakdown Driver must belong to the Vehicle Company."))

    def _calculate_downtime(self):
        if self.incident_date and self.resolution_date:
            delta = frappe.utils.time_diff_in_seconds(
                self.resolution_date, self.incident_date
            )
            self.downtime_hours = round(delta / 3600, 2)
        else:
            self.downtime_hours = 0

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
            job_card.company = self.company
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

    def _set_vehicle_out_of_service(self, preserve_previous=False):
        if self.vehicle:
            from sotrama.tp.validation import get_vehicle_status_before_out_of_service

            previous_status = self.previous_vehicle_status if preserve_previous else None
            if not previous_status:
                previous_status = get_vehicle_status_before_out_of_service(self.vehicle)
                self.db_set("previous_vehicle_status", previous_status)
            frappe.db.set_value(
                "Vehicle", self.vehicle, "vehicle_status", "Out of Service"
            )

    def _restore_vehicle_status(self):
        from sotrama.tp.validation import restore_vehicle_status_when_clear

        restore_vehicle_status_when_clear(
            self.vehicle,
            self.previous_vehicle_status,
            "Breakdown Incident",
            self.name,
        )


@frappe.whitelist()
def update_breakdown_status(name, status, resolution_date=None, resolution_notes=None):
    """Perform an audited, permission-checked transition on a submitted incident."""
    allowed_statuses = {"Reported", "Acknowledged", "In Progress", "Resolved", "Closed"}
    if status not in allowed_statuses:
        frappe.throw(_("Invalid Breakdown Incident status."))

    incident = frappe.get_doc("Breakdown Incident", name)
    incident.check_permission("write")
    if incident.docstatus != 1:
        frappe.throw(_("Only submitted Breakdown Incidents can change operational status."))

    previous_status = incident.status
    if previous_status == status:
        return {"status": status}

    transitions = {
        "Reported": {"Acknowledged", "In Progress", "Resolved"},
        "Acknowledged": {"In Progress", "Resolved"},
        "In Progress": {"Resolved"},
        "Resolved": {"Closed", "Reported", "In Progress"},
        "Closed": {"Reported", "In Progress"},
    }
    if status not in transitions.get(previous_status, set()):
        frappe.throw(
            _("Status cannot change from {0} to {1}.").format(previous_status, status)
        )

    updates = {"status": status}
    if status == "Resolved":
        if not resolution_date:
            frappe.throw(_("Resolution Date is required to resolve a Breakdown Incident."))
        resolution_datetime = frappe.utils.get_datetime(resolution_date)
        incident_datetime = frappe.utils.get_datetime(incident.incident_date)
        if resolution_datetime < incident_datetime:
            frappe.throw(_("Resolution Date cannot be before Incident Date."))
        updates.update({
            "resolution_date": resolution_datetime,
            "resolution_notes": resolution_notes,
            "downtime_hours": round(
                frappe.utils.time_diff_in_seconds(resolution_datetime, incident_datetime) / 3600,
                2,
            ),
        })
    elif status in {"Reported", "In Progress"} and previous_status in {"Resolved", "Closed"}:
        updates.update({"resolution_date": None, "resolution_notes": None, "downtime_hours": 0})

    incident.db_set(updates)
    incident.reload()
    incident._sync_vehicle_after_status_change(previous_status)
    incident.add_comment(
        "Edit",
        _("Operational status changed from {0} to {1}.").format(previous_status, status),
    )
    return {"status": status}
