import frappe
from frappe.model import no_value_fields, table_fields
from frappe.utils import now_datetime

def execute():
	frappe.reload_doc("woocommerce", "doctype", "WooCommerce Settings")
	frappe.reload_doc("woocommerce", "doctype", "Woocommerce Shipping Methods")
	frappe.reload_doc("woocommerce", "doctype", "Woocommerce Taxes")
	frappe.reload_doc("woocommerce", "doctype", "Woocommerce Customer Role Mapping")

	new_settings = frappe.new_doc("Woocommerce Settings")
	for field in frappe.get_meta("Woocommerce Settings").fields:
		if field.fieldtype not in no_value_fields + table_fields:
			value = frappe.db.get_single_value("Woocommerce Settings", field.fieldname)
			if value:
				new_settings.update({
					field.fieldname: value
				})
	new_settings.last_synchronization_datetime = now_datetime()
	new_settings.insert()

	for dt in ["Woocommerce Shipping Methods", "Woocommerce Taxes"]:
		doctype = frappe.qb.DocType(dt)
		frappe.qb.update(doctype).set(doctype.parent, new_settings.name).where(doctype.parenttype=="WooCommerce Settings").run()

	update_custom_fields(new_settings.name)

	frappe.db.delete("Singles", {"doctype": "WooCommerce Settings"})

def update_custom_fields(settings):
	for dt in ["Customer", "Sales Order", "Item", "Address", "Item Attribute", "Item Booking"]:
		if frappe.get_meta(dt).has_field("woocommerce_id"):
			doctype = frappe.qb.DocType(dt)
			woocommerce_id_per_site = frappe.qb.Field(f"woocommerce_id_{settings}")
			frappe.qb.update(doctype).set(woocommerce_id_per_site, doctype.woocommerce_id).run()

	for dt in ["Customer", "Address"]:
		if frappe.get_meta(dt).has_field("woocommerce_email"):
			doctype = frappe.qb.DocType(dt)
			woocommerce_email_per_site = frappe.qb.Field(f"woocommerce_email_{settings}")
			frappe.qb.update(doctype).set(woocommerce_email_per_site, doctype.woocommerce_email).run()

	doctype = frappe.qb.DocType("Item")
	if frappe.get_meta("Item").has_field("last_woocommerce_sync"):
		last_woocommerce_sync_per_site = frappe.qb.Field(f"last_woocommerce_sync_{settings}")
		frappe.qb.update(doctype).set(last_woocommerce_sync_per_site, doctype.last_woocommerce_sync).run()

	if frappe.get_meta("Item").has_field("sync_with_woocommerce"):
		sync_with_woocommerce_per_site = frappe.qb.Field(f"sync_with_woocommerce_{settings}")
		frappe.qb.update(doctype).set(sync_with_woocommerce_per_site, doctype.sync_with_woocommerce).run()

	doctype = frappe.qb.DocType("Sales Order")
	if frappe.get_meta("Sales Order").has_field("woocommerce_number"):
		woocommerce_number_per_site = frappe.qb.Field(f"woocommerce_number_{settings}")
		frappe.qb.update(doctype).set(woocommerce_number_per_site, doctype.woocommerce_number).run()

	to_delete = {
		"Customer": [],
		"Sales Order": [],
		"Item": [],
		"Address": [],
		"Item Attribute": [],
		"Item Booking": [],
	}

	fields = ["woocommerce_id", "woocommerce_email", "last_woocommerce_sync", "sync_with_woocommerce", "woocommerce_number"]

	for td in to_delete:
		for field in fields:
			if field in frappe.db.get_table_columns(td):
				to_delete[td].append(field)
				if custom_field := frappe.db.get_value("Custom Field", dict(fieldname=field, dt=td)):
					frappe.delete_doc_if_exists("Custom Field", custom_field)

	frappe.model.delete_fields(
		to_delete,
		delete=1
	)