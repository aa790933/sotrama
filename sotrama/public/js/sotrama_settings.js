frappe.ui.form.on("Sotrama Settings", {
	refresh(frm) {
		if (frappe.perm.has_perm("Company", 0, "read")) {
			frm.add_custom_button(
				__("Open Companies"),
				() => frappe.set_route("List", "Company"),
				__("Algerian Company"),
			);
		}

		const can_manage_hr_titles =
			frappe.user.has_role("System Manager") || frappe.user.has_role("HR Manager");
		if (!can_manage_hr_titles) return;

		if (frappe.perm.has_perm("Designation", 0, "read")) {
			frm.add_custom_button(
				__("Open Designations"),
				() => frappe.set_route("List", "Designation"),
				__("HR & Designations"),
			);
		}

		if (!frappe.perm.has_perm("Designation", 0, "create")) return;

		frm.add_custom_button(
			__("Import Missing BTPH Job Titles"),
			() => {
				frappe.confirm(
					__("Add only missing titles from the 202-title French BTPH catalogue? Existing designations and Employee records will not be changed."),
					() =>
						frappe.call({
							method: "sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.create_missing_public_works_designations",
							freeze: true,
							freeze_message: __("Checking the Frappe HR Designation catalogue..."),
							error: () => frm.reload_doc(),
							callback: (response) => {
								const count = response.message?.created_count || 0;
								if (count) frm.reload_doc();
							},
						}),
				);
			},
			__("HR & Designations"),
		);
	},
});
