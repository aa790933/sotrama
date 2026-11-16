// Vehicle — client-side validations and auto-calculations
frappe.ui.form.on('Vehicle', {
    refresh: function(frm) {
        // Set default status
        if (frm.is_new() && !frm.doc.vehicle_status) {
            frm.set_value('vehicle_status', 'Active');
        }

        // Add custom buttons
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
                vehicle: frm.doc.name
            });
        });
    },

    license_plate: function(frm) {
        if (frm.doc.license_plate) {
            frm.doc.license_plate = frm.doc.license_plate.toUpperCase();
            frm.refresh_field('license_plate');
        }
    },

    current_odometer: function(frm) {
        if (frm.doc.current_odometer && frm.doc.acquisition_value) {
            // Auto-calculate approximate current value based on mileage
            // Simple depreciation: 10% per year + 0.5% per 10000 km over base
        }
    }
});