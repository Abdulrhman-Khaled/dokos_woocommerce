import frappe

def execute():
	for settings in frappe.get_all("Woocommerce Settings"):
		doc = frappe.get_doc("Woocommerce Settings", settings.name)
		doc.run_method("add_shipping_statuses")