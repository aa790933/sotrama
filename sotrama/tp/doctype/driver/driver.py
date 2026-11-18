import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class Driver(Document):
    """
    Driver — master record for every driver in the fleet.
    Tracks license, certifications, safety record, and assignments.
    """

    def validate(self):
        self._validate_license()
        self._validate_employee_link()
        self._validate_name()

    def _validate_license(self):
        if not self.license_number:
            frappe.throw(_("License Number is required"))
        if self.license_expiry and getdate(self.license_expiry) < getdate(today()):
            frappe.msgprint(
                title=_("Warning"),
                indicator="orange",
                message=_("Driver {0}: License has expired on {1}").format(
                    self.driver_name, self.license_expiry
                ),
            )

    def _validate_name(self):
        if not self.driver_name:
            frappe.throw(_("Driver Name is required"))

    def _validate_employee_link(self):
        from sotrama.tp.settings import get_tp_setting

        previous = self.get_doc_before_save()
        employee_link_changed = not previous or previous.employee != self.employee

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
            employee_data = frappe.db.get_value(
                "Employee", self.employee, ["company", "status"], as_dict=True
            )
            if not employee_data:
                frappe.throw(_("The Employee linked to this Driver no longer exists."))

        if (
            self.status == "Active"
            and get_tp_setting("require_active_employee_for_active_driver", 1)
            and employee_data.status != "Active"
        ):
            frappe.throw(
                _("This Driver cannot remain Active under the current employment policy. Ask an HR Manager to review the linked Employee record.")
            )

        if self.company and employee_data.company and self.company != employee_data.company:
            frappe.throw(
                _("Driver Company must match the linked Employee's Company ({0}).").format(
                    employee_data.company
                )
            )

        self.company = self.company or employee_data.company or get_tp_setting("default_company")

        if employee_link_changed:
            self.driver_name = self.driver_name or employee.employee_name
            self.phone = self.phone or employee.cell_number
            self.email = self.email or employee.company_email or employee.personal_email
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


@frappe.whitelist()
def update_driver_status(name, status):
    """Apply an audited, permission-checked transition to a submitted Driver."""
    transitions = {
        "Active": {"Suspended", "On Leave", "Terminated"},
        "Suspended": {"Active", "On Leave", "Terminated"},
        "On Leave": {"Active", "Suspended", "Terminated"},
        "Terminated": set(),
    }
    driver = frappe.get_doc("Driver", name)
    driver.check_permission("write")
    if driver.docstatus != 1:
        frappe.throw(_("Only submitted Driver records can change operational status."))
    if status == driver.status:
        return {"status": status}
    if status not in transitions.get(driver.status, set()):
        frappe.throw(
            _("Driver status cannot change from {0} to {1}.").format(driver.status, status)
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
