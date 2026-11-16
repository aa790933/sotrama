// Company — Algerian registration fields enhancement
frappe.ui.form.on('Company', {
    refresh: function(frm) {
        // Highlight NIF/NIS/RC fields if empty for Algerian companies
        if (frm.doc.country === 'Algeria') {
            ['nif', 'nis', 'rc'].forEach(function(field) {
                if (!frm.doc[field]) {
                    frm.set_df_property(field, 'reqd', 0);
                    frm.dashboard.show_alert(__('Please enter Algerian registration number: ' + field), 5000);
                }
            });
        }
    },

    country: function(frm) {
        // When country changes to Algeria, show registration fields
        if (frm.doc.country === 'Algeria') {
            frm.dashboard.show_alert(__('Algeria selected — please fill NIF, NIS, and RC'), 3000);
        }
    }
});