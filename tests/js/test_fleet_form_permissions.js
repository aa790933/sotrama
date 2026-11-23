const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function loadHandlers(
	path,
	{ canCreate = () => true, frappeOverrides = {}, locals = {}, Dialog } = {},
) {
	const handlers = {};
	const frappe = {
		ui: {
			Dialog,
			form: {
				on(doctype, events) {
					handlers[doctype] = events;
				},
			},
		},
		utils: { flt: (value) => Number(value) || 0 },
		model: { can_create: canCreate },
			perm: { has_perm: () => true },
	};
	Object.assign(frappe, frappeOverrides);

	vm.runInNewContext(fs.readFileSync(path, "utf8"), {
		frappe,
		locals,
		__: (value) => value,
	});

	return handlers;
}

function makeForm({ isNew = false, docstatus = 0, permissions = [], company = "SOTRAMA", doc = {} } = {}) {
	return {
		perm: permissions,
	    doc: { docstatus, company, ...doc },
		fields_dict: {},
		buttons: [],
        queries: {},
		is_new: () => isNew,
		set_value(values, value) {
			Object.assign(this.doc, typeof values === "string" ? { [values]: value } : values);
			return Promise.resolve();
		},
		add_custom_button(...args) {
			this.buttons.push(args);
		},
		add_child(fieldname, values = {}) {
			this.doc[fieldname] ||= [];
			const row = { ...values };
			this.doc[fieldname].push(row);
			return row;
		},
        set_query(fieldname, callback) {
            this.queries[fieldname] = callback;
        },
		refresh_field() {},
		dashboard: { show_alert() {} },
	};
}

let form;
const settingsHandlers = loadHandlers("sotrama/public/js/sotrama_settings.js", {
	frappeOverrides: {
		user: { has_role: (role) => role === "HR Manager" },
		perm: { has_perm: (doctype, level, permission) => {
			if (doctype === "Company") return permission === "read";
			if (doctype === "Designation") return permission === "read" || permission === "create";
			return false;
		} },
		set_route() {},
	},
})["Sotrama Settings"];
form = makeForm();
settingsHandlers.refresh(form);
assert.deepEqual(
	form.buttons.map(([label]) => label),
	["Open Companies", "Open Designations", "Import Missing BTPH Job Titles"],
	"Company, HR navigation and the explicit BTPH import action must appear only for permitted users",
);

let importConfirmation = "";
let importCall;
const settingsImportAction = loadHandlers("sotrama/public/js/sotrama_settings.js", {
	frappeOverrides: {
		user: { has_role: (role) => role === "HR Manager" },
		perm: { has_perm: () => true },
		set_route() {},
		confirm(message, onYes) { importConfirmation = message; onYes(); },
		call(args) { importCall = args; },
	},
})["Sotrama Settings"];
form = makeForm();
settingsImportAction.refresh(form);
form.buttons.find(([label]) => label === "Import Missing BTPH Job Titles")[1]();
assert.match(importConfirmation, /202-title French BTPH catalogue/);
assert.equal(
	importCall.method,
	"sotrama.sotrama.doctype.sotrama_settings.sotrama_settings.create_missing_public_works_designations",
	"The import action must call the explicit server-side catalogue operation after confirmation",
);

const settingsWithoutDesignationCreate = loadHandlers("sotrama/public/js/sotrama_settings.js", {
	frappeOverrides: {
		user: { has_role: (role) => role === "HR Manager" },
		perm: { has_perm: (doctype, level, permission) => {
			if (doctype === "Company") return permission === "read";
			return doctype === "Designation" && permission === "read";
		} },
		set_route() {},
	},
})["Sotrama Settings"];
form = makeForm();
settingsWithoutDesignationCreate.refresh(form);
assert.deepEqual(
	form.buttons.map(([label]) => label),
	["Open Companies", "Open Designations"],
	"HR users without Designation create permission must not see the seed action",
);

const settingsWithoutCompanyRead = loadHandlers("sotrama/public/js/sotrama_settings.js", {
	frappeOverrides: {
		user: { has_role: () => false },
		perm: { has_perm: () => false },
		set_route() {},
	},
})["Sotrama Settings"];
form = makeForm();
settingsWithoutCompanyRead.refresh(form);
assert.equal(form.buttons.length, 0, "Users without Company or HR permissions must not see setup navigation actions");

const jobCard = loadHandlers("sotrama/public/js/job_card.js")["Maintenance Job Card"];
form = makeForm({ isNew: false, permissions: [{ create: true, write: false }] });
jobCard.refresh(form);
assert.equal(form.buttons.length, 0, "Create-only users must not edit saved job-card drafts");

