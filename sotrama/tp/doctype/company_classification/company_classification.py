import frappe
from frappe import _
from frappe.model.document import Document


class CompanyClassification(Document):
    """
    Company Classification — Algerian public works company grade
    (Catégorie I through IX) per Décret Exécutif n° 14-139 and
    Arrêté Interministeriel du 3 janvier 2024.

    Grade 8 (Class VIII) is the user's target classification.
    Validity: 5 years per MTPIB.
    """

    def validate(self):
        if not self.company:
            frappe.throw(_("Company is required for a Company Classification."))
        from sotrama.tp.settings import validate_company_access

        validate_company_access(self.company, "Company Classification")
        self._validate_grade()
        self._calculate_total_score()

    def _validate_grade(self):
        if not self.grade:
            frappe.throw(_("Grade is required"))
        valid_grades = list(range(1, 10))
        if int(self.grade) not in valid_grades:
            frappe.throw(_("Grade must be between 1 and 9, got {0}").format(self.grade))

    def _calculate_total_score(self):
        """
        Calculate the total classification score per the 2024 Arrêté formula:

        NT = [(CB1×EF) × (CB2×E) + (CB3×RA) + (CB4×FR)] + (CB5×VM)
             + [(CB6×CS) + (CB7×CA)] + (CB8×ABE)

        Where:
        - EF = Effectif (staff size), CB1 = coefficient, E = Encadrement (management), CB2 = coefficient
        - RA = Apprentices, CB3 = coefficient
        - FR = Training (Formation/Perfectionnement/Recyclage), CB4 = coefficient
        - VM = Material Value (equipment), CB5 = coefficient
        - CS = Capital Social, CB6 = coefficient
        - CA = Chiffre d'Affaires (revenue), CB7 = coefficient
        - ABE = Attestations de Bonne Exécution (good execution certificates), CB8 = coefficient, score 1-1.8
        """
        nt = 0

        # Human Resources: [(CB1×EF) × (CB2×E) + (CB3×RA) + (CB4×FR)]
        hr_base = (self.effectif_coefficient or 1) * (self.effectif_score or 0)
        hr_base *= (self.encadrement_coefficient or 1) * (self.encadrement_score or 0)
        hr_base += (self.apprentice_coefficient or 1) * (self.apprentice_score or 0)
        hr_base += (self.training_coefficient or 1) * (self.training_score or 0)

        # Material Value: CB5 × VM
        material = (self.material_value_coefficient or 1) * (
            self.material_value_score or 0
        )

        # Financial: (CB6 × CS) + (CB7 × CA)
        financial = (self.capital_coefficient or 1) * (self.capital_score or 0) + (
            self.revenue_coefficient or 1
        ) * (self.revenue_score or 0)

        # Good Execution: CB8 × ABE (score 1 to 1.8)
        execution = (self.abe_coefficient or 1) * (self.abe_score or 1)

        nt = hr_base + material + financial + execution
        self.total_score = round(nt, 2)

        # Verify the grade matches the score range
        self._verify_grade_range()

    def _verify_grade_range(self):
        """Check that the calculated score falls within the grade's range."""
        # Grade score ranges per Arrêté Interministeriel (categories I-IX)
        ranges = {
            1: (0, 9.8),
            2: (9.8, 18.3),
            3: (18.3, 25.5),
            4: (25.5, 36.3),
            5: (36.3, 44.0),
            6: (44.0, 53.4),
            7: (53.4, 63.0),
            8: (63.0, 72.8),
            9: (72.8, 82.2),
        }
        grade = int(self.grade)
        if grade in ranges:
            low, high = ranges[grade]
            if not (low < self.total_score <= high):
                frappe.msgprint(
                    _(
                        "Total score {0} falls outside Grade {1} range ({2}–{3}). "
                        "Please verify the classification criteria."
                    ).format(self.total_score, grade, low, high),
                    title=_("Score Mismatch"),
                    indicator="orange",
                )
