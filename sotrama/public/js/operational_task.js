// Operational Task — company-scoped vehicle, driver and supervisor assignment.
frappe.ui.form.on('Operational Task', {
    setup(frm) {
        frm.set_query('vehicle', () => ({
            filters: {
                docstatus: 1,
                vehicle_status: ['not in', ['Out of Service', 'Under Repair', 'Retired', 'Scrapped']],
            },
        }));
        frm.set_query('driver', () => {
            const filters = { status: 'Active', docstatus: 1 };
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });
        frm.set_query('supervisor', () => ({
            query: 'sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.search_workshop_employees',
            filters: {
                company: frm.doc.company || '',
                target_doctype: 'Operational Task',
            },
        }));
    },

    refresh(frm) {
        if (!frm.doc.vehicle) return;
        frappe.db.get_value('Vehicle', frm.doc.vehicle, 'vehicle_status')
            .then(({ message }) => {
                if (message && ['Out of Service', 'Under Repair', 'Retired', 'Scrapped'].includes(message.vehicle_status)) {
                    frappe.msgprint({
                        title: __('Warning'),
                        indicator: 'orange',
                        message: __('Vehicle {0} is {1}.', [frm.doc.vehicle, message.vehicle_status]),
                    });
                }
            });
    },

    vehicle(frm) {
        if (!frm.doc.vehicle) {
            return frm.set_value('company', '');
        }
        return frappe.db.get_value('Vehicle', frm.doc.vehicle, [
            'primary_driver', 'vehicle_status', 'company',
        ])
            .then(({ message }) => {
                if (!message) return;
                if (message.primary_driver && !frm.doc.driver) {
                    frm.set_value('driver', message.primary_driver);
                }
                if (message.company) frm.set_value('company', message.company);
                if (['Out of Service', 'Under Repair', 'Retired', 'Scrapped'].includes(message.vehicle_status)) {
                    frappe.msgprint(__('Vehicle is {0}.', [message.vehicle_status]));
                }
            });
    },

    start_odometer(frm) {
        if (frm.doc.start_odometer != null && frm.doc.end_odometer != null) {
            frm.set_value('distance_covered', frm.doc.end_odometer - frm.doc.start_odometer);
        }
    },

    end_odometer(frm) {
        if (frm.doc.start_odometer != null && frm.doc.end_odometer != null) {
            frm.set_value('distance_covered', frm.doc.end_odometer - frm.doc.start_odometer);
        }
    },
});