form = makeForm({ isNew: true, permissions: [{ create: true, write: false }] });
jobCard.refresh(form);
assert.equal(form.buttons.length, 3, "Create permission must expose all add-entry actions on new job cards");

form = makeForm({ isNew: false, permissions: [{ create: false, write: true }] });
jobCard.refresh(form);
assert.equal(form.buttons.length, 3, "Write permission must expose all add-entry actions on saved drafts");
form = makeForm({ isNew: false, permissions: [{ write: false }, { write: false }, { write: true }] });
jobCard.refresh(form);
assert.equal(form.buttons.length, 0, "Field-level write permission must not expose draft add-entry actions");

form = makeForm({ isNew: false, docstatus: 1, permissions: [{ create: true, write: true }] });
jobCard.refresh(form);
assert.equal(form.buttons.length, 0, "Submitted job cards must not expose draft add-entry actions");

const inspection = loadHandlers("sotrama/public/js/inspection.js")["Vehicle Inspection"];
form = makeForm();
inspection.setup(form);
assert.equal(
    form.queries.supervisor().query,
    "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.search_workshop_employees",
    "Inspection supervisor lookup must use the scoped Employee endpoint",
);
assert.equal(form.queries.supervisor().filters.company, "SOTRAMA");
form = makeForm({ isNew: false, permissions: [{ create: true, write: false }] });
inspection.refresh(form);
assert.equal(form.buttons.length, 0, "Create-only users must not edit saved inspection drafts");

form = makeForm({ isNew: true, permissions: [{ create: true, write: false }] });
inspection.refresh(form);
assert.equal(form.buttons.length, 1, "Create permission must expose the checklist action on new inspections");

form = makeForm({ isNew: false, permissions: [{ create: false, write: true }] });
inspection.refresh(form);
assert.equal(form.buttons.length, 1, "Write permission must expose the checklist action on saved drafts");
form = makeForm({ isNew: false, permissions: [{ write: false }, { write: false }, { write: true }] });
inspection.refresh(form);
assert.equal(form.buttons.length, 0, "Field-level write permission must not expose draft checklist actions");

form = makeForm({ isNew: false, docstatus: 1, permissions: [{ create: true, write: true }] });
inspection.refresh(form);
assert.equal(form.buttons.length, 0, "Submitted inspections must not expose draft checklist actions");

const jobCardChildren = loadHandlers("sotrama/public/js/job_card.js");
for (const [childDoctype, fieldname] of [
	["Job Card Part", "parts_used"],
	["Job Card Labour", "labour_lines"],
	["Job Card Other Cost", "other_costs"],
]) {
	const handlers = jobCardChildren[childDoctype];
	assert.equal(typeof handlers[`${fieldname}_remove`], "function", `${fieldname} must recalculate after removing one row`);
	assert.equal(typeof handlers[`${fieldname}_delete`], "function", `${fieldname} must recalculate after bulk deletion`);
}

form = makeForm({ doc: {
	parts_used: [],
	labour_lines: [{ amount: 12 }],
	other_costs: [{ amount: 3 }],
} });
jobCardChildren["Job Card Part"].parts_used_remove(form);
assert.equal(form.doc.total_parts_cost, 0);
assert.equal(form.doc.total_labour_cost, 12);
assert.equal(form.doc.total_other_cost, 3);
assert.equal(form.doc.total_cost, 15, "Single-row part removal must refresh the job-card total");

form = makeForm({ doc: {
	parts_used: [],
	labour_lines: [{ amount: 12 }],
	other_costs: [{ amount: 3 }],
} });
jobCardChildren["Job Card Part"].parts_used_delete(form);
assert.equal(form.doc.total_cost, 15, "Bulk part deletion must refresh the job-card total");

form = makeForm({ doc: {
	parts_used: [{ amount: 20 }],
	labour_lines: [],
	other_costs: [{ amount: 3 }],
} });
jobCardChildren["Job Card Labour"].labour_lines_remove(form);
assert.equal(form.doc.total_cost, 23, "Single-row labour removal must refresh the job-card total");

form = makeForm({ doc: {
	parts_used: [{ amount: 20 }],
	labour_lines: [{ amount: 12 }],
	other_costs: [],
} });
jobCardChildren["Job Card Other Cost"].other_costs_remove(form);
assert.equal(form.doc.total_cost, 32, "Single-row other-cost removal must refresh the job-card total");

