// Maintenance Job Card — client-side calculations
frappe.ui.form.on('Maintenance Job Card', {
    setup(frm) {
        frm.set_query('vehicle', () => ({
            filters: { vehicle_status: ['not in', ['Retired', 'Scrapped']] },
        }));
        frm.set_query('maintenance_schedule', () => ({
            filters: Object.assign(
                { status: 'Active', docstatus: 1 },
                frm.doc.vehicle ? { vehicle: frm.doc.vehicle } : {},
                frm.doc.job_type ? { job_type: frm.doc.job_type } : {},
            ),
        }));
        frm.set_query('item', 'parts_used', () => ({ filters: { is_stock_item: 1, disabled: 0 } }));
    },

    vehicle(frm) {
        if (!frm.doc.vehicle) return;

        frm.set_value('maintenance_schedule', '');

        return frappe.db.get_value('Vehicle', frm.doc.vehicle, [
            'company', 'cost_center', 'current_odometer',
        ]).then(({ message }) => {
            if (!message) return;
            if (message.company) frm.set_value('company', message.company);
            if (message.cost_center) frm.set_value('cost_center', message.cost_center);
            if (!frm.doc.odometer_before && message.current_odometer) {
                frm.set_value('odometer_before', message.current_odometer);
            }
        });
    },

    job_type(frm) {
        if (frm.doc.maintenance_schedule) frm.set_value('maintenance_schedule', '');
    },

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
        (frm.doc.parts_used || []).forEach(function(p) {
            total += (p.quantity || 0) * (p.rate || 0);
        });
        (frm.doc.labour_lines || []).forEach(function(l) {
            total += (l.hours || 0) * (l.rate || 0);
        });
        (frm.doc.other_costs || []).forEach(function(c) {
            total += c.amount || 0;
        });
        frm.set_value('total_cost', total);
    }
});

frappe.ui.form.on('Job Card Part', {
    item(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.item) return;

        return frappe.db.get_value('Item', row.item, ['item_name', 'stock_uom'])
            .then(({ message }) => {
                if (!message) return;
                return Promise.all([
                    frappe.model.set_value(cdt, cdn, 'item_name', message.item_name),
                    frappe.model.set_value(cdt, cdn, 'uom', message.stock_uom),
                ]);
            });
    },
});

frappe.ui.form.on('Job Card Labour', {
    mechanic(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.mechanic) return;

        return frappe.db.get_value('Employee', row.mechanic, 'employee_name')
            .then(({ message }) => {
                if (message && message.employee_name) {
                    return frappe.model.set_value(cdt, cdn, 'mechanic_name', message.employee_name);
                }
            });
    },
});
