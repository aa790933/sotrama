frappe.ui.form.on("Sotrama Settings", {
	refresh(frm) {
		const can_manage_hr_titles =
			frappe.user.has_role("System Manager") || frappe.user.has_role("HR Manager");
		if (frm.is_new() || !frm.doc.add_public_works_designations || !can_manage_hr_titles) return;

		frm.add_custom_button(
			__("Create Missing BTPH Job Titles"),
			() => {
				frappe.call({
					method: "sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.create_missing_public_works_designations",
					freeze: true,
					freeze_message: __("Checking the Frappe HR Designation catalogue..."),
					error: () => frm.reload_doc(),
					callback: (response) => {
						const count = response.message?.created_count || 0;
						if (count) frm.reload_doc();
					},
				});
			},
			__("HR Job Titles"),
		);
	},
});
