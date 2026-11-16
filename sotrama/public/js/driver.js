// Driver — client-side validations
frappe.ui.form.on('Driver', {
    refresh: function(frm) {
        // Check license expiry
        if (frm.doc.license_expiry) {
            var today = frappe.datetime.get_today();
            if (frm.doc.license_expiry < today) {
                frm.set_df_property('status', 'reqd', 1);
                frappe.msgprint({
                    title: __('Warning'),
                    indicator: 'orange',
                    message: __('Driver license has expired on ' + frm.doc.license_expiry)
                });
            } else if (frm.doc.license_expiry < frappe.datetime.add_days(today, 60)) {
                frappe.msgprint({
                    title: __('Notice'),
                    indicator: 'blue',
                    message: __('Driver license expires on ' + frm.doc.license_expiry + '. Please renew soon.')
                });
            }
        }
    },

    license_expiry: function(frm) {
        if (frm.doc.license_expiry) {
            var today = frappe.datetime.get_today();
            if (frm.doc.license_expiry < today) {
                frappe.msgprint({
                    title: __('Warning'),
                    indicator: 'orange',
                    message: __('License has expired!')
                });
            }
        }
    }
});