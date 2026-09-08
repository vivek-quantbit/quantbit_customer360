# ─── Customer 360 API ────────────────────────────────────────────────────────
# quantbit_customer360/api/customer_360.py
# All methods are whitelisted for Frappe client calls.
# ─────────────────────────────────────────────────────────────────────────────

import frappe
from frappe.utils import (
    getdate, nowdate, add_days, date_diff, flt, cint,
    get_first_day, get_last_day, add_months
)
from datetime import date


# ─── 1. Master Data ──────────────────────────────────────────────────────────

@frappe.whitelist()
def customer_360_list(search=None, start=0, page_length=100):
    """Return customers visible to the current user for the dedicated 360 list."""
    search = (search or "").strip()
    or_filters = None
    if search:
        pattern = f"%{search}%"
        or_filters = {"name": ["like", pattern], "customer_name": ["like", pattern]}

    return frappe.get_list(
        "Customer",
        fields=[
            "name",
            "customer_name",
            "customer_group",
            "territory",
            "sales_zone",
            "customer_grade",
        ],
        filters={"disabled": 0},
        or_filters=or_filters,
        order_by="customer_name asc",
        start=cint(start),
        page_length=min(max(cint(page_length), 1), 100),
    )


@frappe.whitelist()
def customer_360_master(customer):
    """
    Returns customer master fields + KYC + strategic fields.
    """
    doc = _get_permitted_customer(customer)

    # KYC status calculation
    kyc_expiry = doc.get("kyc_expiry_date")
    kyc_status, kyc_expiry_display = _kyc_status(kyc_expiry)

    # Customer since = creation date
    customer_since = frappe.db.get_value("Customer", customer, "creation")

    # Open escalations from CRM Issues
    open_escalations = frappe.db.count("Issue", {
        "customer": customer,
        "status": ["in", ["Open", "Replied"]]
    })

    # Complaints YTD (Issues raised this year)
    complaints_ytd = frappe.db.count("Issue", {
        "customer": customer,
        "creation": [">=", f"{date.today().year}-01-01"]
    })

    return {
        "customer_name":       doc.customer_name,
        "customer_group":      doc.customer_group,
        "territory":           doc.territory,
        "sales_zone":          doc.get("sales_zone"),
        "customer_category":   doc.get("customer_category"),
        "assigned_salesperson": _get_salesperson(customer),
        "sales_person":        _get_salesperson(customer),

        # KYC
        "kyc_status":          kyc_status,
        "kyc_expiry_display":  kyc_expiry_display,
        "kyc_date":            str(doc.get("kyc_date") or ""),
        "kyc_expiry_date":     str(kyc_expiry or ""),
        "kyc_approved_by":     doc.get("kyc_approved_by"),
        "kyc_approval_date":   str(doc.get("kyc_approval_date") or ""),

        # Strategic
        "credit_limit":         flt(doc.get("credit_limit")),
        "cheque_bounce_count":  cint(doc.get("cheque_bounce_count")),
        "share_of_wallet":      flt(doc.get("share_of_wallet")),
        "key_decision_maker":   doc.get("key_decision_maker"),
        "competitor_names":     doc.get("competitor_names"),
        "upsell_potential":     doc.get("upsell_potential") or "Low",
        "strategic_account":    cint(doc.get("strategic_account")),

        # Grades (written nightly by scheduled job)
        "customer_grade":      doc.get("customer_grade") or "—",
        "grade_score":         flt(doc.get("grade_score")),
        "payment_score":       flt(doc.get("payment_score")),
        "revenue_score":       flt(doc.get("revenue_score")),
        "regularity_score":    flt(doc.get("regularity_score")),
        "engagement_score":    flt(doc.get("engagement_score")),
        "kyc_score":           flt(doc.get("kyc_score")),
        "grade_last_updated":  str(doc.get("grade_last_updated") or ""),

        # Relationship
        "customer_since":      str(customer_since)[:10],
        "open_escalations":    open_escalations,
        "complaints_ytd":      complaints_ytd,

        # Future
        "last_physical_visit": None,
    }


# ─── 2. Financial Data ───────────────────────────────────────────────────────

