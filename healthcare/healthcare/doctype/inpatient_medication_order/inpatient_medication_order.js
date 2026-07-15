// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Inpatient Medication Order", {
	refresh: function (frm) {
		if (frm.doc.docstatus === 1) {
			frm.trigger("show_progress");
		}

		frm.events.show_medication_order_button(frm);
		frm.events.show_get_from_encounter_button(frm);
		frm.events.show_stop_medication_button(frm);

		frm.set_query("patient", () => {
			return {
				filters: {
					inpatient_record: ["!=", ""],
					inpatient_status: "Admitted",
				},
			};
		});
	},

	show_medication_order_button: function (frm) {
		frm.fields_dict["medication_orders"].grid.wrapper.find(".grid-add-row").hide();
		frm.fields_dict["medication_orders"].grid.add_custom_button(
			__("Add Medication Orders"),
			() => {
				let d = new frappe.ui.Dialog({
					title: __("Add Medication Orders"),
					fields: [
						{
							fieldname: "drug_code",
							label: __("Drug"),
							fieldtype: "Link",
							options: "Item",
							reqd: 1,
							get_query: function () {
								return {
									filters: { is_stock_item: 1 },
								};
							},
						},
						{
							fieldname: "dosage",
							label: __("Dosage"),
							fieldtype: "Link",
							options: "Prescription Dosage",
							reqd: 1,
						},
						{
							fieldname: "period",
							label: __("Period"),
							fieldtype: "Link",
							options: "Prescription Duration",
							reqd: 1,
						},
						{
							fieldname: "dosage_form",
							label: __("Dosage Form"),
							fieldtype: "Link",
							options: "Dosage Form",
							reqd: 1,
						},
					],
					primary_action_label: __("Add"),
					primary_action: () => {
						let values = d.get_values();
						if (values) {
							frm.call({
								doc: frm.doc,
								method: "add_order_entries",
								args: {
									order: values,
								},
								freeze: true,
								freeze_message: __("Adding Order Entries"),
								callback: function () {
									frm.refresh_field("medication_orders");
								},
							});
						}
					},
				});
				d.show();
			},
		);
	},

	show_get_from_encounter_button: function (frm) {
		frm.fields_dict["medication_orders"].grid.add_custom_button(
			__("Get From Encounter"),
			() => {
				if (!frm.doc.patient_encounter) {
					frappe.throw(__("Please select a Patient Encounter to get from"));
				}
				frm.call({
					doc: frm.doc,
					method: "get_from_encounter",
					args: {
						encounter: frm.doc.patient_encounter,
					},
					freeze: true,
					freeze_message: __("Getting From Encounter"),
					callback: function () {
						frm.refresh_field("medication_orders");
					},
				});
			},
		);
	},

	show_stop_medication_button: function (frm) {
		if (frm.doc.docstatus !== 1 || frm.doc.status === "Completed") {
			return;
		}

		frm.add_custom_button(__("Stop Medication Order"), () => {
			frm.call({
				doc: frm.doc,
				method: "get_pending_order_entries_for_stop",
				freeze: true,
				freeze_message: __("Fetching Pending Medication Orders"),
				callback: function (r) {
					const pending_orders = r.message || [];
					if (!pending_orders.length) {
						frappe.msgprint(
							__("No pending medication orders found to stop."),
						);
						return;
					}

					const dialog = new frappe.ui.Dialog({
						title: __("Stop Pending Medication Orders"),
						fields: [
							{
								fieldname: "stop_help",
								fieldtype: "HTML",
								options: `<div class="small text-muted" style="margin-bottom: 10px;">${__(
									"Select the pending medication dates you want to stop.",
								)}</div>`,
							},
							{
								label: __("Pending Medication Orders"),
								fieldname: "pending_orders",
								fieldtype: "Table",
								cannot_add_rows: true,
								cannot_delete_rows: true,
								in_place_edit: false,
								reqd: 1,
								data: pending_orders.map(row => ({
									order_entry_name: row.name,
									drug_name: row.drug_name || row.drug,
									dosage: row.dosage,
									date: row.date,
									time: row.time,
								})),
								fields: [
									{
										fieldname: "order_entry_name",
										fieldtype: "Data",
										hidden: 1,
									},
									{
										fieldname: "drug_name",
										fieldtype: "Data",
										label: __("Drug"),
										in_list_view: 1,
										read_only: 1,
									},
									{
										fieldname: "dosage",
										fieldtype: "Data",
										label: __("Dosage"),
										in_list_view: 1,
										read_only: 1,
									},
									{
										fieldname: "date",
										fieldtype: "Date",
										label: __("Date"),
										in_list_view: 1,
										read_only: 1,
									},
									{
										fieldname: "time",
										fieldtype: "Time",
										label: __("Time"),
										in_list_view: 1,
										read_only: 1,
									},
								],
							},
							{
								fieldname: "reason",
								label: __("Reason"),
								fieldtype: "Small Text",
								reqd: 1,
							},
						],
						primary_action_label: __("Stop Pending Orders"),
						primary_action(values) {
							const selected_rows =
								dialog.fields_dict.pending_orders.grid.get_selected_children();
							const selected_entry_names = selected_rows.map(
								row => row.order_entry_name,
							);

							if (!selected_entry_names.length) {
								frappe.throw(
									__(
										"Please select at least one pending medication order to stop.",
									),
								);
							}

							frm.call({
								doc: frm.doc,
								method: "stop_pending_order_entries",
								args: {
									reason: values.reason,
									order_entry_names: selected_entry_names,
								},
								freeze: true,
								freeze_message: __(
									"Stopping Pending Medication Orders",
								),
								callback: function () {
									dialog.hide();
									frm.reload_doc();
								},
							});
						},
					});

					dialog.show();
					dialog.fields_dict.pending_orders.grid.refresh();
					dialog.fields_dict.pending_orders.grid.wrapper
						.find(".grid-remove-rows")
						.hide();
					dialog.fields_dict.pending_orders.grid.wrapper
						.find(".grid-remove-all-rows")
						.hide();
					dialog.$wrapper.find(".modal-dialog").css("max-width", "900px");
				},
			});
		});
	},

	show_progress: function (frm) {
		let bars = [];
		let message = "";
		let total_orders = frm.doc.total_orders || 0;
		let closed_orders = frm.doc.completed_orders || 0;

		if (frm.doc.medication_orders && frm.doc.medication_orders.length) {
			total_orders = frm.doc.medication_orders.length;
			closed_orders = frm.doc.medication_orders.filter(row =>
				["Completed", "Stopped"].includes(
					row.status || (row.is_completed ? "Completed" : "Pending"),
				),
			).length;
		}

		let title = __("{0} medication orders closed", [closed_orders]);
		if (closed_orders === 1) {
			title = __("{0} medication order closed", [closed_orders]);
		}
		title += __(" out of {0}", [total_orders]);

		bars.push({
			title: title,
			width: total_orders ? (closed_orders / total_orders) * 100 + "%" : "0%",
			progress_class: "progress-bar-success",
		});
		if (bars[0].width == "0%") {
			bars[0].width = "0.5%";
		}
		message = title;
		frm.dashboard.add_progress(__("Status"), bars, message);
	},
});
