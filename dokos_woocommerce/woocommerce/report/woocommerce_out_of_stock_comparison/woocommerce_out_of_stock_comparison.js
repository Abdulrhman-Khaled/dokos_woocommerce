// Copyright (c) 2024, Dokos SAS and contributors
// For license information, please see license.txt

frappe.query_reports["WooCommerce Out of Stock Comparison"] = {
	"filters": [
		{
			fieldtype: "Link",
			fieldname: "site",
			options: "Woocommerce Settings",
			reqd: 1
		}
	],
	onload(report) {
		report.page.set_primary_action(__("Update Stock Levels"), function() {
			var filters = report.get_values();
			frappe.call({
				method: "dokos_woocommerce.woocommerce.report.woocommerce_out_of_stock_comparison.woocommerce_out_of_stock_comparison.update_stock",
				args: {
					filters: filters
				}
			}).then(() => {
				frappe.show_alert({
					indicator: "orange",
					message: "Stock update in progress"
				})
			})
		});

		report.page.add_inner_button(__("WooCommerce Stock Comparison"), function() {
			var filters = report.get_values();
			frappe.set_route('query-report', 'WooCommerce Stock Comparison', { site: filters.site });
		}, __("Linked Reports"));
	}
};
