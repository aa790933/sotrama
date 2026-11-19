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
        self._validate_odometer()
        self._validate_labour_lines()
        self._calculate_totals()
        self._validate_maintenance_schedule()

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

        vehicle = (
            frappe.db.get_value(
                "Vehicle", self.vehicle, ["company", "cost_center"], as_dict=True
            )
            if self.vehicle
            else None
        )
        vehicle_company = vehicle.company if vehicle else None
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
            or get_tp_company_setting(self.company, "default_cost_center")
        )

        if self.company and self.cost_center:
            cost_center_company = frappe.db.get_value(
                "Cost Center", self.cost_center, "company"
            )
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
            "job_type": self.job_type,
            "status": "Active",
            "docstatus": 1,
        }
        if self.maintenance_schedule:
            schedule = frappe.db.get_value(
                "Maintenance Schedule",
                self.maintenance_schedule,
                ["vehicle", "job_type", "status", "docstatus"],
                as_dict=True,
            )
            if not schedule or any(
                (
                    schedule.vehicle != self.vehicle,
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

        schedules = frappe.get_all(
            "Maintenance Schedule",
            filters=schedule_filters,
            fields=["name"],
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
            self.maintenance_schedule = schedules[0].name

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
                continue

            employee = frappe.db.get_value(
                "Employee",
                row.mechanic,
                ["company", "employee_name"],
                as_dict=True,
            )
            if not employee:
                frappe.throw(
                    _("Employee {0} on labour row {1} does not exist.").format(
                        row.mechanic, row.idx
                    )
                )
            if self.company and employee.company and employee.company != self.company:
                frappe.throw(
                    _(
                        "Employee {0} on labour row {1} belongs to Company {2}, not {3}."
                    ).format(row.mechanic, row.idx, employee.company, self.company)
                )
            row.mechanic_name = employee.employee_name

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
            if not row.item or not frappe.db.exists("Item", row.item):
                frappe.throw(
                    _("Select a valid Item for maintenance part row {0}.").format(
                        row.idx
                    )
                )
            if not frappe.db.get_value("Item", row.item, "is_stock_item"):
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

        warehouse = vehicle.parts_warehouse or get_tp_company_setting(
            company, "default_parts_warehouse"
        )
        if not warehouse:
            frappe.throw(
                _(
                    "Set a Parts Warehouse on Vehicle {0} or in TP Settings before issuing stock."
                ).format(vehicle.name)
            )

        warehouse_company = frappe.db.get_value(
            "Warehouse", warehouse, ["company", "is_group", "disabled"], as_dict=True
        )
        if not warehouse_company or warehouse_company.company != company:
            frappe.throw(
                _("Warehouse {0} does not belong to company {1}.").format(
                    warehouse, company
                )
            )
        if warehouse_company.is_group or warehouse_company.disabled:
            frappe.throw(_("Parts Warehouse must be an enabled leaf Warehouse."))

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.company = company
        stock_entry.set_posting_time = 1
        stock_entry.posting_date = self.job_date or frappe.utils.today()

        for row in self.parts_used:
            if not row.item or not frappe.db.exists("Item", row.item):
                frappe.throw(_("Select a valid stock Item in the Parts Used table."))
            if not frappe.db.get_value("Item", row.item, "is_stock_item"):
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


def _validate_workshop_employee_lookup_access(company):
    """Allow fleet roles to see only names for a Company they can operate."""
    frappe.only_for(["System Manager", "Fleet Manager", "Workshop"])
    if not isinstance(company, str) or not company.strip():
        frappe.throw(_("A valid Company is required to search workshop Employees."))

    company = company.strip()
    if not (
        frappe.has_permission("Maintenance Job Card", "write")
        or frappe.has_permission("Maintenance Job Card", "create")
    ):
        frappe.throw(
            _("You do not have permission to add Employees to a Maintenance Job Card."),
            frappe.PermissionError,
        )

    visible_vehicles = frappe.get_list(
        "Vehicle",
        filters={"company": company},
        fields=["name"],
        limit_page_length=1,
    )
    if not visible_vehicles:
        frappe.throw(
            _("You do not have access to the fleet of Company {0}.").format(company),
            frappe.PermissionError,
        )


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
    if not company:
        return []

    _validate_workshop_employee_lookup_access(company)
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
def get_workshop_employee_name(employee, company):
    """Return only the display name of an active Employee in an accessible Company."""
    if not employee or not company:
        frappe.throw(_("Select an Employee and Company."))
    _validate_workshop_employee_lookup_access(company)
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
