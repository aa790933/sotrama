// Company — Algerian registration fields enhancement.
const algerianRegistrationFields = [
    { fieldname: 'custom_nif', label: 'NIF' },
    { fieldname: 'custom_article_imposition', label: "Article d'imposition" },
    { fieldname: 'custom_nis', label: 'NIS' },
    { fieldname: 'custom_rc', label: 'RC' },
    { fieldname: 'custom_capital_social', label: 'Capital Social' },
];

frappe.ui.form.on('Company', {
    refresh(frm) {
        if (frm.doc.country !== 'Algeria' || frm.is_new()) return;

        if (frm.doc.tax_id && frm.doc.custom_nif && frm.doc.tax_id !== frm.doc.custom_nif) {
            frappe.show_alert({
                message: __('NIF and ERPNext Tax ID differ. Reconcile both identifiers before posting tax documents.'),
                indicator: 'orange',
            });
        }

        const missingFields = algerianRegistrationFields
            .filter(({ fieldname }) => !frm.doc[fieldname])
            .filter(({ fieldname }) => frm.fields_dict[fieldname]);

        if (missingFields.length) {
            frappe.show_alert({
                message: __('Complete the Algerian company registration identifiers: {0}', [
                    missingFields.map(({ label }) => label).join(', '),
                ]),
                indicator: 'orange',
            });
        }
    },

    custom_nif(frm) {
        if (frm.doc.country === 'Algeria' && frm.doc.tax_id !== frm.doc.custom_nif) {
            frm.set_value('tax_id', frm.doc.custom_nif || '');
        }
    },

    tax_id(frm) {
        if (frm.doc.country === 'Algeria' && frm.doc.custom_nif !== frm.doc.tax_id) {
            frm.set_value('custom_nif', frm.doc.tax_id || '');
        }
    },
});
