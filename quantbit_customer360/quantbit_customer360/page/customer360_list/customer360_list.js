frappe.pages['customer360-list'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({ parent: wrapper, title: __('Customer 360 List'), single_column: true });
	const $main = $(wrapper).find('.layout-main-section');
	$main.html(frappe.render_template('customer360_list', {}));

	let timer;
	$main.find('.c360-list-search').on('input', function() {
		clearTimeout(timer);
		timer = setTimeout(() => C360List.load(wrapper, this.value), 250);
	});
	$main.find('.c360-list-refresh').on('click', () => C360List.load(wrapper));
	$main.on('click', '[data-customer]', function() {
		window.location.href = `/app/customer360?customer=${encodeURIComponent(this.dataset.customer)}`;
	});
};

frappe.pages['customer360-list'].on_page_show = function(wrapper) {
	C360List.load(wrapper, $(wrapper).find('.c360-list-search').val() || '');
};

const C360List = {
	load(wrapper, search = '') {
		const $root = $(wrapper);
		$root.find('.c360-list-status').show().text(__('Loading customers…'));
		$root.find('.c360-list-table-wrap').hide();
		frappe.call({
			method: 'quantbit_customer360.api.customer_360.customer_360_list',
			args: { search },
		}).then(({ message = [] }) => {
			const rows = message.map(customer => `
				<tr>
					<td><button class="btn btn-link p-0 c360-list-name" data-customer="${this.escape(customer.name)}">${this.escape(customer.customer_name || customer.name)}</button></td>
					<td>${this.escape(customer.customer_group || '—')}</td>
					<td>${this.escape(customer.territory || '—')}</td>
					<td>${this.escape(customer.sales_zone || '—')}</td>
					<td><span class="c360-list-grade">${this.escape(customer.customer_grade || '—')}</span></td>
					<td class="text-right"><button class="btn btn-xs btn-primary" data-customer="${this.escape(customer.name)}">Open 360</button></td>
				</tr>`).join('');
			$root.find('tbody').html(rows);
			$root.find('.c360-list-status').toggle(!message.length).text(__('No customers found'));
			$root.find('.c360-list-table-wrap').toggle(Boolean(message.length));
		}).catch(() => $root.find('.c360-list-status').show().text(__('Unable to load customers')));
	},
	escape(value) {
		return frappe.utils.escape_html(String(value));
	}
};
