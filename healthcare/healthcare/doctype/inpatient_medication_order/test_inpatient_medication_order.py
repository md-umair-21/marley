# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt


import frappe
from frappe.utils import add_days, getdate, now_datetime

from healthcare.healthcare.doctype.inpatient_record.inpatient_record import (
	admit_patient,
	discharge_patient,
	schedule_discharge,
)
from healthcare.healthcare.doctype.inpatient_record.test_inpatient_record import (
	create_inpatient,
	get_healthcare_service_unit,
	mark_invoiced_inpatient_occupancy,
)
from healthcare.tests.utils import HealthcareTestSuite


class TestInpatientMedicationOrder(HealthcareTestSuite):
	def setUp(self):
		super().setUp()
		frappe.db.sql("""delete from `tabInpatient Record`""")
		self.patient = frappe.get_list("Patient", pluck="name")[0]

		# Admit
		ip_record = create_inpatient(self.patient)
		ip_record.expected_length_of_stay = 0
		ip_record.save()
		ip_record.reload()
		service_unit = get_healthcare_service_unit()
		admit_patient(ip_record, service_unit, now_datetime())
		self.ip_record = ip_record

	def test_order_creation(self):
		ipmo = create_ipmo(self.patient)
		ipmo.submit()
		ipmo.reload()

		# 3 dosages per day for 2 days
		self.assertEqual(len(ipmo.medication_orders), 6)
		self.assertEqual(ipmo.medication_orders[0].date, add_days(getdate(), -1))
		self.assertEqual(ipmo.medication_orders[0].status, "Pending")

		prescription_dosage = frappe.get_doc("Prescription Dosage", "1-1-1")
		for i in range(len(prescription_dosage.dosage_strength)):
			self.assertEqual(
				ipmo.medication_orders[i].time, prescription_dosage.dosage_strength[i].strength_time
			)

		self.assertEqual(ipmo.medication_orders[3].date, getdate())

	def test_inpatient_validation(self):
		# Discharge
		schedule_discharge(frappe.as_json({"patient": self.patient}))

		self.ip_record.reload()
		mark_invoiced_inpatient_occupancy(self.ip_record)

		self.ip_record.reload()
		discharge_patient(self.ip_record)

		ipmo = create_ipmo(self.patient)
		# inpatient validation
		self.assertRaises(frappe.ValidationError, ipmo.insert)

	def test_status(self):
		ipmo = create_ipmo(self.patient)
		ipmo.submit()
		ipmo.reload()

		self.assertEqual(ipmo.status, "Pending")

		filters = frappe._dict(
			from_date=add_days(getdate(), -1), to_date=add_days(getdate(), -1), from_time="", to_time=""
		)
		ipme = create_ipme(filters)
		ipme.submit()
		ipmo.reload()
		self.assertEqual(ipmo.status, "In Process")
		self.assertEqual(ipmo.medication_orders[0].status, "Completed")

		filters = frappe._dict(from_date=getdate(), to_date=getdate(), from_time="", to_time="")
		ipme = create_ipme(filters)
		ipme.submit()
		ipmo.reload()
		self.assertEqual(ipmo.status, "Completed")

	def test_multiple_orders_without_patient_encounter(self):
		first_ipmo = create_ipmo(self.patient)
		first_ipmo.insert()

		second_ipmo = create_ipmo(self.patient)
		second_ipmo.start_date = add_days(getdate(), 2)
		second_ipmo.insert()

		self.assertTrue(first_ipmo.name)
		self.assertEqual(first_ipmo.docstatus, 0)
		self.assertFalse(first_ipmo.patient_encounter)

		self.assertTrue(second_ipmo.name)
		self.assertEqual(second_ipmo.docstatus, 0)
		self.assertFalse(second_ipmo.patient_encounter)

	def test_parent_status_is_in_process_when_pending_and_stopped_rows_exist(self):
		ipmo = create_ipmo(self.patient)
		ipmo.submit()
		frappe.db.set_value(
			"Inpatient Medication Order Entry",
			ipmo.medication_orders[0].name,
			{"status": "Stopped", "stop_reason": "Doctor changed treatment"},
			update_modified=False,
		)
		ipmo.reload()
		ipmo.set_status(update=True)
		ipmo.reload()

		self.assertEqual(ipmo.status, "In Process")

	def test_stop_pending_orders_updates_rows_and_keeps_draft_ipme(self):
		ipmo = create_ipmo(self.patient)
		ipmo.submit()

		filters = frappe._dict(
			from_date=add_days(getdate(), -1), to_date=add_days(getdate(), -1), from_time="", to_time=""
		)
		ipme = create_ipme(filters)
		ipme.submit()

		draft_filters = frappe._dict(from_date=getdate(), to_date=getdate(), from_time="", to_time="")
		draft_ipme = create_ipme(draft_filters)
		draft_ipme.insert()
		draft_row_count = len(draft_ipme.medication_orders)
		selected_entries = [entry.name for entry in ipmo.medication_orders if entry.date == getdate()]
		ipmo.reload()
		ipmo.stop_pending_order_entries("Doctor instructed to stop remaining medication", selected_entries)
		ipmo.reload()
		draft_ipme.reload()
		self.assertEqual(ipmo.status, "Completed")
		self.assertTrue(frappe.db.exists("Inpatient Medication Entry", draft_ipme.name))
		self.assertEqual(len(draft_ipme.medication_orders), draft_row_count)

		for entry in ipmo.medication_orders:
			if entry.date == getdate():
				self.assertEqual(entry.status, "Stopped")
				self.assertEqual(entry.stop_reason, "Doctor instructed to stop remaining medication")
			else:
				self.assertEqual(entry.status, "Completed")

	def test_stop_pending_orders_only_updates_selected_rows(self):
		ipmo = create_ipmo(self.patient)
		ipmo.submit()
		selected_entry = ipmo.medication_orders[0].name

		ipmo.stop_pending_order_entries("Stop only first slot", [selected_entry])
		ipmo.reload()

		self.assertEqual(ipmo.status, "In Process")
		self.assertEqual(ipmo.medication_orders[0].status, "Stopped")
		self.assertEqual(ipmo.medication_orders[0].stop_reason, "Stop only first slot")
		self.assertEqual(ipmo.medication_orders[1].status, "Pending")

	def test_stop_pending_orders_throws_refresh_error_if_selected_rows_changed(self):
		ipmo = create_ipmo(self.patient)
		ipmo.submit()
		selected_entry = ipmo.medication_orders[0].name

		frappe.db.set_value(
			"Inpatient Medication Order Entry",
			selected_entry,
			"status",
			"Completed",
			update_modified=False,
		)

		self.assertRaisesRegex(
			frappe.ValidationError,
			"Some selected medication rows are no longer pending",
			lambda: ipmo.stop_pending_order_entries("Stop stale row", [selected_entry]),
		)

	def tearDown(self):
		if frappe.db.get_value("Patient", self.patient, "inpatient_record"):
			# cleanup - Discharge
			schedule_discharge(frappe.as_json({"patient": self.patient}))
			self.ip_record.reload()
			mark_invoiced_inpatient_occupancy(self.ip_record)

			self.ip_record.reload()
			discharge_patient(self.ip_record)

		for doctype in ["Inpatient Medication Entry", "Inpatient Medication Order"]:
			frappe.db.sql(f"delete from `tab{doctype}`")


