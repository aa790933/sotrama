// Operational Task — client-side logic
frappe.ui.form.on('Operational Task', {
    refresh: function(frm) {
        // Check vehicle status
        if (frm.doc.vehicle) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Vehicle',
                    name: frm.doc.vehicle,
                    fieldname: 'vehicle_status'
                },
                callback: function(r) {
                    if (r.message && r.message.vehicle_status === 'Out of Service') {
                        frappe.msgprint({
                            title: __('Warning'),
                            indicator: 'orange',
                            message: __('Vehicle ' + frm.doc.vehicle + ' is Out of Service')
                        });
                    }
                }
            });
        }
    },

    vehicle: function(frm) {
        if (frm.doc.vehicle) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Vehicle',
                    name: frm.doc.vehicle,
                    fieldname: ['primary_driver', 'vehicle_status', 'company']
                },
                callback: function(r) {
                    if (r.message) {
                        if (r.message.primary_driver && !frm.doc.driver) {
                            frm.set_value('driver', r.message.primary_driver);
                        }
                        if (r.message.company) {
                            frm.set_value('company', r.message.company);
                        }
                        if (r.message.vehicle_status === 'Out of Service') {
                            frappe.msgprint(__('Vehicle is Out of Service'));
                        }
                    }
                }
            });
        }
    },

    start_odometer: function(frm) {
        if (frm.doc.end_odometer && frm.doc.start_odometer) {
            frm.set_value('distance_covered', frm.doc.end_odometer - frm.doc.start_odometer);
        }
    },

    end_odometer: function(frm) {
        if (frm.doc.end_odometer && frm.doc.start_odometer) {
            frm.set_value('distance_covered', frm.doc.end_odometer - frm.doc.start_odometer);
        }
    }
});
