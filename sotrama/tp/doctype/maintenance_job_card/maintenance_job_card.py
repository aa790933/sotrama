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

    def on_cancel(self):
        self._cancel_stock_entry()

    def before_submit(self):
        if self.status != "Completed":
            frappe.throw(_("Set the Maintenance Job Card status to Completed before submitting."))
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
        if self.vehicle and self.odometer_after:
            current_odometer = frappe.db.get_value(
                "Vehicle", self.vehicle, "current_odometer"
            ) or 0
            if self.odometer_after < current_odometer:
                frappe.throw(
                    _("Odometer After ({0}) cannot be lower than the vehicle's current reading ({1}).").format(
                        self.odometer_after, current_odometer
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
            if not row.item or not frappe.db.exists("Item", row.item):
                frappe.throw(_("Select a valid Item for maintenance part row {0}.").format(row.idx))
            if not frappe.db.get_value("Item", row.item, "is_stock_item"):
                frappe.throw(_("Item {0} is not a stock item.").format(row.item))
            if not row.quantity or row.quantity <= 0:
                frappe.throw(_("Part quantity must be greater than zero."))

    def _post_stock_entries(self):
        """
        Auto-post consumed parts as a Stock Entry on submit.
        Stock is issued only from an explicitly configured warehouse belonging
        to the vehicle's company. ERPNext resolves item valuation and accounts.
        """
        if not self.parts_used:
            return

        vehicle = frappe.get_doc("Vehicle", self.vehicle)
        if not vehicle.company:
            frappe.throw(
                _("Set a Company on Vehicle {0} before issuing stock.").format(vehicle.name)
            )
        if not vehicle.parts_warehouse:
            frappe.throw(
                _("Set a Parts Warehouse on Vehicle {0} before issuing stock.").format(
                    vehicle.name
                )
            )

        warehouse_company = frappe.db.get_value(
            "Warehouse", vehicle.parts_warehouse, "company"
        )
        if warehouse_company != vehicle.company:
            frappe.throw(
                _("Warehouse {0} does not belong to company {1}.").format(
                    vehicle.parts_warehouse, vehicle.company
                )
            )

        stock_entry = frappe.new_doc("Stock Entry")
        stock_entry.stock_entry_type = "Material Issue"
        stock_entry.company = vehicle.company
        stock_entry.set_posting_time = 1
        stock_entry.posting_date = self.job_date or frappe.utils.today()

        for row in self.parts_used:
            if not row.item or not frappe.db.exists("Item", row.item):
                frappe.throw(_("Select a valid stock Item in the Parts Used table."))
            if not frappe.db.get_value("Item", row.item, "is_stock_item"):
                frappe.throw(_("Item {0} is not a stock item.").format(row.item))
            if not row.quantity or row.quantity <= 0:
                frappe.throw(_("Part quantity must be greater than zero."))
            stock_entry.append("items", {
                "item_code": row.item,
                "qty": row.quantity,
                "s_warehouse": vehicle.parts_warehouse,
            })

        stock_entry.insert(ignore_permissions=True)
        stock_entry.submit()
        self.db_set("stock_entry", stock_entry.name)

    def _cancel_stock_entry(self):
        """Cancel the linked stock issue together with its maintenance job card."""
        if not self.stock_entry or not frappe.db.exists("Stock Entry", self.stock_entry):
            return

        stock_entry = frappe.get_doc("Stock Entry", self.stock_entry)
        if stock_entry.docstatus == 1:
            stock_entry.cancel()

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

            frappe.db.set_value(
                "Maintenance Schedule",
                sched.name,
                {
                    "last_service_date": self.job_date,
                    "last_service_odometer": self.odometer_after or 0,
                    "next_due_odometer": sched.next_due_odometer,
                    "next_due_date": sched.next_due_date,
                },
            )