@frappe.whitelist()
def customer_360_financials(customer):
    """
    Lifetime revenue, YTD, outstanding, overdue aging, dunning.
    Pulls from GL Entries and Sales Invoice.
    """
    _get_permitted_customer(customer)
    today     = getdate(nowdate())
    year_start = getdate(f"{today.year}-04-01")  # Indian FY

    # ── Lifetime revenue from submitted Sales Invoices
    lifetime = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Invoice`
        WHERE customer = %s AND docstatus = 1
    """, customer)[0][0]

    # ── YTD revenue (current FY)
    ytd = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Invoice`
        WHERE customer = %s AND docstatus = 1
          AND posting_date >= %s
    """, (customer, year_start))[0][0]

    # ── Outstanding (all unpaid submitted invoices)
    outstanding_rows = frappe.db.sql("""
        SELECT outstanding_amount, posting_date, due_date
        FROM `tabSales Invoice`
        WHERE customer = %s AND docstatus = 1
          AND outstanding_amount > 0
    """, customer, as_dict=True)

    total_outstanding = sum(r.outstanding_amount for r in outstanding_rows)

    # ── Aging buckets
    aging = {"0_30": 0, "31_60": 0, "61_90": 0, "90plus": 0}
    total_overdue = 0

    for row in outstanding_rows:
        due    = getdate(row.due_date or row.posting_date)
        days   = date_diff(today, due)
        amount = flt(row.outstanding_amount)

        if days < 0:
            aging["0_30"] += amount   # not yet due
        elif days <= 30:
            aging["0_30"] += amount
        elif days <= 60:
            aging["31_60"] += amount
            total_overdue  += amount
        elif days <= 90:
            aging["61_90"] += amount
            total_overdue  += amount
        else:
            aging["90plus"] += amount
            total_overdue   += amount

    # ── Average payment delay (last 12 months paid invoices)
    paid_invoices = frappe.db.sql("""
        SELECT posting_date, due_date, payment_terms_template
        FROM `tabSales Invoice`
        WHERE customer = %s AND docstatus = 1
          AND outstanding_amount = 0
          AND posting_date >= %s
        ORDER BY posting_date DESC LIMIT 50
    """, (customer, add_months(nowdate(), -12)), as_dict=True)

    # Approximate delay as 0 for now (actual needs Payment Entry join)
    # TODO: join with Payment Entry to get actual payment date
    avg_payment_delay = 0

    # ── Payment trend (increasing/decreasing)
    payment_delay_trend = "stable"

    # ── Credit limit from Customer Master
    credit_limit    = flt(frappe.db.get_value("Customer", customer, "credit_limit"))
    credit_utilized = flt(total_outstanding)

    # ── Average discount
    avg_discount = frappe.db.sql("""
        SELECT COALESCE(AVG(discount_amount / NULLIF(grand_total, 0) * 100), 0)
        FROM `tabSales Invoice`
        WHERE customer = %s AND docstatus = 1
          AND posting_date >= %s
    """, (customer, year_start))[0][0]

    # ── Credit notes YTD
    credit_notes_ytd = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Invoice`
        WHERE customer = %s AND docstatus = 1
          AND is_return = 1
          AND posting_date >= %s
    """, (customer, year_start))[0][0]

    cheque_bounce_count = cint(frappe.db.get_value("Customer", customer, "cheque_bounce_count"))
    dunning_phase       = frappe.db.get_value("Customer", customer, "dunning_stage") or "Phase 1"

    return {
        "lifetime_revenue":    flt(lifetime),
        "ytd_revenue":         flt(ytd),
        "total_outstanding":   flt(total_outstanding),
        "total_overdue":       flt(total_overdue),
        "avg_payment_delay":   cint(avg_payment_delay),
        "payment_delay_trend": payment_delay_trend,

        "aging_0_30":   flt(aging["0_30"]),
        "aging_31_60":  flt(aging["31_60"]),
        "aging_61_90":  flt(aging["61_90"]),
        "aging_90plus": flt(aging["90plus"]),

        "credit_limit":      credit_limit,
        "credit_utilized":   credit_utilized,

        "avg_discount_pct":  flt(avg_discount),
        "credit_notes_ytd":  flt(credit_notes_ytd),
        "cheque_bounce_count": cheque_bounce_count,
        "dunning_phase":     dunning_phase,
        "revenue_trend_pct": 0,  # populated by grade engine
    }


# ─── 3. Sales Activity ───────────────────────────────────────────────────────

