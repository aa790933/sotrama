import frappe
from frappe import _
from frappe.model.document import Document

STANDARD_INSPECTION_CHECKS = (
    {
        "category": "Documents réglementaires",
        "item_details": "Carte grise, assurance, visite technique en cours de validité, vignette et autorisations applicables.",
        "is_safety_critical": 0,
    },
    {
        "category": "Freinage et direction",
        "item_details": "Frein de service, frein de stationnement, flexibles, fuites, direction, jeu et assistance.",
        "is_safety_critical": 1,
    },
    {
        "category": "Pneumatiques et suspension",
        "item_details": "État des pneus, sculptures, pression, écrous, roues, suspension et lames.",
        "is_safety_critical": 1,
    },
    {
        "category": "Moteur et transmission",
        "item_details": "Démarrage, moteur, boîte, embrayage, transmission, refroidissement, échappement et fuites.",
        "is_safety_critical": 1,
    },
    {
        "category": "Hydraulique et équipement TP",
        "item_details": "Vérins, flexibles, distributeurs, pompe hydraulique, stabilisateurs et organes de travail.",
        "is_safety_critical": 1,
    },
    {
        "category": "Électricité et signalisation",
        "item_details": "Batterie, alternateur, éclairage, feux stop, clignotants, gyrophare, avertisseur et alarme de recul.",
        "is_safety_critical": 1,
    },
    {
        "category": "Cabine et sécurité",
        "item_details": "Ceinture, rétroviseurs, vitrage, essuie-glaces, extincteur, trousse de secours et triangles.",
        "is_safety_critical": 1,
    },
    {
        "category": "Châssis et structure",
        "item_details": "Châssis, soudures, benne, attelage, crochets, garde-boue et fixations.",
        "is_safety_critical": 1,
    },
    {
        "category": "Niveaux et environnement",
        "item_details": "Huile moteur, liquide de refroidissement, frein, carburant, AdBlue si applicable et absence de fuites au sol.",
        "is_safety_critical": 0,
    },
)


