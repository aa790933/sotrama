import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate, today


class OperationalTask(Document):
    """
    Operational Task — links a vehicle to a specific work assignment
    (road paving, bridge construction, transport, etc.) with the
    staff members involved. Tracks planned vs actual hours, costs,
    and outputs.
    """

    def validate(self):
        self._validate_dates()
        self._validate_vehicle()
        from sotrama.tp.settings import validate_company_access

        validate_company_access(self.company, "Operational Task")
        self._validate_supervisor()
        self._calculate_actuals()

    def on_submit(self):
        self._update_vehicle_odometer()

    def before_submit(self):
        self._validate_transport_regulatory_applicability()

    def _validate_transport_regulatory_applicability(self):
        """Require an explicit, evidenced decision before regulated transport."""
        if self.task_type != "Transport":
            return

        if not self.transport_kind or self.transport_basis not in {
            "For-Hire Transport",
            "Own-Account Transport",
        }:
            frappe.throw(
                _(
                    "Select the Transport Activity and Transport Basis before submission."
                )
            )

        if self.transport_regulatory_status == "To Be Confirmed":
            frappe.throw(
                _(
                    "Confirm transport regulatory applicability with the competent authority before submitting this task."
                )
            )

        if self.transport_regulatory_status not in {
            "Regulated",
            "Officially Confirmed Not Subject",
        }:
            frappe.throw(_("Select a valid Regulatory Applicability decision."))

        authority_decision_required = (
            self.transport_basis == "Own-Account Transport"
            or self.transport_regulatory_status
            == "Officially Confirmed Not Subject"
        )
        if authority_decision_required and not all(
            (
                self.transport_authority_reference,
                self.transport_authority_decision_date,
                self.transport_authority_evidence,
            )
        ):
            frappe.throw(
                _(
                    "A written authority reference, decision date and evidence attachment are required for this transport applicability decision."
                )
            )

        if authority_decision_required and getdate(
            self.transport_authority_decision_date
        ) > getdate(today()):
            frappe.throw(_("The authority decision date cannot be in the future."))

        if authority_decision_required:
            self._validate_transport_authority_evidence()

        if self.transport_regulatory_status == "Regulated":
            if not self.driver:
                frappe.throw(_("A Driver is required for regulated transport."))
            from sotrama.tp.validation import (
                validate_professional_transport_certificate,
            )

            validate_professional_transport_certificate(
                self.driver, self.transport_kind
            )

    def _validate_transport_authority_evidence(self):
        """Require a real, readable File attached to this exact evidence field."""
        evidence_fields = ["name", "file_url"]
        if frappe.db.has_column("File", "is_remote_file"):
            evidence_fields.append("is_remote_file")
        evidence = frappe.db.get_value(
            "File",
            {
                "file_url": self.transport_authority_evidence,
                "attached_to_doctype": self.doctype,
                "attached_to_name": self.name,
                "attached_to_field": "transport_authority_evidence",
            },
            evidence_fields,
            as_dict=True,
        )
        if (
            not evidence
            or evidence.get("is_remote_file")
            or (evidence.get("file_url") or "").startswith(("http://", "https://"))
        ):
            frappe.throw(
                _(
                    "Authority evidence must be an uploaded file attached to this Operational Task, not a remote link or an arbitrary URL."
                )
            )
        frappe.has_permission("File", "read", doc=evidence.name, throw=True)

    def _validate_dates(self):
        if (
            self.start_date
            and self.end_date
            and get_datetime(self.end_date) < get_datetime(self.start_date)
        ):
            frappe.throw(_("End Date cannot be before Start Date"))

    def _calculate_actuals(self):
        if self.start_date and self.end_date:
            seconds = frappe.utils.time_diff_in_seconds(self.end_date, self.start_date)
            self.actual_hours = round(max(seconds, 0) / 3600, 2)
        if self.start_odometer is not None and self.end_odometer is not None:
            if self.end_odometer < self.start_odometer:
                frappe.throw(_("End Odometer cannot be less than Start Odometer"))
            self.distance_covered = round(self.end_odometer - self.start_odometer, 2)

    def _validate_supervisor(self):
        """A task supervisor must be active and belong to the task's Vehicle Company."""
        if not self.supervisor:
            return
        from sotrama.tp.doctype.maintenance_job_card.maintenance_job_card import (
            _validate_workshop_employee_lookup_access,
        )

        _validate_workshop_employee_lookup_access(self.company, "Operational Task")
        employee = frappe.db.get_value(
            "Employee",
            {"name": self.supervisor, "company": self.company},
            ["company", "status"],
            as_dict=True,
        )
        if not employee:
            frappe.throw(
                _("The Task Supervisor must be an Employee of the Vehicle Company.")
            )
        if employee.status != "Active":
            frappe.throw(_("The Task Supervisor must be an Active Employee."))
        if employee.company != self.company:
            frappe.throw(
                _("The Task Supervisor must be an Employee of the Vehicle Company.")
            )

    def _validate_vehicle(self):
        if not self.vehicle:
            frappe.throw(_("Vehicle is required"))
        if self.vehicle:
            from sotrama.tp.validation import validate_submitted_vehicle

            vehicle = validate_submitted_vehicle(
                self.vehicle, fields=("vehicle_status",)
            )
            if vehicle.company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(vehicle.company, "Vehicle")
            vehicle_status = vehicle.vehicle_status
            previous_getter = getattr(self, "get_doc_before_save", None)
            previous = previous_getter() if callable(previous_getter) else None
            vehicle_changed = (
                not previous
                or getattr(self, "_action", None) == "submit"
                or previous.vehicle != self.vehicle
            )
            unavailable_statuses = {
                "Out of Service",
                "Under Repair",
                "Retired",
                "Scrapped",
            }
            if vehicle_changed and vehicle_status in unavailable_statuses:
                frappe.throw(
                    _("Vehicle {0} cannot be assigned while its status is {1}.").format(
                        self.vehicle, vehicle_status
                    )
                )
            vehicle_company = vehicle.company
            if self.company and vehicle_company and self.company != vehicle_company:
                frappe.throw(
                    _("Operational Task Company must match its Vehicle Company.")
                )
            self.company = vehicle_company or self.company

        if self.project and self.company:
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission("Project", self.project)
            project_company = frappe.db.get_value("Project", self.project, "company")
            if project_company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(project_company, "Project")
            if project_company and project_company != self.company:
                frappe.throw(
                    _("Project {0} belongs to Company {1}, not {2}.").format(
                        self.project, project_company, self.company
                    )
                )

        if self.task_type != "Transport" and any(
            (
                self.transport_kind,
                self.transport_basis,
                self.transport_regulatory_status not in (None, "", "To Be Confirmed"),
                self.transport_authority_reference,
                self.transport_authority_decision_date,
                self.transport_authority_evidence,
            )
        ):
            frappe.throw(
                _("Transport regulatory fields can only be set for a Transport task.")
            )
        if self.task_type == "Transport" and (
            not self.transport_kind or not self.transport_basis
        ):
            frappe.throw(
                _("Select the Transport Activity and Transport Basis for this task.")
            )

        previous = self.get_doc_before_save()
        assignment_changed = not previous or any(
            previous.get(fieldname) != self.get(fieldname)
            for fieldname in ("vehicle", "driver", "task_type", "transport_kind")
        )
        if self.driver and (
            not previous
            or self.docstatus == 0
            or getattr(self, "_action", None) == "submit"
            or assignment_changed
        ):
            from sotrama.tp.validation import validate_active_driver

            validate_active_driver(self.driver, self.company)

    def _update_vehicle_odometer(self):
        """Keep the physical odometer monotonic; cancellation never rewinds it."""
        if not self.vehicle or self.end_odometer is None:
            return
        current = frappe.db.get_value("Vehicle", self.vehicle, "current_odometer") or 0
        if self.end_odometer > current:
            frappe.db.set_value(
                "Vehicle", self.vehicle, "current_odometer", self.end_odometer
            )