@frappe.whitelist()
def customer_360_sales(customer):
    """
    Quotations, conversions, MTD/QTD/YTD orders, top SKUs, frequency.
    """
    _get_permitted_customer(customer)
    today      = getdate(nowdate())
    six_ago    = add_months(nowdate(), -6)
    year_start = getdate(f"{today.year}-04-01")
    month_start = get_first_day(today)
    quarter_start = _quarter_start(today)

    # ── Quotations last 6 months
    quotations = frappe.db.sql("""
        SELECT name, status
        FROM `tabQuotation`
        WHERE party_name = %s AND docstatus = 1
          AND transaction_date >= %s
    """, (customer, six_ago), as_dict=True)

    quotation_count = len(quotations)
    converted_count = sum(1 for q in quotations if q.status in ["Order Lost", "Ordered"])
    # "Ordered" = converted to Sales Order
    converted_count = sum(1 for q in quotations if q.status == "Ordered")

    # ── MTD orders
    mtd = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Order`
        WHERE customer = %s AND docstatus = 1
          AND transaction_date >= %s
    """, (customer, month_start))[0][0]

    # ── QTD orders
    qtd = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Order`
        WHERE customer = %s AND docstatus = 1
          AND transaction_date >= %s
    """, (customer, quarter_start))[0][0]

    # ── YTD orders
    ytd = frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total), 0)
        FROM `tabSales Order`
        WHERE customer = %s AND docstatus = 1
          AND transaction_date >= %s
    """, (customer, year_start))[0][0]

    # ── Top 5 SKUs (by value, all time)
    top_skus = frappe.db.sql("""
        SELECT soi.item_code, soi.item_name,
               SUM(soi.amount) AS amount
        FROM `tabSales Order Item` soi
        JOIN `tabSales Order` so ON so.name = soi.parent
        WHERE so.customer = %s AND so.docstatus = 1
        GROUP BY soi.item_code, soi.item_name
        ORDER BY amount DESC
        LIMIT 5
    """, customer, as_dict=True)

    # ── Average order value & frequency
    order_stats = frappe.db.sql("""
        SELECT COUNT(*) AS cnt, AVG(grand_total) AS avg_val,
               MIN(transaction_date) AS first_date
        FROM `tabSales Order`
        WHERE customer = %s AND docstatus = 1
    """, customer, as_dict=True)[0]

    order_count = cint(order_stats.cnt)
    avg_order_value = flt(order_stats.avg_val)

    # Orders per month
    if order_stats.first_date:
        months_active = max(date_diff(today, getdate(order_stats.first_date)) / 30, 1)
        order_frequency = round(order_count / months_active, 1)
    else:
        order_frequency = 0

    # ── Last order date
    last_order_date = frappe.db.sql("""
        SELECT MAX(transaction_date)
        FROM `tabSales Order`
        WHERE customer = %s AND docstatus = 1
    """, customer)[0][0]

    return {
        "quotation_count":  quotation_count,
        "converted_count":  converted_count,
        "mtd_revenue":      flt(mtd),
        "qtd_revenue":      flt(qtd),
        "ytd_orders":       flt(ytd),
        "top_skus":         top_skus,
        "avg_order_value":  avg_order_value,
        "order_frequency":  order_frequency,
        "last_order_date":  str(last_order_date) if last_order_date else "—",
    }


