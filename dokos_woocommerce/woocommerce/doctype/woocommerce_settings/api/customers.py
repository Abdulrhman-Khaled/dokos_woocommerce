import frappe
import frappe.utils.nestedset
from frappe import _
from frappe.contacts.doctype.address.address import get_preferred_address
from frappe.exceptions import DuplicateEntryError, TimestampMismatchError
from frappe.utils import add_to_date, cint, get_datetime, add_years, now_datetime

from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api import WooCommerceAPI, WordpressAPI


class WooCommerceCustomersAPI(WooCommerceAPI):
	def __init__(self, site, version="wc/v3", *args, **kwargs):
		super(WooCommerceCustomersAPI, self).__init__(site, version, args, kwargs)

	def get_customer(self, id):
		return self.get(f"customers/{id}").json()

	def get_customers(self, params=None):
		return self.get("customers", params=params).json()

	def create_customer(self, data):
		return self.post("customers", data).json()

	def update_customer(self, id, data):
		return self.put(f"customers/{id}", data).json()

	def batch_create_update_customer(self, data):
		return self.post("customers/batch", data=data).json()

def get_customers(site):
	wc_api = WooCommerceCustomersAPI(site=site)

	woocommerce_customers = get_woocommerce_customers(wc_api)

	for woocommerce_customer in woocommerce_customers:
		sync_customer(wc_api.settings, woocommerce_customer)


def get_woocommerce_customers(wc_api):
	response = wc_api.get_customers()
	woocommerce_customers = response.json()

	for page_idx in range(1, int(response.headers.get("X-WP-TotalPages")) + 1):
		response = wc_api.get_customers(params={"per_page": 100, "page": page_idx})
		woocommerce_customers.extend(response)

	return woocommerce_customers


@frappe.whitelist()
def push_customers(site):
	frappe.enqueue(_push_customers, site=site, queue="long")

def _push_customers(site):
	wc_api = WooCommerceCustomersAPI(site=site)
	if not wc_api.settings.enable_sync:
		return

	last_modified_timestamp = get_datetime(
		frappe.db.get_value("Scheduled Job Type", "customers.hourly_push_customers", "last_execution")
	)

	for customer_group in wc_api.settings.customer_groups_to_synchronize:
		dokos_customers = frappe.get_all(
			"Customer",
			filters={
				"disabled": 0,
				"customer_group": customer_group.dokos_customer_group,
			},
			or_filters={
				"modified": (">=", add_to_date(last_modified_timestamp, hours=-1)),
				f"woocommerce_id_{wc_api.settings.name}": ("is", "not set")
			},
			fields=["name", "customer_name", "customer_primary_contact", f"woocommerce_id_{wc_api.settings.name}", "email_id", "tax_id"],
		)

		for customer in dokos_customers:
			primary_contact = get_customer_primary_contact(customer.name) if not customer.customer_primary_contact else frappe.get_doc("Contact", customer.customer_primary_contact)
			if not primary_contact.email_id and not customer.email_id:
				continue

			billing_address = get_customer_address(customer.name, "is_primary_address")
			shipping_address = get_customer_address(customer.name, "is_shipping_address")

			woocommerce_object = {
				"email": primary_contact.email_id or customer.email_id,
				"first_name": primary_contact.first_name or "",
				"last_name": primary_contact.last_name or "",
				"username": primary_contact.email_id or customer.email_id,
				"billing": {},
				"shipping": {},
			}

			if wc_api.settings.synchronize_vat_number :
				woocommerce_object.update({
					"meta_data": [
						{
							"key": "vat_number",
							"value": customer.tax_id,
						},
					]
				})

			if billing_address:
				woocommerce_object["billing"].update({
					"first_name": primary_contact.first_name or "",
					"last_name": primary_contact.last_name or "",
					"company": customer.customer_name,
					"address_1": billing_address.address_line1 or "",
					"address_2": billing_address.address_line2 or "",
					"city": billing_address.city or "",
					"state": billing_address.state or "",
					"postcode": billing_address.pincode or "",
					"country": billing_address.country or "",
					"email": billing_address.email_id or primary_contact.email_id or customer.email_id,
					"phone": billing_address.phone or "",
				})

			if shipping_address:
				woocommerce_object["shipping"].update({
					"first_name": primary_contact.first_name or "",
					"last_name": primary_contact.last_name or "",
					"company": customer.customer_name,
					"address_1": shipping_address.address_line1 or "",
					"address_2": shipping_address.address_line2 or "",
					"city": shipping_address.city or "",
					"state": shipping_address.state or "",
					"postcode": shipping_address.pincode or "",
					"country": shipping_address.country or "",
				})

			try:
				if customer.get(f"woocommerce_id_{wc_api.settings.name}"):
					for prop in ("email", "username"):
						del woocommerce_object[prop]
					wc_api.update_customer(customer.get(f"woocommerce_id_{wc_api.settings.name}"), woocommerce_object)
					if wc_api.settings.synchronize_roles:
						update_roles(site, customer.get(f"woocommerce_id_{wc_api.settings.name}"), customer_group.woocommerce_role)

				elif customer_exists := wc_api.get_customers(params={"email": woocommerce_object.get("email"), "role": "all"}):
					frappe.db.set_value("Customer", customer.name, f"woocommerce_id_{wc_api.settings.name}", customer_exists[0].get("id"))

				else:
						woocommerce_object.update({"password": frappe.generate_hash(length=10)})
						if res := wc_api.create_customer(woocommerce_object):
							frappe.db.set_value("Customer", customer.name, f"woocommerce_id_{wc_api.settings.name}", res.get("id"))

							if wc_api.settings.synchronize_roles:
								update_roles(site, res.get("id"), customer_group.woocommerce_role)
			except Exception:
				frappe.log_error(title="WooCommerce Customer Sync Error")


