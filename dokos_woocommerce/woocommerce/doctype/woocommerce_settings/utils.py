import frappe

def get_woocommerce_settings(url):
	return frappe.get_cached_doc("Woocommerce Settings",
		dict(
			woocommerce_server_url=url
		)
	)