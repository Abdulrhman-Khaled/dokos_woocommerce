from pytz import timezone

import frappe
from frappe.utils import (
	add_to_date,
	add_years,
	cint,
	get_datetime,
	get_system_timezone,
	now_datetime,
)

from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api import WooCommerceAPI
from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.utils import get_woocommerce_settings


class WooCommerceOrdersAPI(WooCommerceAPI):
	def __init__(self, site, version="wc/v3", *args, **kwargs):
		super(WooCommerceOrdersAPI, self).__init__(site, version, args, kwargs)

	def get_orders(self, params=None):
		return self.get("orders", params=params)

	def get_order(self, id, params=None):
		return self.get(f"orders/{id}", params=params)


class WooCommerceTaxesAPI(WooCommerceAPI):
	def __init__(self, site, version="wc/v3", *args, **kwargs):
		super(WooCommerceTaxesAPI, self).__init__(site, version, args, kwargs)

	def get_tax(self, id, params=None):
		return self.get(f"taxes/{id}", params=params).json()

	def get_taxes(self, params=None):
		return self.get("taxes", params=params).json()


class WooCommerceShippingMethodsAPI(WooCommerceAPI):
	def __init__(self, site, version="wc/v3", *args, **kwargs):
		super(WooCommerceShippingMethodsAPI, self).__init__(site, version, args, kwargs)

	def get_shipping_methods(self, params=None):
		return self.get("shipping_methods", params=params).json()


class WooCommerceOrdersSync:
	def __init__(self, site):
		self.wc_api = WooCommerceOrdersAPI(site=site)
		self.woocommerce_settings = get_woocommerce_settings(site)
		self.woocommerce_orders = []

		self.get_woocommerce_orders()
		for woocommerce_order in self.woocommerce_orders:
			woocommerce_order_data = frappe.as_json(woocommerce_order)
			if frappe.db.exists("Woocommerce Order", dict(woocommerce_id=woocommerce_order.get("id"), woocommerce_settings=site)):
				so = frappe.get_doc("Woocommerce Order", dict(woocommerce_id=woocommerce_order.get("id"), woocommerce_settings=site))
				so.db_set("data", woocommerce_order_data)
				so.data = woocommerce_order_data
				if so.status != "Closed":
					so.run_method("sync_order")
			else:
				frappe.get_doc({
					"doctype": "Woocommerce Order",
					"woocommerce_id": woocommerce_order.get("id"),
					"woocommerce_settings": self.woocommerce_settings.name,
					"data": woocommerce_order_data
				}).insert(ignore_if_duplicate=True)

		self.set_synchronization_datetime()

	def get_woocommerce_orders(self):
		woocommerce_time_zone = self.wc_api.settings.woocommerce_site_timezone or "UTC"
		user_time_zone = get_system_timezone()
		last_modified_timestamp = get_datetime(
			self.wc_api.settings.last_synchronization_datetime or add_years(now_datetime(), -99)
		)
		localized_timestamp = timezone(user_time_zone).localize(last_modified_timestamp)
		woocommerce_timestamp = localized_timestamp.astimezone(timezone(woocommerce_time_zone))
		per_page = 100
		response = self.wc_api.get_orders(
			params={
				"per_page": per_page,
				"modified_after": woocommerce_timestamp,
				"dp": 4,
			}
		)
		self.woocommerce_orders = response.json()

		for page_idx in range(2, cint(response.headers.get("X-WP-TotalPages")) + 1):
			response = self.wc_api.get_orders(
				params={
					"per_page": per_page,
					"modified_after": woocommerce_timestamp,
					"dp": 4,
					"page": page_idx,
				}
			)
			self.woocommerce_orders.extend(response.json())

	def set_synchronization_datetime(self):
		frappe.db.set_value(
			"Woocommerce Settings",
			self.woocommerce_settings.name,
			"last_synchronization_datetime",
			frappe.utils.get_datetime_str(add_to_date(now_datetime(), minutes=-1)),
		)
