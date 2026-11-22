frappe.ui.form.on('TP Settings', {
    setup(frm) {
        frm.set_query('default_parts_warehouse', () => ({
            filters: {
                company: frm.doc.default_company || undefined,
                is_group: 0,
                disabled: 0,
            },
        }));

        frm.set_query('default_cost_center', () => ({
            filters: {
                company: frm.doc.default_company || undefined,
                is_group: 0,
                disabled: 0,
            },
        }));

        frm.set_query('default_department', () => ({
            filters: { company: frm.doc.default_company || undefined },
        }));

        frm.set_query('company', 'company_defaults', () => ({
            filters: { is_group: 0 },
        }));
        frm.set_query('default_department', 'company_defaults', (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            return { filters: row.company ? { company: row.company } : {} };
        });
        frm.set_query('default_cost_center', 'company_defaults', (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            const filters = { is_group: 0, disabled: 0 };
            if (row.company) filters.company = row.company;
            return { filters };
        });
        frm.set_query('default_parts_warehouse', 'company_defaults', (doc, cdt, cdn) => {
            const row = locals[cdt][cdn];
            const filters = { is_group: 0, disabled: 0 };
            if (row.company) filters.company = row.company;
            return { filters };
        });
    },

    default_company(frm) {
        const fields = [
            'default_department',
            'default_cost_center',
            'default_parts_warehouse',
        ];
        return Promise.all(fields.map((fieldname) => frm.set_value(fieldname, '')));
    },
});

frappe.ui.form.on('TP Company Defaults', {
    company(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        return Promise.all([
            'default_department',
            'default_cost_center',
            'default_parts_warehouse',
        ].map((fieldname) => frappe.model.set_value(cdt, cdn, fieldname, '')));
    },
});
