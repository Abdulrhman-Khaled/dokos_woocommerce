import base64
import hashlib
import hmac
import json
from functools import wraps

import frappe
from frappe import _
from frappe.utils import add_to_date, now_datetime
import frappe.modules.utils

from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.utils import get_woocommerce_settings
from dokos_woocommerce.woocommerce.doctype.woocommerce_order.woocommerce_order import (
	create_update_order,
)

handler_map = {
	"order.created": create_update_order,
	"order.updated": create_update_order,
}


def woocommerce_webhook(f):
	"""
	Decorator validating a woocommerce Webhook request.
	"""

	@wraps(f)
	def wrapper(*args, **kwargs):
		# Try to get required headers and decode the body of the request.
		woocommerce_settings = get_woocommerce_settings(frappe.get_request_header("X-WC-Webhook-Source"))
		sig = base64.b64encode(
			hmac.new(
				woocommerce_settings.secret.encode("utf8"), frappe.request.data, hashlib.sha256
			).digest()
		)

		if (
			frappe.request.data
			and not sig == frappe.get_request_header("X-Wc-Webhook-Signature", "").encode()
		):
			frappe.throw(_("Unverified Webhook Data"))

		return f(*args, **kwargs)

	return wrapper


@frappe.whitelist(allow_guest=True)
def webhooks(*args, **kwargs):
	topic = frappe.local.request.headers.get("X-Wc-Webhook-Topic")
	site = frappe.local.request.headers.get("X-WC-Webhook-Source")
	try:
		data = frappe.parse_json(frappe.safe_decode(frappe.request.data))
	except json.decoder.JSONDecodeError:
		data = frappe.safe_decode(frappe.request.data)

	if not frappe.db.exists("Integration Request", dict(service_id=data.get("id"), creation=(">=", add_to_date(now_datetime(), seconds=-30)))):
		integration_request = create_new_integration_log(data, site, topic)

		if handler := handler_map.get(topic):
			frappe.enqueue(handle_webhook, integration_request=integration_request, handler=handler, data=data, site=site, queue="long")

		else:
			integration_request.db_set("status", "Completed")

def handle_webhook(integration_request, handler, data, site):
	handler(data, site)
	integration_request.db_set("status", "Completed")


def create_new_integration_log(data, site, topic):
	integration_request = frappe.get_doc(
		{
			"doctype": "Integration Request",
			"request_description": "Webhook",
			"integration_request_service": "WooCommerce",
			"service_document": site,
			"service_status": topic,
			"service_id": data.get("id"),
			"data": frappe.as_json(data, indent=2),
		}
	)

	integration_request.flags._name = frappe.generate_hash()

	integration_request.insert(ignore_permissions=True, ignore_if_duplicate=True)

	return integration_request


# def handle_webhook(**kwargs):
# 	integration_request = frappe.get_doc(kwargs.get("doctype"), kwargs.get("docname"))

# 	if handler := handler_map.get(integration_request.service_status):
# 		handler(frappe.parse_json(integration_request.data), integration_request.service_document)
# 		integration_request.db_set("status", "Completed")

def handle_webhook(**kwargs):
    # Safely get integration request
    integration_request = kwargs.get("integration_request")

    if not integration_request:
        doctype = kwargs.get("doctype")
        docname = kwargs.get("docname")
        if doctype and docname:
            integration_request = frappe.get_doc(doctype, docname)
        else:
            frappe.throw("Missing integration_request or doctype/docname")

    # Get handler (import if string)
    handler = kwargs.get("handler")
    if isinstance(handler, str):
        handler = frappe.get_attr(handler)

    # Get raw data (JSON string or dict)
    data = kwargs.get("data") or frappe.parse_json(integration_request.data)

    # Run the handler
    handler(data, integration_request.service_document)
