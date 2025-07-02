# Copyright (c) 2022, Dokos SAS and contributors
# For license information, please see license.txt

from collections import defaultdict
from datetime import datetime

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.contacts.doctype.address.address import get_preferred_address
from frappe.utils import (
	add_days,
	add_to_date,
	cint,
	flt,
	nowdate,
)
from frappe.utils.background_jobs import get_jobs

from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return
from erpnext.utilities.product import get_item_codes_by_attributes
from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note, make_sales_invoice
from erpnext.stock.stock_ledger import NegativeStockError

from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.bookings import (
	WooCommerceBookingsAPI,
)
from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.customers import (
	sync_customer,
	sync_guest_customers,
)
from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products import get_simple_item
from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.orders import (
	WooCommerceOrdersAPI,
	WooCommerceOrdersSync,
)

# from dokos_woocommerce.errors import handle_woocommerce_error

class WoocommerceOrder(Document):
	def after_insert(self):
		self.sync_order()

	def sync_order(self):
		if frappe.conf.developer_mode:
			sync_order(self)
		else:
			frappe.enqueue(
				sync_order, queue="long", doc=self
			)


@frappe.whitelist()
def process_order(order):
	frappe.enqueue("dokos_woocommerce.woocommerce.doctype.woocommerce_order.woocommerce_order._process_order", order=order, queue="long")

def _process_order(order):
	woocommerce_order_doc = frappe.get_doc("Woocommerce Order", order)
	if not woocommerce_order_doc:
		return

	site = frappe.get_cached_value("Woocommerce Settings", woocommerce_order_doc.woocommerce_settings, "woocommerce_server_url")
	wc_api = WooCommerceOrdersAPI(site=site)
	data = wc_api.get_order(frappe.parse_json(woocommerce_order_doc.data).get("id")).json()
	formatted_data = frappe.as_json(data)

	if formatted_data != woocommerce_order_doc.data:
		frappe.db.set_value("Woocommerce Order", order, "data", formatted_data)

	woocommerce_order_doc.reload()
	sync_order(woocommerce_order_doc)


def create_update_order(data, site):
	woocommerce_order_data = data

	# Step 1: Get the name of the Woocommerce Settings doc
	settings_name = frappe.get_cached_value("Woocommerce Settings", {"woocommerce_server_url": site})
	if not settings_name:
		frappe.throw(f"Woocommerce Settings not found for site: {site}")

	# Step 2: Check if the order already exists
	if frappe.db.exists("Woocommerce Order", {
		"woocommerce_id": woocommerce_order_data.get("id"),
		"woocommerce_settings": settings_name
	}):
		# Update existing order
		so = frappe.get_doc("Woocommerce Order", {
			"woocommerce_id": woocommerce_order_data.get("id"),
			"woocommerce_settings": settings_name
		}, for_update=True)
		so.data = frappe.as_json(woocommerce_order_data)
		so.flags.ignore_permissions = True
		so.save()

		if so.status != "Closed":
			so.run_method("sync_order")
	else:
		# Create new order
		frappe.get_doc({
			"doctype": "Woocommerce Order",
			"woocommerce_id": woocommerce_order_data.get("id"),
			"woocommerce_settings": settings_name,  # ✅ Fixed here
			"data": frappe.as_json(woocommerce_order_data)
		}).insert(ignore_permissions=True)


def sync_orders(site):


	if sync_order in get_jobs()[frappe.local.site]:
		return

	WooCommerceOrdersSync(site)

def sync_order(doc):
	WooCommerceOrderSync(doc).sync()


