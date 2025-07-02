// Copyright (c) 2022, Dokos SAS and contributors
// For license information, please see license.txt

frappe.ui.form.on('Woocommerce Order', {
	refresh: function(frm) {
		frm.add_custom_button(__('Retry'), () => {
			frappe.call({
				method:"dokos_woocommerce.woocommerce.doctype.woocommerce_order.woocommerce_order.process_order",
				args: {
					order: frm.doc.name
				}
			}).then(() => {
				frappe.show_alert({
					message: __("Retry in progress"),
					indicator: "green"
				})
			})
		}, __("Actions"));

		frm.add_custom_button(__('Close'), () => {
			frm.set_value("status", "Closed")
			frm.save()
		}, __("Actions"))

		frappe.db.get_value("Sales Order", {[`woocommerce_id_${frm.doc.woocommerce_settings}`]: frm.doc.woocommerce_id}, "name", r => {
			if (r.name) {
				frm.add_custom_button(__('Sales Order'), () => {
					frappe.set_route("List", "Sales Order", {[`woocommerce_id_${frm.doc.woocommerce_settings}`]: frm.doc.woocommerce_id})
				})
			}
		})
	}
});
