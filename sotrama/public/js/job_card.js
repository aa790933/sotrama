// Maintenance Job Card — clear child-row actions and live cost summaries.
(() => {
    const updateTotals = (frm) => {
        const amount = (value) => frappe.utils.flt(value);
        const totalParts = (frm.doc.parts_used || []).reduce(
            (total, row) => total + amount(row.amount),
            0,
        );
        const totalLabour = (frm.doc.labour_lines || []).reduce(
            (total, row) => total + amount(row.amount),
            0,
        );
        const totalOther = (frm.doc.other_costs || []).reduce(
            (total, row) => total + amount(row.amount),
            0,
        );

        return frm.set_value({
            total_parts_cost: totalParts,
            total_labour_cost: totalLabour,
            total_other_cost: totalOther,
            total_cost: totalParts + totalLabour + totalOther,
        });
    };

    const updateRowAmount = (frm, cdt, cdn, quantityField) => {
        const row = locals[cdt][cdn];
        const lineAmount = frappe.utils.flt(row[quantityField]) * frappe.utils.flt(row.rate);
        return frappe.model.set_value(cdt, cdn, 'amount', lineAmount).then(() => updateTotals(frm));
    };

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
        frm.set_query('mechanic', 'labour_lines', () => ({
            query: 'sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.search_workshop_employees',
            filters: { company: frm.doc.company || '' },
        }));
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
        // A saved draft needs write permission; create permission applies only
        // while the document is still new. Do not show add-row actions that the
        // user cannot save on an existing draft.
        const canEdit = (frm.perm || []).some((permission) =>
            frm.is_new() ? permission.create : permission.write,
        );
        if (frm.doc.docstatus === 0 && canEdit) {
            const addRow = (fieldname, description) => {
                frm.add_child(fieldname);
                frm.refresh_field(fieldname);
                frappe.show_alert({
                    message: __('A new row was added. {0}', [description]),
                    indicator: 'blue',
                });
            };

            frm.add_custom_button(
                __('Add Spare Part (Item)'),
                () => addRow('parts_used', __('Select a stock Item and enter its quantity and rate.')),
                __('Add Entry'),
            );
            frm.add_custom_button(
                __('Add Mechanic (Employee)'),
                () => addRow('labour_lines', __('Select an active Employee, then enter hours and hourly rate.')),
                __('Add Entry'),
            );
            frm.add_custom_button(
                __('Add Other Cost'),
                () => addRow('other_costs', __('Enter a cost description, category and amount.')),
                __('Add Entry'),
            );
        }

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
    // Frappe 16 Grid emits <table_field>_delete on the child DocType.
    parts_used_delete(frm) {
        return updateTotals(frm);
    },
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
    quantity(frm, cdt, cdn) {
        return updateRowAmount(frm, cdt, cdn, 'quantity');
    },
    rate(frm, cdt, cdn) {
        return updateRowAmount(frm, cdt, cdn, 'quantity');
    },
});

frappe.ui.form.on('Job Card Labour', {
    labour_lines_delete(frm) {
        return updateTotals(frm);
    },
    mechanic(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.mechanic) {
            return frappe.model.set_value(cdt, cdn, 'mechanic_name', '');
        }

        return frappe.call({
            method: 'sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.get_workshop_employee_name',
            args: { employee: row.mechanic, company: frm.doc.company },
        }).then(({ message }) => {
            if (message) {
                return frappe.model.set_value(cdt, cdn, 'mechanic_name', message);
            }
        });
    },
    hours(frm, cdt, cdn) {
        return updateRowAmount(frm, cdt, cdn, 'hours');
    },
    rate(frm, cdt, cdn) {
        return updateRowAmount(frm, cdt, cdn, 'hours');
    },
});

frappe.ui.form.on('Job Card Other Cost', {
    other_costs_delete(frm) {
        return updateTotals(frm);
    },
    amount(frm) {
        return updateTotals(frm);
    },
});
})();
