# Copyright (c) 2024, Dokos SAS and contributors
# For license information, please see license.txt

import requests

import frappe
from frappe import _
from frappe.utils import flt

from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products import (
	WooCommerceProducts
)

def execute(filters=None):
	columns = get_columns()
	data = get_data(filters)

	return columns, data

def get_columns():
	return [
		{
			"fieldtype": "Link",
			"fieldname": "item",
			"options": "Item",
			"label": _("Item"),
			"width": 200
		},
		{
			"fieldtype": "Data",
			"fieldname": "item_name",
			"label": _("Item Name"),
			"width": 250
		},
		{
			"fieldtype": "Data",
			"fieldname": "woocommerce_id",
			"label": _("WooCommerce ID"),
			"width": 150,
		},
		{
			"fieldtype": "Float",
			"fieldname": "dokos_stock_level",
			"label": _("Dokos Stock Level"),
			"width": 150
		}
	]


def get_data(filters):
	result = []

	woocommerce_settings = frappe.get_cached_doc("Woocommerce Settings", filters.site)

	wc_api = WooCommerceProducts(site=woocommerce_settings.woocommerce_server_url)
	for status in ["outofstock", "onbackorder"]:
		try:
			response = wc_api.get_products(params={"status": "publish", "stock_status": status})
			products = response.json()
			for product in products:
				item_data = frappe.db.get_value("Item", {f"woocommerce_id_{woocommerce_settings.name}": product.get("id")}, ["name", "item_name", "safety_stock"], as_dict=True)
				bin_level = frappe.db.get_value("Bin", dict(item_code=item_data.name, warehouse=woocommerce_settings.warehouse), "actual_qty")

				if bin_level and flt(bin_level) >= flt(item_data.safety_stock):
					result.append({
						"woocommerce_id": product.get("id"),
						"item": item_data.name,
						"item_name": item_data.item_name,
						"dokos_stock_level": bin_level,
					})
		except requests.exceptions.ChunkedEncodingError:
			frappe.throw(
				_("A network error prevented fetching WooCommerce data. Please try again in a minute.")
			)


	return result


@frappe.whitelist()
def get_out_of_stock_summary():
	result = []
	for settings in frappe.get_all("Woocommerce Settings", filters={"enable_sync": 1}, pluck="name"):
		result.extend(
			get_data(frappe._dict(site=settings))
		)

	return {
		"value": len(result),
		"fieldtype": "Int",
		"route": ["query-report", "WooCommerce Out of Stock Comparison"]
	}

@frappe.whitelist()
def update_stock(filters):
	from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products import _update_stock

	report_filters = frappe._dict(frappe.parse_json(filters))
	data = get_data(
		report_filters
	)

	woocommerce_settings = frappe.get_cached_doc("Woocommerce Settings", report_filters.site)
	for row in data:
		bin = frappe.db.get_value("Bin", dict(item_code=row["item"], warehouse=woocommerce_settings.warehouse))
		doc = frappe.get_doc("Bin", bin)
		_update_stock(doc, woocommerce_settings.woocommerce_server_url)