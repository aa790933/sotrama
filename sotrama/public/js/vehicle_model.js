frappe.ui.form.on('Vehicle Model', {
    setup(frm) {
        frm.set_query('vehicle_make', () => ({
            filters: { active: 1 },
        }));
    },
});
