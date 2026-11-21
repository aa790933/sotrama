import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class MaintenanceJobCard(Document):
    """
    Maintenance Job Card — the core work order for every repair,
    service, or maintenance event on a fleet vehicle.
    Tracks parts, labour, vendor, costs, and links to breakdowns.
    """

    def validate(self):
        self._validate_dates()
        self._set_company_and_cost_center()
        from sotrama.tp.settings import validate_company_access

        validate_company_access(self.company, "Maintenance Job Card")
        self._validate_breakdown_links()
        self._validate_odometer()
        self._validate_driver_at_time()
        self._validate_labour_lines()
        self._validate_other_costs()
        self._calculate_totals()
        self._validate_maintenance_schedule()
        self._validate_system_managed_fields()

    def on_submit(self):
        self._post_stock_entries()
        self._update_vehicle_odometer()
        self._generate_next_schedule()

    def on_cancel(self):
        self._cancel_stock_entry()
        self._restore_schedule_on_cancel()

    def before_submit(self):
        if self.status != "Completed":
            frappe.throw(
                _("Set the Maintenance Job Card status to Completed before submitting.")
            )
        self._check_parts_available()

    def _validate_system_managed_fields(self):
        fields = (
            "stock_entry",
            "linked_maintenance_schedule",
            "previous_schedule_last_service_date",
            "previous_schedule_last_service_odometer",
            "previous_schedule_last_service_job_card",
            "previous_schedule_next_due_date",
            "previous_schedule_next_due_odometer",
            "applied_schedule_last_service_odometer",
            "linked_breakdown",
            "linked_breakdown_incident",
        )
        previous = self.get_doc_before_save()
        if not previous:
            if any(self.get(fieldname) for fieldname in fields):
                allowed_breakdown_link = (
                    frappe.flags.get("in_breakdown_job_card_creation")
                    and self.linked_breakdown_incident
                    and not self.linked_breakdown
                    and not any(
                        self.get(fieldname)
                        for fieldname in fields
                        if fieldname != "linked_breakdown_incident"
                    )
                )
                if allowed_breakdown_link:
                    return
                frappe.throw(
                    _(
                        "Stock Entry and schedule history fields are managed by the maintenance workflow."
                    )
                )
            return
        for fieldname in fields:
            if self.get(fieldname) != previous.get(fieldname):
                frappe.throw(
                    _("{0} is managed by the maintenance workflow.").format(
                        frappe.get_meta(self.doctype).get_label(fieldname)
                    )
                )

    def _validate_breakdown_links(self):
        """Keep any breakdown reference within this Job Card's Vehicle and Company."""
        for fieldname in ("linked_breakdown", "linked_breakdown_incident"):
            incident_name = self.get(fieldname)
            if not incident_name:
                continue
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission(
                "Breakdown Incident", incident_name
            )
            incident = frappe.db.get_value(
                "Breakdown Incident",
                incident_name,
                ["company", "vehicle", "docstatus"],
                as_dict=True,
            )
            if not incident:
                frappe.throw(
                    _("Linked Breakdown Incident {0} does not exist.").format(
                        incident_name
                    )
                )
            if incident.company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(incident.company, "Breakdown Incident")
            if incident.company != self.company or incident.vehicle != self.vehicle:
                frappe.throw(
                    _(
                        "Linked Breakdown Incident must belong to the same Company and Vehicle as this Job Card."
                    )
                )
            if incident.docstatus != 1:
                frappe.throw(_("Linked Breakdown Incident must be submitted."))

    # ------------------------------------------------------------------

    def _validate_dates(self):
        if (
            self.job_date
            and self.completion_date
            and getdate(self.completion_date) < getdate(self.job_date)
        ):
            frappe.throw(_("Completion Date cannot be before Job Date"))

    def _set_company_and_cost_center(self):
        from sotrama.tp.settings import get_tp_company_setting, get_tp_setting

        if self.vehicle:
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission("Vehicle", self.vehicle)
        vehicle = (
            frappe.db.get_value(
                "Vehicle", self.vehicle, ["company", "cost_center"], as_dict=True
            )
            if self.vehicle
            else None
        )
        vehicle_company = vehicle.company if vehicle else None
        if vehicle_company:
            from sotrama.tp.settings import validate_company_access

            validate_company_access(vehicle_company, "Vehicle")
        if self.company and vehicle_company and self.company != vehicle_company:
            frappe.throw(
                _("Maintenance Job Card Company must match its Vehicle Company.")
            )
        self.company = (
            vehicle_company or self.company or get_tp_setting("default_company")
        )
        self.cost_center = (
            self.cost_center
            or (vehicle.cost_center if vehicle else None)
            or get_tp_company_setting(
                self.company, "default_cost_center", "Maintenance Job Card"
            )
        )

        if self.company and self.cost_center:
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission("Cost Center", self.cost_center)
            cost_center_company = frappe.db.get_value(
                "Cost Center", self.cost_center, "company"
            )
            if cost_center_company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(cost_center_company, "Cost Center")
            if cost_center_company and cost_center_company != self.company:
                frappe.throw(
                    _("Cost Center {0} does not belong to Company {1}.").format(
                        self.cost_center, self.company
                    )
                )

    def _validate_maintenance_schedule(self):
        if (
            self.job_nature != "Scheduled Service"
            or not self.vehicle
            or not self.job_type
        ):
            self.maintenance_schedule = None
            return

        schedule_filters = {
            "vehicle": self.vehicle,
            "company": self.company,
            "job_type": self.job_type,
            "status": "Active",
            "docstatus": 1,
        }
        if self.maintenance_schedule:
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission(
                "Maintenance Schedule", self.maintenance_schedule
            )
            schedule = frappe.db.get_value(
                "Maintenance Schedule",
                self.maintenance_schedule,
                ["vehicle", "job_type", "status", "docstatus", "company"],
                as_dict=True,
            )
            if not schedule:
                frappe.throw(
                    _(
                        "Select an active Maintenance Schedule matching this Vehicle and Job Type."
                    )
                )
            if schedule.company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(schedule.company, "Maintenance Schedule")
            if any(
                (
                    schedule.vehicle != self.vehicle,
                    schedule.company != self.company,
                    schedule.job_type != self.job_type,
                    schedule.status != "Active",
                    schedule.docstatus != 1,
                )
            ):
                frappe.throw(
                    _(
                        "Select an active Maintenance Schedule matching this Vehicle and Job Type."
                    )
                )
            return

        schedules = frappe.get_list(
            "Maintenance Schedule",
            filters=schedule_filters,
            fields=["name", "company"],
            order_by="creation desc",
            limit_page_length=2,
        )
        if len(schedules) > 1:
            frappe.throw(
                _(
                    "More than one active schedule exists for this Vehicle and Job Type. Select the schedule to complete."
                )
            )
        if schedules:
            from sotrama.tp.validation import validate_linked_document_read_permission

            schedule = schedules[0]
            validate_linked_document_read_permission(
                "Maintenance Schedule", schedule.name
            )
            if schedule.company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(schedule.company, "Maintenance Schedule")
            if schedule.company != self.company:
                frappe.throw(
                    _("The Maintenance Schedule must belong to the Job Card Company.")
                )
            self.maintenance_schedule = schedule.name

    def _validate_odometer(self):
        if (
            self.odometer_before is not None
            and self.odometer_after is not None
            and self.odometer_after < self.odometer_before
        ):
            frappe.throw(
                _(
                    "Odometer After ({0}) cannot be less than Odometer Before ({1})"
                ).format(self.odometer_after, self.odometer_before)
            )
        if self.vehicle and self.odometer_after is not None:
            current_odometer = (
                frappe.db.get_value("Vehicle", self.vehicle, "current_odometer") or 0
            )
            if self.odometer_after < current_odometer:
                frappe.throw(
                    _(
                        "Odometer After ({0}) cannot be lower than the vehicle's current reading ({1})."
                    ).format(self.odometer_after, current_odometer)
                )

    def _validate_labour_lines(self):
        """Keep workshop labour linked to Employees in the work order's Company."""
        for row in self.labour_lines or []:
            if row.hours is not None and row.hours <= 0:
                frappe.throw(
                    _("Labour hours must be greater than zero on row {0}.").format(
                        row.idx
                    )
                )
            if row.rate is not None and row.rate < 0:
                frappe.throw(
                    _("Labour rate cannot be negative on row {0}.").format(row.idx)
                )
            if not row.mechanic:
                row.mechanic_name = None
                continue
            _validate_workshop_employee_lookup_access(
                self.company, "Maintenance Job Card"
            )

            employee = frappe.db.get_value(
                "Employee",
                {"name": row.mechanic, "company": self.company},
                ["company", "employee_name"],
                as_dict=True,
            )
            if not employee:
                frappe.throw(
                    _(
                        "Employee {0} on labour row {1} does not exist in the Job Card Company."
                    ).format(row.mechanic, row.idx)
                )
            if employee.company != self.company:
                frappe.throw(
                    _("The selected Employee is not part of the Job Card Company.")
                )
            row.mechanic_name = employee.employee_name

    def _validate_other_costs(self):
        """Other Costs are expenses, so negative values must not reduce totals."""
        for row in self.other_costs or []:
            if row.amount is not None and row.amount < 0:
                frappe.throw(
                    _("Other cost amount cannot be negative on row {0}.").format(
                        row.idx
                    )
                )

    def _validate_driver_at_time(self):
        """Keep historical driver attribution within the Job Card Company."""
        if not self.driver_at_time:
            return
        from sotrama.tp.validation import validate_linked_document_read_permission

        validate_linked_document_read_permission("Driver", self.driver_at_time)
        driver = frappe.db.get_value(
            "Driver", self.driver_at_time, ["company"], as_dict=True
        )
        if not driver:
            frappe.throw(_("The Driver at Time of Issue does not exist."))
        if driver.company:
            from sotrama.tp.settings import validate_company_access

            validate_company_access(driver.company, "Driver")
        if self.company and driver.company and driver.company != self.company:
            frappe.throw(
                _("Driver at Time of Issue must belong to the Job Card Company.")
            )

    def _calculate_totals(self):
        total_parts = 0
        for row in self.parts_used or []:
            row.amount = (row.quantity or 0) * (row.rate or 0)
            total_parts += row.amount

        total_labour = 0
        for row in self.labour_lines or []:
            row.amount = (row.hours or 0) * (row.rate or 0)
            total_labour += row.amount

        total_other = 0
        for row in self.other_costs or []:
            total_other += row.amount or 0

        self.total_parts_cost = total_parts
        self.total_labour_cost = total_labour
        self.total_other_cost = total_other
        self.total_cost = total_parts + total_labour + total_other

    def _check_parts_available(self):
        for row in self.parts_used or []:
            if not row.item:
                frappe.throw(
                    _("Select a valid Item for maintenance part row {0}.").format(
                        row.idx
                    )
                )
            from sotrama.tp.validation import validate_linked_document_read_permission

            validate_linked_document_read_permission("Item", row.item)
            item = frappe.db.get_value(
                "Item", row.item, ["is_stock_item", "disabled"], as_dict=True
            )
            if not item:
                frappe.throw(
                    _("Select a valid Item for maintenance part row {0}.").format(
                        row.idx
                    )
                )
            if item.disabled:
                frappe.throw(
                    _("Disabled Item {0} cannot be used as a maintenance part.").format(
                        row.item
                    )
                )
            if not item.is_stock_item:
                frappe.throw(_("Item {0} is not a stock item.").format(row.item))
            if not row.quantity or row.quantity <= 0:
                frappe.throw(_("Part quantity must be greater than zero."))

            if row.rate is not None and row.rate < 0:
                frappe.throw(_("Part rate cannot be negative."))

    def _post_stock_entries(self):
        """
        Auto-post consumed parts as a Stock Entry on submit.
        Stock is issued only from an explicitly configured warehouse belonging
        to the vehicle's company. ERPNext resolves item valuation and accounts.
        """
        if not self.parts_used:
            return

        vehicle = frappe.get_doc("Vehicle", self.vehicle)
        company = self.company or vehicle.company
        if not company:
            frappe.throw(
                _(
                    "Set a Company on Vehicle {0} or in TP Settings before issuing stock."
                ).format(vehicle.name)
            )
        from sotrama.tp.settings import get_tp_company_setting
        from sotrama.tp.validation import validate_linked_document_read_permission

        warehouse = vehicle.parts_warehouse or get_tp_company_setting(
            company, "default_parts_warehouse", "Maintenance Job Card"
        )
        if not warehouse:
            frappe.throw(
                _(
                    "Set a Parts Warehouse on Vehicle {0} or in TP Settings before issuing stock."
                ).format(vehicle.name)
            )

        validate_linked_document_read_permission("Warehouse", warehouse)

        warehouse_company = frappe.db.get_value(
            "Warehouse", warehouse, ["company", "is_group", "disabled"], as_dict=True
        )
        if not warehouse_company or warehouse_company.company != company:
            frappe.throw(
                _("Warehouse {0} does not belong to company {1}.").format(
                    warehouse, company
                )
            )
        from sotrama.tp.settings import validate_company_access

        validate_company_access(warehouse_company.company, "Warehouse")
        if warehouse_company.is_group or warehouse_company.disabled:
            frappe.throw(_("Parts Warehouse must be an enabled leaf Warehouse."))

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.company = company
        stock_entry.set_posting_time = 1
        stock_entry.posting_date = self.job_date or frappe.utils.today()

        for row in self.parts_used:
            if not row.item:
                frappe.throw(_("Select a valid stock Item in the Parts Used table."))
            validate_linked_document_read_permission("Item", row.item)
            item = frappe.db.get_value(
                "Item", row.item, ["is_stock_item", "disabled"], as_dict=True
            )
            if not item:
                frappe.throw(_("Select a valid stock Item in the Parts Used table."))
            if item.disabled:
                frappe.throw(
                    _("Disabled Item {0} cannot be used as a maintenance part.").format(
                        row.item
                    )
                )
            if not item.is_stock_item:
                frappe.throw(_("Item {0} is not a stock item.").format(row.item))
            if not row.quantity or row.quantity <= 0:
                frappe.throw(_("Part quantity must be greater than zero."))
            stock_entry.append(
                "items",
                {
                    "item_code": row.item,
                    "qty": row.quantity,
                    "s_warehouse": warehouse,
                    "cost_center": self.cost_center,
                },
            )

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()
        self.db_set("stock_entry", stock_entry.name)

    def _cancel_stock_entry(self):
        """Cancel the linked stock issue together with its maintenance job card."""
        if not self.stock_entry or not frappe.db.exists(
            "Stock Entry", self.stock_entry
        ):
            return

        stock_entry = frappe.get_doc("Stock Entry", self.stock_entry)
        if stock_entry.docstatus == 1:
            stock_entry.cancel()

    def _update_vehicle_odometer(self):
        """Update the linked Vehicle's current odometer."""
        if self.vehicle and self.odometer_after is not None:
            current_odometer = (
                frappe.db.get_value("Vehicle", self.vehicle, "current_odometer") or 0
            )
            if self.odometer_after > current_odometer:
                frappe.db.set_value(
                    "Vehicle", self.vehicle, "current_odometer", self.odometer_after
                )

    def _generate_next_schedule(self):
        """
        If this job is a scheduled service, create the next Maintenance Schedule
        occurrence based on the job type interval.
        """
        if (
            self.job_nature != "Scheduled Service"
            or not self.job_type
            or not self.vehicle
        ):
            return

        if self.maintenance_schedule:
            sched = frappe.get_doc("Maintenance Schedule", self.maintenance_schedule)
            self.linked_maintenance_schedule = sched.name
            self.previous_schedule_last_service_date = sched.last_service_date
            self.previous_schedule_last_service_odometer = sched.last_service_odometer
            self.previous_schedule_last_service_job_card = sched.last_service_job_card
            self.previous_schedule_next_due_date = sched.next_due_date
            self.previous_schedule_next_due_odometer = sched.next_due_odometer
            service_odometer = self.odometer_after
            if service_odometer is None:
                service_odometer = frappe.db.get_value(
                    "Vehicle", self.vehicle, "current_odometer"
                )
            if service_odometer is None:
                service_odometer = sched.last_service_odometer
            self.applied_schedule_last_service_odometer = service_odometer
            self.db_set(
                {
                    "linked_maintenance_schedule": self.linked_maintenance_schedule,
                    "previous_schedule_last_service_date": self.previous_schedule_last_service_date,
                    "previous_schedule_last_service_odometer": self.previous_schedule_last_service_odometer,
                    "previous_schedule_last_service_job_card": self.previous_schedule_last_service_job_card,
                    "previous_schedule_next_due_date": self.previous_schedule_next_due_date,
                    "previous_schedule_next_due_odometer": self.previous_schedule_next_due_odometer,
                    "applied_schedule_last_service_odometer": self.applied_schedule_last_service_odometer,
                }
            )
            sched.last_service_date = self.job_date
            sched.last_service_odometer = service_odometer
            sched.last_service_job_card = self.name

            # Calculate next due based on mileage interval
            if (
                sched.schedule_type == "Mileage"
                and sched.interval_km
                and service_odometer is not None
            ):
                sched.next_due_odometer = service_odometer + sched.interval_km
            elif sched.schedule_type == "Calendar" and sched.interval_months:
                from frappe.utils import add_months

                sched.next_due_date = add_months(
                    self.job_date or frappe.utils.today(), sched.interval_months
                )

            frappe.db.set_value(
                "Maintenance Schedule",
                sched.name,
                {
                    "last_service_date": self.job_date,
                    "last_service_odometer": service_odometer,
                    "last_service_job_card": self.name,
                    "next_due_odometer": sched.next_due_odometer,
                    "next_due_date": sched.next_due_date,
                },
            )

    def _restore_schedule_on_cancel(self):
        if not self.linked_maintenance_schedule or not frappe.db.exists(
            "Maintenance Schedule", self.linked_maintenance_schedule
        ):
            return

        schedule = frappe.get_doc(
            "Maintenance Schedule", self.linked_maintenance_schedule
        )
        # Do not overwrite a newer service's schedule update.
        if schedule.last_service_job_card == self.name:
            schedule.db_set(
                {
                    "last_service_date": self.previous_schedule_last_service_date,
                    "last_service_odometer": self.previous_schedule_last_service_odometer,
                    "last_service_job_card": self.previous_schedule_last_service_job_card,
                    "next_due_date": self.previous_schedule_next_due_date,
                    "next_due_odometer": self.previous_schedule_next_due_odometer,
                }
            )


