// Copyright (c) 2025, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Practitioner Availability", {
	refresh: function (frm) {
		frm.events.toggle_capacity_fields(frm);
	},

	end_time: function (frm) {
		frm.events.set_duration(frm);
	},

	start_time: function (frm) {
		frm.events.set_duration(frm);
	},

	set_duration: function (frm) {
		if (frm.doc.end_time && frm.doc.start_time) {
			end_date = frm.doc.end_date || frm.doc.start_date;

			start = new Date(`${frm.doc.start_date} ${frm.doc.start_time}`);
			end = new Date(`${frm.doc.end_date} ${frm.doc.end_time}`);

			frm.set_value("duration", (parseInt(end - start) / 60000) | 0);
		}
	},

	validate: function (frm) {
		if (frm.doc.type == "Available") {
			frm.set_value("reason", "");
		}
	},

	type: function (frm) {
		frm.events.toggle_capacity_fields(frm);
		if (
			frm.doc.type == "Available" &&
			frm.doc.scope_type != "Healthcare Practitioner"
		) {
			frm.set_value("scope_type", "Healthcare Practitioner");
		}
	},

	create_slots: function (frm) {
		frm.events.toggle_capacity_fields(frm);
	},

	toggle_capacity_fields: function (frm) {
		const show_capacity =
			frm.doc.type == "Available" && !cint(frm.doc.create_slots);
		frm.toggle_reqd("maximum_appointments", show_capacity);
		if (!show_capacity) {
			frm.set_value("maximum_appointments", null);
		}
	},
});
