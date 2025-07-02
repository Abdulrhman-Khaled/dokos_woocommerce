import frappe
from dokos_woocommerce.patches.allow_multiple_woocommerce_sites import execute as _allow_multiple_woocommerce_sites

def before_install():
	if frappe.db.exists("DocType", "WooCommerce Settings"):
		frappe.db.delete("DocType", "WooCommerce Settings")
		frappe.db.commit()

	Singles = frappe.qb.DocType("Singles")
	if frappe.qb.from_(Singles).select(Singles.field).where(Singles.doctype=="WooCommerce Settings").run():
		_allow_multiple_woocommerce_sites()


def before_tests():
	from erpnext.setup.utils import before_tests as _before_tests

	_before_tests()