def update_roles(site, user, role):
	WordpressAPI(site=site).post(f'users/{user}', {
		"roles": [role]
	})


def sync_customer(settings, woocommerce_customer):
	customer_name = woocommerce_customer.get("billing", {}).get("company")
	customer_type = (
		"Company" if woocommerce_customer.get("billing", {}).get("company") else "Individual"
	)

	if not customer_name:
		customer_name = (
			f'{woocommerce_customer.get("billing", {}).get("first_name")} {woocommerce_customer.get("billing", {}).get("last_name")}'
			if woocommerce_customer.get("billing", {}).get("last_name")
			else None
		)

	if not customer_name:
		customer_name = (
			(
				woocommerce_customer.get("first_name")
				+ " "
				+ (woocommerce_customer.get("last_name") if woocommerce_customer.get("last_name") else "")
			)
			if woocommerce_customer.get("first_name")
			else woocommerce_customer.get("email")
		)

	try:
		if cint(woocommerce_customer.get("id")) and frappe.db.exists(
			"Customer", {f"woocommerce_id_{settings.name}": woocommerce_customer.get("id")}
		):
			customer = frappe.get_doc("Customer", {f"woocommerce_id_{settings.name}": woocommerce_customer.get("id")})

		elif frappe.db.exists("Customer", {f"woocommerce_email_{settings.name}": woocommerce_customer.get("email")}):
			customer = frappe.get_doc("Customer", {f"woocommerce_email_{settings.name}": woocommerce_customer.get("email")})

		else:
			# try to match territory
			country_name = get_country_name(woocommerce_customer["billing"]["country"])
			if frappe.db.exists("Territory", country_name):
				territory = country_name
			else:
				territory = frappe.utils.nestedset.get_root_of("Territory")

			customer = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": customer_name,
					f"woocommerce_id_{settings.name}": woocommerce_customer.get("id"),
					f"woocommerce_email_{settings.name}": woocommerce_customer.get("email"),
					"customer_group": settings.customer_group,
					"territory": territory,
					"customer_type": customer_type,
				}
			)
			customer.flags.ignore_mandatory = True
			customer.insert(ignore_permissions=True, ignore_if_duplicate=True)

		if customer:
			customer.update(
				{
					"customer_name": customer_name,
					f"woocommerce_email_{settings.name}": woocommerce_customer.get("email"),
					"customer_type": customer_type,
				}
			)
			try:
				customer.flags.ignore_mandatory = True
				customer.flags.ignore_permissions = True
				customer.save()
			except frappe.exceptions.TimestampMismatchError:
				# Handle the update of two sales orders customers details concurrently
				pass

			billing_address = woocommerce_customer.get("billing")
			if billing_address:
				add_billing_address(settings, customer, woocommerce_customer)

			shipping_address = woocommerce_customer.get("shipping")
			if shipping_address:
				add_shipping_address(settings, customer, woocommerce_customer)

			add_contact(customer, woocommerce_customer)

		frappe.db.commit()

		return customer
	except Exception:
		frappe.log_error(_("Woocommerce Customer Creation Error"))


def sync_guest_customers(site, order):
	wc_api = WooCommerceCustomersAPI(site=site)
	customer_object = {
		"first_name": order.get("billing", {}).get("first_name"),
		"last_name": order.get("billing", {}).get("last_name"),
		"email": order.get("billing", {}).get("email"),
		"id": 0,
		"billing": order.get("billing"),
		"shipping": order.get("shipping"),
	}

	return sync_customer(wc_api.settings, customer_object)


