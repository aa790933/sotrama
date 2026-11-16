from __future__ import unicode_literals

import frappe
from frappe import _
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
        """
        Auto-post consumed parts as a Stock Entry on submit.
        Creates a Material Issue Stock Entry linking parts consumed
        during maintenance to the fleet warehouse.
        """
        if not self.parts_used:
            return

        vehicle = frappe.get_doc("Vehicle", self.vehicle)
        warehouse = vehicle.cost_center or frappe.get_value(
            "Company", frappe.defaults.get_user_default("Company"), "default_warehouse"
        )

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.company = frappe.defaults.get_user_default("Company")
        stock_entry.set_posting_time = 1
        stock_entry.posting_date = self.job_date or frappe.utils.today()

        for row in self.parts_used:
            stock_entry.append("items", {
                "item_code": row.item,
                "qty": row.quantity or 1,
                "s_warehouse": warehouse,
                "basic_rate": row.rate or 0,
                "expense_account": "Maintenance Expenses - COA",
            })

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()

    def _update_vehicle_odometer(self):
        """Update the linked Vehicle's current odometer."""
        if self.vehicle and self.odometer_after:
            frappe.db.set_value(
                "Vehicle", self.vehicle, "current_odometer", self.odometer_after
            )

    def _generate_next_schedule(self):
        """
        If this job is a scheduled service, create the next Maintenance Schedule
        occurrence based on the job type interval.
        """
        if not self.job_type or not self.vehicle:
            return

        vehicle = frappe.get_doc("Vehicle", self.vehicle)

        # Find existing active schedule for this vehicle + job type
        existing = frappe.get_all(
            "Maintenance Schedule",
            filters={
                "vehicle": self.vehicle,
                "job_type": self.job_type,
                "status": "Active",
            },
            fields=["name", "next_due_odometer"],
        )

        if existing:
            sched = frappe.get_doc("Maintenance Schedule", existing[0]["name"])
            sched.last_service_date = self.job_date
            sched.last_service_odometer = self.odometer_after or 0

            # Calculate next due based on mileage interval
            if sched.schedule_type == "Mileage" and sched.interval_km:
                sched.next_due_odometer = (self.odometer_after or 0) + sched.interval_km
            elif sched.schedule_type == "Calendar" and sched.interval_months:
                from frappe.utils import add_months
                sched.next_due_date = add_months(
                    self.job_date or frappe.utils.today(), sched.interval_months
                )

            sched.save(ignore_permissions=True)