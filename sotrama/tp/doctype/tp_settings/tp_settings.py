import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class TPSettings(Document):
    """Central configuration for fleet-wide defaults and operational policies."""

    def validate(self):
        self._validate_company_defaults()

        for fieldname in (
            "driver_document_alert_days",
            "vehicle_document_alert_days",
            "maintenance_due_alert_days",
        ):
            days = self.get(fieldname)
            if days is not None and (int(days) < 0 or int(days) > 3650):
                frappe.throw(_("{0} must be between 0 and 3650 days.").format(self.meta.get_label(fieldname)))

        if not self.default_company:
            if any((
                self.default_company_classification,
                self.default_parts_warehouse,
                self.default_cost_center,
                self.default_department,
            )):
                frappe.throw(
                    _("Select a Default Company before setting a default Warehouse, Cost Center or Department.")
                )
            return

        if self.default_company_classification:
            classification = frappe.db.get_value(
                "Company Classification",
                self.default_company_classification,
                ["active", "company", "docstatus", "expiry_date"],
                as_dict=True,
            )
            if not classification or not classification.active:
                frappe.throw(_("Default Company Classification must be active."))
            if classification.docstatus != 1:
                frappe.throw(_("Default Company Classification must be submitted."))
            if classification.expiry_date and getdate(classification.expiry_date) < getdate(frappe.utils.today()):
                frappe.throw(_("Default Company Classification certificate has expired."))
            if classification.company and classification.company != self.default_company:
                frappe.throw(
                    _("Default Company Classification must belong to the Default Company.")
                )

        if self.default_parts_warehouse:
            warehouse = frappe.db.get_value(
                "Warehouse",
                self.default_parts_warehouse,
                ["company", "is_group", "disabled"],
                as_dict=True,
            )
            if not warehouse:
                frappe.throw(_("Default Parts Warehouse does not exist."))
            if warehouse.company != self.default_company:
                frappe.throw(
                    _("Default Parts Warehouse must belong to the Default Company.")
                )
            if warehouse.is_group or warehouse.disabled:
                frappe.throw(
                    _("Default Parts Warehouse must be an enabled leaf Warehouse.")
                )

        if self.default_cost_center:
            cost_center = frappe.db.get_value(
                "Cost Center",
                self.default_cost_center,
                ["company", "is_group", "disabled"],
                as_dict=True,
            )
            if not cost_center:
                frappe.throw(_("Default Cost Center does not exist."))
            if cost_center.company != self.default_company:
                frappe.throw(
                    _("Default Cost Center must belong to the Default Company.")
                )
            if cost_center.is_group or cost_center.disabled:
                frappe.throw(
                    _("Default Cost Center must be an enabled leaf Cost Center.")
                )

        if self.default_department:
            department_company = frappe.db.get_value(
                "Department", self.default_department, "company"
            )
            if department_company and department_company != self.default_company:
                frappe.throw(
                    _("Default Department must belong to the Default Company.")
                )

    def _validate_company_defaults(self):
        seen_companies = set()
        for row in self.company_defaults or []:
            if not row.company:
                frappe.throw(_("Company is required in each Company Defaults row."))
            if row.company in seen_companies:
                frappe.throw(
                    _("Company {0} has more than one TP defaults row.").format(row.company)
                )
            seen_companies.add(row.company)

            if not row.active:
                continue

            if row.company_classification:
                classification = frappe.db.get_value(
                    "Company Classification",
                    row.company_classification,
                    ["active", "company", "docstatus", "expiry_date"],
                    as_dict=True,
                )
                if not classification or not classification.active:
                    frappe.throw(
                        _("Company Classification in row {0} must be active.").format(row.idx)
                    )
                if classification.docstatus != 1:
                    frappe.throw(
                        _("Company Classification in row {0} must be submitted.").format(row.idx)
                    )
                if classification.expiry_date and getdate(classification.expiry_date) < getdate(frappe.utils.today()):
                    frappe.throw(
                        _("Company Classification in row {0} has expired.").format(row.idx)
                    )
                if classification.company and classification.company != row.company:
                    frappe.throw(
                        _("Company Classification in row {0} belongs to another Company.").format(row.idx)
                    )

            if row.default_department:
                department_company = frappe.db.get_value(
                    "Department", row.default_department, "company"
                )
                if department_company and department_company != row.company:
                    frappe.throw(
                        _("Department in Company Defaults row {0} belongs to another Company.").format(row.idx)
                    )

            if row.default_cost_center:
                cost_center = frappe.db.get_value(
                    "Cost Center",
                    row.default_cost_center,
                    ["company", "is_group", "disabled"],
                    as_dict=True,
                )
                if (
                    not cost_center
                    or cost_center.company != row.company
                    or cost_center.is_group
                    or cost_center.disabled
                ):
                    frappe.throw(
                        _("Cost Center in Company Defaults row {0} must be an enabled leaf Cost Center for that Company.").format(row.idx)
                    )

            if row.default_parts_warehouse:
                warehouse = frappe.db.get_value(
                    "Warehouse",
                    row.default_parts_warehouse,
                    ["company", "is_group", "disabled"],
                    as_dict=True,
                )
                if (
                    not warehouse
                    or warehouse.company != row.company
                    or warehouse.is_group
                    or warehouse.disabled
                ):
                    frappe.throw(
                        _("Parts Warehouse in Company Defaults row {0} must be an enabled leaf Warehouse for that Company.").format(row.idx)
                    )
