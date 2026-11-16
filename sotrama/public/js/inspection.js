// Vehicle Inspection — client-side checklist logic
frappe.ui.form.on('Vehicle Inspection', {
    refresh: function(frm) {
        if (frm.is_new() && !frm.doc.inspection_items || frm.doc.inspection_items.length === 0) {
            // Auto-populate standard inspection categories
            var standard_checks = [
                {category: 'Check Electrical', item_details: 'Battery, Alternator, Starter, Lighting, Wiring, Fuses, Horn, Dashboard Instruments'},
                {category: 'Check Mechanical', item_details: 'Engine, Transmission, Clutch, Driveline, Suspension, Steering, Braking, Cooling, Fuel, Exhaust'},
                {category: 'Check Tyres', item_details: 'Wheels, Tyres, Tread Depth, Air Pressure, Sidewall, Valve Stems, Wear Pattern'},
                {category: 'Check Windscreen', item_details: 'Cleanliness, Cracks, Wiper Blades, Washer Fluid, Seal, Windows, Mirrors'},
                {category: 'Check Safety Equipment', item_details: 'Fire Extinguisher, First Aid Kit, Warning Triangles, Reflector Vest, Safety Hammer'},
                {category: 'Check Documents', item_details: 'Registration, Insurance, Pollution Certificate, Technical Inspection'},
                {category: 'Check Lights', item_details: 'Headlights, Taillights, Brake Lights, Turn Signals, Hazard Lights'},
                {category: 'Check Fluid Levels', item_details: 'Engine Oil, Coolant, Brake Fluid, Power Steering, Windshield Washer'},
            ];

            standard_checks.forEach(function(check) {
                var row = frm.add_child('inspection_items');
                row.category = check.category;
                row.item_details = check.item_details;
                row.status = 'Okay';
            });
            frm.refresh_field('inspection_items');
        }
    },

    inspection_items: function(frm) {
        // Auto-calculate total defects
        var defects = 0;
        frm.doc.inspection_items.forEach(function(row) {
            if (row.status === 'Defective') defects++;
        });
        frm.set_value('total_defects', defects);

        // If any critical item is defective, warn
        var critical_categories = ['Check Mechanical', 'Check Braking', 'Check NTSA Inspection'];
        var has_critical = frm.doc.inspection_items.some(function(row) {
            return critical_categories.includes(row.category) && row.status === 'Defective';
        });

        if (has_critical) {
            frm.dashboard.show_alert(__('Critical defect detected — vehicle may be Out of Service'), 5000);
        }
    }
});