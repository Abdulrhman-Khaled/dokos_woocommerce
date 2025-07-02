// Copyright (c) 2024, Dokos SAS and contributors
// For license information, please see license.txt

frappe.query_reports["WooCommerce Stock Comparison"] = {
	"filters": [
		{
			fieldtype: "Link",
			fieldname: "site",
			options: "Woocommerce Settings",
			reqd: 1
		}
	],
	onload(report) {
		report.page.add_inner_button(__("WooCommerce Out of Stock Comparison"), function() {
			var filters = report.get_values();
			frappe.set_route('query-report', 'WooCommerce Out of Stock Comparison', { site: filters.site });
		}, __("Linked Reports"));
	}
};
