import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class SotramaPayrollRule(Document):
    def validate(self):
        if self.effective_to and getdate(self.effective_to) < getdate(self.effective_from):
            frappe.throw("Effective To must be on or after Effective From")

        if self.active_for_calculation and self.status != "Approved":
            frappe.throw("Only an approved legal rule can be active for calculation")

        if self.status == "Approved" and not (self.legal_source or self.source_url):
            frappe.throw("An approved rule must reference an official legal source")