def add_billing_address(settings, customer, woocommerce_customer):
	existing_address = get_preferred_address("Customer", customer.name, "is_primary_address")
	_add_update_address(settings, customer, woocommerce_customer, "Billing", existing_address)


def add_shipping_address(settings, customer, woocommerce_customer):
	existing_address = get_preferred_address("Customer", customer.name, "is_shipping_address")
	_add_update_address(settings, customer, woocommerce_customer, "Shipping", existing_address)


def _add_update_address(
	settings, customer, woocommerce_customer, address_type, existing_address=None
):
	woocommerce_address = woocommerce_customer.get(address_type.lower())

	country = get_country_name(woocommerce_address.get("country"))
	if not frappe.db.exists("Country", country):
		country = frappe.db.get_value("Company", settings.company, "country")

	try:
		if existing_address:
			doc = frappe.get_doc("Address", existing_address)
		else:
			doc = frappe.new_doc("Address")

		doc.flags.ignore_permissions = True
		doc.update(
			{
				"address_title": customer.name,
				"address_type": address_type,
				"address_line1": woocommerce_address.get("address_1") or "No Address Line 1",
				"address_line2": woocommerce_address.get("address_2"),
				"city": woocommerce_address.get("city") or "City",
				"state": woocommerce_address.get("state"),
				"pincode": woocommerce_address.get("postcode"),
				"country": country,
				"phone": woocommerce_address.get("phone"),
				"email_id": woocommerce_address.get("email"),
				"is_primary_address": address_type == "Billing",
				"is_shipping_address": address_type == "Shipping",
				"links": [{"link_doctype": "Customer", "link_name": customer.name}],
			}
		)
		try:
			doc.save()
		except frappe.exceptions.TimestampMismatchError:
			# Handle the update of two sales orders contact details concurrently
			pass

	except Exception:
		doc.log_error(_("Woocommerce Address Error"))


def add_contact(customer, woocommerce_customer):
	existing_contact = frappe.db.get_value(
		"Contact", dict(email_id=woocommerce_customer["billing"]["email"]), "name"
	)
	try:
		if existing_contact:
			doc = frappe.get_doc("Contact", existing_contact)
		else:
			doc = frappe.new_doc("Contact")

		doc.flags.ignore_permissions = True
		doc.update(
			{
				"first_name": woocommerce_customer["billing"]["first_name"],
				"last_name": woocommerce_customer["billing"]["last_name"],
				"email_ids": [{"email_id": woocommerce_customer["billing"]["email"], "is_primary": 1}],
				"phone_nos": [{"phone": woocommerce_customer["billing"]["phone"], "is_primary_phone": 1}],
				"links": [{"link_doctype": "Customer", "link_name": customer.name}],
				"is_primary_contact": 1,
				"is_billing_contact": 1
			}
		)
		try:
			doc.save()
		except DuplicateEntryError:
			pass
		except TimestampMismatchError:
			# Handle the update of two sales orders contact details concurrently
			pass

	except Exception:
		doc.log_error(_("Woocommerce Contact Error"))


def get_country_name(code):
	return frappe.db.get_value("Country", dict(code=code), "name")

def get_customer_primary_contact(customer):
	con = frappe.qb.DocType("Contact")
	dlink = frappe.qb.DocType("Dynamic Link")

	contacts = (
		frappe.qb.from_(con)
		.join(dlink)
		.on(con.name == dlink.parent)
		.select(con.name, con.first_name, con.last_name, con.email_id)
		.where((dlink.link_name == customer))
		.run(as_dict=True)
	)

	return contacts[0] if contacts else frappe._dict()

def get_customer_address(customer, preferred_key="is_primary_address"):
	add = frappe.qb.DocType("Address")
	dlink = frappe.qb.DocType("Dynamic Link")

	query = (
		frappe.qb.from_(add)
		.join(dlink)
		.on(add.name == dlink.parent)
		.select(add.name, add.address_line1, add.address_line2, add.city, add.state, add.pincode, add.country, add.email_id, add.phone)
		.where((dlink.link_name == customer))
	)

	if preferred_key == "is_primary_address":
		query = query.where((add.is_primary_address==1) | ((add.is_primary_address==0) & (add.is_shipping_address==0)))
	elif preferred_key == "is_shipping_address":
		query = query.where(add.is_shipping_address==1)

	addresses =  query.run(as_dict=True)
	return addresses[0] if addresses else frappe._dict()