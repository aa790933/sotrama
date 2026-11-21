import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, getdate, today

DRIVER_STATUS_TRANSITIONS = {
    "Active": {"Suspended", "On Leave", "Terminated"},
    "Suspended": {"Active", "On Leave", "Terminated"},
    "On Leave": {"Active", "Suspended", "Terminated"},
    "Terminated": set(),
}


class Driver(Document):
    """
    Driver — master record for every driver in the fleet.
    Tracks license, certifications, safety record, and assignments.
    """

    def validate(self):
        self._validate_license()
        self._validate_employee_link()
        from sotrama.tp.settings import validate_company_access

        validate_company_access(self.company, "Driver")
        self._validate_name()
        self._validate_status_transition()
        self._validate_company_ownership()
        self._validate_system_managed_fields()

    def _validate_system_managed_fields(self):
        previous = self.get_doc_before_save()
        if previous:
            if cint(self.total_incidents) != cint(previous.total_incidents):
                frappe.throw(
                    _(
                        "Total Incidents is calculated from submitted Breakdown Incidents."
                    )
                )
        elif cint(self.total_incidents):
            frappe.throw(
                _("Total Incidents is calculated from submitted Breakdown Incidents.")
            )

    def _validate_company_ownership(self):
        previous = self.get_doc_before_save()
        if (
            previous
            and previous.docstatus == 1
            and previous.company
            and previous.company != self.company
        ):
            frappe.throw(
                _(
                    "Driver Company cannot be changed after submission. Create a new Driver record for a new employing company to preserve HR and Fleet history."
                )
            )

    def _validate_status_transition(self):
        previous = self.get_doc_before_save()
        if not previous or previous.docstatus != 1 or previous.status == self.status:
            return
        if self.status not in DRIVER_STATUS_TRANSITIONS.get(previous.status, set()):
            frappe.throw(
                _("Driver status cannot change from {0} to {1}.").format(
                    previous.status, self.status
                )
            )

    def on_update_after_submit(self):
        previous = self.get_doc_before_save()
        if not previous or previous.status == self.status:
            return
        if self.status == "Active":
            from sotrama.tp.validation import validate_active_driver

            validate_active_driver(self.name, self.company)
        self.add_comment(
            "Edit",
            _("Driver status changed from {0} to {1}.").format(
                previous.status, self.status
            ),
        )

    def _validate_license(self):
        if self.license_expiry and getdate(self.license_expiry) < getdate(today()):
            frappe.msgprint(
                _("Driver {0}: License has expired on {1}").format(
                    self.driver_name, self.license_expiry
                ),
                title=_("Warning"),
                indicator="orange",
            )

    def _validate_name(self):
        if not self.driver_name:
            frappe.throw(_("Driver Name is required"))

    def _validate_employee_link(self):
        from sotrama.tp.settings import get_tp_setting

        previous = self.get_doc_before_save()
        employee_link_changed = not previous or previous.employee != self.employee

        if employee_link_changed and (
            self.employee or (previous and previous.employee)
        ):
            frappe.only_for(["System Manager", "HR Manager"])

        if not self.employee:
            self.company = self.company or get_tp_setting("default_company")
            if get_tp_setting("require_employee_link", 0):
                frappe.throw(_("Select an Employee from ERPNext / Frappe HR."))
            return

        if employee_link_changed:
            employee = frappe.get_doc("Employee", self.employee)
            employee.check_permission("read")
            employee_data = frappe._dict(
                company=employee.company,
                status=employee.status,
            )
        else:
            # Existing links may be maintained by Fleet users without granting
            # them ongoing read access to the Employee/HR record.
            if not self.company:
                frappe.throw(
                    _("Set the Driver Company before validating its Employee link.")
                )
            employee_data = frappe.db.get_value(
                "Employee",
                {"name": self.employee, "company": self.company},
                ["company", "status"],
                as_dict=True,
            )
            if not employee_data:
                frappe.throw(
                    _(
                        "The Employee linked to this Driver no longer exists in the Driver Company."
                    )
                )

        if employee_data.company:
            from sotrama.tp.settings import validate_company_access

            validate_company_access(employee_data.company, "Employee")

        if (
            self.status == "Active"
            and get_tp_setting("require_active_employee_for_active_driver", 1)
            and employee_data.status != "Active"
        ):
            frappe.throw(
                _(
                    "This Driver cannot remain Active under the current employment policy. Ask an HR Manager to review the linked Employee record."
                )
            )

        if (
            self.company
            and employee_data.company
            and self.company != employee_data.company
        ):
            frappe.throw(_("Driver Company must match the linked Employee's Company."))

        self.company = (
            self.company or employee_data.company or get_tp_setting("default_company")
        )

        if employee_link_changed:
            self.driver_name = self.driver_name or employee.employee_name
            # Fleet-visible contact fields must not inherit personal HR data.
            # HR can enter a company-approved operational number and email.
            self.email = self.email or employee.company_email
            self.hire_date = self.hire_date or employee.date_of_joining

        duplicate = frappe.db.exists(
            "Driver",
            {"employee": self.employee, "name": ("!=", self.name or "")},
        )
        if duplicate:
            frappe.throw(
                _("Employee {0} is already linked to Driver {1}.").format(
                    self.employee, duplicate
                )
            )


@frappe.whitelist(methods=["POST"])
def update_driver_status(name, status):
    """Apply an audited, permission-checked transition to a submitted Driver."""
    driver = frappe.get_doc("Driver", name)
    driver.check_permission("write")
    if driver.docstatus != 1:
        frappe.throw(_("Only submitted Driver records can change operational status."))
    if status == driver.status:
        return {"status": status}
    if status not in DRIVER_STATUS_TRANSITIONS.get(driver.status, set()):
        frappe.throw(
            _("Driver status cannot change from {0} to {1}.").format(
                driver.status, status
            )
        )

    previous_status = driver.status
    driver.db_set("status", status)
    driver.reload()
    if status == "Active":
        from sotrama.tp.validation import validate_active_driver

        validate_active_driver(driver.name, driver.company)
    driver.add_comment(
        "Edit",
        _("Driver status changed from {0} to {1}.").format(previous_status, status),
    )
    return {"status": status}
