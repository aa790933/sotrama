// Vehicle — client-side validations and auto-calculations
function applyTpVehicleDefaults(frm) {
    if (!frm.is_new() || !frm.doc.company) return;
    return frappe.call({
        method: 'sotrama.tp.settings.get_tp_company_defaults',
        args: { company: frm.doc.company },
    }).then(({ message }) => {
        if (!message) return;
        const values = {};
        const fields = {
            default_department: 'department',
            default_cost_center: 'cost_center',
            default_parts_warehouse: 'parts_warehouse',
        };
        Object.entries(fields).forEach(([setting, fieldname]) => {
            if (!frm.doc[fieldname] && message[setting]) values[fieldname] = message[setting];
        });
        if (Object.keys(values).length) return frm.set_value(values);
    }).catch(() => {});
}

frappe.ui.form.on('Vehicle', {
    setup(frm) {
        frm.set_query('vehicle_make', () => ({ filters: { active: 1 } }));
        frm.set_query('model', () => ({
            filters: {
                vehicle_make: frm.doc.vehicle_make || '__no_match__',
                active: 1,
            },
        }));

        frm.set_query('parts_warehouse', () => {
            const filters = { is_group: 0, disabled: 0 };
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });

        frm.set_query('cost_center', () => {
            const filters = { is_group: 0, disabled: 0 };
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });

        frm.set_query('department', () => {
            return frm.doc.company ? { filters: { company: frm.doc.company } } : {};
        });
        frm.set_query('primary_driver', () => {
            const filters = { status: 'Active', docstatus: 1 };
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });

    },

    refresh: function(frm) {
        // Set default status
        if (frm.is_new() && !frm.doc.vehicle_status) {
            frm.set_value('vehicle_status', 'Active');
        }

        if (frm.is_new() && !frm.doc.company) {
            frappe.call({
                method: 'sotrama.tp.settings.get_tp_default_company',
                args: { applicable_for: 'Vehicle' },
            }).then(({ message: company }) => {
                if (company && !frm.doc.company) {
                    frm.set_value('company', company).then(() => applyTpVehicleDefaults(frm));
                }
            }).catch(() => {});
        } else {
            applyTpVehicleDefaults(frm);
        }

        if (!frm.is_new()) {
            frm.add_custom_button(__('Create Breakdown Incident'), function() {
                frappe.new_doc('Breakdown Incident', {
                    vehicle: frm.doc.name,
                    location: frm.doc.current_location
                });
            });

            frm.add_custom_button(__('Create Inspection'), function() {
                frappe.new_doc('Vehicle Inspection', {
                    vehicle: frm.doc.name,
                    inspection_type: 'Pre-Use'
                });
            });

            frm.add_custom_button(__('Create Job Card'), function() {
                frappe.new_doc('Maintenance Job Card', {
                    vehicle: frm.doc.name,
                    company: frm.doc.company,
                    cost_center: frm.doc.cost_center
                });
            });
        }
    },

    company(frm) {
        if (!frm.doc.company) return;

        const scopedFields = [
            ['parts_warehouse', 'Warehouse'],
            ['cost_center', 'Cost Center'],
            ['department', 'Department'],
        ];

        return Promise.all(scopedFields.map(([fieldname, doctype]) => {
            const current = frm.doc[fieldname];
            if (!current) return;
            return frappe.db.get_value(doctype, current, 'company').then(({ message }) => {
                if (message && message.company && message.company !== frm.doc.company) {
                    return frm.set_value(fieldname, '');
                }
            });
        })).then(() => applyTpVehicleDefaults(frm));
    },

    vehicle_make(frm) {
        if (frm.doc.model) return frm.set_value('model', '');
    },

    license_plate: function(frm) {
        if (frm.doc.license_plate) {
            frm.doc.license_plate = frm.doc.license_plate.toUpperCase();
            frm.refresh_field('license_plate');
        }
    }
});