class VehicleInspection(Document):
    """
    Vehicle Inspection — structured checklist for pre-use, periodic,
    and post-incident inspections. Each inspection item has a status
    (Not Checked/Okay/Defective), remarks, and optional photo proof.
    """

    def validate(self):
        self._set_company_from_vehicle()
        self._validate_supervisor()
        self._validate_items()
        self._calculate_defects()
        self._validate_follow_up()
        self._validate_system_managed_fields()

    def _set_company_from_vehicle(self):
        if not self.vehicle:
            return

        from sotrama.tp.validation import validate_linked_document_read_permission

        validate_linked_document_read_permission("Vehicle", self.vehicle)
        vehicle_company = frappe.db.get_value("Vehicle", self.vehicle, "company")
        if vehicle_company:
            from sotrama.tp.settings import validate_company_access

            validate_company_access(vehicle_company, "Vehicle")
        if self.company and vehicle_company and self.company != vehicle_company:
            frappe.throw(_("Inspection Company must match the Vehicle Company."))
        self.company = vehicle_company or self.company
        from sotrama.tp.settings import validate_company_access

        validate_company_access(self.company, "Vehicle Inspection")

        if self.driver:
            validate_linked_document_read_permission("Driver", self.driver)
            driver = frappe.db.get_value(
                "Driver", self.driver, ["company", "status"], as_dict=True
            )
            if not driver:
                frappe.throw(_("The Inspection Driver does not exist."))
            if driver.company:
                from sotrama.tp.settings import validate_company_access

                validate_company_access(driver.company, "Driver")
            if driver.company and self.company and driver.company != self.company:
                frappe.throw(_("Inspection Driver must belong to the Vehicle Company."))
            if self.inspection_type != "Post-Incident" and driver.status != "Active":
                frappe.throw(
                    _("Only an Active Driver can be assigned to this inspection type.")
                )

    def _validate_supervisor(self):
        """A supervisor must be an active Employee of the inspected Vehicle Company."""
        if not self.supervisor:
            return
        from sotrama.tp.doctype.maintenance_job_card.maintenance_job_card import (
            _validate_workshop_employee_lookup_access,
        )

        _validate_workshop_employee_lookup_access(self.company, "Vehicle Inspection")
        employee = frappe.db.get_value(
            "Employee",
            {"name": self.supervisor, "company": self.company},
            ["company", "status"],
            as_dict=True,
        )
        if not employee:
            frappe.throw(
                _(
                    "The Inspection Supervisor must be an Employee of the Vehicle Company."
                )
            )
        if employee.status != "Active":
            frappe.throw(_("The Inspection Supervisor must be an Active Employee."))
        if employee.company != self.company:
            frappe.throw(
                _(
                    "The Inspection Supervisor must be an Employee of the Vehicle Company."
                )
            )

    def on_submit(self):
        self._create_defect_issues()
        self._clear_followed_up_inspection()
        self._update_vehicle_status()
        if self.follow_up_of and not self.has_critical_defect:
            self._restore_vehicle_status()

    def before_submit(self):
        self._validate_items(require_completed=True)
        self._calculate_defects()
        self._validate_follow_up_result()
        if self.vehicle:
            from sotrama.tp.validation import get_vehicle_status_before_out_of_service

            self.previous_vehicle_status = get_vehicle_status_before_out_of_service(
                self.vehicle
            )

    def before_cancel(self):
        if self.has_critical_defect:
            frappe.throw(
                _(
                    "A submitted inspection with a safety-critical defect cannot be cancelled. Complete a successful follow-up inspection to clear the vehicle safety hold."
                )
            )

    def on_cancel(self):
        if self._reopen_followed_up_inspection():
            return
        self._restore_vehicle_status()

    def _validate_follow_up(self):
        if not self.follow_up_of:
            return
        if self.follow_up_of == self.name:
            frappe.throw(_("An inspection cannot be a follow-up of itself."))

        from sotrama.tp.validation import validate_linked_document_read_permission

        validate_linked_document_read_permission(
            "Vehicle Inspection", self.follow_up_of
        )
        previous = frappe.get_doc("Vehicle Inspection", self.follow_up_of)
        if previous.company:
            from sotrama.tp.settings import validate_company_access

            validate_company_access(previous.company, "Vehicle Inspection")
        if previous.docstatus != 1 or not previous.has_critical_defect:
            frappe.throw(
                _(
                    "Select a submitted inspection with an unresolved safety-critical defect."
                )
            )
        if previous.vehicle != self.vehicle:
            frappe.throw(
                _(
                    "Follow-up Inspection and original Inspection must use the same Vehicle."
                )
            )
        if previous.company != self.company:
            frappe.throw(
                _(
                    "Follow-up Inspection and original Inspection must use the same Company."
                )
            )
        if (
            previous.critical_defect_cleared_by
            and previous.critical_defect_cleared_by != self.name
        ):
            frappe.throw(
                _(
                    "The selected critical inspection has already been cleared by another follow-up."
                )
            )

    def _validate_follow_up_result(self):
        if self.follow_up_of and (
            self.has_critical_defect or self.overall_status != "Pass"
        ):
            frappe.throw(
                _(
                    "A follow-up can clear a critical defect only when its overall result is Pass and it has no critical defects."
                )
            )

    def _validate_system_managed_fields(self):
        previous = self.get_doc_before_save()
        if not previous:
            if (
                self.critical_defect_cleared_by
                or self.previous_vehicle_status
                or any(row.linked_issue for row in (self.inspection_items or []))
            ):
                frappe.throw(
                    _(
                        "Critical Defect Cleared By and Linked Issue are managed by the inspection workflow."
                    )
                )
            return

        for fieldname in ("critical_defect_cleared_by", "previous_vehicle_status"):
            if self.get(fieldname) != previous.get(fieldname):
                frappe.throw(
                    _(
                        "{0} is managed by the inspection workflow and cannot be edited directly."
                    ).format(frappe.get_meta(self.doctype).get_label(fieldname))
                )

        previous_issue_links = {
            row.name: row.linked_issue for row in (previous.inspection_items or [])
        }
        for row in self.inspection_items or []:
            if row.linked_issue != previous_issue_links.get(row.name):
                frappe.throw(
                    _(
                        "Linked Issue is managed by the inspection workflow and cannot be edited directly."
                    )
                )

    def _clear_followed_up_inspection(self):
        if self.follow_up_of and not self.has_critical_defect:
            frappe.db.set_value(
                "Vehicle Inspection",
                self.follow_up_of,
                "critical_defect_cleared_by",
                self.name,
            )

    def _reopen_followed_up_inspection(self):
        if not self.follow_up_of or not frappe.db.exists(
            "Vehicle Inspection", self.follow_up_of
        ):
            return False

        previous = frappe.get_doc("Vehicle Inspection", self.follow_up_of)
        if (
            previous.docstatus == 1
            and previous.has_critical_defect
            and previous.critical_defect_cleared_by == self.name
        ):
            previous.db_set("critical_defect_cleared_by", None)
            frappe.db.set_value(
                "Vehicle", self.vehicle, "vehicle_status", "Out of Service"
            )
            return True
        return False

    def _validate_items(self, require_completed=False):
        self._ensure_standard_checklist()
        self._enforce_safety_critical_flags()
        if require_completed and not self.inspection_items:
            frappe.throw(
                _("Add at least one inspection checklist item before submitting.")
            )

        for row in self.inspection_items or []:
            if row.status not in ("Okay", "Defective"):
                if require_completed:
                    frappe.throw(
                        _("Complete the inspection result for: {0}.").format(
                            row.category
                        )
                    )
                continue
            if (
                require_completed
                and row.status == "Defective"
                and not (row.remarks or "").strip()
            ):
                frappe.throw(
                    _("Remarks required for defective item: {0}").format(row.category)
                )

    def _ensure_standard_checklist(self):
        """Restore any deleted mandatory safety checklist category server-side."""
        existing = {
            (row.category or "").strip().casefold()
            for row in (self.inspection_items or [])
        }
        for check in STANDARD_INSPECTION_CHECKS:
            if check["category"].casefold() not in existing:
                self.append(
                    "inspection_items",
                    {
                        **check,
                        "status": "Not Checked",
                    },
                )

    def _enforce_safety_critical_flags(self):
        """Workshop users cannot downgrade custom checks to non-safety-critical.

        Fleet Managers and System Managers can classify custom checks explicitly.
        For Workshop, only the two standard administrative/fluids categories are
        non-critical; all new custom categories default to safety-critical, and
        an existing critical flag can never be cleared by a Workshop user.
        """
        roles = set(frappe.get_roles())
        if roles.intersection({"System Manager", "Fleet Manager"}):
            return

        previous = self.get_doc_before_save()
        previous_flags = {
            row.name: bool(row.is_safety_critical)
            for row in (previous.inspection_items if previous else [])
        }
        non_critical_standard = {
            check["category"].strip().casefold(): check["item_details"]
            .strip()
            .casefold()
            for check in STANDARD_INSPECTION_CHECKS
            if not check["is_safety_critical"]
        }
        seen_standard_noncritical = set()
        for row in self.inspection_items or []:
            category = (row.category or "").strip().casefold()
            details = (row.item_details or "").strip().casefold()
            is_standard_noncritical = (
                category in non_critical_standard
                and details == non_critical_standard[category]
                and category not in seen_standard_noncritical
            )
            if is_standard_noncritical:
                row.is_safety_critical = int(previous_flags.get(row.name, False))
                seen_standard_noncritical.add(category)
            else:
                row.is_safety_critical = 1

    def _calculate_defects(self):
        self.total_defects = sum(
            1 for row in (self.inspection_items or []) if row.status == "Defective"
        )
        critical_terms = (
            "mechanical",
            "brak",
            "steer",
            "tyre",
            "tire",
            "chassis",
            "technical inspection",
            "frein",
            "direction",
            "pneumatique",
            "moteur",
            "hydraulique",
            "structure",
        )
        self.has_critical_defect = int(
            any(
                row.status == "Defective"
                and (
                    row.is_safety_critical
                    or any(
                        term in (row.category or "").casefold()
                        for term in critical_terms
                    )
                )
                for row in (self.inspection_items or [])
            )
        )
        checks_complete = bool(self.inspection_items) and all(
            row.status in ("Okay", "Defective")
            and (row.status != "Defective" or (row.remarks or "").strip())
            for row in self.inspection_items
        )
        self.overall_status = None
        if checks_complete:
            self.overall_status = (
                "Fail"
                if self.has_critical_defect
                else "Conditional Pass"
                if self.total_defects
                else "Pass"
            )

    def _create_defect_issues(self):
        """For each defective item, auto-create an ERPNext Issue."""
        for row in self.inspection_items or []:
            if row.status == "Defective" and not row.linked_issue:
                issue = frappe.new_doc("Issue")
                issue.subject = _("[Vehicle Inspection] {0} — {1}").format(
                    self.vehicle, row.category
                )
                issue.description = _(
                    "Created from Vehicle Inspection {0}.\n\n{1}"
                ).format(self.name, row.remarks)
                if self.company:
                    issue.company = self.company
                issue.insert(ignore_permissions=True)
                row.db_set("linked_issue", issue.name)

    def _update_vehicle_status(self):
        """If critical defects found, mark vehicle Out of Service."""
        if self.has_critical_defect and self.vehicle:
            frappe.db.set_value(
                "Vehicle", self.vehicle, "vehicle_status", "Out of Service"
            )

    def _restore_vehicle_status(self):
        from sotrama.tp.validation import restore_vehicle_status_when_clear

        restore_vehicle_status_when_clear(
            self.vehicle,
            self.previous_vehicle_status,
            "Vehicle Inspection",
            self.name,
        )
