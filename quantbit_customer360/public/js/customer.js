frappe.ui.form.on('Customer', {
	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__('Customer 360'), () => {
			window.location.href = `/app/customer360?customer=${encodeURIComponent(frm.doc.name)}`;
		}, __('View'));
	}
});
