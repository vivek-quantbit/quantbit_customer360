// ─── Customer 360 Page ───────────────────────────────────────────────────────
// Frappe Custom Page: quantbit_customer360/quantbit_customer360/page/customer360/customer360.js
// ─────────────────────────────────────────────────────────────────────────────

frappe.pages['customer360'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Customer 360',
		single_column: true
	});

	// Render base HTML
	$(wrapper).find('.layout-main-section').html(frappe.render_template('customer360', {}));
	$(wrapper).find('.c360-back').on('click keydown', function(event) {
		if (event.type === 'click' || event.key === 'Enter' || event.key === ' ') {
			event.preventDefault();
			frappe.set_route('List', 'Customer');
		}
	});

	// Bind open customer button (will be set after load)
	frappe.pages['customer360'].customer_name = null;
};

frappe.pages['customer360'].on_page_show = function(wrapper) {
	// Get customer from URL param: /customer360?customer=Columbia+Petrochem
	let params   = frappe.utils.get_url_params();
	let customer = params.customer || frappe.pages['customer360'].customer_name;

	if (!customer) {
		// Show customer picker if no param
		frappe.prompt({
			fieldname: 'customer',
			label: 'Select Customer',
			fieldtype: 'Link',
			options: 'Customer',
			reqd: 1
		}, (values) => {
			C360.load(values.customer);
		}, 'Open Customer 360', 'Open');
		return;
	}

	C360.load(customer);
};

