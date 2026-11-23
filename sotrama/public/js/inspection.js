// Vehicle Inspection — client-side checklist logic.
(() => {
const criticalTerms = [
    'mechanical', 'brak', 'steer', 'tyre', 'tire', 'chassis',
    'technical inspection', 'frein', 'direction', 'pneumatique',
    'moteur', 'hydraulique', 'structure',
];

const updateInspectionSummary = (frm) => {
    const items = frm.doc.inspection_items || [];
    const defects = items.filter((row) => row.status === 'Defective');
    frm.set_value('total_defects', defects.length);

    const hasCritical = defects.some((row) =>
        row.is_safety_critical || criticalTerms.some((term) =>
            (row.category || '').toLocaleLowerCase().includes(term),
        ),
    );
    const checksComplete = items.length > 0 && items.every((row) =>
        ['Okay', 'Defective'].includes(row.status)
            && (row.status !== 'Defective' || Boolean((row.remarks || '').trim())),
    );
    frm.set_value(
        'overall_status',
        checksComplete
            ? hasCritical ? 'Fail' : defects.length ? 'Conditional Pass' : 'Pass'
            : '',
    );
    if (hasCritical) {
        frm.dashboard.show_alert(__('Safety-critical defect detected — submitting this inspection will mark the vehicle Out of Service.'), 5000);
    }
};

frappe.ui.form.on('Vehicle Inspection', {
    setup(frm) {
        frm.set_query('vehicle', () => ({
            filters: { docstatus: 1, vehicle_status: ['not in', ['Retired', 'Scrapped']] },
        }));
        frm.set_query('driver', () => {
            const filters = { status: 'Active', docstatus: 1 };
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });
        frm.set_query('supervisor', () => ({
            query: 'sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.search_workshop_employees',
            filters: {
                company: frm.doc.company || '',
                target_doctype: 'Vehicle Inspection',
            },
        }));
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
        // A saved draft needs write permission; create permission applies only
        // while the document is still new. Do not show add-row actions that the
        // user cannot save on an existing draft.
        const canEdit = frm.is_new()
            ? !!frm.perm?.[0]?.create
            : !!frm.perm?.[0]?.write;
        if (frm.doc.docstatus === 0 && canEdit) {
            frm.add_custom_button(__('Add Custom Check'), () => {
                const dialog = new frappe.ui.Dialog({
                    title: __('Add Vehicle-Specific Check'),
                    fields: [
                        {
                            fieldtype: 'Data',
                            fieldname: 'category',
                            label: __('Category'),
                            reqd: 1,
                            description: __('Name the vehicle system or area to inspect.'),
                        },
                        {
                            fieldtype: 'Small Text',
                            fieldname: 'item_details',
                            label: __('What to Check'),
                            reqd: 1,
                            description: __('Describe the exact point the inspector must verify.'),
                        },
                    ],
                    primary_action_label: __('Add Check'),
                    primary_action(values) {
                        const category = (values.category || '').trim();
                        const itemDetails = (values.item_details || '').trim();
                        if (!category || !itemDetails) return;

                        frm.add_child('inspection_items', {
                            category,
                            item_details: itemDetails,
                            status: 'Not Checked',
                        });
                        frm.refresh_field('inspection_items');
                        updateInspectionSummary(frm);
                        dialog.hide();
                    },
                });
                dialog.show();
            }, __('Checklist'));
        }

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
                row.status = 'Not Checked';
                row.is_safety_critical = check.is_safety_critical ? 1 : 0;
            });
            frm.refresh_field('inspection_items');
        }

        if (!frm.is_new() && frm.doc.docstatus === 1 && frm.doc.has_critical_defect) {
            if (frm.doc.critical_defect_cleared_by) {
                if (frappe.perm.has_perm('Vehicle Inspection', 0, 'read')) {
                    frm.add_custom_button(__('Open Follow-up Inspection'), () => {
                        frappe.set_route(
                            'Form',
                            'Vehicle Inspection',
                            frm.doc.critical_defect_cleared_by,
                        );
                    });
                }
            } else if (frappe.model.can_create('Vehicle Inspection')) {
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
        const vehicle = frm.doc.vehicle;
        return frappe.db.get_value('Vehicle', vehicle, [
            'company', 'primary_driver', 'current_odometer',
        ]).then(({ message }) => {
            if (!message || frm.doc.vehicle !== vehicle) return;
            if (message.company) frm.set_value('company', message.company);
            if (!frm.doc.driver && message.primary_driver) frm.set_value('driver', message.primary_driver);
            if (!frm.doc.odometer && message.current_odometer) frm.set_value('odometer', message.current_odometer);
        });
    },

    inspection_items: function(frm) {
        updateInspectionSummary(frm);
    }
});

frappe.ui.form.on('Inspection Item', {
    // Frappe Grid uses _remove for one row and _delete for bulk deletion.
    inspection_items_add(frm) {
        updateInspectionSummary(frm);
    },
    status(frm) {
        updateInspectionSummary(frm);
    },
    is_safety_critical(frm) {
        updateInspectionSummary(frm);
    },
    category(frm) {
        updateInspectionSummary(frm);
    },
    remarks(frm) {
        updateInspectionSummary(frm);
    },
    inspection_items_remove(frm) {
        updateInspectionSummary(frm);
    },
    inspection_items_delete(frm) {
        updateInspectionSummary(frm);
    },
});
})();
