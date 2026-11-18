frappe.ui.form.on('Company Classification', {
    refresh(frm) {
        if (!frm.is_new() || frm.doc.company) return;

        frappe.db.get_single_value('TP Settings', 'default_company').then((company) => {
            if (company && !frm.doc.company) frm.set_value('company', company);
        });
    },
});
