frappe.listview_settings.Customer = frappe.listview_settings.Customer || {};

const existingOnload = frappe.listview_settings.Customer.onload;
frappe.listview_settings.Customer.onload = function(listview) {
	if (existingOnload) existingOnload(listview);

	listview.page.add_inner_button(__('Customer 360 List'), () => {
		frappe.set_route('customer360-list');
	});
};
