frappe.ui.form.on('Item Booking', {
	refresh(frm) {
		frm.trigger("set_woocommerce_info")
	},
	set_woocommerce_info: function(frm) {
		const meta = frappe.get_meta("Item Booking")
		meta.fields.map(f => {
			if (f.fieldname.startsWith("woocommerce_id") && frm.doc[f.fieldname]) {
				frappe.db.get_value("Woocommerce Settings", f.fieldname.substring(15), "woocommerce_server_url")
				.then(r => {
					console.log("R", r.message)
					const full_url = `${r.message.woocommerce_server_url}wp-admin/post.php?post=${frm.doc[f.fieldname]}&action=edit`
					let msg = __("This booking has been created in WooCommerce Booking.\n")
					msg += __("Any date modification needs to be done at <a href='{}' target='_blank'>this address</a>.", [full_url])
					frm.dashboard.set_headline_alert(msg)
				})
			}
		})
	}
})