const inspectionChildren = loadHandlers("sotrama/public/js/inspection.js");
const inspectionItems = inspectionChildren["Inspection Item"];
assert.equal(typeof inspectionItems.inspection_items_remove, "function", "Inspection summary must refresh after one check is removed");
assert.equal(typeof inspectionItems.inspection_items_delete, "function", "Inspection summary must refresh after bulk deletion");
form = makeForm({ doc: {
	inspection_items: [{ status: "Okay", remarks: "" }],
} });
inspectionItems.inspection_items_remove(form);
assert.equal(form.doc.total_defects, 0);
assert.equal(form.doc.overall_status, "Pass", "Removing a defective check must refresh the inspection result");
form = makeForm({ doc: { inspection_items: [{ status: "Okay", remarks: "" }] } });
inspectionItems.inspection_items_delete(form);
assert.equal(form.doc.overall_status, "Pass", "Bulk check deletion must refresh the inspection result");

const inspectionDialogs = [];
class TestDialog {
	constructor(options) { this.options = options; inspectionDialogs.push(this); }
	show() { this.shown = true; }
	hide() { this.hidden = true; }
}
const inspectionWithDialog = loadHandlers("sotrama/public/js/inspection.js", {
	Dialog: TestDialog,
})["Vehicle Inspection"];
form = makeForm({ isNew: true, permissions: [{ create: true }], doc: {
	inspection_items: [{ category: "Existing", item_details: "Existing point", status: "Okay" }],
} });
inspectionWithDialog.refresh(form);
assert.equal(form.buttons[0][0], "Add Custom Check");
form.buttons[0][1]();
assert.equal(inspectionDialogs.length, 1);
assert.deepEqual(
	Array.from(inspectionDialogs[0].options.fields, (field) => field.fieldname),
	["category", "item_details"],
	"A custom inspection check must ask for a category and a clear inspection point without placeholder values",
);
inspectionDialogs[0].options.primary_action({ category: "  ", item_details: "  " });
assert.equal(form.doc.inspection_items.length, 1, "Blank custom checks must not be added");
assert.equal(inspectionDialogs[0].hidden, undefined, "The dialog must remain open until valid details are supplied");
inspectionDialogs[0].options.primary_action({ category: "Hydraulic system", item_details: "Check hose leaks" });
assert.equal(form.doc.inspection_items[1].category, "Hydraulic system");
assert.equal(form.doc.inspection_items[1].status, "Not Checked");
assert.notEqual(form.doc.inspection_items[1].is_safety_critical, 1, "Custom checks must not be marked safety-critical without an explicit assessment");
assert.equal(inspectionDialogs[0].hidden, true);

const vehicleHandlers = loadHandlers("sotrama/public/js/vehicle.js", {
	canCreate: (doctype) => doctype === "Maintenance Job Card",
})["Vehicle"];
form = makeForm({ docstatus: 1, doc: { name: "VEH-001", company: "SOTRAMA" } });
vehicleHandlers.refresh(form);
assert.deepEqual(form.buttons.map(([label]) => label), ["Create Job Card"], "Vehicle actions must only show doctypes the user can create");

const breakdownRefresh = loadHandlers("sotrama/public/js/breakdown.js")["Breakdown Incident"].refresh;
form = makeForm({ docstatus: 1, doc: { name: "BRK-001", status: "Reported" } });
breakdownRefresh(form);
assert.equal(form.buttons.length, 0, "Read-only users must not see Breakdown status actions");
form = makeForm({ docstatus: 1, doc: { name: "BRK-001", status: "Reported", linked_job_card: "MC-001" } });
breakdownRefresh(form);
assert.deepEqual(form.buttons.map(([label]) => label), ["Open Job Card"], "Read-only users with linked-record access must retain navigation");
const breakdownWithoutJobCardRead = loadHandlers("sotrama/public/js/breakdown.js", {
	frappeOverrides: { perm: { has_perm: () => false } },
})["Breakdown Incident"].refresh;
form = makeForm({ docstatus: 1, doc: { name: "BRK-001", status: "Reported", linked_job_card: "MC-001" } });
breakdownWithoutJobCardRead(form);
assert.equal(form.buttons.length, 0, "Users without Job Card read permission must not see the navigation action");
form = makeForm({ docstatus: 1, permissions: [{ write: true }], doc: { name: "BRK-001", status: "Reported" } });
breakdownRefresh(form);
assert.equal(form.buttons.length, 2, "Users with write permission must see valid Breakdown status actions");
form = makeForm({ docstatus: 1, permissions: [{ write: false }, { write: false }, { write: true }], doc: { name: "BRK-001", status: "Reported" } });
breakdownRefresh(form);
assert.equal(form.buttons.length, 0, "Field-level write permission must not expose document status actions");

