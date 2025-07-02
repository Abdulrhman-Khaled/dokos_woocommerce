# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.custom.doctype.property_setter.property_setter import make_property_setter
from frappe.model.document import Document
from frappe.model.meta import get_field_precision


from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.orders import (
	WooCommerceShippingMethodsAPI,
	WooCommerceTaxesAPI,
)
from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products import (
	sync_items,
)
from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.webhooks import (
	create_webhooks,
	delete_webhooks,
)

from dokos_woocommerce.woocommerce.doctype.woocommerce_order.woocommerce_order import (
	sync_orders,
)


class WoocommerceSettings(Document):
	def validate(self):
		self.validate_settings()
		self.create_delete_custom_fields()
		self.update_property_setters()
		self.create_webhook_url()
		self.add_shipping_statuses()

	def on_update(self):
		self.create_webhooks()

	def create_delete_custom_fields(self):
		if self.enable_sync:
			# For translations: _("WooCommerce ID ({0})") _("WooCommerce Email ({0})") _("Last WooCommerce Sync ({0})") _("Sync with WooCommerce ({0})") _("WooCommerce Number ({0})")
			create_custom_fields(
				{
					("Customer", "Sales Order", "Item", "Address", "Item Attribute", "Item Booking"): dict(
						fieldname=f"woocommerce_id_{self.name}",
						label="WooCommerce ID ({0})".format(self.woocommerce_server_url),
						fieldtype="Data",
						read_only=1,
						print_hide=1,
						translatable=0,
						in_standard_filter=1,
					),
					("Customer", "Address"): dict(
						fieldname=f"woocommerce_email_{self.name}",
						label="WooCommerce Email ({0})".format(self.woocommerce_server_url),
						fieldtype="Data",
						read_only=1,
						print_hide=1,
						translatable=0,
					),
					("Item"): [
						dict(
							fieldname=f"last_woocommerce_sync_{self.name}",
							label="Last WooCommerce Sync ({0})".format(self.woocommerce_server_url),
							fieldtype="Datetime",
							hidden=1,
							print_hide=1,
						),
						dict(
							fieldname=f"sync_with_woocommerce_{self.name}",
							label="Sync with WooCommerce ({0})".format(self.woocommerce_server_url),
							fieldtype="Check",
							insert_after="is_stock_item",
							print_hide=1,
						),
					],
					("Sales Order"): dict(
						fieldname=f"woocommerce_number_{self.name}",
						label="WooCommerce Number ({0})".format(self.woocommerce_server_url),
						fieldtype="Data",
						read_only=1,
						translatable=0,
					),
				}
			)


	def update_property_setters(self):
		currency_precision = self.currency_precision or 4
		for doctype in (
			"Sales Order Item",
			"Sales Invoice Item",
		):
			meta = frappe.get_meta(doctype)
			for field in meta.fields:
				if field.fieldtype in ("Currency") and get_field_precision(field) != currency_precision:
					if "total" not in field.fieldname:
						make_property_setter(
							doctype,
							field.fieldname,
							"precision",
							currency_precision,
							"Select",
							validate_fields_for_doctype=False,
						)
					else:
						make_property_setter(
							doctype,
							field.fieldname,
							"precision",
							2,
							"Select",
							validate_fields_for_doctype=False,
						)

	def validate_settings(self):
		if self.enable_sync:
			if not self.secret:
				self.set("secret", frappe.generate_hash())

			if not self.woocommerce_server_url:
				frappe.throw(_("Please enter Woocommerce Server URL"))

			if not self.woocommerce_server_url.endswith("/"):
				self.woocommerce_server_url = f"{self.woocommerce_server_url}/"

			if not self.api_consumer_key:
				frappe.throw(_("Please enter API Consumer Key"))

			if not self.api_consumer_secret:
				frappe.throw(_("Please enter API Consumer Secret"))

	def create_webhook_url(self):
		endpoint = "/api/method/dokos_woocommerce.woocommerce_connection.webhooks"

		try:
			url = frappe.request.url
		except RuntimeError:
			# for CI Test to work
			url = "http://localhost:8000"

		server_url = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(url))

		delivery_url = server_url + endpoint
		self.endpoint = delivery_url

	def create_webhooks(self):
		if frappe.conf.developer_mode:
			return

		if self.enable_sync and self.endpoint:
			create_webhooks(self.woocommerce_server_url)
		elif (
			not self.enable_sync
			and self.woocommerce_server_url
			and self.api_consumer_key
			and self.api_consumer_secret
		):
			delete_webhooks(self.woocommerce_server_url)

	def add_shipping_statuses(self):
		if not self.shipping_statuses:
			for status in ["shipped", "completed", "lpc_transit", "lpc_delivered"]:
				self.append("shipping_statuses", {
					"shipping_status": status
				})


@frappe.whitelist()
def generate_secret(settings):
	woocommerce_settings = frappe.get_doc("Woocommerce Settings", settings)
	woocommerce_settings.secret = frappe.generate_hash()
	woocommerce_settings.save()


@frappe.whitelist()
def get_series():
	return {
		"sales_order_series": frappe.get_meta("Sales Order").get_options("naming_series"),
	}


@frappe.whitelist()
def get_taxes(site):
	wc_api = WooCommerceTaxesAPI(site=site)
	taxes = wc_api.get_taxes()
	return taxes


@frappe.whitelist()
def get_shipping_methods(site):
	wc_api = WooCommerceShippingMethodsAPI(site=site)
	shipping_methods = wc_api.get_shipping_methods(params={"per_page": 100})
	return shipping_methods


@frappe.whitelist()
def get_products(site):
	frappe.enqueue("dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products.sync_items", site=site, timeout=1500)


@frappe.whitelist()
def push_products(site):
	frappe.enqueue("dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products.sync_products", site=site, timeout=1500)


def sync_woocommerce():
	for settings in frappe.get_all("Woocommerce Settings", filters={"enable_sync": 1}, fields=["woocommerce_server_url"]):
		sync_items(settings.woocommerce_server_url)
		sync_orders(settings.woocommerce_server_url)


def retry_created_orders():
	for woocommerce_order in frappe.get_all("Woocommerce Order", filters={"status": ("in", ("Pending", "Order Created"))}):
		frappe.get_doc("Woocommerce Order", woocommerce_order.name).run_method("sync_order")
