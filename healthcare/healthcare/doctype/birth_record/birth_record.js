// Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Birth Record", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Birth Record", {
	mother_patient(frm) {
		// Clear dependent fields when mother changes
		frm.set_value("inpatient_record", null);
		frm.set_value("patient_encounter", null);
	},

	onload(frm) {
		// Filter Inpatient Record
		frm.set_query("inpatient_record", function () {
			return {
				filters: {
					patient: frm.doc.mother_patient,
				},
			};
		});

		// Filter Patient Encounter
		frm.set_query("patient_encounter", function () {
			return {
				filters: {
					patient: frm.doc.mother_patient,
				},
			};
		});
	},
});
