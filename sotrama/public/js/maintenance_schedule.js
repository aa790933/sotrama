frappe.ui.form.on('Maintenance Schedule', {
    setup(frm) {
        frm.set_query('vehicle', () => ({
            filters: { vehicle_status: ['not in', ['Retired', 'Scrapped']] },
        }));
    },

    vehicle(frm) {
        if (!frm.doc.vehicle) return;
        return frappe.db.get_value('Vehicle', frm.doc.vehicle, 'company').then(({ message }) => {
            if (message && message.company) frm.set_value('company', message.company);
        });
    },

    refresh(frm) {
        if (frm.is_new() || frm.doc.docstatus !== 1) return;

        const updateStatus = (status) => frappe.call({
            method: 'sotrama.tp.doctype.maintenance_schedule.maintenance_schedule.update_maintenance_schedule_status',
            args: { name: frm.doc.name, status },
        }).then(() => frm.reload_doc());

        if (frm.doc.status === 'Active') {
            frm.add_custom_button(__('Pause Schedule'), () => updateStatus('Paused'));
            frm.add_custom_button(__('Complete Schedule'), () => updateStatus('Completed'));
        } else if (frm.doc.status === 'Paused') {
            frm.add_custom_button(__('Resume Schedule'), () => updateStatus('Active'));
            frm.add_custom_button(__('Complete Schedule'), () => updateStatus('Completed'));
        } else if (frm.doc.next_schedule) {
            frm.add_custom_button(__('Open Next Schedule'), () => {
                frappe.set_route('Form', 'Maintenance Schedule', frm.doc.next_schedule);
            });
        }
    },
});
