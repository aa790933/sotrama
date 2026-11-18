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
            default_company_classification: 'company_classification',
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

        frm.set_query('company_classification', () => ({
            filters: { active: 1, docstatus: 1 },
            or_filters: frm.doc.company ? [
                ['Company Classification', 'company', '=', frm.doc.company],
                ['Company Classification', 'company', 'is', 'not set'],
            ] : [],
        }));
    },

    refresh: function(frm) {
        // Set default status
        if (frm.is_new() && !frm.doc.vehicle_status) {
            frm.set_value('vehicle_status', 'Active');
        }

        if (frm.is_new() && !frm.doc.company) {
            frappe.db.get_single_value('TP Settings', 'default_company').then((company) => {
                if (company && !frm.doc.company) {
                    frm.set_value('company', company).then(() => applyTpVehicleDefaults(frm));
                }
            });
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

    license_plate: function(frm) {
        if (frm.doc.license_plate) {
            frm.doc.license_plate = frm.doc.license_plate.toUpperCase();
            frm.refresh_field('license_plate');
        }
    }
});
