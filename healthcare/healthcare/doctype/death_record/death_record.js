// Copyright (c) 2026, earthians Health Informatics Pvt. Ltd. and contributors
// For license information, please see license.txt

// frappe.ui.form.on("Death Record", {
// 	refresh(frm) {

// 	},
// });
frappe.ui.form.on("Death Record", {
    patient(frm) {
        // Clear dependent fields when patient changes
        frm.set_value("inpatient_record", null);
        frm.set_value("patient_encounter", null);
    },

    onload(frm) {
        // Filter Inpatient Record
        frm.set_query("inpatient_record", function() {
            return {
                filters: {
                    "patient": frm.doc.patient
                }
            };
        });

        // Filter Patient Encounter
        frm.set_query("patient_encounter", function() {
            return {
                filters: {
                    "patient": frm.doc.patient
                }
            };
        });
    }

});