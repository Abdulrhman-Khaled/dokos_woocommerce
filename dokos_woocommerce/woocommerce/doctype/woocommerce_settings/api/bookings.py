from dokos_woocommerce.woocommerce.doctype.woocommerce_settings.api import WooCommerceAPI


class WooCommerceBookingsAPI(WooCommerceAPI):
	def __init__(self, site, version="wc-bookings/v1", *args, **kwargs):
		super(WooCommerceBookingsAPI, self).__init__(site, version, args, kwargs)

	def get_booking(self, id, params=None):
		return self.get(f"bookings/{id}", params=params)

	def get_bookings(self, params=None):
		return self.get("bookings", params=params)

	def get_booking_slots(self, params=None):
		return self.get("products/slots", params=params)
