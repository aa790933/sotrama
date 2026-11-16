// Maintenance Job Card — client-side calculations
frappe.ui.form.on('Maintenance Job Card', {
    refresh: function(frm) {
        // Auto-set odometer before from vehicle
        if (frm.is_new() && frm.doc.vehicle && !frm.doc.odometer_before) {
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Vehicle',
                    name: frm.doc.vehicle,
                    fieldname: 'current_odometer'
                },
                callback: function(r) {
                    if (r.message && r.message.current_odometer) {
                        frm.set_value('odometer_before', r.message.current_odometer);
                    }
                }
            });
        }
    },

    odometer_before: function(frm) {
        if (frm.doc.odometer_after && frm.doc.odometer_before) {
            if (frm.doc.odometer_after < frm.doc.odometer_before) {
                frappe.msgprint(__('Odometer After cannot be less than Odometer Before'));
                frm.set_value('odometer_after', '');
            }
        }
    },

    odometer_after: function(frm) {
        if (frm.doc.odometer_before && frm.doc.odometer_after) {
            if (frm.doc.odometer_after < frm.doc.odometer_before) {
                frappe.msgprint(__('Odometer After cannot be less than Odometer Before'));
                frm.set_value('odometer_after', '');
            }
        }
    },

    before_submit: function(frm) {
        // Validate parts and labour totals
        var total = 0;
        frm.doc.parts_used.forEach(function(p) {
            total += (p.quantity || 0) * (p.rate || 0);
        });
        frm.doc.labour_lines.forEach(function(l) {
            total += (l.hours || 0) * (l.rate || 0);
        });
        frm.doc.other_costs.forEach(function(c) {
            total += c.amount || 0;
        });
        frm.set_value('total_cost', total);
    }
});