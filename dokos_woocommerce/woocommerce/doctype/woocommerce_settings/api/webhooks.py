from requests.exceptions import ConnectionError

import frappe
from frappe import _

from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api import WooCommerceAPI

WEBHOOKS = {
	"coupon.created": "Coupon Created",
	"coupon.updated": "Coupon Updated",
	"coupon.deleted": "Coupon Deleted",
	"coupon.restored": "Coupon Restored",
	"customer.created": "Customer Created",
	"customer.updated": "Customer Updated",
	"customer.deleted": "Customer Deleted",
	"customer.restored": "Customer Restored",
	"order.created": "Order Created",
	"order.updated": "Order Updated",
	"order.deleted": "Order Deleted",
	"order.restored": "Order Restored",
	"product.created": "Product Created",
	"product.updated": "Product Updated",
	"product.deleted": "Product Deleted",
	"product.restored": "Product Restored",
}

class WooCommerceWebhooks(WooCommerceAPI):
	def __init__(self, site, version="wc/v3", *args, **kwargs):
		super(WooCommerceWebhooks, self).__init__(site, version, args, kwargs)

	def create(self, data):
		return self.post("webhooks", data).json()

	def get_list(self):
		try:
			return self.get("webhooks", params={"per_page": 100}).json()
		except ConnectionError:
			frappe.msgprint(_("Please check your connexion to your WooCommerce site"), raise_exception=True, alert=True)


def create_webhooks(site):
	wc_api = WooCommerceWebhooks(site=site)
	webhooks = {
		x.get("topic"): x.get("delivery_url")
		for x in wc_api.get_list()
	}

	for topic, name in WEBHOOKS.items():
		if not webhooks.get(topic) == wc_api.settings.endpoint:
			wc_api.create(
				{
					"topic": topic,
					"name": name,
					"delivery_url": wc_api.settings.endpoint,
					"secret": wc_api.settings.secret,
				}
			)


def delete_webhooks(site):
	wc_api = WooCommerceWebhooks(site=site)

	webhooks = wc_api.get("webhooks", params={"per_page": 100}).json()
	for webhook in webhooks:
		wc_api.delete(f"webhooks/{webhook['id']}", params={"force": True}).json()


@frappe.whitelist()
def webhooks_healthcheck():
	webhooks = []
	for site in frappe.get_all("Woocommerce Settings", filters={"enable_sync": 1}, pluck="woocommerce_server_url"):
		wc_api = WooCommerceWebhooks(site=site)
		webhooks.extend(
			[x for x in wc_api.get_list() if x.get("status") != "active"]
		)

	return {
		"value": len(webhooks),
		"fieldtype": "Int"
	}