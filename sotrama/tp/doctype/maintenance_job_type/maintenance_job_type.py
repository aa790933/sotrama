
import frappe
from frappe import _
from frappe.model.document import Document


class MaintenanceJobType(Document):
    """
    Maintenance Job Type — master for categorising maintenance jobs
    (e.g. Oil Change, Brake Service, Transmission Service).
    Grouped into categories for reporting.
    """

    def before_naming(self):
        self.job_type_name = (self.job_type_name or "").strip()

    def validate(self):
        if not self.job_type_name:
            frappe.throw(_("Job Type Name is required"))
        if not self.job_category:
            frappe.throw(_("Job Category is required"))
