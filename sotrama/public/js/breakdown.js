// Breakdown Incident — client-side logic
frappe.ui.form.on('Breakdown Incident', {
    refresh: function(frm) {
        if (frm.doc.status === 'Reported') {
            frm.add_custom_button(__('Create Job Card'), function() {
                frappe.new_doc('Maintenance Job Card', {
                    vehicle: frm.doc.vehicle,
                    job_nature: 'Breakdown',
                    job_date: frm.doc.incident_date,
                    linked_breakdown_incident: frm.doc.name,
                    driver_at_time: frm.doc.driver,
                    reported_issue: frm.doc.description
                });
            });
        }

        if (frm.doc.status === 'Resolved' || frm.doc.status === 'Closed') {
            frm.add_custom_button(__('Reopen'), function() {
                frappe.call({
                    method: 'frappe.client.set_value',
                    args: {
                        doctype: 'Breakdown Incident',
                        name: frm.doc.name,
                        fieldname: 'status',
                        value: 'Reported'
                    },
                    callback: function(r) {
                        if (!r.exc) {
                            frappe.msgprint(__('Breakdown reopened'));
                            frm.reload_doc();
                        }
                    }
                });
            });
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