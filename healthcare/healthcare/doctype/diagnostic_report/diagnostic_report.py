# Copyright (c) 2023, healthcare and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.workflow import get_workflow_name, get_workflow_state_field

CATEGORY_TITLE_MARKER = " [Observation Category: {0}]"


def get_diagnostic_report_base_title(patient_name, age, gender):
	return f"{patient_name} - {age or ''} {gender}"


def get_diagnostic_report_title(patient_name, age, gender, observation_category=None):
	title = get_diagnostic_report_base_title(patient_name, age, gender)
	if observation_category:
		title += CATEGORY_TITLE_MARKER.format(observation_category)
	return title


def get_observation_category_from_title(title):
	if not title or "[Observation Category:" not in title:
		return None

	_, _, suffix = title.rpartition("[Observation Category:")
	if not suffix:
		return None

	category = suffix.rstrip("]").strip()
	return category or None


def get_diagnostic_report_name(ref_doctype, docname, observation_category=None):
	filters = {"ref_doctype": ref_doctype, "docname": docname}
	if observation_category:
		filters["title"] = ["like", f"%{CATEGORY_TITLE_MARKER.format(observation_category)}"]

	return frappe.db.get_value("Diagnostic Report", filters, "name")


class DiagnosticReport(Document):
	def validate(self):
		self.set_reference_details()
		self.set_age()
		self.set_title()
		# set_diagnostic_status(self)

	def before_insert(self):
		if self.ref_doctype == "Sales Invoice" and self.docname:
			self.practitioner = frappe.db.get_value(self.ref_doctype, self.docname, "ref_practitioner")

	def set_age(self):
		if not self.age:
			patient_doc = frappe.get_doc("Patient", self.patient)
			if patient_doc.dob:
				self.age = patient_doc.calculate_age(self.reference_posting_date).get("age_in_string")

	def set_title(self):
		observation_category = get_observation_category_from_title(self.title)
		self.title = get_diagnostic_report_title(
			self.patient_name, self.age, self.gender, observation_category
		)

	def set_reference_details(self):
		if self.ref_doctype == "Sales Invoice" and self.docname:
			self.reference_posting_date = frappe.db.get_value("Sales Invoice", self.docname, "posting_date")

	@property
	def sales_invoice_status(self):
		return frappe.db.get_value(self.ref_doctype, self.docname, "status")


def diagnostic_report_print(diagnostic_report):
	from healthcare.healthcare.doctype.observation.observation import get_observation_details

	return get_observation_details(diagnostic_report)


def validate_observations_has_result(doc):
	if doc.ref_doctype == "Sales Invoice":
		submittable = True
		filters = {
			"sales_invoice": doc.docname,
			"docstatus": ["!=", 2],
			"has_component": False,
			"status": ["!=", "Cancelled"],
		}
		observation_category = get_observation_category_from_title(doc.title)
		if observation_category:
			filters["observation_category"] = observation_category
		observations = frappe.db.get_all("Observation", filters, pluck="name")
		for obs in observations:
			if not frappe.get_doc("Observation", obs).has_result():
				submittable = False
		return submittable


def set_diagnostic_status(doc):
	if doc.get("__islocal"):
		return
	filters = {
		"sales_invoice": doc.docname,
		"docstatus": 0,
		"status": ["!=", "Approved"],
		"has_component": 0,
	}
	observation_category = get_observation_category_from_title(doc.title)
	if observation_category:
		filters["observation_category"] = observation_category
	observations = frappe.db.get_all("Observation", filters)
	workflow_name = get_workflow_name("Diagnostic Report")
	workflow_state_field = get_workflow_state_field(workflow_name)
	if observations and len(observations) > 0:
		set_status = "Partially Approved"
	else:
		set_status = "Approved"
	doc.status = set_status
	doc.set(workflow_state_field, set_status)


@frappe.whitelist()
def set_observation_status(docname):
	doc = frappe.get_doc("Diagnostic Report", docname)
	if doc.ref_doctype == "Sales Invoice":
		filters = {
			"sales_invoice": doc.docname,
			"docstatus": ["!=", 2],
			"has_component": False,
			"status": ["not in", ["Cancelled", "Approved", "Rejected"]],
		}
		observation_category = get_observation_category_from_title(doc.title)
		if observation_category:
			filters["observation_category"] = observation_category
		observations = frappe.db.get_all("Observation", filters, pluck="name")
		if observations:
			for obs in observations:
				if doc.status in ["Approved", "Rejected"]:
					observation_doc = frappe.get_doc("Observation", obs)
					if observation_doc.has_result():
						if doc.status == "Approved" and observation_doc.status not in [
							"Approved",
							"Rejected",
						]:
							observation_doc.status = doc.status
							observation_doc.save().submit()
						if doc.status == "Rejected" and observation_doc.status == "Approved":
							new_doc = frappe.copy_doc(observation_doc)
							new_doc.status = ""
							new_doc.insert()
							observation_doc.cancel()
