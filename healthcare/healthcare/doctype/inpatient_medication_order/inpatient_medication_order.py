# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from typing import Any
from frappe import _
from frappe.model.document import Document
from frappe.utils import cstr

from healthcare.healthcare.doctype.patient_encounter.patient_encounter import (
	get_prescription_dates,
)


class InpatientMedicationOrder(Document):
	def validate(self):
		self.validate_inpatient()
		self.validate_duplicate()
		self.normalize_order_entry_statuses()
		self.set_status()

	def on_submit(self):
		self.validate_inpatient()
		self.normalize_order_entry_statuses()
		self.set_status(update=True)

	def on_cancel(self):
		self.set_status(update=True)

	def validate_inpatient(self):
		if not self.inpatient_record:
			frappe.throw(_("No Inpatient Record found against patient {0}").format(self.patient))

	def validate_duplicate(self):
		if not self.patient_encounter:
			return

		existing_mo = frappe.db.exists(
			"Inpatient Medication Order",
			{
				"patient_encounter": self.patient_encounter,
				"docstatus": ("!=", 2),
				"name": ("!=", self.name),
			},
		)
		if existing_mo:
			frappe.throw(
				_("An Inpatient Medication Order {0} against Patient Encounter {1} already exists.").format(
					existing_mo, self.patient_encounter
				),
				frappe.DuplicateEntryError,
			)

	def normalize_order_entry_statuses(self):
		for entry in self.medication_orders:
			if not entry.status:
				entry.status = "Completed" if entry.is_completed else "Pending"

	def get_order_entry_status(self, entry):
		return entry.status or ("Completed" if entry.is_completed else "Pending")

	def set_total_orders(self):
		self.total_orders = len(self.medication_orders)

	def set_completed_orders(self):
		self.completed_orders = sum(
			1 for entry in self.medication_orders if self.get_order_entry_status(entry) != "Pending"
		)

	def set_status(self, update=False):
		self.set_total_orders()
		self.set_completed_orders()
		status = {"0": "Draft", "1": "Submitted", "2": "Cancelled"}[cstr(self.docstatus or 0)]

		if self.docstatus == 1:
			pending_orders = self.total_orders - self.completed_orders
			if pending_orders == self.total_orders:
				status = "Pending"
			elif pending_orders == 0:
				status = "Completed"
			else:
				status = "In Process"

		self.status = status
		if update and self.name and not self.is_new():
			frappe.db.set_value(
				self.doctype,
				self.name,
				{
					"status": self.status,
					"total_orders": self.total_orders,
					"completed_orders": self.completed_orders,
				},
				update_modified=False,
			)

	def get_pending_order_entries(self):
		pending_orders = []
		for entry in self.medication_orders:
			if self.get_order_entry_status(entry) != "Pending":
				continue

			pending_orders.append(
				{
					"name": entry.name,
					"drug": entry.drug,
					"drug_name": entry.drug_name,
					"dosage": entry.dosage,
					"dosage_form": entry.dosage_form,
					"date": entry.date,
					"time": entry.time,
					"instructions": entry.instructions,
				}
			)

		return pending_orders

	@frappe.whitelist()
	def get_pending_order_entries_for_stop(self):
		return self.get_pending_order_entries()

	@frappe.whitelist()
	def stop_pending_order_entries(self, reason: str, order_entry_names: list[str] | str | None = None):
		self.check_permission("write")

		if self.docstatus != 1:
			frappe.throw(_("Only submitted Inpatient Medication Orders can be stopped."))

		reason = (reason or "").strip()
		if not reason:
			frappe.throw(_("Reason is mandatory to stop pending medication orders."))

		pending_entry_names = {entry.get("name") for entry in self.get_pending_order_entries()}
		if not pending_entry_names:
			frappe.throw(_("No pending medication orders found to stop."))

		order_entry_names = frappe.parse_json(order_entry_names) if order_entry_names else []
		selected_entry_names = [
			entry_name for entry_name in order_entry_names if entry_name in pending_entry_names
		]
		if not selected_entry_names:
			frappe.throw(_("Please select at least one pending medication order to stop."))

		selected_entries = frappe.get_all(
			"Inpatient Medication Order Entry",
			filters={"name": ("in", selected_entry_names), "parent": self.name},
			fields=["name", "status"],
		)
		selected_status_map = {entry.name: entry.status or "Pending" for entry in selected_entries}
		if len(selected_status_map) != len(selected_entry_names) or any(
			selected_status_map.get(entry_name) != "Pending" for entry_name in selected_entry_names
		):
			frappe.throw(
				_(
					"Some selected medication rows are no longer pending. Please refresh the document and try again."
				)
			)

		self.remove_rows_from_draft_ipme(selected_entry_names)

		for entry_name in selected_entry_names:
			frappe.db.set_value(
				"Inpatient Medication Order Entry",
				entry_name,
				{"status": "Stopped", "stop_reason": reason},
				update_modified=False,
			)

		self.reload()
		self.set_status(update=True)

	def get_ipme_map_for_rows(self, order_entry_names):
		entry_refs = frappe.get_all(
			"Inpatient Medication Entry Detail",
			filters={"against_imoe": ("in", order_entry_names)},
			fields=["parent", "against_imoe"],
		)

		ipme_map = {}
		for ref in entry_refs:
			ipme_map.setdefault(ref.parent, set()).add(ref.against_imoe)

		return ipme_map

	def remove_rows_from_draft_ipme(self, order_entry_names):
		ipme_map = self.get_ipme_map_for_rows(order_entry_names)

		for ipme_name, linked_order_entries in ipme_map.items():
			ipme = frappe.get_doc("Inpatient Medication Entry", ipme_name)

			if ipme.docstatus == 1:
				frappe.throw(
					_(
						"Some selected medication rows are already administered in submitted Inpatient Medication Entry {0}. Please refresh the document and try again."
					).format(frappe.bold(ipme.name))
				)

			if ipme.docstatus == 2:
				continue

			remaining_rows = [
				row for row in ipme.medication_orders if row.against_imoe not in linked_order_entries
			]

			if len(remaining_rows) == len(ipme.medication_orders):
				continue

			ipme.set("medication_orders", remaining_rows)
			if remaining_rows:
				ipme.save(ignore_permissions=True)
			else:
				frappe.delete_doc("Inpatient Medication Entry", ipme.name, ignore_permissions=True)

	@frappe.whitelist()
	def add_order_entries(self, order: dict[str, Any]):
		if order.get("drug_code"):
			dosage = frappe.get_doc("Prescription Dosage", order.get("dosage"))
			dates = get_prescription_dates(order.get("period"), self.start_date)
			for date in dates:
				for dose in dosage.dosage_strength:
					entry = self.append("medication_orders")
					entry.drug = order.get("drug_code")
					entry.drug_name = frappe.db.get_value("Item", order.get("drug_code"), "item_name")
					entry.dosage = dose.strength
					entry.dosage_form = order.get("dosage_form")
					entry.date = date
					entry.time = dose.strength_time
					entry.status = "Pending"
			self.end_date = dates[-1]
		return

	@frappe.whitelist()
	def get_from_encounter(self, encounter):
		patient_encounter = frappe.get_doc("Patient Encounter", encounter)
		if not patient_encounter.drug_prescription:
			return
		for drug in patient_encounter.drug_prescription:
			self.add_order_entries(drug)
