# Copyright (c) 2023, healthcare and Contributors
# See license.txt

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import flt, getdate, nowtime

from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
	get_income_account,
	get_receivable_account,
)
from healthcare.healthcare.doctype.diagnostic_report.diagnostic_report import (
	get_diagnostic_report_name,
	get_diagnostic_report_title,
)
from healthcare.healthcare.doctype.observation.observation import get_observation_details
from healthcare.tests.utils import HealthcareTestSuite


class TestObservation(HealthcareTestSuite):
	def test_single_observation_from_invoice_without_sample(self):
		self.enable_observation_on_invoice_submit()

		obs_name = "_Test Observation without Sample"
		patient = self.get_test_patient()
		obs_template = frappe.get_doc("Observation Template", obs_name)
		sales_invoice = create_sales_invoice(patient, obs_name)

		self.assertTrue(
			frappe.db.exists(
				"Observation",
				{
					"observation_template": obs_template.name,
					"patient": patient,
					"sales_invoice": sales_invoice.name,
				},
			)
		)

		self.assertTrue(
			frappe.db.exists(
				"Diagnostic Report",
				{
					"docname": sales_invoice.name,
					"patient": patient,
				},
			)
		)

	def test_single_observation_from_invoice_with_sample(self):
		self.enable_observation_on_invoice_submit()

		patient = self.get_test_patient()
		obs_name = "_Test Observation with Sample"
		obs_template = frappe.get_doc("Observation Template", obs_name)
		sales_invoice = create_sales_invoice(patient, obs_name)

		sample_docname = frappe.db.exists(
			"Sample Collection",
			{
				"patient": patient,
			},
		)

		self.assertTrue(sample_docname)
		self.assertTrue(
			frappe.db.exists(
				"Observation Sample Collection",
				{
					"parent": sample_docname,
					"observation_template": obs_template.name,
				},
			)
		)

		self.assertTrue(
			frappe.db.exists(
				"Diagnostic Report",
				{
					"docname": sales_invoice.name,
					"patient": patient,
				},
			)
		)

	def test_has_component_observation_from_invoice_without_sample(self):
		self.enable_observation_on_invoice_submit()

		patient = self.get_test_patient()
		obs_name = "_Test Observation Grouped without Sample"
		obs_template = frappe.get_doc("Observation Template", obs_name)
		sales_invoice = create_sales_invoice(patient, obs_name)

		self.assertTrue(
			frappe.db.exists(
				"Observation",
				{
					"observation_template": obs_template.name,
					"patient": patient,
					"sales_invoice": sales_invoice.name,
				},
			)
		)

		self.assertTrue(
			frappe.db.exists(
				"Observation",
				{
					"observation_template": obs_name,
					"patient": patient,
					"sales_invoice": sales_invoice.name,
				},
			)
		)

		self.assertTrue(
			frappe.db.exists(
				"Diagnostic Report",
				{
					"docname": sales_invoice.name,
					"patient": patient,
				},
			)
		)

	def test_has_component_observation_from_invoice_with_sample(self):
		self.enable_observation_on_invoice_submit()

		patient = self.get_test_patient()
		obs_name = "_Test Observation Grouped with Sample"
		obs_template = frappe.get_doc("Observation Template", obs_name)
		sales_invoice = create_sales_invoice(patient, obs_name)

		self.assertTrue(
			frappe.db.exists(
				"Observation",
				{
					"observation_template": obs_template.name,
					"patient": patient,
					"sales_invoice": sales_invoice.name,
				},
			)
		)

		sample_docname = frappe.db.exists(
			"Sample Collection",
			{
				"patient": patient,
			},
		)

		self.assertTrue(sample_docname)
		self.assertTrue(
			frappe.db.exists(
				"Observation Sample Collection",
				{
					"parent": sample_docname,
					"observation_template": obs_template.name,
				},
			)
		)

		self.assertTrue(
			frappe.db.exists(
				"Diagnostic Report",
				{
					"docname": sales_invoice.name,
					"patient": patient,
				},
			)
		)

	def test_observation_from_encounter(self):
		observation_template = frappe.get_doc("Observation Template", "_Test Observation without Sample")
		patient = self.get_test_patient()
		encounter = create_patient_encounter(patient, observation_template.name)

		self.assertTrue(
			frappe.db.exists(
				"Service Request",
				{
					"patient": patient,
					"template_dn": observation_template.name,
					"order_group": encounter.name,
				},
			)
		)

	def test_category_specific_reports_filter_observations(self):
		self.enable_observation_on_invoice_submit()

		patient = self.get_test_patient()
		sales_invoice = create_sales_invoice(patient, "_Test Observation without Sample")
		lab_report = get_diagnostic_report_name("Sales Invoice", sales_invoice.name, "Laboratory")
		self.assertTrue(lab_report)

		imaging_template = ensure_imaging_observation_template()
		imaging_observation = frappe.new_doc("Observation")
		imaging_observation.posting_datetime = getdate()
		imaging_observation.patient = patient
		imaging_observation.observation_template = imaging_template.name
		imaging_observation.sales_invoice = sales_invoice.name
		imaging_observation.company = sales_invoice.company
		imaging_observation.result_text = "Clear"
		imaging_observation.insert(ignore_permissions=True)

		patient_doc = frappe.get_doc("Patient", patient)
		imaging_report = frappe.new_doc("Diagnostic Report")
		imaging_report.company = sales_invoice.company
		imaging_report.patient = patient
		imaging_report.ref_doctype = "Sales Invoice"
		imaging_report.docname = sales_invoice.name
		imaging_report.title = get_diagnostic_report_title(
			patient_doc.patient_name,
			patient_doc.calculate_age(sales_invoice.posting_date).get("age_in_string"),
			patient_doc.sex,
			"Imaging",
		)
		imaging_report.save(ignore_permissions=True)

		lab_data, _ = get_observation_details(lab_report)
		imaging_data, _ = get_observation_details(imaging_report.name)

		self.assertTrue(lab_data)
		self.assertTrue(imaging_data)
		self.assertEqual(
			{"Laboratory"}, {row["observation"]["observation_category"] for row in lab_data}
		)
		self.assertEqual({"Imaging"}, {row["observation"]["observation_category"] for row in imaging_data})

	def test_category_specific_status_updates_only_matching_report(self):
		self.enable_observation_on_invoice_submit()

		patient = self.get_test_patient()
		sales_invoice = create_sales_invoice(patient, "_Test Observation without Sample")
		lab_report = get_diagnostic_report_name("Sales Invoice", sales_invoice.name, "Laboratory")
		self.assertTrue(lab_report)

		imaging_template = ensure_imaging_observation_template()
		imaging_observation = frappe.new_doc("Observation")
		imaging_observation.posting_datetime = getdate()
		imaging_observation.patient = patient
		imaging_observation.observation_template = imaging_template.name
		imaging_observation.sales_invoice = sales_invoice.name
		imaging_observation.company = sales_invoice.company
		imaging_observation.result_text = "Clear"
		imaging_observation.insert(ignore_permissions=True)

		patient_doc = frappe.get_doc("Patient", patient)
		imaging_report = frappe.new_doc("Diagnostic Report")
		imaging_report.company = sales_invoice.company
		imaging_report.patient = patient
		imaging_report.ref_doctype = "Sales Invoice"
		imaging_report.docname = sales_invoice.name
		imaging_report.title = get_diagnostic_report_title(
			patient_doc.patient_name,
			patient_doc.calculate_age(sales_invoice.posting_date).get("age_in_string"),
			patient_doc.sex,
			"Imaging",
		)
		imaging_report.save(ignore_permissions=True)

		lab_observation = frappe.get_all(
			"Observation",
			filters={
				"sales_invoice": sales_invoice.name,
				"observation_category": "Laboratory",
			},
			fields=["name"],
			limit=1,
		)[0]
		lab_observation_doc = frappe.get_doc("Observation", lab_observation.name)
		lab_observation_doc.result_data = "5"
		lab_observation_doc.status = "Approved"
		lab_observation_doc.save()
		lab_observation_doc.submit()

		self.assertEqual("Approved", frappe.db.get_value("Diagnostic Report", lab_report, "status"))
		self.assertEqual("Open", frappe.db.get_value("Diagnostic Report", imaging_report.name, "status"))

	def test_formula_computes_result(self):
		self.enable_observation_on_invoice_submit()
		patient = self.get_test_patient()

		result = self.run_formula_test_case(
			patient=patient,
			input_value_1=5,
			input_value_2=2,
			operator="+",
		)

		self.assertEqual(flt(result["formula_1_result"]), 7)

	def test_formula_with_invalid_operand_keeps_result_empty(self):
		self.enable_observation_on_invoice_submit()
		patient = self.get_test_patient()

		result = self.run_formula_test_case(
			patient=patient,
			input_value_1="a",
			input_value_2=8,
			operator="*",
			operand_1_db_set=True,
		)

		self.assertIsNone(result["formula_1_result"])

	def test_formula_can_use_patient_custom_field(self):
		self.enable_observation_on_invoice_submit()
		self.ensure_patient_custom_field()

		patient = self.get_test_patient()
		custom_field_value = 10
		frappe.db.set_value("Patient", patient, "test_custom_field", custom_field_value)

		result = self.run_formula_test_case(
			patient=patient,
			input_value_1=5,
			input_value_2=2,
			operator="+",
			custom_formula=f"+{custom_field_value}",
		)

		self.assertEqual(flt(result["formula_1_result"]), 17)

	def test_formula_respects_patient_condition(self):
		self.enable_observation_on_invoice_submit()
		patient = self.get_test_patient()

		result = self.run_formula_test_case(
			patient=patient,
			input_value_1=7,
			input_value_2=5,
			operator="+",
			condition1="gender=='Male'",
			condition2="gender=='Female'",
		)

		self.assertEqual(flt(result["formula_2_result"]), 2)

	def run_formula_test_case(
		self,
		patient,
		input_value_1,
		input_value_2,
		operator,
		custom_formula="",
		condition1=None,
		condition2=None,
		operand_1_db_set=False,
	):
		obs_name = "_Test Observation Grouped without Sample"
		obs_template = frappe.get_doc("Observation Template", obs_name)

		first_component = obs_template.observation_component[0]
		first_abbr = first_component.abbr
		first_obs_template = first_component.observation_template

		operand_2_template = frappe.get_doc("Observation Template", "_Test Observation Operand 2")
		result_template_1 = frappe.get_doc("Observation Template", "_Test Observation Formula Result 1")

		obs_template.append(
			"observation_component",
			{
				"observation_template": operand_2_template.name,
				"abbr": operand_2_template.abbr,
			},
		)

		obs_template.append(
			"observation_component",
			{
				"observation_template": result_template_1.name,
				"abbr": "TF1",
				"based_on_formula": 1,
				"formula": f"{first_abbr}{operator}{operand_2_template.abbr} {custom_formula}".strip(),
				"condition": condition1,
			},
		)

		result_template_2 = None
		if condition2:
			result_template_2 = frappe.get_doc("Observation Template", "_Test Observation Formula Result 2")
			obs_template.append(
				"observation_component",
				{
					"observation_template": result_template_2.name,
					"abbr": "TF2",
					"based_on_formula": 1,
					"formula": f"{first_abbr}-{operand_2_template.abbr}",
					"condition": condition2,
				},
			)

		obs_template.save()

		create_sales_invoice(patient, obs_template.name)

		child_obs_1 = self.get_latest_observation_name(patient, first_obs_template)
		child_obs_2 = self.get_latest_observation_name(patient, operand_2_template.name)

		if not operand_1_db_set:
			child_obs_1_doc = frappe.get_doc("Observation", child_obs_1)
			child_obs_1_doc.result_data = str(input_value_1)
			child_obs_1_doc.save()
		else:
			frappe.db.set_value("Observation", child_obs_1, "result_data", str(input_value_1))

		child_obs_2_doc = frappe.get_doc("Observation", child_obs_2)
		child_obs_2_doc.result_data = str(input_value_2)
		child_obs_2_doc.save()

		return {
			"formula_1_result": self.get_result_data(patient, result_template_1.name),
			"formula_2_result": self.get_result_data(patient, result_template_2.name)
			if result_template_2
			else None,
		}

	def get_latest_observation_name(self, patient, observation_template):
		rows = frappe.get_all(
			"Observation",
			filters={
				"patient": patient,
				"observation_template": observation_template,
			},
			fields=["name"],
			order_by="creation desc",
			limit=1,
		)

		self.assertTrue(rows, f"No Observation found for template {observation_template}")
		return rows[0].name

	def get_result_data(self, patient, observation_template):
		rows = frappe.get_all(
			"Observation",
			filters={
				"patient": patient,
				"observation_template": observation_template,
			},
			fields=["name", "result_data"],
			order_by="creation desc",
			limit=1,
		)

		self.assertTrue(rows, f"No Observation found for template {observation_template}")
		return rows[0].result_data

	def get_test_patient(self):
		return frappe.get_list("Patient", pluck="name")[0]

	def enable_observation_on_invoice_submit(self):
		frappe.db.set_single_value("Healthcare Settings", "create_observation_on_si_submit", 1)

	def ensure_patient_custom_field(self):
		custom_fields = {
			"Patient": [
				{
					"fieldname": "test_custom_field",
					"label": "Test Calculation",
					"fieldtype": "Int",
				}
			]
		}
		create_custom_fields(custom_fields, update=True)


