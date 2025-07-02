import frappe
from itertools import groupby

def execute():
	settings = frappe.get_all("Woocommerce Settings", pluck="name")
	for setting in settings:
		fieldname = f"woocommerce_id_{setting}"
		sales_orders = frappe.get_all("Sales Order", filters={fieldname: ("is", "set"), "docstatus": 1, "status": ("!=", "Closed")}, fields=["name", fieldname, "per_billed", "per_delivered"], order_by=f"{fieldname} ASC")

		for _k, g in groupby(sales_orders, lambda x:x[fieldname]):
			sales_orders_list = list(g)
			if len(sales_orders_list) > 1:
				for so in sales_orders_list:
					if not so.per_billed and not so.per_delivered:
						try:
							doc = frappe.get_doc("Sales Order", so.name)
							doc.cancel()
							frappe.delete_doc("Sales Order", doc.name)
						except Exception:
							print(doc.name)
							print(frappe.get_traceback())