const driverRefresh = loadHandlers("sotrama/public/js/driver.js")["Driver"].refresh;
form = makeForm({ docstatus: 1, doc: { name: "DRV-001", status: "Active" } });
driverRefresh(form);
assert.equal(form.buttons.length, 0, "Read-only users must not see Driver status actions");
form = makeForm({ docstatus: 1, permissions: [{ write: true }], doc: { name: "DRV-001", status: "Active" } });
driverRefresh(form);
assert.equal(form.buttons.length, 3, "Users with write permission must see valid Driver status actions");
form = makeForm({ docstatus: 1, permissions: [{ write: false }, { write: false }, { write: true }], doc: { name: "DRV-001", status: "Active" } });
driverRefresh(form);
assert.equal(form.buttons.length, 0, "Field-level write permission must not expose Driver status actions");

const scheduleRefresh = loadHandlers("sotrama/public/js/maintenance_schedule.js")["Maintenance Schedule"].refresh;
form = makeForm({ docstatus: 1, doc: { name: "SCH-001", status: "Active" } });
scheduleRefresh(form);
assert.equal(form.buttons.length, 0, "Read-only users must not see Maintenance Schedule status actions");
form = makeForm({ docstatus: 1, permissions: [{ write: true }], doc: { name: "SCH-001", status: "Active" } });
scheduleRefresh(form);
assert.equal(form.buttons.length, 2, "Users with write permission must see valid Maintenance Schedule status actions");
form = makeForm({ docstatus: 1, permissions: [{ write: false }, { write: false }, { write: true }], doc: { name: "SCH-001", status: "Active" } });
scheduleRefresh(form);
assert.equal(form.buttons.length, 0, "Field-level write permission must not expose schedule status actions");
form = makeForm({ docstatus: 1, doc: { name: "SCH-001", status: "Completed", next_schedule: "SCH-002" } });
scheduleRefresh(form);
assert.deepEqual(form.buttons.map(([label]) => label), ["Open Next Schedule"], "Read-only users must retain navigation to the generated successor schedule");

form = makeForm({ docstatus: 1, doc: { name: "INSP-001", has_critical_defect: 1, critical_defect_cleared_by: "INSP-002" } });
inspection.refresh(form);
assert.deepEqual(form.buttons.map(([label]) => label), ["Open Follow-up Inspection"], "Users with read access must retain follow-up navigation");
const inspectionWithoutRead = loadHandlers("sotrama/public/js/inspection.js", {
	frappeOverrides: { perm: { has_perm: () => false } },
})["Vehicle Inspection"].refresh;
form = makeForm({ docstatus: 1, doc: { name: "INSP-001", has_critical_defect: 1, critical_defect_cleared_by: "INSP-002" } });
inspectionWithoutRead(form);
assert.equal(form.buttons.length, 0, "Users without follow-up read access must not see the navigation action");
const inspectionWithoutCreate = loadHandlers("sotrama/public/js/inspection.js", {
	canCreate: () => false,
})["Vehicle Inspection"].refresh;
form = makeForm({ docstatus: 1, doc: { name: "INSP-001", has_critical_defect: 1 } });
inspectionWithoutCreate(form);
assert.equal(form.buttons.length, 0, "Users without Inspection create permission must not see the follow-up action");

const operationalTask = loadHandlers("sotrama/public/js/operational_task.js")["Operational Task"];
form = makeForm();
operationalTask.setup(form);
assert.equal(
    form.queries.supervisor().query,
    "sotrama.tp.doctype.maintenance_job_card.maintenance_job_card.search_workshop_employees",
    "Operational Task supervisor lookup must use the scoped Employee endpoint",
);
assert.equal(form.queries.supervisor().filters.company, "SOTRAMA");
assert.equal(typeof operationalTask.refresh, "function", "Existing vehicle-status warning must remain available");
assert.equal(typeof operationalTask.vehicle, "function", "Vehicle selection must continue to derive company and primary driver");
assert.equal(typeof operationalTask.start_odometer, "function");
assert.equal(typeof operationalTask.end_odometer, "function");

const driverSource = fs.readFileSync("sotrama/public/js/driver.js", "utf8");
assert.doesNotMatch(driverSource, /cell_number|personal_email/);
assert.match(driverSource, /'employee_name', 'company', 'company_email'/);
assert.doesNotMatch(driverSource, /phone:\s*message\./);
assert.doesNotMatch(driverSource, /email:\s*message\.company_email\s*\|\|/);