class WooCommerceOrderSync:
	def __init__(self, doc):
		self.order = doc
		self.woocommerce_order = frappe.parse_json(self.order.data)
		site = frappe.get_cached_value("Woocommerce Settings", self.order.woocommerce_settings, "woocommerce_server_url")
		self.wc_api = WooCommerceOrdersAPI(site=site)
		self.settings = self.wc_api.settings
		self.customer = None
		self.sales_order = None
		self.bookings = []

	def sync(self):
		self.order.db_set("error", "")
		self.order.db_set("error_message", "")
		self.order.db_set("error_notification_sent", 0)

		# Completed orders and closed orders refunded or failed don't need to be synchronized again
		if self.is_completed_order() or self.is_closed_order():
			self.order.db_set("status", "Order Updated")
			return self.update_all_creation_statuses()

		if self.woocommerce_order.get("customer_id") == 0 and not self.woocommerce_order.get(
			"billing", {}
		).get("email"):
			if self.order.status != "Error":
				self.order.db_set("status", "Error")
			return

		self.order.db_set("status", "Pending")

		self.get_customer()

		if self.customer:
			try:
				if frappe.db.exists(
					"Sales Order", {f"woocommerce_id_{self.settings.name}": self.woocommerce_order.get("id"), "docstatus": 1}
				):
					self._update_sales_order()
				elif self.woocommerce_order.get("status") == "cancelled":
					self.order.db_set("status", "Closed")
				else:
					self._new_sales_order()
			except Exception as e:
				frappe.db.rollback()
				self.register_error(error_message=str(e))

	def update_all_creation_statuses(self):
		for field in ["order_created", "sales_invoice_created", "payment_created", "delivery_note_created"]:
			if not self.order.get(field):
				self.order.db_set(field, 1)


	def is_completed_order(self):
		return frappe.db.exists(
			"Sales Order",
			{f"woocommerce_id_{self.settings.name}": self.woocommerce_order.get("id"), "status": "Completed", "docstatus": 1},
		) or (self.order.order_created and self.order.delivery_note_created and self.order.payment_created and self.order.sales_invoice_created)

	def is_closed_order(self):
		return frappe.db.exists(
			"Sales Order",
			{f"woocommerce_id_{self.settings.name}": self.woocommerce_order.get("id"), "status": "Closed", "docstatus": 1},
		) and self.woocommerce_order.get("status") in ("failed", "refunded")

	def get_customer(self):
		if self.woocommerce_order.get("customer_id") != 0:
			self._sync_customer(self.woocommerce_order.get("customer_id"))

		if not self.customer:
			self.customer = sync_guest_customers(self.wc_api.settings.woocommerce_server_url, self.woocommerce_order)

	def _sync_customer(self, id):
		woocommerce_customer = self.wc_api.get(f"customers/{id}").json()
		self.customer = sync_customer(self.settings, woocommerce_customer)

	def _update_sales_order(self):
		original_so = frappe.get_doc(
			"Sales Order", {f"woocommerce_id_{self.settings.name}": self.woocommerce_order.get("id"), "docstatus": 1}, for_update=True
		)
		if original_so.status == "Closed":
			original_so.update_status("Draft")

		if self.woocommerce_order.get("status") == "cancelled":
			original_so.cancel()
			return self.order.db_set("status", "Closed")

		# TODO: check if that can happen
		# if original_so.docstatus == 2 and self.woocommerce_order.get("status") != "cancelled":
		# 	return frappe.db.set_value("Sales Order", original_so.name, "docstatus", 1)

		updated_so = self.create_sales_order()
		self.sales_order = original_so

		so_are_similar = compare_sales_orders(original_so, updated_so)

		if not so_are_similar and not (flt(original_so.per_delivered) or flt(original_so.per_billed)):
			try:
				original_so.flags.ignore_permissions = True
				original_so.cancel()

				self.sales_order = updated_so
				self.sales_order.flags.ignore_permissions = True
				self.sales_order.insert()
				self.sales_order.submit()
			except Exception:
				# Usually this throws an exception when the original so can't be cancelled
				pass

		if self.sales_order:
			self.update_so_status()
			delivery_statuses = [s.shipping_status for s in self.wc_api.settings.shipping_statuses]

			if cint(self.wc_api.settings.create_payments_and_sales_invoice):
				if self.woocommerce_order.get("status") == "refunded":
					self.refund_sales_order()
				elif self.woocommerce_order.get("date_paid") or (
					self.woocommerce_order.get("payment_method")
					and self.woocommerce_order.get("status") in delivery_statuses
				):
					# Delivered sales orders with a payment method are assumed to be paid
					self.register_payment_and_invoice()

			if self.woocommerce_order.get("status") in delivery_statuses:
				self.register_delivery()

		self.order.db_set("status", "Order Updated")
		self.order.db_set("order_created", 1)

	def update_so_status(self):
		self.sales_order.reload()
		if self.woocommerce_order.get("status") == "on-hold":
			self.sales_order.update_status("On Hold")
			self.update_booking_status("Not Confirmed")
		elif self.sales_order.status == "On Hold":
			self.sales_order.reload()
			self.sales_order.update_status("Draft")
		elif self.woocommerce_order.get("status") == "failed":
			self.sales_order.update_status("Closed")
			self.update_booking_status("Cancelled")

	def update_booking_status(self, status):
		for item in self.sales_order.items:
			if item.item_booking:
				frappe.db.set_value("Item Booking", item.item_booking, "status", status)

	def _new_sales_order(self):
		self.delete_existing_drafts()

		so = self.create_sales_order()

		if so.items:
			try:
				if self.woocommerce_order.get("status") == "on-hold":
					so.status = "On Hold"
				so.flags.ignore_permissions = True
				so.insert()

				so_total = so.rounded_total or so.grand_total
				if flt(so_total) != flt(self.woocommerce_order.get("total")):
					if not self.round_order(so):
						error_message = _("WooCommerce Order ({0}) and Sales Order ({1}) totals don't match").format(self.woocommerce_order.get("total"), so_total)
						return self.register_error(error_message=error_message)

				so.submit()
				self.order.db_set("status", "Order Created")
				self.order.db_set("order_created", 1)
			except Exception as e:
				self.register_error(
					error_message=str(e)
				)
		else:
			error = f"No items found for Woocommerce order {self.woocommerce_order.get('id')}"
			self.register_error(
				error_message=error
			)

	def delete_existing_drafts(self):
		for so in frappe.get_all(
			"Sales Order", {f"woocommerce_id_{self.settings.name}": self.woocommerce_order.get("id"), "docstatus": 0}
		):
			frappe.delete_doc("Sales Order", so.name, ignore_permissions=True)

	def register_error(self, error=None, error_message=None):
		self.order.db_set("status", "Error")
		self.order.db_set("error", error or frappe.get_traceback())

		if error_message:
			self.order.db_set("error_message", error_message, notify=True)

		self.order.reload()
		self.order.run_notifications("on_error")

	def create_sales_order(self):
		delivery_date = add_days(
			self.woocommerce_order.get("date_created_gmt") or nowdate(), self.settings.delivery_after_days
		)
		return frappe.get_doc(
			{
				"doctype": "Sales Order",
				"order_type": "Shopping Cart",
				"naming_series": self.settings.sales_order_series,
				f"woocommerce_id_{self.settings.name}": self.woocommerce_order.get("id"),
				f"woocommerce_number_{self.settings.name}": self.woocommerce_order.get("number"),
				"transaction_date": self.woocommerce_order.get("date_created_gmt") or nowdate(),
				"customer": self.customer.name,
				"customer_group": self.customer.customer_group,
				"delivery_date": delivery_date,
				"company": self.settings.company,
				"selling_price_list": self.settings.price_list,
				"ignore_pricing_rule": 1,
				"items": self.get_order_items(delivery_date),
				"taxes": self.get_order_taxes(),
				"currency": self.woocommerce_order.get("currency"),
				"taxes_and_charges": None,
				"customer_address": get_preferred_address(
					"Customer", self.customer.name, "is_primary_address"
				),
				"shipping_address_name": get_preferred_address(
					"Customer", self.customer.name, "is_shipping_address"
				),
				"disable_rounded_total": 0,
			}
		)

	def round_order(self, sales_order):
		if sales_order.total_taxes_and_charges == (flt(self.woocommerce_order.get("total_tax")) + flt(self.woocommerce_order.get("shipping_total"))):
			sales_order.rounding_adjustment = sales_order.base_rounding_adjustment = flt(self.woocommerce_order.get("total")) - sales_order.grand_total
			sales_order.is_consolidated = True
			sales_order.rounded_total = flt(self.woocommerce_order.get("total"))
			sales_order.save()
			return flt(sales_order.rounded_total) == flt(self.woocommerce_order.get("total"))

		return False

	def get_order_items(self, delivery_date):
		items = []
		tax_is_included = self.settings.vat_is_included
		for item in self.woocommerce_order.get("line_items"):
			item_code = None

			if not flt(item.get("price")) and True in [
				x.get("key") == "_bundled_by" or x.get("key") == "_bundled_item_id"
				for x in item.get("meta_data")
			]:
				continue

			if not item.get("product_id"):
				item_code = self.get_or_create_missing_item(item)

			if not item_code:
				item_code = self.get_item_code_and_warehouse(item)

			if item_code:
				warehouse = frappe.db.get_value("Website Item", dict(item_code=item_code), "website_warehouse")
				item_data = frappe.db.get_value(
					"Item", item_code, ("stock_uom", "enable_item_booking"), as_dict=True
				)

				items.append(
					{
						"item_code": item_code,
						"rate": ((flt(item.get("total")) + flt(item.get("total_tax"))) / flt(item.get("quantity"))) if tax_is_included else flt(item.get("price")),
						"is_free_item": not flt(item.get("price")),
						"delivery_date": delivery_date,
						"qty": item.get("quantity"),
						"warehouse": warehouse or self.settings.warehouse,
						"stock_uom": item_data.get("stock_uom"),
						"uom": frappe.db.get_value("Item", item_code, "sales_uom") or item_data.get("stock_uom"),
						"discount_percentage": 0.0 if flt(item.get("price")) else 100.0,
						"item_booking": self.get_booking_for_line_item(item, item_code)
						if item_data.get("enable_item_booking")
						else None,
					}
				)
			else:
				message=_("Item missing for Woocommerce product: {0}").format(item.get("product_id"))
				self.register_error(error_message=message)

		return items

	def get_item_code_and_warehouse(self, item):
		if cint(item.get("variation_id")) > 0:
			item_code = frappe.db.get_value(
				"Item", {f"woocommerce_id_{self.settings.name}": item.get("variation_id")}, "item_code"
			)
		else:
			item_code = frappe.db.get_value("Item", {f"woocommerce_id_{self.settings.name}": item.get("product_id")}, "item_code")

			if item_code:
				has_variants = frappe.db.get_value(
					"Item", {f"woocommerce_id_{self.settings.name}": item.get("product_id")}, "has_variants"
				)

				if cint(has_variants) and len(item.get("meta_data")):
					variants = get_item_codes_by_attributes(
						{
							x.get("display_key"): x.get("value")
							for x in item.get("meta_data")
							if isinstance(x.get("value"), str)
						},
						item_code,
					)
					if variants:
						item_code = variants[0]

		return item_code

	def get_or_create_missing_item(self, product):
		item = frappe.db.get_value("Item", product.get("name"))

		if not item:
			item_doc = frappe.get_doc(
				get_simple_item(self.settings, {"name": product.get("name"), "categories": []})
			)
			item_doc.insert(ignore_permissions=True, ignore_if_duplicate=True)

			if item_doc:
				item = item_doc.name

		return item

	def get_booking_for_line_item(self, line_item, item_code):
		if not self.bookings:
			self.get_woocommerce_bookings()

		for booking in self.bookings:
			if booking.get("order_item_id") == line_item.get("id"):
				return self.create_update_item_booking(booking, item_code)

	def get_woocommerce_bookings(self):
		# TODO: implement a request filtered by order as soon as it is available on WooCoommerce side
		try:
			bookings = (
				WooCommerceBookingsAPI()
				.get_bookings(
					params={"after": add_to_date(self.woocommerce_order.get("date_created"), hours=-1)}
				)
				.json()
				or []
			)

			self.bookings = [b for b in bookings if b.get("order_id") == self.woocommerce_order.get("id")]
		except Exception:
			self.bookings = []

	def create_update_item_booking(self, booking, item_code):
		existing_booking = frappe.db.get_value("Item Booking", {f"woocommerce_id_{self.settings.name}": booking.get("id")})
		if existing_booking:
			doc = frappe.get_doc("Item Booking", existing_booking)
		else:
			doc = frappe.new_doc("Item Booking")
			doc.update({f"woocommerce_id_{self.settings.name}":  booking.get("id")})

		doc.starts_on = datetime.fromtimestamp(booking.get("start"))
		doc.ends_on = datetime.fromtimestamp(booking.get("end"))
		doc.all_day = booking.get("all_day")
		doc.status = (
			"Confirmed"
			if booking.get("status") in ("paid", "confirmed", "complete")
			else ("Cancelled" if booking.get("status") == "cancelled" else "Not Confirmed")
		)
		doc.item = item_code
		doc.google_calendar_event_id = booking.get("google_calendar_event_id")
		doc.party_type = "Customer"
		doc.party = self.customer.name
		doc.insert(ignore_permissions=True)

		return doc.name

	def get_order_taxes(self):
		taxes = []
		tax_is_included = self.settings.vat_is_included
		for tax_detail in self.woocommerce_order.get("tax_lines"):
			account_head = self.get_tax_account_head(tax_detail.get("rate_id"))
			taxes.append(
				{
					"charge_type": "On Net Total" if tax_is_included else "Actual",
					"account_head": account_head,
					"description": self.get_label_from_wc_tax_summary(tax_detail.get("rate_id")),
					"rate": 0,
					"tax_amount": (
						flt(tax_detail.get("shipping_tax_total", 0.0), precision=self.settings.currency_precision or 3) +
						flt(tax_detail.get("tax_total", 0.0), precision=self.settings.currency_precision or 3)
					),
					"included_in_print_rate": tax_is_included,
					"cost_center": self.settings.cost_center,
				}
			)

		taxes = self.update_taxes_with_shipping_lines(taxes)
		taxes = self.update_taxes_with_fee_lines(taxes)

		return taxes


	def get_label_from_wc_tax_summary(self, id):
		for tax in self.woocommerce_order.get("tax_lines"):
			if tax.get("rate_id") == id:
				return tax.get("label")

	def update_taxes_with_fee_lines(self, taxes):
		for fee_charge in self.woocommerce_order.get("fee_lines"):
			taxes.insert(
				0,
				{
					"charge_type": "Actual",
					"account_head": self.settings.fee_account,
					"description": fee_charge["name"],
					"tax_amount": fee_charge["amount"],
					"cost_center": self.settings.cost_center,
				},
			)

		return taxes

	def update_taxes_with_shipping_lines(self, taxes):
		for shipping_charge in self.woocommerce_order.get("shipping_lines"):
			if shipping_charge.get("method_id"):
				account_head = self.get_shipping_account_head(shipping_charge.get("method_id"))

				if account_head:
					taxes.insert(
						0,
						{
							"charge_type": "Actual",
							"account_head": account_head,
							"description": shipping_charge.get("method_title"),
							"tax_amount": shipping_charge.get("total"),
							"cost_center": self.settings.cost_center,
						},
					)
				else:
					message=_("WooCommerce Order: {0}\n\nAccount head missing for Woocommerce shipping method: {1}").format(
						self.woocommerce_order.get("id"), shipping_charge.get("method_id")
					)
					self.register_error(error_message=message)

				if self.settings.vat_is_included:
					for shipping_charge_tax in shipping_charge.get("taxes"):
						if shipping_charge_tax.get("total"):
							account_head = self.get_tax_account_head(shipping_charge_tax.get("id"))
							taxes.append(
								{
									"charge_type": "On Previous Row Amount",
									"row_id": 1,
									"account_head": account_head,
									"description": self.get_label_from_wc_tax_summary(shipping_charge_tax.get("id")),
									"rate": frappe.get_cached_value("Account", account_head, "tax_rate"),
									"included_in_print_rate": 0,
									"cost_center": self.settings.cost_center,
								}
							)

		return taxes

	def get_tax_account_head(self, id):
		accounts = frappe.get_all(
			"Woocommerce Taxes", filters=dict(woocommerce_tax_id=id, parent=self.settings.name), fields=["account"], limit=1
		)
		if accounts:
			return accounts[0].account

	def get_shipping_account_head(self, id):
		accounts = frappe.get_all(
			"Woocommerce Shipping Methods",
			filters=dict(woocommerce_shipping_method_id=id, parent=self.settings.name),
			fields=["account"],
			limit=1,
		)
		if accounts:
			return accounts[0].account

	def refund_sales_order(self):
		sales_invoices = frappe.get_all(
			"Sales Invoice Item", filters={"sales_order": self.sales_order.name}, pluck="parent"
		)

		for sales_invoice in sales_invoices:
			credit_note = frappe.new_doc("Sales Invoice")
			credit_note.flags.ignore_permissions = True
			credit_note = make_sales_return(sales_invoice, credit_note)

			credit_note.allocate_advances_automatically = False
			credit_note.advances = []

			credit_note.insert()
			credit_note.submit()

			payment_entry = get_payment_entry("Sales Invoice", credit_note.name)
			if payment_entry.paid_amount:
				payment_entry.reference_no = (
					self.woocommerce_order.get("transaction_id")
					or self.woocommerce_order.get("payment_method_title")
					or _("WooCommerce Order")
				)
				payment_entry.reference_date = self.woocommerce_order.get("date_paid")
				payment_entry.insert(ignore_permissions=True)
				payment_entry.submit()

		else:
			frappe.db.set_value("Sales Order", self.sales_order.name, "status", "Closed")

	def register_payment_and_invoice(self):
		# Keep 99.99 because of rounding issues
		if flt(self.sales_order.per_billed) < 99.99 and self.sales_order.docstatus == 1:
			try:
				if self.sales_order.status in ("On Hold", "Closed"):
					frappe.db.set_value("Sales Order", self.sales_order.name, "status", "To Bill")

				self.make_payment()
				self.make_sales_invoice_from_sales_order()
			except Exception:
				message=_("WooCommerce Order: {0}\n\n{1}").format(
					self.woocommerce_order.get("id"), frappe.get_traceback()
				)
				self.register_error(error_message=message)
		elif flt(self.sales_order.per_billed) >= 99.99 and self.sales_order.docstatus == 1:
			self.order.db_set("sales_invoice_created", 1)
			self.order.db_set("payment_created", 1)

	def register_delivery(self):
		if flt(self.sales_order.per_delivered) < 100:
			self._make_delivery_note()
		else:
			self.order.db_set("delivery_note_created", 1)

	def _make_delivery_note(self):
		dn = frappe.new_doc("Delivery Note")
		dn.flags.ignore_permissions = True
		self.sales_order.flags.ignore_permissions = True
		dn = make_delivery_note(self.sales_order.name, target_doc=dn)
		dn.set_posting_time = True
		dn.posting_date = self.woocommerce_order.get("date_completed")
		dn.run_method("set_missing_values")
		dn.insert(ignore_permissions=True)
		try:
			dn.submit()
			self.order.db_set("delivery_note_created", 1)
		except NegativeStockError:
			pass

	def make_payment(self):
		if (
			flt(self.sales_order.advance_paid) < flt(self.sales_order.grand_total)
			and self.woocommerce_order.get("transaction_id")
			and not frappe.get_all(
				"Payment Entry", dict(reference_no=self.woocommerce_order.get("transaction_id"))
			)
		):
			frappe.flags.ignore_account_permission = True
			frappe.flags.ignore_permissions = True
			payment_entry = get_payment_entry(self.sales_order.doctype, self.sales_order.name)
			if payment_entry.paid_amount:
				if self.woocommerce_order.get("payment_method") == "stripe":
					self.add_stripe_fees(payment_entry)
				payment_entry.posting_date = self.woocommerce_order.get("date_paid")
				payment_entry.reference_no = (
					self.woocommerce_order.get("transaction_id")
					or self.woocommerce_order.get("payment_method_title")
					or _("WooCommerce Order")
				)
				payment_entry.reference_date = self.woocommerce_order.get("date_paid")
				payment_entry.insert(ignore_permissions=True)

				if payment_entry.difference_amount:
					payment_entry.append(
						"deductions",
						{
							"account": frappe.db.get_value("Company", self.sales_order.company, "write_off_account"),
							"cost_center": self.sales_order.cost_center
							or frappe.db.get_value("Company", payment_entry.company, "cost_center"),
							"amount": payment_entry.difference_amount,
						},
					)
				payment_entry.submit()
				self.order.db_set("payment_created", 1)

	def add_stripe_fees(self, payment_entry):
		if not self.settings.stripe_gateway:
			return

		stripe_gateway = frappe.get_doc("Payment Gateway", self.settings.stripe_gateway)
		if not stripe_gateway.fee_account:
			return

		keys = ["_stripe_fee", "_stripe_net", "_stripe_currency", "_stripe_charge_captured"]
		charge = defaultdict(str)
		for meta in self.woocommerce_order.get("meta_data"):
			if meta.get("key") in keys:
				charge[meta.get("key")] = meta.get("value")

		if (
			not charge.get("_stripe_charge_captured") and not charge.get("_stripe_charge_captured") == "yes"
		):
			return

		payment_entry.update(
			{
				"paid_amount": flt(charge.get("_stripe_net")),
				"received_amount": flt(charge.get("_stripe_net")),
			}
		)

		payment_entry.append(
			"deductions",
			{
				"account": stripe_gateway.fee_account,
				"cost_center": stripe_gateway.cost_center
				or frappe.db.get_value("Company", payment_entry.company, "cost_center"),
				"amount": flt(charge.get("_stripe_fee")),
			},
		)

	def make_sales_invoice_from_sales_order(self):
		if not frappe.db.sql(
			f"""
				select
					si.name
				from
					`tabSales Invoice` si, `tabSales Invoice Item` si_item
				where
					si.name = si_item.parent
					and si_item.sales_order = {frappe.db.escape(self.sales_order.name)}
					and si.docstatus = 0
			"""
		):
			si = make_sales_invoice(self.sales_order.name, ignore_permissions=True)
			si.set_posting_time = True
			si.posting_date = self.woocommerce_order.get("date_paid")
			si.allocate_advances_automatically = True
			si.insert(ignore_permissions=True)
			si.submit()
			self.order.db_set("sales_invoice_created", 1)


def compare_sales_orders(original, updated):
	if not updated.items:
		return True

	if original.docstatus == 2:
		return False

	if updated.grand_total and original.grand_total != updated.grand_total:
		return False

	if len(updated.items) and len(original.items) != len(updated.items):
		return False

	if len(original.taxes) and len(updated.taxes) and len(original.taxes) != len(updated.taxes):
		return False

	original_qty_per_item = get_qty_per_item(original.items)
	updated_qty_per_item = get_qty_per_item(updated.items)
	for it in updated_qty_per_item:
		if not original_qty_per_item.get(it):
			return False

		if original_qty_per_item.get(it) != updated_qty_per_item[it]:
			return False

	return True


def get_qty_per_item(items):
	qty_per_item = defaultdict(float)
	for item in items:
		qty_per_item[item.item_code] += item.qty

	return qty_per_item


@frappe.whitelist()
def bulk_retry(docnames):
	for docname in frappe.parse_json(docnames):
		frappe.enqueue(process_order, order=docname, queue="long")