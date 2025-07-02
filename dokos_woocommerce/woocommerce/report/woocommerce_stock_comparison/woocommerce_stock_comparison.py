# Copyright (c) 2024, Dokos SAS and contributors
# For license information, please see license.txt

import requests

import frappe
from frappe import _

from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products import WooCommerceProducts

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
			"fieldname": "woocommerce_stock_level",
			"label": _("WooCommerce Stock Level"),
			"width": 150
		},
		{
			"fieldtype": "Float",
			"fieldname": "dokos_stock_level",
			"label": _("Dokos Stock Level"),
			"width": 150
		},
		{
			"fieldtype": "Percent",
			"fieldname": "difference",
			"label": _("Stock Difference"),
			"width": 150
		}
	]

def get_data(filters):
	woocommerce_settings = frappe.get_cached_doc("Woocommerce Settings", filters.site)

	products = get_products(woocommerce_settings.woocommerce_server_url)

	product_stock_info = {x["id"]: x["stock_quantity"] for x in products}

	result = []
	for id, stock_level in product_stock_info.items():
		item_data = frappe.db.get_value("Item", {f"woocommerce_id_{filters.site}": id}, ["name", "item_name"], as_dict=True)
		bin_level = frappe.db.get_value("Bin", dict(item_code=item_data.name, warehouse=woocommerce_settings.warehouse), "actual_qty")
		row = {
			"woocommerce_id": id,
			"woocommerce_stock_level": stock_level,
			"item": item_data.name,
			"item_name": item_data.item_name,
			"dokos_stock_level": bin_level,
			"difference": ((stock_level - bin_level) * 100) / stock_level if stock_level else 0
		}
		result.append(row)

	return result

def get_products(woocommerce_server_url):
	try:
		wc_api = WooCommerceProducts(site=woocommerce_server_url)
		response = wc_api.get_products(params={"status": "publish"})
		products = response.json()

		for page_idx in range(1, int(response.headers.get("X-WP-TotalPages")) + 1):
			response = wc_api.get_products(params={"per_page": 100, "page": page_idx, "status": "publish"})
			products.extend(response.json())

		return frappe.parse_json(products)
	except requests.exceptions.ChunkedEncodingError:
			frappe.throw(
				_("A network error prevented fetching WooCommerce data. Please try again in a minute.")
			)
