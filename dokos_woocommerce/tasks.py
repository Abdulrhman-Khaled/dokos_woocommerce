import frappe
from frappe.utils import getdate, add_months, nowdate

from dokos_woocommerce.woocommerce.doctype.woocommerce_order.woocommerce_order import process_order

def retry_orders_in_error_status():
	for order in frappe.get_all("Woocommerce Order", filters={"status": "Error"}):
		process_order(order.name)


def retry_incomplete_orders():
	for order in frappe.get_all("Woocommerce Order", filters={"status": ("!=", "Closed")}, or_filters={"order_created": 0, "delivery_note_created": 0, "payment_created": 0, "sales_invoice_created": 0}, fields=["name", "data"]):
		data = frappe.parse_json(order.data)
		date_created = data.get("date_created")
		date_completed = data.get("date_completed")

		if date_completed and getdate(date_completed) <= getdate(add_months(nowdate(), -1)):
			process_order(order.name)

		elif date_created and getdate(date_created) <= getdate(add_months(nowdate(), -1)):
			process_order(order.name)