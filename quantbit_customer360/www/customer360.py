from urllib.parse import urlencode

import frappe
from frappe import _

no_cache = 1


def get_context(context):
	query_string = frappe.request.query_string.decode("utf-8")
	requested_path = "/customer360" + (f"?{query_string}" if query_string else "")

	if frappe.session.user == "Guest":
		frappe.redirect(f"/login?{urlencode({'redirect-to': requested_path})}")

	if frappe.db.get_value("User", frappe.session.user, "user_type") == "Website User":
		frappe.throw(_("You are not permitted to access this page."), frappe.PermissionError)

	target = "/app/customer360" + (f"?{query_string}" if query_string else "")
	frappe.redirect(target)
