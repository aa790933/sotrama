frappe.ui.form.on('Company Classification', {
    setup(frm) {
        frm.set_query('company', () => ({
            query: 'sotrama.tp.settings.search_company_classification_companies',
        }));
    },
    refresh(frm) {
        if (!frm.is_new() || frm.doc.company) return;

        frappe.call({
            method: 'sotrama.tp.settings.get_tp_default_company',
            args: { applicable_for: 'Company Classification' },
        }).then(({ message: company }) => {
            if (company && !frm.doc.company) frm.set_value('company', company);
        }).catch(() => {});
    },
});
