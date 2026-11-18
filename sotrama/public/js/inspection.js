// Vehicle Inspection — client-side checklist logic
frappe.ui.form.on('Vehicle Inspection', {
    setup(frm) {
        frm.set_query('vehicle', () => ({
            filters: { vehicle_status: ['not in', ['Retired', 'Scrapped']] },
        }));
        frm.set_query('driver', () => {
            const filters = { status: 'Active' };
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });
        frm.set_query('follow_up_of', () => ({
            filters: {
                vehicle: frm.doc.vehicle || undefined,
                docstatus: 1,
                has_critical_defect: 1,
                critical_defect_cleared_by: ['is', 'not set'],
                name: ['!=', frm.doc.name || ''],
            },
        }));
    },

    refresh: function(frm) {
        if (frm.is_new() && (!frm.doc.inspection_items || frm.doc.inspection_items.length === 0)) {
            // Auto-populate standard inspection categories
            var standard_checks = [
                {category: 'Documents réglementaires', item_details: 'Carte grise, assurance, visite technique en cours de validité, vignette et autorisations applicables.', is_safety_critical: false},
                {category: 'Freinage et direction', item_details: 'Frein de service, frein de stationnement, flexibles, fuites, direction, jeu et assistance.', is_safety_critical: true},
                {category: 'Pneumatiques et suspension', item_details: 'État des pneus, sculptures, pression, écrous, roues, suspension et lames.', is_safety_critical: true},
                {category: 'Moteur et transmission', item_details: 'Démarrage, moteur, boîte, embrayage, transmission, refroidissement, échappement et fuites.', is_safety_critical: true},
                {category: 'Hydraulique et équipement TP', item_details: 'Vérins, flexibles, distributeurs, pompe hydraulique, stabilisateurs et organes de travail.', is_safety_critical: true},
                {category: 'Électricité et signalisation', item_details: 'Batterie, alternateur, éclairage, feux stop, clignotants, gyrophare, avertisseur et alarme de recul.', is_safety_critical: true},
                {category: 'Cabine et sécurité', item_details: 'Ceinture, rétroviseurs, vitrage, essuie-glaces, extincteur, trousse de secours et triangles.', is_safety_critical: true},
                {category: 'Châssis et structure', item_details: 'Châssis, soudures, benne, attelage, crochets, garde-boue et fixations.', is_safety_critical: true},
                {category: 'Niveaux et environnement', item_details: 'Huile moteur, liquide de refroidissement, frein, carburant, AdBlue si applicable et absence de fuites au sol.', is_safety_critical: false},
            ];

            standard_checks.forEach(function(check) {
                var row = frm.add_child('inspection_items');
                row.category = check.category;
                row.item_details = check.item_details;
                row.status = 'Okay';
                row.is_safety_critical = check.is_safety_critical ? 1 : 0;
            });
            frm.refresh_field('inspection_items');
        }

        if (!frm.is_new() && frm.doc.docstatus === 1 && frm.doc.has_critical_defect) {
            if (frm.doc.critical_defect_cleared_by) {
                frm.add_custom_button(__('Open Follow-up Inspection'), () => {
                    frappe.set_route(
                        'Form',
                        'Vehicle Inspection',
                        frm.doc.critical_defect_cleared_by,
                    );
                });
            } else {
                frm.add_custom_button(__('Create Follow-up Inspection'), () => {
                    frappe.new_doc('Vehicle Inspection', {
                        vehicle: frm.doc.vehicle,
                        company: frm.doc.company,
                        inspection_type: 'Post-Incident',
                        follow_up_of: frm.doc.name,
                    });
                });
            }
        }
    },

    vehicle(frm) {
        if (!frm.doc.vehicle) return;
        return frappe.db.get_value('Vehicle', frm.doc.vehicle, [
            'company', 'primary_driver', 'current_odometer',
        ]).then(({ message }) => {
            if (!message) return;
            if (message.company) frm.set_value('company', message.company);
            if (!frm.doc.driver && message.primary_driver) frm.set_value('driver', message.primary_driver);
            if (!frm.doc.odometer && message.current_odometer) frm.set_value('odometer', message.current_odometer);
        });
    },

    inspection_items: function(frm) {
        // Auto-calculate total defects
        var defects = 0;
        frm.doc.inspection_items.forEach(function(row) {
            if (row.status === 'Defective') defects++;
        });
        frm.set_value('total_defects', defects);

        // If any critical item is defective, warn
        var critical_categories = ['Freinage et direction', 'Pneumatiques et suspension', 'Moteur et transmission', 'Hydraulique et équipement TP', 'Châssis et structure'];
        var has_critical = frm.doc.inspection_items.some(function(row) {
            return critical_categories.includes(row.category) && row.status === 'Defective';
        });

        if (has_critical) {
            frm.dashboard.show_alert(__('Critical defect detected — vehicle may be Out of Service'), 5000);
        }
    }
});
