"""Shared fleet validation rules for cross-linked operational records."""

import frappe
from frappe import _
from frappe.utils import getdate, today

from sotrama.tp.settings import get_tp_setting


def validate_linked_document_read_permission(doctype: str, docname: str | None):
    """Require read access to the exact linked record under Frappe's permission rules."""
    if docname:
        frappe.has_permission(doctype, "read", doc=docname, throw=True)


def validate_active_driver(driver_name: str, company: str | None = None):
    """Validate that a driver can be assigned to a vehicle or work task.

    Medical and safety-training expiry blocking are site policies, not assumed
    statutory rules; they are opt-in in TP Settings. Driving-licence blocking
    is a configurable policy and remains off by default for mixed fleets that
    include off-road equipment operators. Regulated transport always performs
    its separate mandatory current-licence checks.
    """
    validate_linked_document_read_permission("Driver", driver_name)
    driver = frappe.db.get_value(
        "Driver",
        driver_name,
        [
            "status",
            "company",
            "employee",
            "docstatus",
            "license_class",
            "license_expiry",
            "medical_expiry",
            "safety_training_expiry",
            "professional_certificate",
            "professional_certificate_number",
        ],
        as_dict=True,
    )
    if not driver:
        frappe.throw(_("Driver {0} does not exist.").format(driver_name))

    if driver.company:
        from sotrama.tp.settings import validate_company_access

        validate_company_access(driver.company, "Driver")

    if driver.status != "Active" or driver.docstatus != 1:
        frappe.throw(
            _(
                "Driver {0} must be a submitted, Active Driver before assignment."
            ).format(driver_name)
        )

    if company and driver.company and driver.company != company:
        frappe.throw(
            _("Driver {0} belongs to a different Company.").format(driver_name)
        )

    if driver.employee and get_tp_setting(
        "require_active_employee_for_active_driver", 1
    ):
        from sotrama.tp.settings import validate_company_access

        if driver.company:
            validate_company_access(driver.company, "Employee")
        employee = frappe.db.get_value(
            "Employee",
            {"name": driver.employee, "company": driver.company},
            ["company", "status"],
            as_dict=True,
        )
        if (
            not employee
            or employee.status != "Active"
            or employee.company != driver.company
        ):
            frappe.throw(
                _(
                    "Driver {0} cannot be assigned under the current employment policy. Ask an HR Manager to review the linked Employee record."
                ).format(driver_name)
            )

    checks = (
        ("license_expiry", "block_expired_driver_license", 0, _("driving licence")),
        (
            "medical_expiry",
            "block_expired_medical_certificate",
            0,
            _("medical fitness certificate"),
        ),
        (
            "safety_training_expiry",
            "block_expired_safety_training",
            0,
            _("safety training certificate"),
        ),
    )
    current_date = getdate(today())
    for fieldname, setting, default, label in checks:
        expiry_date = driver.get(fieldname)
        if (
            expiry_date
            and getdate(expiry_date) < current_date
            and get_tp_setting(setting, default)
        ):
            if fieldname == "medical_expiry":
                frappe.throw(
                    _(
                        "Driver {0} cannot be assigned under the current HR compliance policy. Ask an HR Manager to review the restricted records."
                    ).format(driver_name)
                )
            frappe.throw(
                _("Driver {0} has an expired {1} ({2}).").format(
                    driver_name, label, expiry_date
                )
            )

    return driver


