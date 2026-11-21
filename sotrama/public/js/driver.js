// Driver form integration with the canonical ERPNext / Frappe HR Employee.
frappe.ui.form.on('Driver', {
    setup(frm) {
        const canManageEmployeeLink =
            frappe.user.has_role('System Manager') || frappe.user.has_role('HR Manager');
        frm.set_df_property('employee', 'read_only', !canManageEmployeeLink);

        frm.set_query('employee', () => {
            const filters = {};
            if (!frm.doc.status || frm.doc.status === 'Active') {
                filters.status = 'Active';
            }
            if (frm.doc.company) filters.company = frm.doc.company;
            return { filters };
        });
    },

    refresh(frm) {
        // Keep this field visible: the Employee link is optional by default,
        // but a site administrator may require it from TP Settings.
        if (
            frm.fields_dict.employee
            && (frappe.user.has_role('System Manager') || frappe.user.has_role('HR Manager'))
        ) {
            frm.toggle_display('employee', true);
            frappe.db.get_single_value('TP Settings', 'require_employee_link')
                .then((required) => frm.set_df_property('employee', 'reqd', Boolean(required)))
                .catch(() => frm.set_df_property('employee', 'reqd', false));
        }

        if (frm.is_new() || frm.doc.docstatus !== 1 || frm.doc.status === 'Terminated') return;

        const updateStatus = (status) => frappe.call({
            method: 'sotrama.tp.doctype.driver.driver.update_driver_status',
            args: { name: frm.doc.name, status },
        }).then(() => frm.reload_doc());

        if (frm.doc.status === 'Active') {
            frm.add_custom_button(__('Suspend'), () => updateStatus('Suspended'));
            frm.add_custom_button(__('Set On Leave'), () => updateStatus('On Leave'));
        } else {
            frm.add_custom_button(__('Reactivate'), () => updateStatus('Active'));
            if (frm.doc.status === 'Suspended') {
                frm.add_custom_button(__('Set On Leave'), () => updateStatus('On Leave'));
            }
        }
        frm.add_custom_button(__('Terminate'), () => {
            frappe.confirm(
                __('Terminate this Driver record? This action cannot be reversed.'),
                () => updateStatus('Terminated'),
            );
        });
    },

    employee(frm) {
        if (!frm.doc.employee) return;

        return frappe.db.get_value('Employee', frm.doc.employee, [
            'employee_name', 'company', 'company_email', 'date_of_joining',
        ]).then(({ message }) => {
            if (!message) return;

            const values = {
                driver_name: message.employee_name,
                company: message.company,
                hire_date: message.date_of_joining,
            };
            if (message.company_email) values.email = message.company_email;

            return frm.set_value(values);
        }).catch(() => {
            frappe.show_alert({
                message: __('You do not have permission to read this Employee record. Ask an HR Manager to grant the appropriate access.'),
                indicator: 'orange',
            });
        });
    },
});
