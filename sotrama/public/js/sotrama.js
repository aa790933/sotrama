// Sotrama — global Desk utilities.

frappe.provide('sotrama');

// Utility: format DZD currency
sotrama.format_dzd = function(value) {
    if (value === undefined || value === null) return '';
    return frappe.format(value, {fieldtype: 'Currency'}) + ' DZD';
};
