from frappe.model.document import Document
from frappe.utils import add_days, getdate, today


class VehicleDocument(Document):
    """Vehicle document row in the parent Vehicle's renewal register."""


def get_vehicle_document_status(expiry_date, alert_days=30, reference_date=None):
    """Return the current status for a vehicle document's expiry date."""
    if not expiry_date:
        return "Pending"

    current_date = getdate(reference_date or today())
    expiry = getdate(expiry_date)
    days = 30 if alert_days is None else max(0, int(alert_days))
    threshold = getdate(add_days(current_date, days))

    if expiry < current_date:
        return "Expired"
    if expiry <= threshold:
        return "Expiring Soon"
    return "Valid"


def refresh_vehicle_document_statuses():
    """Backfill status values for existing Vehicle Document rows after migrate."""
    import frappe

    if not frappe.db.table_exists("Vehicle Document"):
        return 0

    from sotrama.tp.settings import get_tp_setting

    alert_days = get_tp_setting("vehicle_document_alert_days", 30)
    documents = frappe.get_all(
        "Vehicle Document",
        filters={"parenttype": "Vehicle", "parentfield": "vehicle_documents"},
        fields=["name", "expiry_date", "status"],
        limit_page_length=0,
    )
    changed = 0
    for document in documents:
        status = get_vehicle_document_status(document.expiry_date, alert_days)
        if document.status == status:
            continue
        frappe.db.set_value(
            "Vehicle Document",
            document.name,
            "status",
            status,
            update_modified=False,
        )
        changed += 1
    return changed