def validate_professional_transport_certificate(driver_name: str, transport_kind: str):
    """Enforce Road Code 26-09 Articles 79–80 for regulated transport work.

    The law applies by transport activity, not by a guessed mapping from the
    driver's licence category. Medical and screening review dates are entered
    from the competent provider/implementing regulations; no interval is
    invented here.
    """
    regulated_activities = {
        "Transport collectif de personnes",
        "Transport scolaire",
        "Transport de marchandises",
        "Transport de matières dangereuses",
        "Transport par taxi",
    }
    if transport_kind not in regulated_activities:
        return

    validate_linked_document_read_permission("Driver", driver_name)
    driver = frappe.get_doc("Driver", driver_name)
    if driver.company:
        from sotrama.tp.settings import validate_company_access

        validate_company_access(driver.company, "Driver")
    if (
        not driver.license_number
        or not driver.license_class
        or not driver.license_expiry
    ):
        frappe.throw(
            _(
                "Driver {0} must have a current driving licence number, category and expiry recorded by HR before regulated transport."
            ).format(driver_name)
        )
    if getdate(driver.license_expiry) < getdate(today()):
        frappe.throw(
            _(
                "Driver {0} does not have a current driving licence for regulated transport."
            ).format(driver_name)
        )

    # This setting controls the additional professional certificate and
    # medical/screening evidence policy only. A current road-driving licence
    # remains mandatory for every regulated transport activity.
    if not get_tp_setting("require_professional_certificate_for_transport", 1):
        return

    if not (driver.professional_certificate or driver.professional_certificate_number):
        frappe.throw(
            _("Driver {0} requires a Brevet Professionnel for {1}.").format(
                driver_name, transport_kind
            )
        )

    records = sorted(
        (
            row
            for row in (driver.compliance_records or [])
            if row.check_type in ("Medical Fitness Examination", "Drug Screening")
        ),
        key=lambda row: (getdate(row.test_date), row.idx),
        reverse=True,
    )
    latest_by_type = {}
    for record in records:
        latest_by_type.setdefault(record.check_type, record)

    for check_type, expected_result in (
        ("Medical Fitness Examination", "Fit"),
        ("Drug Screening", "Negative"),
    ):
        record = latest_by_type.get(check_type)
        if not record:
            frappe.throw(
                _(
                    "Driver {0} does not have current professional-transport compliance clearance. Ask an HR Manager to review the restricted records."
                ).format(driver_name)
            )
        if record.result != expected_result:
            frappe.throw(
                _(
                    "Driver {0} does not have current professional-transport compliance clearance. Ask an HR Manager to review the restricted records."
                ).format(driver_name)
            )
        current_date = getdate(today())
        if (
            not record.test_date
            or getdate(record.test_date) > current_date
            or not record.valid_until
            or getdate(record.valid_until) < current_date
            or getdate(record.valid_until) < getdate(record.test_date)
        ):
            frappe.throw(
                _(
                    "Driver {0} does not have current professional-transport compliance clearance. Ask an HR Manager to review the restricted records."
                ).format(driver_name)
            )


def get_vehicle_status_before_out_of_service(vehicle_name: str):
    """Preserve the original non-OOS state across overlapping failure causes."""
    current_status = frappe.db.get_value("Vehicle", vehicle_name, "vehicle_status")
    if current_status != "Out of Service":
        return current_status

    causes = []
    causes.extend(
        frappe.get_all(
            "Breakdown Incident",
            filters={
                "vehicle": vehicle_name,
                "docstatus": 1,
                "status": ["not in", ["Resolved", "Closed"]],
            },
            fields=["creation", "previous_vehicle_status"],
            limit_page_length=0,
        )
    )
    causes.extend(
        frappe.get_all(
            "Vehicle Inspection",
            filters={
                "vehicle": vehicle_name,
                "docstatus": 1,
                "has_critical_defect": 1,
                "critical_defect_cleared_by": ["is", "not set"],
            },
            fields=["creation", "previous_vehicle_status"],
            limit_page_length=0,
        )
    )

    for cause in sorted(causes, key=lambda row: row.creation):
        previous_status = cause.previous_vehicle_status
        if previous_status and previous_status != "Out of Service":
            return previous_status

    return current_status


def get_open_vehicle_safety_holds(
    vehicle_name: str,
    cancelled_doctype: str | None = None,
    cancelled_name: str | None = None,
):
    """Return unresolved breakdown and safety-critical inspection records."""
    if not vehicle_name:
        return {"breakdown": None, "critical_inspection": None}

    breakdown_filters = {
        "vehicle": vehicle_name,
        "docstatus": 1,
        "status": ["not in", ["Resolved", "Closed"]],
    }
    inspection_filters = {
        "vehicle": vehicle_name,
        "docstatus": 1,
        "has_critical_defect": 1,
        "critical_defect_cleared_by": ["is", "not set"],
    }
    if cancelled_name and cancelled_doctype == "Breakdown Incident":
        breakdown_filters["name"] = ["!=", cancelled_name]
    if cancelled_name and cancelled_doctype == "Vehicle Inspection":
        inspection_filters["name"] = ["!=", cancelled_name]

    return {
        "breakdown": frappe.db.exists("Breakdown Incident", breakdown_filters),
        "critical_inspection": frappe.db.exists(
            "Vehicle Inspection", inspection_filters
        ),
    }


def prevent_submitted_fleet_record_deletion(doc, method=None):
    """Preserve submitted/cancelled Fleet records as an operational audit trail."""
    if doc.docstatus != 0:
        frappe.throw(
            _(
                "Submitted or cancelled Fleet records cannot be deleted. Keep the audit history and use the document's controlled status or cancellation workflow."
            )
        )


def restore_vehicle_status_when_clear(
    vehicle_name: str,
    fallback_status: str | None,
    cancelled_doctype: str | None = None,
    cancelled_name: str | None = None,
):
    """Restore a vehicle only after every active breakdown/critical defect clears."""
    if not vehicle_name:
        return

    holds = get_open_vehicle_safety_holds(
        vehicle_name, cancelled_doctype, cancelled_name
    )
    current_status = frappe.db.get_value("Vehicle", vehicle_name, "vehicle_status")
    if not any(holds.values()) and current_status == "Out of Service":
        frappe.db.set_value(
            "Vehicle",
            vehicle_name,
            "vehicle_status",
            fallback_status or "Active",
        )
