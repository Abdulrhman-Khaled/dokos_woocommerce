import frappe

def execute():
	if settings := frappe.get_all("Woocommerce Settings"):
		frappe.get_doc("Woocommerce Settings", settings[0].name).run_method("update_property_setters")