from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class MaintenanceJobType(Document):
    """
    Maintenance Job Type — master for categorising maintenance jobs
    (e.g. Oil Change, Brake Service, Transmission Service).
    Grouped into categories for reporting.
    """

    def validate(self):
        if not self.job_category:
            frappe.throw(_("Job Category is required"))