// ─── Main Controller ─────────────────────────────────────────────────────────
var C360 = {

	customer: null,
	data: {},

	load: function(customer_name) {
		this.customer = customer_name;

		// Show loading state
		this._setLoading(true);

		// Fetch all data in parallel
		Promise.all([
			this._fetch('customer_360_master',    { customer: customer_name }),
			this._fetch('customer_360_financials', { customer: customer_name }),
			this._fetch('customer_360_sales',      { customer: customer_name }),
			this._fetch('customer_360_timeline',   { customer: customer_name }),
		]).then(([master, financials, sales, timeline]) => {
			this.data = { master, financials, sales, timeline };
			this._render();
			this._setLoading(false);
		}).catch(err => {
			console.error('Customer 360 load error:', err);
			$('.c360-grid').css('opacity', 1);
			$('#c360-flags').html(
				'<span class="flag-tag flag-red">Unable to load customer data. Check the error log.</span>'
			);
			frappe.msgprint('Failed to load Customer 360 data. Please try again.');
			this._setLoading(false);
		});
	},

	_fetch: function(method, args) {
		return frappe.call({
			method: `quantbit_customer360.api.customer_360.${method}`,
			args: args,
			freeze: false
		}).then(r => r.message || {});
	},

	_setLoading: function(state) {
		// Simple toggle — in production use a skeleton loader
		$('.c360-grid').css('opacity', state ? 0.4 : 1);
	},

	// ── Master Render ─────────────────────────────────────────────────────────
	_render: function() {
		const { master, financials, sales, timeline } = this.data;

		this._renderHeader(master);
		this._renderFlags(master, financials);
		this._renderKPIs(financials, master);
		this._renderFinancialPanel(financials);
		this._renderSalesPanel(sales);
		this._renderRelationshipPanel(master);
		this._renderRiskPanel(master, financials);
		this._renderScorecard(master);
		this._renderTimeline(timeline);
	},

	// ── Header ────────────────────────────────────────────────────────────────
	_renderHeader: function(m) {
		$('#c360-customer-name').text(m.customer_name || this.customer);

		$('#c360-zone-chip').text(m.sales_zone ? `${m.sales_zone} Zone` : 'No Zone');
		$('#c360-category-chip').text(m.customer_category || 'Uncategorized');

		// KYC chip
		let kycClass = 'valid', kycText = `✅ KYC Valid until ${m.kyc_expiry_display}`;
		if (m.kyc_status === 'Expiring Soon') {
			kycClass = 'expiring';
			kycText  = `⚠️ KYC Expiring ${m.kyc_expiry_display}`;
		} else if (m.kyc_status === 'Expired') {
			kycClass = 'expired';
			kycText  = `🔴 KYC Expired ${m.kyc_expiry_display}`;
		}
		$('#c360-kyc-chip').text(kycText).removeClass('valid expiring expired').addClass(kycClass);

		// Open Customer button
		$('#c360-open-customer').off('click').on('click', () => {
			frappe.set_route('Form', 'Customer', this.customer);
		});
	},

	// ── Alert Flags ───────────────────────────────────────────────────────────
	_renderFlags: function(m, f) {
		let flags = [];

		// Red flags
		if (m.kyc_status === 'Expired')
			flags.push({ cls: 'flag-red', icon: '🔴', text: 'KYC Expired' });
		if (f.aging_90plus > 0)
			flags.push({ cls: 'flag-red', icon: '🔴', text: 'Overdue 90+ Days' });
		if (f.credit_utilized > f.credit_limit && f.credit_limit > 0)
			flags.push({ cls: 'flag-red', icon: '🔴', text: 'Credit Limit Breached' });
		if (m.cheque_bounce_count >= 3)
			flags.push({ cls: 'flag-red', icon: '🔴', text: `${m.cheque_bounce_count} Cheque Bounces` });

		// Amber flags
		if (m.kyc_status === 'Expiring Soon')
			flags.push({ cls: 'flag-amber', icon: '⚠️', text: 'KYC Expiring Soon' });
		if (f.aging_31_60 > 0)
			flags.push({ cls: 'flag-amber', icon: '⚠️', text: 'Overdue 31–60 Days' });
		if (f.payment_delay_trend === 'increasing')
			flags.push({ cls: 'flag-amber', icon: '⚠️', text: 'Payment Delay Increasing' });
		if (f.revenue_trend_pct < -20)
			flags.push({ cls: 'flag-amber', icon: '⚠️', text: 'Order Volume Declining' });

		// Green flags
		if (m.customer_grade === 'A')
			flags.push({ cls: 'flag-green', icon: '🟢', text: 'Grade A Customer' });
		if (f.avg_payment_delay <= 5 && m.cheque_bounce_count === 0)
			flags.push({ cls: 'flag-green', icon: '🟢', text: 'Consistent Payer' });
		if (f.revenue_trend_pct > 20)
			flags.push({ cls: 'flag-green', icon: '🟢', text: 'Growing Account' });
		if (m.strategic_account)
			flags.push({ cls: 'flag-green', icon: '⭐', text: 'Strategic Account' });

		const flagsHtml = flags.map(f =>
			`<span class="flag-tag ${f.cls}">${f.icon} ${f.text}</span>`
		).join('');

		$('#c360-flags').html(flagsHtml);
	},

	// ── KPIs ──────────────────────────────────────────────────────────────────
	_renderKPIs: function(f, m) {
		const fmt = this._fmt;

		$('#kpi-lifetime').find('.kpi-value').text(fmt(f.lifetime_revenue));
		$('#kpi-ytd').find('.kpi-value').text(fmt(f.ytd_revenue));
		$('#kpi-outstanding').find('.kpi-value').text(fmt(f.total_outstanding));
		$('#kpi-overdue').find('.kpi-value')
			.text(fmt(f.total_overdue))
			.css('color', f.total_overdue > 0 ? 'var(--red)' : 'var(--green)');

		let delayText = f.avg_payment_delay > 0
			? `${f.avg_payment_delay} days`
			: 'On time';
		$('#kpi-pay-delay').find('.kpi-value')
			.text(delayText)
			.css('color', f.avg_payment_delay > 15 ? 'var(--amber)' : 'inherit');

		// Grade badge
		let grade = m.customer_grade || '—';
		$('#kpi-grade').find('.kpi-value')
			.text(grade)
			.attr('class', `kpi-value grade-value grade-${grade}`);
	},

	// ── Financial Panel ───────────────────────────────────────────────────────
	_renderFinancialPanel: function(f) {
		const fmt  = this._fmt;
		const max  = Math.max(f.aging_0_30, f.aging_31_60, f.aging_61_90, f.aging_90plus, 1);

		this._setAging('aging-0-30',   f.aging_0_30,   max, fmt);
		this._setAging('aging-31-60',  f.aging_31_60,  max, fmt);
		this._setAging('aging-61-90',  f.aging_61_90,  max, fmt);
		this._setAging('aging-90plus', f.aging_90plus, max, fmt);

		// Credit bar
		let utilPct = f.credit_limit > 0 ? Math.min((f.credit_utilized / f.credit_limit) * 100, 100) : 0;
		$('#credit-bar').css('width', utilPct + '%');
		if (f.credit_utilized > f.credit_limit) $('#credit-bar').addClass('over-limit');

		$('#c360-open-customer').closest('.c360-header').find('#credit-util-label')
			.text(`${Math.round(utilPct)}% utilized`);
		$('#credit-util-label').text(`Credit: ${Math.round(utilPct)}% used`);

		$('#val-credit-limit').text(fmt(f.credit_limit));
		$('#val-credit-utilized').text(`Utilized: ${fmt(f.credit_utilized)}`);
		$('#val-credit-available').text(`Available: ${fmt(Math.max(f.credit_limit - f.credit_utilized, 0))}`);

		$('#val-discount').text(f.avg_discount_pct ? `${f.avg_discount_pct.toFixed(1)}%` : '0%');
		$('#val-credit-notes').text(fmt(f.credit_notes_ytd));
		$('#val-bounces').text(f.cheque_bounce_count || 0);
		$('#val-dunning').text(f.dunning_phase || 'Phase 1');
	},

	_setAging: function(id, value, max, fmt) {
		let pct = max > 0 ? Math.round((value / max) * 100) : 0;
		$(`#${id}`).find('.aging-bar').css('width', pct + '%');
		$(`#${id}`).find('.aging-amount').text(value > 0 ? fmt(value) : '—');
	},

	// ── Sales Panel ───────────────────────────────────────────────────────────
	_renderSalesPanel: function(s) {
		const fmt = this._fmt;
		const esc = this._escape;

		$('#val-quotations').text(s.quotation_count || 0);
		$('#val-converted').text(s.converted_count || 0);

		let convRate = s.quotation_count > 0
			? Math.round((s.converted_count / s.quotation_count) * 100)
			: 0;
		$('#val-conv-rate').text(convRate + '%');

		$('#val-mtd').text(fmt(s.mtd_revenue));
		$('#val-qtd').text(fmt(s.qtd_revenue));
		$('#val-ytd-orders').text(fmt(s.ytd_orders));

		// SKU list
		let skuHtml = '';
		let skuMax  = s.top_skus && s.top_skus.length > 0 ? s.top_skus[0].amount : 1;
		(s.top_skus || []).slice(0, 5).forEach((sku, i) => {
			let pct = Math.round((sku.amount / skuMax) * 100);
			skuHtml += `
				<div class="sku-item">
					<span class="sku-rank">${i + 1}</span>
					<span class="sku-name">${esc(sku.item_name)}</span>
					<div class="sku-bar-wrap"><div class="sku-bar" style="width:${pct}%"></div></div>
					<span class="sku-val">${fmt(sku.amount)}</span>
				</div>`;
		});
		$('#sku-list').html(skuHtml || '<span style="font-size:12px;color:var(--text-dim)">No data</span>');

		$('#val-avg-order').text(fmt(s.avg_order_value));
		$('#val-order-freq').text(s.order_frequency ? `${s.order_frequency}/month` : '—');
		$('#val-last-order').text(s.last_order_date || '—');
	},

	// ── Relationship Panel ────────────────────────────────────────────────────
	_renderRelationshipPanel: function(m) {
		$('#val-key-contact').text(m.key_decision_maker || '—');
		$('#val-salesperson').text(m.sales_person || '—');
		$('#val-territory').text(m.territory || '—');
		$('#val-competitors').text(m.competitor_names || 'Not recorded');

		// Customer since
		if (m.customer_since) {
			let years = this._yearsSince(m.customer_since);
			$('#val-customer-since-label').text(`Customer for ${years}`);
		}

		// Tags
		let upsell = m.upsell_potential || 'Low';
		$('#tag-upsell')
			.text(`Upsell: ${upsell}`)
			.attr('class', `info-tag ${upsell.toLowerCase()}`);

		$('#tag-strategic')
			.text(m.strategic_account ? '⭐ Strategic Account' : 'Standard Account')
			.attr('class', `info-tag ${m.strategic_account ? 'strategic' : ''}`);

		$('#tag-wallet')
			.text(m.share_of_wallet ? `~${m.share_of_wallet}% Wallet Share` : 'Wallet: Unknown');

		$('#val-escalations').text(m.open_escalations || '0');
		$('#val-complaints').text(m.complaints_ytd || '0');
		$('#val-last-visit').text('Future scope — mobile app');
	},

	// ── Risk Panel ────────────────────────────────────────────────────────────
	_renderRiskPanel: function(m, f) {
		// KYC block
		let kycBlockClass = 'kyc-valid';
		let kycIcon = '✅', kycText = 'KYC Valid', kycExpiry = '';

		if (m.kyc_status === 'Expiring Soon') {
			kycBlockClass = 'kyc-expiring'; kycIcon = '⚠️'; kycText = 'KYC Expiring Soon';
			kycExpiry = `Expires ${m.kyc_expiry_display}`;
		} else if (m.kyc_status === 'Expired') {
			kycBlockClass = 'kyc-expired'; kycIcon = '🔴'; kycText = 'KYC Expired';
			kycExpiry = `Expired ${m.kyc_expiry_display}`;
		} else {
			kycExpiry = `Valid until ${m.kyc_expiry_display}`;
		}

		$('#kyc-status-block').attr('class', `kyc-status-block ${kycBlockClass}`);
		$('#kyc-icon').text(kycIcon);
		$('#kyc-status-text').text(kycText);
		$('#kyc-expiry-text').text(kycExpiry);

		// Risk items
		this._setRiskItem('risk-credit', '#rval-credit',
			f.credit_utilized <= f.credit_limit ? 'dot-green' : 'dot-red',
			f.credit_utilized <= f.credit_limit ? 'Within Limit' : '⚠️ Breached'
		);

		let overdueStatus = 'dot-green', overdueText = 'No Overdue';
		if (f.aging_90plus > 0)     { overdueStatus = 'dot-red';    overdueText = `${this._fmt(f.aging_90plus)} — 90d+`; }
		else if (f.aging_61_90 > 0) { overdueStatus = 'dot-orange'; overdueText = `${this._fmt(f.aging_61_90)} — 61-90d`; }
		else if (f.aging_31_60 > 0) { overdueStatus = 'dot-amber';  overdueText = `${this._fmt(f.aging_31_60)} — 31-60d`; }
		this._setRiskItem('risk-overdue', '#rval-overdue', overdueStatus, overdueText);

		this._setRiskItem('risk-dunning', '#rval-dunning', 'dot-grey',
			f.dunning_phase || 'Phase 1 (Salesperson)'
		);

		this._setRiskItem('risk-bounce', '#rval-bounce',
			m.cheque_bounce_count === 0 ? 'dot-green' : m.cheque_bounce_count < 3 ? 'dot-amber' : 'dot-red',
			`${m.cheque_bounce_count || 0} bounces`
		);

		this._setRiskItem('risk-kyc-hist', '#rval-kyc-hist', 'dot-grey',
			m.kyc_approved_by ? `${m.kyc_approval_date} by ${m.kyc_approved_by}` : '—'
		);
	},

	_setRiskItem: function(rowId, valSel, dotClass, text) {
		$(`#${rowId}`).find('.risk-dot').attr('class', `risk-dot ${dotClass}`);
		$(valSel).text(text);
	},

	// ── Scorecard ─────────────────────────────────────────────────────────────
	_renderScorecard: function(m) {
		let grade = m.customer_grade || '—';
		let score = m.grade_score || 0;

		$('#sc-grade').text(grade).attr('class', `grade-letter grade-${grade}`);
		$('#sc-score').text(`${score} / 100`);
		$('#sc-updated').text(m.grade_last_updated ? `Updated ${m.grade_last_updated}` : '');

		const rows = [
			{ id: 'sc-payment',    score: m.payment_score,    weight: 0.30 },
			{ id: 'sc-revenue',    score: m.revenue_score,    weight: 0.25 },
			{ id: 'sc-regularity', score: m.regularity_score, weight: 0.20 },
			{ id: 'sc-engagement', score: m.engagement_score, weight: 0.15 },
			{ id: 'sc-kyc',        score: m.kyc_score,        weight: 0.10 },
		];

		rows.forEach(row => {
			let s    = row.score || 0;
			let contrib = (s * row.weight).toFixed(1);
			let $row = $(`#${row.id}`);
			$row.find('.sc-bar').css('width', s + '%');
			$row.find('.sc-pct').text(s);
			$row.find('.sc-contrib').text(`= ${contrib}`);
		});
	},

	// ── Timeline ──────────────────────────────────────────────────────────────
	_renderTimeline: function(events) {
		const esc = this._escape;
		const iconMap = {
			'payment':   { icon: '💳', cls: 'type-payment' },
			'dispatch':  { icon: '📦', cls: 'type-dispatch' },
			'order':     { icon: '✅', cls: 'type-order' },
			'quotation': { icon: '📄', cls: 'type-quotation' },
			'kyc':       { icon: '📋', cls: 'type-kyc' },
			'complaint': { icon: '⚠️', cls: 'type-complaint' },
		};

		if (!events || events.length === 0) {
			$('#c360-timeline').html(
				'<div style="padding:20px;text-align:center;color:var(--text-dim);font-size:13px">No interactions recorded yet</div>'
			);
			return;
		}

		let html = events.slice(0, 10).map(ev => {
			let type = ev.type || 'order';
			let { icon, cls } = iconMap[type] || { icon: '📌', cls: 'type-order' };
			return `
				<div class="tl-item">
					<div class="tl-dot ${cls}">${icon}</div>
					<div class="tl-content">
						<div class="tl-main">${esc(ev.description)}</div>
						<div class="tl-meta">${esc(ev.reference || '')}</div>
					</div>
					<div class="tl-date">${ev.date}</div>
				</div>`;
		}).join('');

		$('#c360-timeline').html(html);
	},

	// ── Utilities ─────────────────────────────────────────────────────────────
	_fmt: function(val) {
		// Formats numbers to Indian notation: ₹1.2 Cr / ₹45 L / ₹12,500
		if (!val || val === 0) return '₹0';
		if (val >= 10000000) return `₹${(val / 10000000).toFixed(2)} Cr`;
		if (val >= 100000)   return `₹${(val / 100000).toFixed(1)} L`;
		return `₹${val.toLocaleString('en-IN')}`;
	},

	_escape: function(value) {
		return frappe.utils.escape_html(String(value ?? ''));
	},

	_yearsSince: function(dateStr) {
		let d     = frappe.datetime.str_to_obj(dateStr);
		let now   = new Date();
		let years = now.getFullYear() - d.getFullYear();
		let months= now.getMonth() - d.getMonth();
		if (months < 0) { years--; months += 12; }
		return months > 0 ? `${years}y ${months}m` : `${years} years`;
	}
};
