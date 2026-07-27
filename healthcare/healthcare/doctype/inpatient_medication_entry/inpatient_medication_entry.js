// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

function prompt_to_remove_stopped_rows(frm) {
	if (
		frm.doc.docstatus !== 0 ||
		!(frm.doc.medication_orders || []).length ||
		frm.__stopped_row_prompt_open
	) {
		return;
	}

	frappe.call({
		method: "get_stopped_linked_rows",
		doc: frm.doc,
		callback: function (r) {
			const stopped_rows = r.message || [];
			if (!stopped_rows.length) {
				return;
			}

			frm.__stopped_row_prompt_open = true;
			const message =
				stopped_rows.length === 1
					? __(
							"1 medication row in this draft entry was stopped in the linked Inpatient Medication Order. Do you want to remove it now?",
					  )
					: __(
							"{0} medication rows in this draft entry were stopped in the linked Inpatient Medication Order. Do you want to remove them now?",
							[stopped_rows.length],
					  );

			frappe.confirm(
				message,
				() => {
					const rows_to_remove = new Set(stopped_rows.map(row => row.name));
					const remaining_rows = (frm.doc.medication_orders || [])
						.filter(row => !rows_to_remove.has(row.name))
						.map(row => ({ ...row }));
					frappe.model.clear_table(frm.doc, "medication_orders");
					remaining_rows.forEach(row =>
						frm.add_child("medication_orders", row),
					);
					frm.refresh_field("medication_orders");
					frm.dirty();
					frm.__stopped_row_prompt_open = false;
				},
				() => {
					frm.__stopped_row_prompt_open = false;
					frappe.show_alert({
						message: __(
							"Stopped medication rows were kept in draft. Remove them before saving or submitting.",
						),
						indicator: "orange",
					});
				},
			);
		},
	});
}

frappe.ui.form.on("Inpatient Medication Entry", {
	refresh: function (frm) {
		// Ignore cancellation of doctype on cancel all
		frm.ignore_doctypes_on_cancel_all = ["Stock Entry"];
		frm.fields_dict["medication_orders"].grid.wrapper.find(".grid-add-row").hide();

		frm.set_query("item_code", () => {
			return {
				filters: {
					is_stock_item: 1,
				},
			};
		});

		frm.set_query("drug_code", "medication_orders", () => {
			return {
				filters: {
					is_stock_item: 1,
				},
			};
		});

		frm.set_query("warehouse", () => {
			return {
				filters: {
					company: frm.doc.company,
				},
			};
		});

		prompt_to_remove_stopped_rows(frm);

		if (frm.doc.__islocal || frm.doc.docstatus !== 0 || !frm.doc.update_stock)
			return;

		frm.add_custom_button(__("Make Stock Entry"), function () {
			frappe.call({
				method: "healthcare.healthcare.doctype.inpatient_medication_entry.inpatient_medication_entry.make_difference_stock_entry",
				args: { docname: frm.doc.name },
				freeze: true,
				callback: function (r) {
					if (r.message) {
						var doclist = frappe.model.sync(r.message);
						frappe.set_route("Form", doclist[0].doctype, doclist[0].name);
					} else {
						frappe.msgprint({
							title: __("No Drug Shortage"),
							message: __(
								"All the drugs are available with sufficient qty to process this Inpatient Medication Entry.",
							),
							indicator: "green",
						});
					}
				},
			});
		});
	},

	patient: function (frm) {
		if (frm.doc.patient) frm.set_value("service_unit", "");
	},

	get_medication_orders: function (frm) {
		frappe.call({
			method: "get_medication_orders",
			doc: frm.doc,
			freeze: true,
			freeze_message: __("Fetching Pending Medication Orders"),
			callback: function () {
				refresh_field("medication_orders");
				prompt_to_remove_stopped_rows(frm);
			},
		});
	},
});
