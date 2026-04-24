# Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint


class BirthRecord(Document):
	def validate(self):
		for newborn_detail in self.get("newborn_details") or []:
			self.validate_birth_outcome(newborn_detail)
			self.validate_apgar_scores(newborn_detail)

	def validate_birth_outcome(self, newborn_detail):
		live_birth = cint(newborn_detail.live_birth)
		stillbirth = cint(newborn_detail.stillbirth)

		if live_birth == stillbirth:
			frappe.throw(
				frappe._(
					"Select exactly one birth outcome: either Live Birth or Stillbirth. (Row {0})"
				).format(newborn_detail.idx)
			)

	def validate_apgar_scores(self, newborn_detail):
		for fieldname in ("apgar_1_min", "apgar_5_min", "apgar_10_min"):
			value = newborn_detail.get(fieldname)
			if value is None:
				continue

			if isinstance(value, bool):
				frappe.throw(
					frappe._("Invalid {0}: {1}. Expected an integer between 0 and 10. (Row {2})").format(
						fieldname, value, newborn_detail.idx
					)
				)

			try:
				int_value = int(value)
			except (TypeError, ValueError):
				frappe.throw(
					frappe._("Invalid {0}: {1}. Expected an integer between 0 and 10. (Row {2})").format(
						fieldname, value, newborn_detail.idx
					)
				)

			if str(value).strip() != str(int_value) or not 0 <= int_value <= 10:
				frappe.throw(
					frappe._("Invalid {0}: {1}. Expected an integer between 0 and 10. (Row {2})").format(
						fieldname, value, newborn_detail.idx
					)
				)
