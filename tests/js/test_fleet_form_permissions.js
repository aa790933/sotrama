const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function loadHandlers(path) {
	const handlers = {};
	const frappe = {
		ui: {
			form: {
				on(doctype, events) {
					handlers[doctype] = events;
				},
			},
		},
		utils: { flt: (value) => Number(value) || 0 },
	};

	vm.runInNewContext(fs.readFileSync(path, "utf8"), {
		frappe,
		locals: {},
		__: (value) => value,
	});

	return handlers;
}

function makeForm({ isNew = false, docstatus = 0, permissions = [], company = "SOTRAMA" } = {}) {
	return {
		perm: permissions,
        doc: { docstatus, company },
		buttons: [],
        queries: {},
		is_new: () => isNew,
		add_custom_button(...args) {
			this.buttons.push(args);
		},
		add_child() {
			return {};
		},
        set_query(fieldname, callback) {
            this.queries[fieldname] = callback;
        },
		refresh_field() {},
		dashboard: { show_alert() {} },
	};
}

const jobCard = loadHandlers("sotrama/public/js/job_card.js")["Maintenance Job Card"];
let form = makeForm({ isNew: false, permissions: [{ create: true, write: false }] });
jobCard.refresh(form);
assert.equal(form.buttons.length, 0, "Create-only users must not edit saved job-card drafts");

form = makeForm({ isNew: true, permissions: [{ create: true, write: false }] });
jobCard.refresh(form);
assert.equal(form.buttons.length, 3, "Create permission must expose all add-entry actions on new job cards");

form = makeForm({ isNew: false, permissions: [{ create: false, write: true }] });
jobCard.refresh(form);
assert.equal(form.buttons.length, 3, "Write permission must expose all add-entry actions on saved drafts");

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

form = makeForm({ isNew: false, docstatus: 1, permissions: [{ create: true, write: true }] });
inspection.refresh(form);
assert.equal(form.buttons.length, 0, "Submitted inspections must not expose draft checklist actions");

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

process.stdout.write("Fleet form permission tests passed.\n");