# ─── 4. Timeline ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def customer_360_timeline(customer):
    """
    Last 10 interactions across: Sales Order, Payment, Delivery Note,
    Quotation, KYC updates, Issues/Complaints.
    """
    _get_permitted_customer(customer)
    events = []

    # Sales Orders
    orders = frappe.db.sql("""
        SELECT name, transaction_date, grand_total, status
        FROM `tabSales Order`
        WHERE customer = %s AND docstatus = 1
        ORDER BY transaction_date DESC LIMIT 5
    """, customer, as_dict=True)
    for o in orders:
        events.append({
            "date":        str(o.transaction_date),
            "type":        "order",
            "description": f"SO {o.name} confirmed — ₹{_lakh(o.grand_total)}",
            "reference":   o.name,
        })

    # Delivery Notes
    dns = frappe.db.sql("""
        SELECT name, posting_date, grand_total
        FROM `tabDelivery Note`
        WHERE customer = %s AND docstatus = 1
        ORDER BY posting_date DESC LIMIT 4
    """, customer, as_dict=True)
    for d in dns:
        events.append({
            "date":        str(d.posting_date),
            "type":        "dispatch",
            "description": f"{d.name} dispatched — ₹{_lakh(d.grand_total)}",
            "reference":   d.name,
        })

    # Payments received
    payments = frappe.db.sql("""
        SELECT pe.name, pe.posting_date, pe.paid_amount
        FROM `tabPayment Entry` pe
        WHERE pe.party = %s AND pe.party_type = 'Customer'
          AND pe.docstatus = 1
        ORDER BY pe.posting_date DESC LIMIT 4
    """, customer, as_dict=True)
    for p in payments:
        events.append({
            "date":        str(p.posting_date),
            "type":        "payment",
            "description": f"Payment received — ₹{_lakh(p.paid_amount)}",
            "reference":   p.name,
        })

    # Quotations
    quotes = frappe.db.sql("""
        SELECT name, transaction_date, grand_total, status
        FROM `tabQuotation`
        WHERE party_name = %s AND docstatus = 1
        ORDER BY transaction_date DESC LIMIT 3
    """, customer, as_dict=True)
    for q in quotes:
        status_txt = "converted" if q.status == "Ordered" else q.status.lower()
        events.append({
            "date":        str(q.transaction_date),
            "type":        "quotation",
            "description": f"{q.name} sent — {status_txt}",
            "reference":   q.name,
        })

    # Issues / Complaints
    issues = frappe.db.sql("""
        SELECT name, opening_date, subject, status
        FROM `tabIssue`
        WHERE customer = %s
        ORDER BY opening_date DESC LIMIT 3
    """, customer, as_dict=True)
    for i in issues:
        events.append({
            "date":        str(i.opening_date),
            "type":        "complaint",
            "description": f"Issue: {i.subject[:50]} — {i.status}",
            "reference":   i.name,
        })

    # Sort all events by date desc, take top 10
    events.sort(key=lambda x: x["date"], reverse=True)
    return events[:10]


# ─── Scheduled Job: Grade Engine ─────────────────────────────────────────────

def calculate_all_customer_grades():
    """
    Nightly job. Called from hooks.py scheduler_events.
    Recalculates A/B/C/D grade for every active customer.
    """
    customers = frappe.db.get_all("Customer",
        filters={"disabled": 0},
        pluck="name"
    )

    for customer in customers:
        try:
            _calculate_grade(customer)
        except Exception as e:
            frappe.log_error(f"Grade calc failed for {customer}: {e}", "Customer Grade Engine")

    frappe.db.commit()


def _calculate_grade(customer):
    today      = getdate(nowdate())
    year_start = getdate(f"{today.year}-04-01")

    # 1. Payment score
    p = _payment_score(customer, today)

    # 2. Revenue growth score
    r = _revenue_growth_score(customer, today, year_start)

    # 3. Order regularity score
    o = _order_regularity_score(customer, today)

    # 4. Engagement score
    e = _engagement_score(customer, today)

    # 5. KYC compliance score
    k = _kyc_score_calc(customer)

    total = (p * 0.30) + (r * 0.25) + (o * 0.20) + (e * 0.15) + (k * 0.10)
    total = round(total, 1)

    if total >= 85:   grade = "A"
    elif total >= 65: grade = "B"
    elif total >= 45: grade = "C"
    else:             grade = "D"

    frappe.db.set_value("Customer", customer, {
        "customer_grade":    grade,
        "grade_score":       total,
        "payment_score":     round(p, 1),
        "revenue_score":     round(r, 1),
        "regularity_score":  round(o, 1),
        "engagement_score":  round(e, 1),
        "kyc_score":         round(k, 1),
        "grade_last_updated": nowdate(),
    }, update_modified=False)


