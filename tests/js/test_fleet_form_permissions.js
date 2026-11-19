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

function makeForm({ isNew = false, docstatus = 0, permissions = [] } = {}) {
	return {
		perm: permissions,
		doc: { docstatus },
		buttons: [],
		is_new: () => isNew,
		add_custom_button(...args) {
			this.buttons.push(args);
		},
		add_child() {
			return {};
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

process.stdout.write("Fleet form permission tests passed.\n");
