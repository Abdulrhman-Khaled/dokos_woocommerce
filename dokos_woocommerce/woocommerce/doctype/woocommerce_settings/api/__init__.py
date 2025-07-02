import requests
from requests.exceptions import ConnectionError
import base64

from woocommerce import API

import frappe
from frappe import _

from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.utils import get_woocommerce_settings


class WooCommerceAPI:
	def __init__(self, site, version="wc/v3", *args, **kwargs):
		self.settings = get_woocommerce_settings(site)
		self.version = version
		self.api = {}

		if (
			self.settings.woocommerce_server_url
			and self.settings.api_consumer_key
			and self.settings.api_consumer_secret
		):
			self.api = API(
				url=self.settings.woocommerce_server_url,
				consumer_key=self.settings.api_consumer_key,
				consumer_secret=self.settings.get_password(fieldname="api_consumer_secret"),
				version=version,
				timeout=5000,
			)

	def get(self, path, params=None):
		try:
			res = self.api.get(path, params=params or {})
			return self.validate_response(res, path, params)
		except ConnectionError:
			frappe.msgprint(_("Please check your connexion to your WooCommerce site"), raise_exception=True, alert=True)

	def post(self, path, data):
		res = self.api.post(path, data)
		return self.validate_response(res, path, data)

	def put(self, path, data):
		res = self.api.put(path, data)
		return self.validate_response(res, path, data)

	def delete(self, path, params=None):
		res = self.api.delete(path, params=params or {})
		return self.validate_response(res, path, params)

	def validate_response(self, response, path, data=None):
		try:
			response.raise_for_status()
			return response
		except Exception:
			message = f"""
				response: {response.text}\n
				path: {path}\n
				data/params: {data or ''}
			"""
			frappe.log_error(message=message, title="WooCommerce Request Error")
			raise


class WordpressAPI:
	def __init__(self, site):
		self.settings = get_woocommerce_settings(site)

		self.user = self.settings.wp_api_username
		self.password = self.settings.get_password(fieldname="wp_application_password")
		self.credentials = self.user + ":" + self.password
		self.token = base64.b64encode(self.credentials.encode())
		self.headers = {'Authorization': 'Basic ' + self.token.decode('utf-8')}

	def get(self, path, params=None):
		res = requests.get(f"{self.settings.woocommerce_server_url}wp-json/wp/v2/{path}", headers=self.headers, params=params)
		return self.validate_response(res)

	def post(self, path, data):
		res = requests.post(f"{self.settings.woocommerce_server_url}wp-json/wp/v2/{path}", headers=self.headers, data=data)
		return self.validate_response(res)

	def validate_response(self, response):
		response.raise_for_status()
		return response