def _validate_workshop_employee_lookup_access(company, target_doctype):
    """Allow a limited Employee projection only for an authorized Fleet workflow."""
    frappe.only_for(["System Manager", "Fleet Manager", "Workshop"])
    if not isinstance(company, str) or not company.strip():
        frappe.throw(_("A valid Company is required to search workshop Employees."))

    company = company.strip()
    if target_doctype not in {
        "Maintenance Job Card",
        "Vehicle Inspection",
        "Operational Task",
    }:
        frappe.throw(
            _("Employee lookup is not available for this DocType."),
            frappe.PermissionError,
        )
    if not (
        frappe.has_permission(target_doctype, "write")
        or frappe.has_permission(target_doctype, "create")
    ):
        frappe.throw(
            _("You do not have permission to look up Employees for this Fleet record."),
            frappe.PermissionError,
        )

    from sotrama.tp.settings import validate_company_access

    validate_company_access(company, target_doctype)
    validate_company_access(company, "Employee")
    validate_company_access(company, "Vehicle")


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def search_workshop_employees(
    doctype, txt, searchfield, start, page_len, filters, **kwargs
):
    """Search only active employee names for the current accessible fleet Company.

    This deliberately avoids granting Fleet Manager or Workshop broad read
    access to HRMS Employee records and their personal information.
    """
    if doctype != "Employee":
        frappe.throw(_("This search is only for Frappe HR Employee records."))

    filters = frappe.parse_json(filters) if isinstance(filters, str) else filters
    if filters is None:
        filters = {}
    if not isinstance(filters, dict):
        frappe.throw(_("Invalid Employee search filters."))
    company = filters.get("company")
    target_doctype = filters.get("target_doctype")
    if not company:
        return []

    _validate_workshop_employee_lookup_access(company, target_doctype)
    company = company.strip()
    search_text = f"%{txt or ''}%"
    return frappe.get_all(
        "Employee",
        filters={"company": company, "status": "Active"},
        or_filters=[
            ["Employee", "name", "like", search_text],
            ["Employee", "employee_name", "like", search_text],
        ],
        fields=["name", "employee_name", "designation"],
        order_by="employee_name asc",
        start=start,
        page_length=page_len,
        as_list=True,
    )


@frappe.whitelist()
def get_workshop_employee_name(
    employee, company, target_doctype="Maintenance Job Card"
):
    """Return only the display name of an active Employee in an accessible Company."""
    if not employee or not company:
        frappe.throw(_("Select an Employee and Company."))
    _validate_workshop_employee_lookup_access(company, target_doctype)
    company = company.strip()
    employee_name = frappe.db.get_value(
        "Employee",
        {"name": employee, "company": company, "status": "Active"},
        "employee_name",
    )
    if not employee_name:
        frappe.throw(
            _("Select an active Employee belonging to Company {0}.").format(company)
        )
    return employee_name
