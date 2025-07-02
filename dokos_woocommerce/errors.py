import frappe
from frappe import _


def handle_woocommerce_error(func):
	def wrapper(*args, **kwargs):
		try:
			return func(*args, **kwargs)
		except frappe.exceptions.ValidationError as e:
			sync = args[0]
			sync.order.db_set("error_message", str(e))
			raise

	return wrapper