async function runAsyncRaceTests() {
	const driver = loadHandlers("sotrama/public/js/driver.js", {
		frappeOverrides: {
			db: {
				get_value: () => Promise.resolve({
					message: {
						employee_name: "Old Employee",
						company: "OLD-COMPANY",
						company_email: "old@example.invalid",
						date_of_joining: "2020-01-01",
					},
				}),
			},
		},
	})["Driver"];
	form = makeForm({ doc: { employee: "EMP-OLD", driver_name: "Current Name", company: "CURRENT-COMPANY" } });
	const pending = driver.employee(form);
	form.doc.employee = "EMP-NEW";
	await pending;
	assert.equal(form.doc.driver_name, "Current Name", "A stale Employee lookup must not overwrite the newly selected Employee");
	assert.equal(form.doc.company, "CURRENT-COMPANY", "A stale Employee lookup must not change the Driver Company");

	const vehicleLookups = {};
	const vehicle = loadHandlers("sotrama/public/js/vehicle.js", {
		frappeOverrides: {
			db: {
				get_value: (doctype, name) => new Promise((resolve) => {
					vehicleLookups[name] = resolve;
				}),
			},
		},
	})["Vehicle"];
	form = makeForm({ doc: {
		company: "COMPANY-A",
		parts_warehouse: "WH-OLD",
		cost_center: "CC-OLD",
		department: "DEP-OLD",
	} });
	const pendingCompanyLookups = vehicle.company(form);
	form.doc.parts_warehouse = "WH-NEW";
	form.doc.cost_center = "CC-NEW";
	form.doc.department = "DEP-NEW";
	vehicleLookups["WH-OLD"]({ message: { company: "COMPANY-B" } });
	vehicleLookups["CC-OLD"]({ message: { company: "COMPANY-B" } });
	vehicleLookups["DEP-OLD"]({ message: { company: "COMPANY-B" } });
	await pendingCompanyLookups;
	assert.equal(form.doc.parts_warehouse, "WH-NEW", "A stale Warehouse lookup must not clear a newly selected same-company value");
	assert.equal(form.doc.cost_center, "CC-NEW", "A stale Cost Center lookup must not clear a newly selected same-company value");
	assert.equal(form.doc.department, "DEP-NEW", "A stale Department lookup must not clear a newly selected same-company value");

	let resolveCompanyDefaults;
	const vehicleDefaults = loadHandlers("sotrama/public/js/vehicle.js", {
		frappeOverrides: {
			call: () => new Promise((resolve) => {
				resolveCompanyDefaults = resolve;
			}),
		},
	})["Vehicle"];
	form = makeForm({ isNew: true, doc: { company: "COMPANY-A" } });
	const pendingDefaults = vehicleDefaults.company(form);
	await new Promise((resolve) => setImmediate(resolve));
	form.doc.company = "COMPANY-B";
	resolveCompanyDefaults({
		message: {
			default_department: "DEP-A",
			default_cost_center: "CC-A",
			default_parts_warehouse: "WH-A",
		},
	});
	await pendingDefaults;
	assert.equal(form.doc.department, undefined, "A stale Company-default response must not apply another Company's Department");
	assert.equal(form.doc.cost_center, undefined, "A stale Company-default response must not apply another Company's Cost Center");
	assert.equal(form.doc.parts_warehouse, undefined, "A stale Company-default response must not apply another Company's Warehouse");

	let resolveJobCardVehicle;
	const jobCard = loadHandlers("sotrama/public/js/job_card.js", {
		frappeOverrides: {
			db: {
				get_value: () => new Promise((resolve) => {
					resolveJobCardVehicle = resolve;
				}),
			},
		},
	})["Maintenance Job Card"];
	form = makeForm({ doc: {
		vehicle: "VEH-OLD",
		maintenance_schedule: "SCH-OLD",
		cost_center: "CC-OLD",
		odometer_before: 500,
	} });
	const pendingJobCardVehicle = jobCard.vehicle(form);
	form.doc.cost_center = "CC-MANUAL";
	form.doc.odometer_before = 650;
	resolveJobCardVehicle({
		message: { company: "COMPANY-OLD", cost_center: "CC-OLD", current_odometer: 700 },
	});
	await pendingJobCardVehicle;
	assert.equal(form.doc.cost_center, "CC-MANUAL", "A delayed Vehicle lookup must not overwrite a manually selected Cost Center");
	assert.equal(form.doc.odometer_before, 650, "A delayed Vehicle lookup must not overwrite a manually entered starting odometer");
}

runAsyncRaceTests()
	.then(() => process.stdout.write("Fleet form permission and async-race tests passed.\n"))
	.catch((error) => {
		console.error(error);
		process.exitCode = 1;
	});
