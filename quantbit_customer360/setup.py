import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


CUSTOMER_FIELDS = [
	{"fieldname": "kyc_section", "fieldtype": "Section Break", "label": "KYC Details", "insert_after": "customer_details"},
	{"fieldname": "kyc_date", "fieldtype": "Date", "label": "KYC Date", "insert_after": "kyc_section"},
	{"fieldname": "kyc_expiry_date", "fieldtype": "Date", "label": "KYC Expiry Date", "read_only": 1, "insert_after": "kyc_date"},
	{"fieldname": "kyc_status", "fieldtype": "Select", "label": "KYC Status", "options": "Valid\nExpiring Soon\nExpired", "read_only": 1, "insert_after": "kyc_expiry_date"},
	{"fieldname": "kyc_documents", "fieldtype": "Attach", "label": "KYC Documents", "insert_after": "kyc_status"},
	{"fieldname": "kyc_approved_by", "fieldtype": "Link", "label": "KYC Approved By", "options": "User", "insert_after": "kyc_documents"},
	{"fieldname": "kyc_approval_date", "fieldtype": "Date", "label": "KYC Approval Date", "insert_after": "kyc_approved_by"},
	{"fieldname": "sales_config_section", "fieldtype": "Section Break", "label": "Sales Configuration", "insert_after": "kyc_approval_date"},
	{"fieldname": "customer_category", "fieldtype": "Select", "label": "Customer Category", "options": "Regular\nIrregular\nNot Factored\nUnknown", "insert_after": "sales_config_section"},
	{"fieldname": "sales_zone", "fieldtype": "Select", "label": "Sales Zone", "options": "North\nSouth\nEast\nWest", "insert_after": "customer_category"},
	{"fieldname": "quotation_format", "fieldtype": "Select", "label": "Quotation Format", "options": "Format 1\nFormat 2\nFormat 3\nFormat 4\nFormat 5\nFormat 6\nFormat 7\nFormat 8", "insert_after": "sales_zone"},
	{"fieldname": "dunning_stage", "fieldtype": "Select", "label": "Dunning Stage", "options": "Phase 1 - Salesperson\nPhase 2 - Direct Customer", "insert_after": "quotation_format"},
	{"fieldname": "credit_limit", "fieldtype": "Currency", "label": "Credit Limit", "insert_after": "dunning_stage"},
	{"fieldname": "strategic_section", "fieldtype": "Section Break", "label": "Strategic Profile", "insert_after": "credit_limit"},
	{"fieldname": "key_decision_maker", "fieldtype": "Data", "label": "Key Decision Maker", "insert_after": "strategic_section"},
	{"fieldname": "competitor_names", "fieldtype": "Small Text", "label": "Competitor Names", "insert_after": "key_decision_maker"},
	{"fieldname": "upsell_potential", "fieldtype": "Select", "label": "Upsell Potential", "options": "Low\nMedium\nHigh", "insert_after": "competitor_names"},
	{"fieldname": "strategic_account", "fieldtype": "Check", "label": "Strategic Account", "insert_after": "upsell_potential"},
	{"fieldname": "share_of_wallet", "fieldtype": "Float", "label": "Share of Wallet %", "insert_after": "strategic_account"},
	{"fieldname": "cheque_bounce_count", "fieldtype": "Int", "label": "Cheque Bounce Count", "insert_after": "share_of_wallet"},
	{"fieldname": "last_physical_visit", "fieldtype": "Date", "label": "Last Physical Visit", "insert_after": "cheque_bounce_count"},
	{"fieldname": "grade_section", "fieldtype": "Section Break", "label": "Customer Grade", "insert_after": "last_physical_visit"},
	{"fieldname": "customer_grade", "fieldtype": "Select", "label": "Grade", "options": "A\nB\nC\nD", "read_only": 1, "insert_after": "grade_section"},
	{"fieldname": "grade_score", "fieldtype": "Float", "label": "Score", "read_only": 1, "insert_after": "customer_grade"},
	{"fieldname": "payment_score", "fieldtype": "Float", "label": "Payment Score", "read_only": 1, "insert_after": "grade_score"},
	{"fieldname": "revenue_score", "fieldtype": "Float", "label": "Revenue Score", "read_only": 1, "insert_after": "payment_score"},
	{"fieldname": "regularity_score", "fieldtype": "Float", "label": "Regularity Score", "read_only": 1, "insert_after": "revenue_score"},
	{"fieldname": "engagement_score", "fieldtype": "Float", "label": "Engagement Score", "read_only": 1, "insert_after": "regularity_score"},
	{"fieldname": "kyc_score", "fieldtype": "Float", "label": "KYC Score", "read_only": 1, "insert_after": "engagement_score"},
	{"fieldname": "grade_last_updated", "fieldtype": "Date", "label": "Grade Updated", "read_only": 1, "insert_after": "kyc_score"},
]


def install_customer_fields():
	create_custom_fields({"Customer": CUSTOMER_FIELDS}, update=True)
	frappe.clear_cache(doctype="Customer")
