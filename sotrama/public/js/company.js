// Company — Algerian registration fields enhancement.
const algerianRegistrationFields = [
    { fieldname: 'custom_nif', label: 'NIF' },
    { fieldname: 'custom_nis', label: 'NIS' },
    { fieldname: 'custom_rc', label: 'RC' },
];

frappe.ui.form.on('Company', {
    refresh(frm) {
        if (frm.doc.country !== 'Algeria' || frm.is_new()) return;

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
});
