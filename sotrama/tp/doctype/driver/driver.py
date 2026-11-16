import frappe
from frappe import _
from frappe.model.document import Document


class Driver(Document):
    """
    Driver — master record for every driver in the fleet.
    Tracks license, certifications, safety record, and assignments.
    """

    def validate(self):
        self._validate_license()
        self._validate_name()

    def _validate_license(self):
        if not self.license_number:
            frappe.throw(_("License Number is required"))
        if self.license_expiry and self.license_expiry < frappe.utils.today():
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