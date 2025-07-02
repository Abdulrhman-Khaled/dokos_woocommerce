// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on('Woocommerce Settings', {
	setup(frm) {
		frm.set_query("warehouse", () => {
			return {
				company: frm.doc.company
			}
		})
	},
	refresh(frm) {
		frappe.call({
			method: "frappe.core.doctype.system_settings.system_settings.load",
			callback: function(data) {
				frappe.all_timezones = data.message.timezones;
				frm.set_df_property("woocommerce_site_timezone", "options", frappe.all_timezones);
			}
		});

		if (frm.doc.enable_sync) {
			frm.trigger("sync_buttons");
		}
		frm.trigger("add_button_generate_secret");
		frm.trigger("check_enabled");
	},

	enable_sync(frm) {
		frm.trigger("check_enabled");
	},

	add_button_generate_secret(frm) {
		frm.add_custom_button(__('Generate Secret'), () => {
			frappe.confirm(
				__("Apps using current key won't be able to access, are you sure?"),
				() => {
					frappe.call({
						type:"POST",
						method:"dokos_woocommerce.woocommerce.doctype.woocommerce_settings.woocommerce_settings.generate_secret",
						args: {
							settings: frm.doc.name
						}
					}).done(() => {
						frm.reload_doc();
					}).fail(() => {
						frappe.msgprint(__("Could not generate Secret"));
					});
				}
			);
		});
	},

	check_enabled (frm) {
		frm.set_df_property("woocommerce_server_url", "reqd", frm.doc.enable_sync);
		frm.set_df_property("api_consumer_key", "reqd", frm.doc.enable_sync);
		frm.set_df_property("api_consumer_secret", "reqd", frm.doc.enable_sync);
	},

	get_tax_account(frm) {
		frappe.xcall("dokos_woocommerce.woocommerce.doctype.woocommerce_settings.woocommerce_settings.get_taxes", {
			site: frm.doc.woocommerce_server_url
		})
		.then(r => {
			frm.clear_table("tax_accounts")
			if (r && r.length) {
				r.forEach(tax => {
					const child = frm.add_child("tax_accounts");
					child.woocommerce_tax_id = tax.id;
					child.woocommerce_tax_name = tax.name;
				})
				refresh_field("tax_accounts");
			}
		})
	},

	get_shipping_methods(frm) {
		frappe.xcall("dokos_woocommerce.woocommerce.doctype.woocommerce_settings.woocommerce_settings.get_shipping_methods", {
			site: frm.doc.woocommerce_server_url
		})
		.then(r => {
			frm.clear_table("shipping_accounts")
			if (r && r.length) {
				r.forEach(method => {
					const child = frm.add_child("shipping_accounts");
					child.woocommerce_shipping_method_id = method.id;
					child.woocommerce_shipping_method_title = method.title;
				})
				refresh_field("shipping_accounts");
			}
		})
	},

	sync_buttons(frm) {
		frm.add_custom_button(__('Get WooCommerce products'), () => {
			frappe.confirm(
				__("Add WooCommerce products to Dokos ?"),
				() => {
					frappe.show_alert({
						indicator: "orange",
						message: __("WooCommerce products are being added to Dokos")
					})
					frappe.call({
						type:"POST",
						method:"dokos_woocommerce.woocommerce.doctype.woocommerce_settings.woocommerce_settings.get_products",
						args: {
							site: frm.doc.woocommerce_server_url
						}
					});
				}
			);
		}, __("Actions"));

		frm.add_custom_button(__('Push items to WooCommerce'), () => {
			frappe.confirm(
				__("Add Dokos items to WooCommerce ?"),
				() => {
					frappe.show_alert({
						indicator: "orange",
						message: __("Dokos items are being pushed to WooCommerce")
					})
					frappe.call({
						type:"POST",
						method:"dokos_woocommerce.woocommerce.doctype.woocommerce_settings.woocommerce_settings.push_products",
						args: {
							site: frm.doc.woocommerce_server_url
						}
					});
				}
			);
		}, __("Actions"));

		frm.add_custom_button(__('Push Customers to WooCommerce'), () => {
			frappe.confirm(
				__("Add Dokos customers to WooCommerce ?"),
				() => {
					frappe.show_alert({
						indicator: "orange",
						message: __("Dokos customers are being pushed to WooCommerce")
					})
					frappe.call({
						type:"POST",
						method:"dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.customers.push_customers",
						args: {
							site: frm.doc.woocommerce_server_url
						}
					});
				}
			);
		}, __("Actions"));
	}
});

frappe.ui.form.on("Woocommerce Settings", "onload", function () {
	frappe.call({
		method: "dokos_woocommerce.woocommerce.doctype.woocommerce_settings.woocommerce_settings.get_series",
		callback: function (r) {
			$.each(r.message, function (key, value) {
				set_field_options(key, value);
			});
		}
	});
});
