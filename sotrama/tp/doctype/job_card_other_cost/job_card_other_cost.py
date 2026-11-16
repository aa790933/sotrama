
import frappe
from frappe import _
from frappe.model.document import Document


class JobCardOtherCost(Document):
    """Child table — incidental costs (tow, rental, etc.) on a job card."""

    def validate(self):
        if not self.amount:
            frappe.throw(_("Amount is required"))