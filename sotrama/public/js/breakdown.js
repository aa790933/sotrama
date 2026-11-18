// Breakdown Incident — client-side logic
frappe.ui.form.on('Breakdown Incident', {
    setup(frm) {
        frm.set_query('vehicle', () => ({
            filters: { vehicle_status: ['not in', ['Retired', 'Scrapped']] },
        }));
        frm.set_query('driver', () => {
            // Breakdowns are historical events, not new driver assignments.
            const filters = { docstatus: 1 };
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });
    },

    vehicle(frm) {
        if (!frm.doc.vehicle) return;
        return frappe.db.get_value('Vehicle', frm.doc.vehicle, [
            'company', 'primary_driver', 'current_location',
        ]).then(({ message }) => {
            if (!message) return;
            if (message.company) frm.set_value('company', message.company);
            if (!frm.doc.driver && message.primary_driver) frm.set_value('driver', message.primary_driver);
            if (!frm.doc.location && message.current_location) frm.set_value('location', message.current_location);
        });
    },

    refresh: function(frm) {
        if (frm.doc.linked_job_card) {
            frm.add_custom_button(__('Open Job Card'), function() {
                frappe.set_route('Form', 'Maintenance Job Card', frm.doc.linked_job_card);
            });
        }

        if (!frm.is_new() && frm.doc.docstatus === 1) {
            const transition = (status, values = {}) => frappe.call({
                method: 'sotrama.tp.doctype.breakdown_incident.breakdown_incident.update_breakdown_status',
                args: { name: frm.doc.name, status, ...values },
            }).then(() => frm.reload_doc());

            if (frm.doc.status === 'Reported' || frm.doc.status === 'Acknowledged') {
                const next = frm.doc.status === 'Reported' ? 'Acknowledged' : 'In Progress';
                frm.add_custom_button(
                    frm.doc.status === 'Reported' ? __('Acknowledge') : __('Start Work'),
                    () => transition(next),
                );
            }

            if (['Reported', 'Acknowledged', 'In Progress'].includes(frm.doc.status)) {
                frm.add_custom_button(__('Resolve'), () => {
                    const dialog = new frappe.ui.Dialog({
                        title: __('Resolve Breakdown'),
                        fields: [
                            {
                                fieldname: 'resolution_date',
                                label: __('Resolution Date'),
                                fieldtype: 'Datetime',
                                default: frappe.datetime.now_datetime(),
                                reqd: 1,
                            },
                            {
                                fieldname: 'resolution_notes',
                                label: __('Resolution Notes'),
                                fieldtype: 'Text Editor',
                                reqd: 1,
                            },
                        ],
                        primary_action_label: __('Resolve'),
                        primary_action(values) {
                            transition('Resolved', values).then(() => dialog.hide());
                        },
                    });
                    dialog.show();
                });
            } else if (frm.doc.status === 'Resolved') {
                frm.add_custom_button(__('Close'), () => transition('Closed'));
                frm.add_custom_button(__('Reopen'), () => transition('In Progress'));
            } else if (frm.doc.status === 'Closed') {
                frm.add_custom_button(__('Reopen'), () => transition('In Progress'));
            }
        }
    },

    incident_date: function(frm) {
        if (frm.doc.incident_date && frm.doc.resolution_date) {
            if (frm.doc.resolution_date < frm.doc.incident_date) {
                frappe.msgprint(__('Resolution Date cannot be before Incident Date'));
                frm.set_value('resolution_date', '');
            }
        }
    },

    severity: function(frm) {
        if (frm.doc.severity === 'Critical') {
            frm.dashboard.show_alert(__('Critical breakdown — mark vehicle Out of Service'), 5000);
        }
    }
});
