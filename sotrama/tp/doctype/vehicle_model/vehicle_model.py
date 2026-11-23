import frappe
from frappe import _
from frappe.model.document import Document


class VehicleModel(Document):
    """Vehicle Model — specific model under a make (e.g. Actros 2646)."""

    def before_naming(self):
        self.model_name = (self.model_name or "").strip()
        self._set_vehicle_make_from_legacy()

    def autoname(self):
        if not self.vehicle_make or not self.model_name:
            return
        make_name = frappe.db.get_value(
            "Vehicle Make", self.vehicle_make, "make_name"
        ) or self.vehicle_make
        self.name = f"{make_name.strip()}-{self.model_name}"

    def validate(self):
        if not self.model_name:
            frappe.throw(_("Model Name is required"))
        self._set_vehicle_make_from_legacy()
        if not self.vehicle_make:
            frappe.throw(_("Select a Vehicle Make for this Model."))

        duplicate = frappe.db.get_value(
            "Vehicle Model",
            {
                "vehicle_make": self.vehicle_make,
                "model_name": self.model_name,
            },
            "name",
        )
        if duplicate and (self.is_new() or duplicate != self.name):
            frappe.throw(
                _(
                    "A model with this name already exists for the selected Vehicle Make."
                )
            )

        previous = self.get_doc_before_save()
        make_changed = (
            not previous
            or getattr(self, "_action", None) == "submit"
            or previous.vehicle_make != self.vehicle_make
        )
        self.make = self.vehicle_make
        if not make_changed:
            return

        from sotrama.tp.validation import validate_linked_document_read_permission

        validate_linked_document_read_permission("Vehicle Make", self.vehicle_make)
        make = frappe.db.get_value(
            "Vehicle Make",
            self.vehicle_make,
            ["active"],
            as_dict=True,
        )
        if not make or not make.active:
            frappe.throw(_("Select an active Vehicle Make."))

    def _set_vehicle_make_from_legacy(self):
        if self.vehicle_make or not self.make:
            return
        legacy_make = self.make
        self.vehicle_make = frappe.db.get_value(
            "Vehicle Make", {"make_name": legacy_make}, "name"
        ) or (
            legacy_make
            if frappe.db.exists("Vehicle Make", legacy_make)
            else None
        )
