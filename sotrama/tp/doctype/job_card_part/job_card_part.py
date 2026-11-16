from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class JobCardPart(Document):
    """Child table — parts consumed on a maintenance job card."""

    def validate(self):
        if self.item and self.quantity and self.rate:
            self.amount = self.quantity * self.rate
        if self.quantity and not self.item:
            frappe.throw(_("Item is required when quantity is specified"))


class JobCardLabour(Document):
    """Child table — labour lines on a maintenance job card."""

    def validate(self):
        if self.hours and self.rate:
            self.amount = self.hours * self.rate
        if self.hours and not self.mechanic:
            frappe.throw(_("Mechanic is required when hours are specified"))


class JobCardOtherCost(Document):
    """Child table — incidental costs (tow, rental, etc.) on a job card."""

    def validate(self):
        if not self.amount:
            frappe.throw(_("Amount is required"))


class JobCardPhoto(Document):
    """Child table — photos attached to a job card."""

    def validate(self):
        if not self.photo:
            frappe.throw(_("Photo is required"))


class BreakdownPhoto(Document):
    """Child table — photos attached to a breakdown incident."""

    def validate(self):
        if not self.photo:
            frappe.throw(_("Photo is required"))


class InspectionItem(Document):
    """Child table — individual checklist items on a vehicle inspection."""

    def validate(self):
        if not self.category:
            frappe.throw(_("Category is required"))
        if not self.item_details:
            frappe.throw(_("Item Details is required"))