def _payment_score(customer, today):
    overdue_90 = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabSales Invoice`
        WHERE customer=%s AND docstatus=1
          AND outstanding_amount > 0
          AND DATEDIFF(%s, due_date) > 90
    """, (customer, today))[0][0]
    if overdue_90 > 0: return 0

    bounces = cint(frappe.db.get_value("Customer", customer, "cheque_bounce_count"))
    # Simplified: use bounce count as proxy; enhance with actual payment delay later
    if bounces == 0: return 90
    if bounces == 1: return 60
    if bounces == 2: return 35
    return 10


def _revenue_growth_score(customer, today, year_start):
    curr_qstart = _quarter_start(today)
    prev_qstart = add_months(curr_qstart, -3)
    prev_qend   = add_days(curr_qstart, -1)

    curr_q = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total),0) FROM `tabSales Order`
        WHERE customer=%s AND docstatus=1 AND transaction_date>=%s
    """, (customer, curr_qstart))[0][0])

    prev_q = flt(frappe.db.sql("""
        SELECT COALESCE(SUM(grand_total),0) FROM `tabSales Order`
        WHERE customer=%s AND docstatus=1
          AND transaction_date>=%s AND transaction_date<=%s
    """, (customer, prev_qstart, prev_qend))[0][0])

    if curr_q == 0: return 0
    if prev_q == 0: return 80  # new business
    pct = ((curr_q - prev_q) / prev_q) * 100
    if pct >  20: return 100
    if pct >   5: return 80
    if pct > -5:  return 60
    if pct > -20: return 35
    return 10


def _order_regularity_score(customer, today):
    months_with_orders = 0
    for i in range(6):
        m_start = get_first_day(add_months(today, -i))
        m_end   = get_last_day(add_months(today, -i))
        count = frappe.db.sql("""
            SELECT COUNT(*) FROM `tabSales Order`
            WHERE customer=%s AND docstatus=1
              AND transaction_date>=%s AND transaction_date<=%s
        """, (customer, m_start, m_end))[0][0]
        if count > 0: months_with_orders += 1

    scores = {6: 100, 5: 80, 4: 60, 3: 35, 2: 15, 1: 10, 0: 0}
    return scores.get(months_with_orders, 0)


def _engagement_score(customer, today):
    sixty_ago = add_days(today, -60)
    ninety_ago = add_days(today, -90)

    # Recent converted quotation
    converted = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabQuotation`
        WHERE party_name=%s AND docstatus=1
          AND status='Ordered' AND transaction_date>=%s
    """, (customer, sixty_ago))[0][0]
    if converted > 0: return 100

    # Recent quotation sent
    quoted = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabQuotation`
        WHERE party_name=%s AND docstatus=1
          AND transaction_date>=%s
    """, (customer, sixty_ago))[0][0]
    if quoted > 0: return 70

    if not frappe.db.exists("DocType", "CRM Call Log"):
        return 0

    # CRM activity
    activity_60 = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabCRM Call Log`
        WHERE lead=%s AND creation>=%s
    """, (customer, sixty_ago))[0][0]
    if activity_60 > 0: return 60

    activity_90 = frappe.db.sql("""
        SELECT COUNT(*) FROM `tabCRM Call Log`
        WHERE lead=%s AND creation>=%s
    """, (customer, ninety_ago))[0][0]
    if activity_90 > 0: return 40

    return 0


def _kyc_score_calc(customer):
    expiry = frappe.db.get_value("Customer", customer, "kyc_expiry_date")
    if not expiry: return 0
    expiry = getdate(expiry)
    today  = getdate(nowdate())
    days_left = date_diff(expiry, today)
    if days_left > 30:  return 100
    if days_left > 0:   return 60
    if days_left > -30: return 20
    return 0


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _get_permitted_customer(customer):
    doc = frappe.get_doc("Customer", customer)
    doc.check_permission("read")
    return doc

def _kyc_status(kyc_expiry_date):
    if not kyc_expiry_date:
        return "Expired", "Never set"
    expiry = getdate(kyc_expiry_date)
    today  = getdate(nowdate())
    days   = date_diff(expiry, today)
    display = expiry.strftime("%d-%b-%Y")
    if days > 30:  return "Valid", display
    if days >= 0:  return "Expiring Soon", display
    return "Expired", display


def _get_salesperson(customer):
    sp = frappe.db.sql("""
        SELECT sales_person FROM `tabSales Team`
        WHERE parent=%s AND parenttype='Customer'
        LIMIT 1
    """, customer)
    return sp[0][0] if sp else "—"


def _lakh(val):
    val = flt(val)
    if val >= 10000000: return f"{val/10000000:.2f} Cr"
    if val >= 100000:   return f"{val/100000:.1f} L"
    return f"{val:,.0f}"


def _quarter_start(d):
    month = d.month
    if month <= 3:   qm = 1
    elif month <= 6: qm = 4
    elif month <= 9: qm = 7
    else:            qm = 10
    return getdate(f"{d.year}-{qm:02d}-01")
