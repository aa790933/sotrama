import frappe
from frappe import _
from frappe.model.document import Document


class CompanyClassification(Document):
    """
    Company Classification — Algerian public works company grade
    (Catégorie I through IX) per Décret Exécutif n° 14-139.

    Grade 8 (Class VIII) is the user's target classification.
    """

    def validate(self):
        self._validate_grade()
        self._calculate_total_score()

    def _validate_grade(self):
        if not self.grade:
            frappe.throw(_("Grade is required"))
        valid_grades = list(range(1, 10))
        if int(self.grade) not in valid_grades:
            frappe.throw(
                _("Grade must be between 1 and 9, got {0}").format(self.grade)
            )

    def _calculate_total_score(self):
        """Calculate the total classification score per the ministerial formula."""
        nt = 0
        if self.effectif_score:
            nt += (self.effectif_coefficient or 1) * self.effectif_score
        if self.encadrement_score:
            nt += (self.encadrement_coefficient or 1) * self.encadrement_score
        if self.apprentice_score:
            nt += (self.apprentice_coefficient or 1) * self.apprentice_score
        if self.training_score:
            nt += (self.training_coefficient or 1) * self.training_score
        if self.material_value_score:
            nt += (self.material_value_coefficient or 1) * self.material_value_score
        if self.capital_score:
            nt += (self.capital_coefficient or 1) * self.capital_score
        if self.revenue_score:
            nt += (self.revenue_coefficient or 1) * self.revenue_score
        if self.docs_score:
            nt += (self.docs_coefficient or 1) * self.docs_score
        if self.certification_score:
            nt += (self.certification_coefficient or 1) * self.certification_score
        self.total_score = round(nt, 2)

        # Verify the grade matches the score range
        self._verify_grade_range()

    def _verify_grade_range(self):
        """Check that the calculated score falls within the grade's range."""
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
                    title=_("Score Mismatch"),
                    indicator="orange",
                    message=_(
                        "Total score {0} falls outside Grade {1} range ({1}–{2}). "
                        "Please verify the classification criteria."
                    ).format(self.total_score, low, high),
                )