
frappe.listview_settings['Woocommerce Order'] = {
	onload(listview) {
		listview.page.add_action_item(
			__("Retry orders creation"),
			() => {
				const docnames = listview.get_checked_items(true);
				frappe.call({
					method: "dokos_woocommerce.woocommerce.doctype.woocommerce_order.woocommerce_order.bulk_retry",
					args: {
						docnames: docnames
					}
				}).then(() => {
					frappe.show_alert(__("Retry in progress"))
				})
			},
		);
	},
	hide_name_column: true,
}