def create_dosage_form():
	if not frappe.db.exists("Dosage Form", "Tablet"):
		frappe.get_doc({"doctype": "Dosage Form", "dosage_form": "Tablet"}).insert()


def create_drug(item=None):
	if not item:
		item = "Dextromethorphan"
	drug = frappe.db.exists("Item", {"item_code": "Dextromethorphan"})
	if not drug:
		drug = frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": "Dextromethorphan",
				"item_name": "Dextromethorphan",
				"item_group": "Products",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"valuation_rate": 50,
				"opening_stock": 20,
			}
		).insert()


def get_orders():
	create_dosage_form()
	create_drug()
	return {
		"drug_code": "Dextromethorphan",
		"drug_name": "Dextromethorphan",
		"dosage": "1-1-1",
		"dosage_form": "Tablet",
		"period": "2 Day",
	}


def create_ipmo(patient):
	orders = get_orders()
	ipmo = frappe.new_doc("Inpatient Medication Order")
	ipmo.patient = patient
	ipmo.company = "_Test Company"
	ipmo.start_date = add_days(getdate(), -1)
	ipmo.add_order_entries(orders)

	return ipmo


def create_ipme(filters, update_stock=0):
	ipme = frappe.new_doc("Inpatient Medication Entry")
	ipme.company = "_Test Company"
	ipme.posting_date = getdate()
	ipme.update_stock = update_stock
	if update_stock:
		ipme.warehouse = "Stores - _TC"
	for key, value in filters.items():
		ipme.set(key, value)
	ipme = ipme.get_medication_orders()

	return ipme