def create_sales_invoice(patient, item):
	sales_invoice = frappe.new_doc("Sales Invoice")
	sales_invoice.patient = patient
	sales_invoice.customer = frappe.db.get_value("Patient", patient, "customer")
	sales_invoice.due_date = getdate()
	sales_invoice.company = "_Test Company"
	sales_invoice.debit_to = get_receivable_account("_Test Company")
	sales_invoice.append(
		"items",
		{
			"item_code": item,
			"item_name": item,
			"description": item,
			"qty": 1,
			"uom": "Nos",
			"conversion_factor": 1,
			"income_account": get_income_account(None, "_Test Company"),
			"rate": 300,
			"amount": 300,
		},
	)

	sales_invoice.set_missing_values()
	sales_invoice.submit()
	return sales_invoice


def create_patient_encounter(patient, observation_template):
	patient_encounter = frappe.new_doc("Patient Encounter")
	patient_encounter.patient = patient
	patient_encounter.practitioner = frappe.get_list("Healthcare Practitioner", pluck="name")[0]
	patient_encounter.appointment_type = "_Test Appointment Type"
	patient_encounter.encounter_date = getdate()
	patient_encounter.encounter_time = nowtime()

	patient_encounter.append("lab_test_prescription", {"observation_template": observation_template})

	patient_encounter.submit()
	return patient_encounter


def ensure_imaging_observation_template():
	template_name = "_Test Imaging Observation"
	expected_category = "Imaging"
	if frappe.db.exists("Observation Template", template_name):
		template = frappe.get_doc("Observation Template", template_name)
		if template.observation_category == expected_category:
			return template

	template = frappe.new_doc("Observation Template")
	template.observation = template_name
	template.abbr = "TIO"
	template.observation_category = expected_category
	template.permitted_data_type = "Text"
	template.sample_collection_required = 0
	template.item_group = "Services"
	template.insert(ignore_permissions=True)
	return template
