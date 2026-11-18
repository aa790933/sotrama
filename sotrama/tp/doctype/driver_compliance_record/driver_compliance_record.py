import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class DriverComplianceRecord(Document):
    """Restricted HR record of medical fitness and drug-screening checks."""

    def validate(self):
        allowed_results = {
            "Medical Fitness Examination": {"Fit", "Unfit"},
            "Drug Screening": {"Negative", "Positive", "Pending"},
        }
        if self.result not in allowed_results.get(self.check_type, set()):
            frappe.throw(_("Select a result that matches the compliance check type."))
        if self.test_date and getdate(self.test_date) > getdate(today()):
            frappe.throw(_("Examination Date cannot be in the future."))
        if self.valid_until and self.test_date and getdate(self.valid_until) < getdate(self.test_date):
            frappe.throw(_("Review / Valid Until cannot be before the Examination Date."))
        if not (self.reference_number or self.evidence):
            frappe.throw(_("Provide a certificate/reference number or attach the supporting evidence."))
