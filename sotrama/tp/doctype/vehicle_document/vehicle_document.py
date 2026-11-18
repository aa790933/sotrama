
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_days, getdate, today


class VehicleDocument(Document):
    """Child table — documents attached to a vehicle with expiry tracking."""

    def validate(self):
        if not self.document_type:
            frappe.throw(_("Document Type is required"))

        from sotrama.tp.settings import get_tp_setting

        configured_days = get_tp_setting("vehicle_document_alert_days", 30)
        alert_days = int(30 if configured_days is None else configured_days)
        if self.expiry_date and getdate(self.expiry_date) < getdate(today()):
            self.status = "Expired"
        elif self.expiry_date:
            if getdate(self.expiry_date) <= getdate(add_days(today(), alert_days)):
                self.status = "Expiring Soon"
            else:
                self.status = "Valid"
        else:
            self.status = "Pending"
