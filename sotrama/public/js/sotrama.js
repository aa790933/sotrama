// Sotrama — global desk JS
// Loaded on every Frappe Desk page

frappe.pages['sotrama-dashboard'].on_load = function(wrapper) {
    // Dashboard placeholder — can be extended with fleet KPI cards
};

frappe.provide('sotrama');

// Utility: format DZD currency
sotrama.format_dzd = function(value) {
    if (value === undefined || value === null) return '';
    return frappe.format(value, {fieldtype: 'Currency'}) + ' DZD';
};