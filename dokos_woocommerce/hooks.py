from . import __version__ as app_version

app_name = "dokos_woocommerce"
app_title = "WooCommerce"
app_publisher = "Dokos SAS"
app_description = "WooCommerce Integration for Dokos"
app_email = "hello@dokos.io"
app_license = "AGPLv3"
required_apps = ["erpnext"]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/dokos_woocommerce/css/dokos_woocommerce.css"
# app_include_js = "/assets/dokos_woocommerce/js/dokos_woocommerce.js"

# include js, css files in header of web template
# web_include_css = "/assets/dokos_woocommerce/css/dokos_woocommerce.css"
# web_include_js = "/assets/dokos_woocommerce/js/dokos_woocommerce.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "dokos_woocommerce/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Item Booking" : "public/js/item_booking.js"
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
#	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
#	"methods": "dokos_woocommerce.utils.jinja_methods",
#	"filters": "dokos_woocommerce.utils.jinja_filters"
# }

# Installation
# ------------

before_install = "dokos_woocommerce.install.before_install"
#after_install = "dokos_woocommerce.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "dokos_woocommerce.uninstall.before_uninstall"
# after_uninstall = "dokos_woocommerce.uninstall.after_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "dokos_woocommerce.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
#	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
#	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
#	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"Bin": {
# 		"on_update": "dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products.update_stock"
# 	},
# }

after_bin_qty_update = ["dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products.update_stock"]

# Scheduled Tasks
# ---------------

scheduler_events = {
	"hourly_long": [
		"dokos_woocommerce.woocommerce.doctype.woocommerce_settings.woocommerce_settings.sync_woocommerce",
		"dokos_woocommerce.woocommerce.doctype.woocommerce_settings.woocommerce_settings.retry_created_orders",
		"dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.products.hourly_stock_update",
		"dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api.customers.push_customers"
	],
	"daily": [
		"dokos_woocommerce.tasks.retry_orders_in_error_status"
	],
	"weekly": [
		"dokos_woocommerce.tasks.retry_incomplete_orders"
	]
}

# Testing
# -------

before_tests = "dokos_woocommerce.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
#	"frappe.desk.doctype.event.event.get_events": "dokos_woocommerce.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "dokos_woocommerce.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]


# User Data Protection
# --------------------

# user_data_fields = [
#	{
#		"doctype": "{doctype_1}",
#		"filter_by": "{filter_by}",
#		"redact_fields": ["{field_1}", "{field_2}"],
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_2}",
#		"filter_by": "{filter_by}",
#		"partial": 1,
#	},
#	{
#		"doctype": "{doctype_3}",
#		"strict": False,
#	},
#	{
#		"doctype": "{doctype_4}"
#	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
#	"dokos_woocommerce.auth.validate"
# ]

webhooks_handler = {
	"WooCommerce": "dokos_woocommerce.woocommerce_connection.handle_webhook"
}