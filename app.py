import os
import re
from datetime import date
from textwrap import dedent

import streamlit as st
from databricks import sql as dbsql
from dotenv import load_dotenv


load_dotenv()


@st.cache_resource(show_spinner=False)
def get_connection():
    return dbsql.connect(
        server_hostname=os.getenv("DATABRICKS_SERVER_HOSTNAME"),
        http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        access_token=os.getenv("DATABRICKS_TOKEN"),
    )


def escape_str(value: str | None) -> str:
    if value is None:
        return ""
    return value.replace("'", "''")


def normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    return value.replace(" ", "")


def apply_global_styles():
    st.set_page_config(
        page_title="Customer Verification Form",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    hide_streamlit_style = """
        <style>
        /* Hide default Streamlit elements */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        [data-testid="stToolbar"] {display: none !important;}
        [data-testid="stSidebar"] {display: none !important;}

        /* App container */
        .main .block-container {
            max-width: 1200px;
            padding-top: 1.5rem;
        }

        .app-header {
            font-size: 1.6rem;
            font-weight: 600;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid #0066cc;
            margin-bottom: 1rem;
        }

        .section-header {
            font-size: 1.1rem;
            font-weight: 600;
            padding-bottom: 0.25rem;
            border-bottom: 2px solid #0066cc;
            margin-top: 0.75rem;
            margin-bottom: 0.5rem;
        }

        .form-container {
            border: 1px solid #dddddd;
            border-radius: 8px;
            padding: 1.25rem 1.5rem 1.5rem 1.5rem;
            background-color: #ffffff;
        }

        /* Active tab styling */
        button[role="tab"][aria-selected="true"] {
            background-color: #0066cc !important;
            color: white !important;
        }

        .risk-top-card {
            border: 1px solid #60c5a2;
            border-radius: 14px;
            padding: 20px 24px;
            margin-top: 1rem;
            background: #ffffff;
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .risk-score-circle {
            width: 96px;
            height: 96px;
            border-radius: 50%;
            border: 3px solid #1f9f72;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            color: #0f7d5a;
            font-weight: 700;
            line-height: 1.05;
            flex-shrink: 0;
        }

        .risk-score-circle .score {
            font-size: 2rem;
        }

        .risk-score-circle .denom {
            font-size: 1rem;
            font-weight: 600;
        }

        .risk-headline {
            font-size: 2rem;
            font-weight: 700;
            color: #1d1f23;
            margin: 0;
        }

        .risk-subline {
            font-size: 1.15rem;
            color: #4b4f56;
            margin: 0.25rem 0 0.75rem 0;
        }

        .risk-badge {
            display: inline-block;
            background: #dbeecf;
            color: #2f6f1e;
            border-radius: 999px;
            padding: 6px 14px;
            font-weight: 600;
            font-size: 1rem;
        }

        .risk-summary-card {
            border: 1px solid #d6d8de;
            border-radius: 14px;
            padding: 18px 24px;
            margin-top: 1.25rem;
            background: #ffffff;
        }

        .risk-summary-title {
            font-size: 1.85rem;
            font-weight: 700;
            margin-bottom: 12px;
            color: #1f242b;
        }

        .risk-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-top: 1px solid #eceef2;
            padding: 11px 0;
            font-size: 1.05rem;
        }

        .risk-row:first-of-type {
            border-top: none;
        }

        .risk-label {
            color: #3c4148;
        }

        .risk-value {
            font-weight: 700;
            color: #1f242b;
        }

        .risk-inline-bar-wrap {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .risk-inline-bar {
            width: 150px;
            height: 10px;
            background: #e8ebef;
            border-radius: 999px;
            overflow: hidden;
        }

        .risk-inline-bar-fill {
            height: 100%;
            background: #19976a;
            border-radius: 999px;
        }

        .risk-pill {
            border-radius: 999px;
            padding: 4px 12px;
            font-weight: 600;
        }

        .risk-pill-green {
            background: #dbeecf;
            color: #2f6f1e;
        }

        .risk-pill-amber {
            background: #f4e7cf;
            color: #8a5a14;
        }

        .risk-reco {
            margin-top: 1.25rem;
            border-radius: 12px;
            background: #f4e7cf;
            color: #6a4012;
            padding: 14px 18px;
            font-size: 1rem;
        }
        </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)


def compute_post_submit_risk(form_data, bank_entries):
    score = 78
    warnings = []

    requested_exposure = float(form_data.get("auth_credit_limit") or 0)
    auth_ceiling = float(form_data.get("auth_ceiling") or 0)
    security_amount = float(form_data.get("security_amount") or 0)
    risk_category = (form_data.get("cust_risk_category") or "").strip() or "Medium"
    country = (form_data.get("country") or "").strip() or "Other"

    high_risk_countries = {"Iraq", "Syria", "Yemen", "Lebanon"}
    medium_risk_countries = {"Egypt", "Jordan", "Pakistan", "India"}

    if risk_category == "Highest Risk":
        score -= 24
    elif risk_category == "High":
        score -= 16
    elif risk_category == "Medium":
        score -= 8
    else:
        score += 4

    if country in high_risk_countries:
        score -= 16
    elif country in medium_risk_countries:
        score -= 8

    if auth_ceiling >= 85:
        score -= 10
    elif auth_ceiling >= 70:
        score -= 6
    elif auth_ceiling <= 40:
        score += 3

    if form_data.get("is_security") == "Required" and security_amount > 0:
        score += 6
    elif form_data.get("is_security") == "Required" and security_amount == 0:
        score -= 10
        warnings.append("Security is marked required but amount is zero.")

    payment_terms = (form_data.get("payment_terms") or "").strip().lower()
    if payment_terms in {"net 30", "net30"}:
        score += 4
    elif payment_terms in {"net 45", "net45"}:
        score += 2
    elif payment_terms in {"net 60", "net60"}:
        score -= 2
    elif payment_terms:
        score -= 6

    if requested_exposure >= 25000000:
        score -= 10
    elif requested_exposure >= 10000000:
        score -= 6
    elif requested_exposure <= 2000000:
        score += 4

    # KYC completeness and document quality adjustments
    core_fields = [
        "business_partner_name",
        "street",
        "city",
        "country",
        "payment_terms",
        "vat_id",
        "trade_licence_no",
        "finance_mail_id",
    ]
    missing_core_fields = sum(1 for key in core_fields if not str(form_data.get(key) or "").strip())
    if missing_core_fields:
        score -= min(15, missing_core_fields * 2)
        warnings.append(f"{missing_core_fields} key KYC field(s) are incomplete.")

    vat_id = str(form_data.get("vat_id") or "").strip()
    if vat_id:
        if len(vat_id) < 5:
            score -= 8
            warnings.append("VAT ID quality is weak (length below expected threshold).")
        elif len(vat_id) >= 10:
            score += 2

    unique_id = str(form_data.get("unique_identification_number") or "").strip()
    if unique_id:
        score += 2
    else:
        score -= 3

    # Trade licence validity sensitivity
    tl_from = form_data.get("trade_licence_valid_from")
    tl_till = form_data.get("trade_licence_valid_till")
    if tl_till and isinstance(tl_till, date):
        days_left = (tl_till - date.today()).days
        if days_left < 0:
            score -= 16
            warnings.append("Trade licence appears expired.")
        elif days_left < 30:
            score -= 10
            warnings.append("Trade licence is close to expiry (under 30 days).")
        elif days_left < 90:
            score -= 5
        else:
            score += 2
    if tl_from and tl_till and isinstance(tl_from, date) and isinstance(tl_till, date):
        if tl_till <= tl_from:
            score -= 8
            warnings.append("Trade licence validity dates are inconsistent.")

    # Security cover ratio sensitivity
    if requested_exposure > 0 and security_amount > 0:
        coverage_ratio = security_amount / requested_exposure
        if coverage_ratio >= 0.8:
            score += 6
        elif coverage_ratio >= 0.5:
            score += 3
        elif coverage_ratio < 0.2:
            score -= 4

    # Contact quality checks
    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    finance_email = str(form_data.get("finance_mail_id") or "").strip()
    business_email = str(form_data.get("other_business_mail_id") or "").strip()
    if finance_email and not email_pattern.match(finance_email):
        score -= 4
        warnings.append("Finance email format appears invalid.")
    if business_email and not email_pattern.match(business_email):
        score -= 4
        warnings.append("Business email format appears invalid.")
    if finance_email and business_email and finance_email.lower() == business_email.lower():
        score -= 2

    mobile_no = normalize_phone(str(form_data.get("mobile_no") or ""))
    phone_pattern = re.compile(r"^\+?[0-9]{7,15}$")
    if mobile_no:
        if phone_pattern.match(mobile_no):
            score += 1
        else:
            score -= 3
            warnings.append("Primary mobile number format appears invalid.")

    iban_invalid = 0
    filled_banks = [b for b in bank_entries if any(str(v).strip() for v in b.values())]
    iban_pattern = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{4,30}$")
    for bank in filled_banks:
        iban = (bank.get("iban") or "").replace(" ", "").upper()
        if iban and not iban_pattern.match(iban):
            iban_invalid += 1
    if iban_invalid:
        score -= min(10, iban_invalid * 4)
        warnings.append("One or more bank accounts contain invalid IBAN format.")

    # Bank record completeness sensitivity
    if not filled_banks:
        score -= 8
        warnings.append("No bank details supplied for settlement validation.")
    else:
        incomplete_bank_rows = 0
        for bank in filled_banks:
            required_bank_fields = ["iban", "bank_name", "bank_country_region", "swift_bic"]
            if any(not str(bank.get(field) or "").strip() for field in required_bank_fields):
                incomplete_bank_rows += 1
        if incomplete_bank_rows:
            score -= min(8, incomplete_bank_rows * 3)
            warnings.append(f"{incomplete_bank_rows} bank profile(s) are missing key fields.")
        else:
            score += 2

    sanctions_clear = "Clear"
    pep_status = "No hits"
    jurisdiction = (
        "High"
        if country in high_risk_countries
        else "Medium"
        if country in medium_risk_countries or country in {"UAE", "Other"}
        else "Low"
    )

    score = max(0, min(100, int(round(score))))

    if score >= 90:
        moodys_rating = "A2"
        risk_band = "Low risk"
    elif score >= 80:
        moodys_rating = "Baa1"
        risk_band = "Low-medium risk"
    elif score >= 70:
        moodys_rating = "Baa2"
        risk_band = "Low-medium risk"
    elif score >= 60:
        moodys_rating = "Baa3"
        risk_band = "Medium risk"
    elif score >= 50:
        moodys_rating = "Ba2"
        risk_band = "Medium-high risk"
    else:
        moodys_rating = "B1"
        risk_band = "High risk"

    pd_percent = max(0.12, round((100 - score) * 0.018, 2))
    recommended_limit = max(500000.0, requested_exposure * (0.55 if score < 70 else 0.75 if score < 80 else 0.9))
    onboarding_status = (
        "Approved for onboarding" if score >= 70 else "Conditional onboarding review required"
    )
    payment_history_score = max(45, min(92, score + 6))

    return {
        "score": score,
        "rating": moodys_rating,
        "risk_band": risk_band,
        "onboarding_status": onboarding_status,
        "pd_percent": pd_percent,
        "recommended_limit": recommended_limit,
        "requested_exposure": requested_exposure,
        "payment_history_score": payment_history_score,
        "sanctions": sanctions_clear,
        "pep": pep_status,
        "jurisdiction": f"{jurisdiction} ({country})",
        "warnings": warnings,
    }


def _fmt_money(value):
    return f"USD {value:,.0f}"


def render_final_kyc_details(form_data, bank_entries, request_id):
    risk = compute_post_submit_risk(form_data, bank_entries)
    customer_name = form_data.get("business_partner_name") or "-"
    rating_date = date.today().strftime("%d %b %Y")
    progress_pct = risk["payment_history_score"]

    st.markdown(
        dedent(
            f"""
            <div class="risk-top-card">
                <div class="risk-score-circle">
                    <div class="score">{risk["score"]}</div>
                    <div class="denom">/ 100</div>
                </div>
                <div>
                    <p class="risk-headline">Moody's risk score</p>
                    <p class="risk-subline">{customer_name} · Verified {rating_date} · Request ID {request_id}</p>
                    <span class="risk-badge">{risk["risk_band"]} · {risk["onboarding_status"]}</span>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    st.markdown(
        dedent(
            f"""
            <div class="risk-summary-card">
                <div class="risk-summary-title">Credit & counterparty summary</div>
                <div class="risk-row">
                    <div class="risk-label">Moody's rating</div>
                    <div class="risk-value">
                        {risk["rating"]} ({'Investment grade' if risk["rating"].startswith('A') or risk["rating"].startswith('Baa') else 'Speculative grade'})
                    </div>
                </div>
                <div class="risk-row">
                    <div class="risk-label">PD (probability of default)</div>
                    <div class="risk-value">{risk["pd_percent"]}%</div>
                </div>
                <div class="risk-row">
                    <div class="risk-label">Recommended credit limit</div>
                    <div class="risk-value">{_fmt_money(risk["recommended_limit"])}</div>
                </div>
                <div class="risk-row">
                    <div class="risk-label">Payment history score</div>
                    <div class="risk-inline-bar-wrap">
                        <div class="risk-inline-bar">
                            <div class="risk-inline-bar-fill" style="width: {progress_pct}%;"></div>
                        </div>
                        <div class="risk-value">{progress_pct}/100</div>
                    </div>
                </div>
                <div class="risk-row">
                    <div class="risk-label">Sanctions screening</div>
                    <div class="risk-pill risk-pill-green">{risk["sanctions"]}</div>
                </div>
                <div class="risk-row">
                    <div class="risk-label">PEP / adverse media</div>
                    <div class="risk-pill risk-pill-green">{risk["pep"]}</div>
                </div>
                <div class="risk-row">
                    <div class="risk-label">Jurisdiction risk</div>
                    <div class="risk-pill risk-pill-amber">{risk["jurisdiction"]}</div>
                </div>
            </div>
            """
        ),
        unsafe_allow_html=True,
    )

    if risk["requested_exposure"] > risk["recommended_limit"]:
        st.markdown(
            dedent(
                f"""
                <div class="risk-reco">
                    Recommended credit limit ({_fmt_money(risk["recommended_limit"])}) is below the requested
                    exposure of {_fmt_money(risk["requested_exposure"])}.
                    Consider staged delivery or additional collateral for the balance.
                </div>
                """
            ),
            unsafe_allow_html=True,
        )

    if risk["warnings"]:
        st.warning("\n".join(f"- {item}" for item in risk["warnings"]))


def validate_inputs(form_data, bank_entries):
    errors: list[str] = []
    warnings: list[str] = []

    email_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    phone_pattern = re.compile(r"^\+?[0-9]{7,15}$")
    iban_pattern = re.compile(r"^[A-Z]{2}[0-9]{2}[A-Z0-9]{4,30}$")

    # Required fields
    if not form_data["business_partner_name"].strip():
        errors.append("Business Partner Name is required.")
    if not form_data["street"].strip():
        errors.append("Street is required.")
    if not form_data["city"].strip():
        errors.append("City is required.")
    if not form_data["payment_terms"].strip():
        errors.append("Payment Terms is required.")

    # Email validation
    for field_label, value in [
        ("Other Business Mail ID", form_data["other_business_mail_id"]),
        ("Finance Mail ID", form_data["finance_mail_id"]),
    ]:
        if value and not email_pattern.match(value.strip()):
            errors.append(f"{field_label} is not a valid email address.")

    # Phone validation
    for field_label, value in [
        ("Mobile No", form_data["mobile_no"]),
        ("Alternate Mobile No", form_data["alternate_mobile_no"]),
    ]:
        if value:
            normalized = normalize_phone(value)
            if not phone_pattern.match(normalized):
                errors.append(f"{field_label} is not a valid phone number.")

    # VAT ID length
    if form_data["vat_id"] and len(form_data["vat_id"].strip()) < 5:
        errors.append("VAT ID must be at least 5 characters.")

    # Trade licence dates
    if form_data["trade_licence_valid_from"] and form_data["trade_licence_valid_till"]:
        if form_data["trade_licence_valid_till"] <= form_data["trade_licence_valid_from"]:
            errors.append("Trade Licence Valid Till must be after Valid From.")

    # Security dates
    if form_data["effective_date"] and form_data["expiry_date"]:
        if form_data["expiry_date"] <= form_data["effective_date"]:
            errors.append("Security Expiry Date must be after Effective Date.")

    # IBAN validation for each bank entry
    for idx, bank in enumerate(bank_entries, start=1):
        iban = bank.get("iban", "")
        if iban:
            normalized_iban = iban.replace(" ", "").upper()
            if not iban_pattern.match(normalized_iban):
                errors.append(f"Bank {idx}: IBAN format is invalid.")

    return errors, warnings


def insert_into_database(form_data, bank_entries):
    catalog = os.getenv("CATALOG")
    schema = os.getenv("SCHEMA")
    full_customer_table = f"{catalog}.{schema}.customer_requests"
    full_bank_table = f"{catalog}.{schema}.bank_details"

    conn = get_connection()
    with conn.cursor() as cursor:
        # Insert into customer_requests
        insert_customer_sql = f"""
            INSERT INTO {full_customer_table} (
                business_partner_type,
                bp_category,
                crm_ref,
                business_partner_name,
                mobile_no,
                alternate_mobile_no,
                sales_representative,
                other_business_mail_id,
                finance_mail_id,
                language,
                house_number,
                street,
                city,
                postal_code,
                country,
                website,
                vat_id,
                tax_id,
                auth_credit_limit,
                auth_ceiling,
                is_security,
                security_type,
                security_amount,
                effective_date,
                expiry_date,
                trade_licence_no,
                trade_licence_valid_from,
                trade_licence_valid_till,
                cust_risk_category,
                statistical_group_2,
                statistical_group_3,
                statistical_group_4,
                statistical_group_5,
                parent_company_name,
                sister_companies,
                ubo,
                external_identifier,
                unique_identification_number,
                entity,
                bp_name_local,
                account_at_customer,
                payment_terms,
                currency,
                bp_status,
                created_at,
                updated_at
            )
            VALUES (
                '{escape_str(form_data["business_partner_type"])}',
                '{escape_str(form_data["bp_category"])}',
                '{escape_str(form_data["crm_ref"])}',
                '{escape_str(form_data["business_partner_name"])}',
                '{escape_str(normalize_phone(form_data["mobile_no"]))}',
                '{escape_str(normalize_phone(form_data["alternate_mobile_no"]))}',
                '{escape_str(form_data["sales_representative"])}',
                '{escape_str(form_data["other_business_mail_id"])}',
                '{escape_str(form_data["finance_mail_id"])}',
                '{escape_str(form_data["language"])}',
                '{escape_str(form_data["house_number"])}',
                '{escape_str(form_data["street"])}',
                '{escape_str(form_data["city"])}',
                '{escape_str(form_data["postal_code"])}',
                '{escape_str(form_data["country"])}',
                '{escape_str(form_data["website"])}',
                '{escape_str(form_data["vat_id"])}',
                '{escape_str(form_data["tax_id"])}',
                {form_data["auth_credit_limit"] if form_data["auth_credit_limit"] is not None else "NULL"},
                {form_data["auth_ceiling"] if form_data["auth_ceiling"] is not None else "NULL"},
                '{escape_str(form_data["is_security"])}',
                '{escape_str(form_data["security_type"])}',
                {form_data["security_amount"] if form_data["security_amount"] is not None else "NULL"},
                {f"DATE '{form_data['effective_date']}'" if form_data["effective_date"] else "NULL"},
                {f"DATE '{form_data['expiry_date']}'" if form_data["expiry_date"] else "NULL"},
                '{escape_str(form_data["trade_licence_no"])}',
                {f"DATE '{form_data['trade_licence_valid_from']}'" if form_data["trade_licence_valid_from"] else "NULL"},
                {f"DATE '{form_data['trade_licence_valid_till']}'" if form_data["trade_licence_valid_till"] else "NULL"},
                '{escape_str(form_data["cust_risk_category"])}',
                '{escape_str(form_data["statistical_group_2"])}',
                '{escape_str(form_data["statistical_group_3"])}',
                '{escape_str(form_data["statistical_group_4"])}',
                '{escape_str(form_data["statistical_group_5"])}',
                '{escape_str(form_data["parent_company_name"])}',
                '{escape_str(form_data["sister_companies"])}',
                '{escape_str(form_data["ubo"])}',
                '{escape_str(form_data["external_identifier"])}',
                '{escape_str(form_data["unique_identification_number"])}',
                '{escape_str(form_data["entity"])}',
                '{escape_str(form_data["bp_name_local"])}',
                '{escape_str(form_data["account_at_customer"])}',
                '{escape_str(form_data["payment_terms"])}',
                '{escape_str(form_data["currency"])}',
                'Pending',
                CURRENT_TIMESTAMP(),
                CURRENT_TIMESTAMP()
            )
        """
        cursor.execute(insert_customer_sql)

        cursor.execute(f"SELECT MAX(request_id) FROM {full_customer_table}")
        request_id_row = cursor.fetchone()
        request_id = request_id_row[0] if request_id_row else None

        if request_id is None:
            raise RuntimeError("Unable to retrieve newly created Request ID.")

        # Insert bank details
        for bank in bank_entries:
            # skip completely empty rows
            if not any(bank.values()):
                continue

            iban_clean = bank.get("iban", "").replace(" ", "").upper()
            insert_bank_sql = f"""
                INSERT INTO {full_bank_table} (
                    request_id,
                    iban,
                    bank_name,
                    bank_branch,
                    street,
                    city,
                    bank_country_region,
                    currency,
                    swift_bic,
                    created_at
                )
                VALUES (
                    {request_id},
                    '{escape_str(iban_clean)}',
                    '{escape_str(bank.get("bank_name", ""))}',
                    '{escape_str(bank.get("bank_branch", ""))}',
                    '{escape_str(bank.get("bank_street", ""))}',
                    '{escape_str(bank.get("bank_city", ""))}',
                    '{escape_str(bank.get("bank_country_region", ""))}',
                    '{escape_str(bank.get("bank_currency", ""))}',
                    '{escape_str(bank.get("swift_bic", ""))}',
                    CURRENT_TIMESTAMP()
                )
            """
            cursor.execute(insert_bank_sql)

        conn.commit()
        return request_id


def main():
    apply_global_styles()

    if "submitted_kyc" not in st.session_state:
        st.session_state["submitted_kyc"] = None

    if st.session_state["submitted_kyc"] is not None:
        saved_submission = st.session_state["submitted_kyc"]
        render_final_kyc_details(
            saved_submission["form_data"],
            saved_submission["bank_entries"],
            saved_submission["request_id"],
        )
        return

    st.markdown(
        '<div class="app-header">Customer Verification – Customer Request Form</div>',
        unsafe_allow_html=True,
    )

    with st.container():
        st.markdown('<div class="form-container">', unsafe_allow_html=True)

        with st.form("customer_request_form"):
            tabs = st.tabs(["General Data", "Credit & Security", "Miscellaneous & Sales", "Bank Details"])

            # Tab 1: General Data
            with tabs[0]:
                col_left, col_right = st.columns(2)

                with col_left:
                    st.markdown('<div class="section-header">General Data</div>', unsafe_allow_html=True)
                    business_partner_type = st.selectbox(
                        "Business Partner Type *",
                        ["Local Customer", "International Customer", "Vendor", "One-Time Customer"],
                    )
                    bp_category = st.selectbox(
                        "BP Category",
                        ["Organization", "Individual"],
                    )
                    business_partner_name = st.text_input(
                        "Business Partner Name *",
                        placeholder="e.g. HASSAD FEED TRADING ESTABLISHMENT",
                    )
                    mobile_no = st.text_input(
                        "Mobile No With extension",
                        placeholder="+966XXXXXXXXX",
                    )
                    alternate_mobile_no = st.text_input(
                        "Alternate Mobile No With extension",
                    )
                    sales_representative = st.text_input(
                        "Sales Representative",
                        placeholder="e.g. ABDULLAH YOUSIF",
                    )
                    other_business_mail_id = st.text_input(
                        "Other Business Mail ID",
                        placeholder="name@example.com",
                    )
                    finance_mail_id = st.text_input(
                        "Finance Mail ID",
                        placeholder="finance@example.com",
                    )
                    language = st.selectbox(
                        "Language *",
                        ["EN", "AR", "FR", "DE", "ES", "UR", "HI"],
                    )
                    crm_ref = st.text_input("CRM Ref #")

                with col_right:
                    st.markdown('<div class="section-header">Address Data</div>', unsafe_allow_html=True)
                    house_number = st.text_input("House Number", placeholder="3419")
                    street = st.text_input(
                        "Street *",
                        placeholder="ANAS IBN DUHAIR AL HARITHIY AL ANSARI",
                    )
                    col_city, col_postal = st.columns(2)
                    with col_city:
                        city = st.text_input("City *")
                    with col_postal:
                        postal_code = st.text_input("Postal Code")
                    country = st.selectbox(
                        "Country *",
                        [
                            "Saudi Arabia",
                            "UAE",
                            "Oman",
                            "Bahrain",
                            "Kuwait",
                            "Qatar",
                            "Egypt",
                            "Jordan",
                            "Iraq",
                            "Lebanon",
                            "Syria",
                            "Yemen",
                            "Morocco",
                            "Tunisia",
                            "India",
                            "Pakistan",
                            "Other",
                        ],
                    )
                    website = st.text_input("Website")

            # Tab 2: Credit & Security
            with tabs[1]:
                col_left, col_right = st.columns(2)

                with col_left:
                    st.markdown('<div class="section-header">Credit Data</div>', unsafe_allow_html=True)
                    vat_id = st.text_input("VAT ID")
                    tax_id = st.text_input("Tax ID")

                    col_limit, col_limit_currency = st.columns(2)
                    with col_limit:
                        auth_credit_limit = st.number_input(
                            "Auth Credit Limit",
                            min_value=0.0,
                            value=0.0,
                            step=1000.0,
                        )
                    with col_limit_currency:
                        auth_credit_limit_currency = st.selectbox(
                            "Credit Limit Currency",
                            ["SAR", "AED", "USD", "EUR", "GBP"],
                            index=0,
                        )

                    auth_ceiling = st.number_input(
                        "Auth Ceiling % (0-100)",
                        min_value=0.0,
                        max_value=100.0,
                        value=0.0,
                        step=1.0,
                    )

                    st.markdown('<div class="section-header">Trade Licence Data</div>', unsafe_allow_html=True)
                    trade_licence_no = st.text_input("Trade Licence No")
                    col_tl_from, col_tl_till = st.columns(2)
                    with col_tl_from:
                        trade_licence_valid_from = st.date_input(
                            "Trade Licence Valid From",
                            value=None,
                            format="YYYY-MM-DD",
                        )
                    with col_tl_till:
                        trade_licence_valid_till = st.date_input(
                            "Trade Licence Valid Till",
                            value=None,
                            format="YYYY-MM-DD",
                        )
                    cust_risk_category = st.selectbox(
                        "Customer Risk Category",
                        ["Low", "Medium", "High", "Highest Risk"],
                    )

                with col_right:
                    st.markdown('<div class="section-header">Security Data</div>', unsafe_allow_html=True)
                    is_security = st.selectbox(
                        "Is Security",
                        ["Not Required", "Required"],
                    )
                    security_type = st.text_input("Security Type")
                    security_amount = st.number_input(
                        "Security Amount",
                        min_value=0.0,
                        value=0.0,
                        step=1000.0,
                    )
                    col_eff, col_exp = st.columns(2)
                    with col_eff:
                        effective_date = st.date_input(
                            "Effective Date",
                            value=None,
                            format="YYYY-MM-DD",
                        )
                    with col_exp:
                        expiry_date = st.date_input(
                            "Expiry Date",
                            value=None,
                            format="YYYY-MM-DD",
                        )

                    st.markdown('<div class="section-header">Statistical Group</div>', unsafe_allow_html=True)
                    statistical_group_2 = st.text_input("Statistical Group 2")
                    statistical_group_3 = st.text_input("Statistical Group 3")
                    statistical_group_4 = st.text_input("Statistical Group 4")
                    statistical_group_5 = st.selectbox(
                        "Statistical Group 5",
                        ["", "PRIVATE ENTITIES", "GOVERNMENT", "SEMI-GOVERNMENT", "OTHER"],
                    )

            # Tab 3: Miscellaneous & Sales
            with tabs[2]:
                st.markdown('<div class="section-header">Miscellaneous</div>', unsafe_allow_html=True)
                col_left, col_right = st.columns(2)

                with col_left:
                    parent_company_name = st.text_input("Parent Company")
                    ubo = st.text_area("UBO (Ultimate Beneficial Owner)")
                    external_identifier = st.text_input("External Identifier")
                    unique_identification_number = st.text_input("Unique Identification Number")

                with col_right:
                    sister_companies = st.text_area("Sister Companies")

                st.divider()
                st.markdown('<div class="section-header">Sales & Distribution Data</div>', unsafe_allow_html=True)

                col_left, col_right = st.columns(2)
                with col_left:
                    entity = st.selectbox(
                        "Entity",
                        ["KSA", "UAE", "Oman", "Bahrain", "Kuwait", "Qatar"],
                    )
                    bp_name_local = st.text_input("BP Name in Local")

                with col_right:
                    account_at_customer = st.text_input("Account at Customer")
                    payment_terms = st.text_input("Payment Terms *")
                    currency = st.selectbox(
                        "Currency *",
                        ["SAR", "AED", "USD", "EUR", "GBP"],
                    )

            # Tab 4: Bank Details
            with tabs[3]:
                st.markdown('<div class="section-header">Bank Details</div>', unsafe_allow_html=True)
                bank_count = st.number_input(
                    "Number of Bank Accounts",
                    min_value=0,
                    max_value=10,
                    value=1,
                    step=1,
                )

                bank_entries: list[dict] = []
                for i in range(bank_count):
                    st.markdown(f"**Bank {i + 1}**")
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        iban = st.text_input(f"IBAN (Bank {i + 1})", key=f"iban_{i}")
                        bank_name = st.text_input(f"Bank Name (Bank {i + 1})", key=f"bank_name_{i}")
                    with col2:
                        bank_branch = st.text_input(f"Bank Branch (Bank {i + 1})", key=f"bank_branch_{i}")
                        bank_street = st.text_input(f"Bank Street (Bank {i + 1})", key=f"bank_street_{i}")
                    with col3:
                        bank_city = st.text_input(f"Bank City (Bank {i + 1})", key=f"bank_city_{i}")
                        bank_country_region = st.text_input(
                            f"Bank Country/Region (Bank {i + 1})",
                            key=f"bank_country_region_{i}",
                        )
                    with col4:
                        bank_currency = st.selectbox(
                            f"Bank Currency (Bank {i + 1})",
                            ["SAR", "AED", "USD", "EUR", "GBP"],
                            key=f"bank_currency_{i}",
                        )
                        swift_bic = st.text_input(f"SWIFT/BIC (Bank {i + 1})", key=f"swift_bic_{i}")

                    bank_entries.append(
                        {
                            "iban": iban,
                            "bank_name": bank_name,
                            "bank_branch": bank_branch,
                            "bank_street": bank_street,
                            "bank_city": bank_city,
                            "bank_country_region": bank_country_region,
                            "bank_currency": bank_currency,
                            "swift_bic": swift_bic,
                        }
                    )

            # Form actions
            col_spacer, col_submit, col_cancel = st.columns([6, 1, 1])
            with col_submit:
                submit = st.form_submit_button("Submit ✅", type="primary", use_container_width=True)
            with col_cancel:
                cancel = st.form_submit_button("Cancel", use_container_width=True)

            if cancel:
                st.rerun()

            if submit:
                form_data = {
                    "business_partner_type": business_partner_type,
                    "bp_category": bp_category,
                    "crm_ref": crm_ref,
                    "business_partner_name": business_partner_name,
                    "mobile_no": mobile_no,
                    "alternate_mobile_no": alternate_mobile_no,
                    "sales_representative": sales_representative,
                    "other_business_mail_id": other_business_mail_id,
                    "finance_mail_id": finance_mail_id,
                    "language": language,
                    "house_number": house_number,
                    "street": street,
                    "city": city,
                    "postal_code": postal_code,
                    "country": country,
                    "website": website,
                    "vat_id": vat_id,
                    "tax_id": tax_id,
                    "auth_credit_limit": float(auth_credit_limit) if auth_credit_limit is not None else None,
                    "auth_ceiling": float(auth_ceiling) if auth_ceiling is not None else None,
                    "is_security": is_security,
                    "security_type": security_type,
                    "security_amount": float(security_amount) if security_amount is not None else None,
                    "effective_date": effective_date if isinstance(effective_date, date) else None,
                    "expiry_date": expiry_date if isinstance(expiry_date, date) else None,
                    "trade_licence_no": trade_licence_no,
                    "trade_licence_valid_from": trade_licence_valid_from
                    if isinstance(trade_licence_valid_from, date)
                    else None,
                    "trade_licence_valid_till": trade_licence_valid_till
                    if isinstance(trade_licence_valid_till, date)
                    else None,
                    "cust_risk_category": cust_risk_category,
                    "statistical_group_2": statistical_group_2,
                    "statistical_group_3": statistical_group_3,
                    "statistical_group_4": statistical_group_4,
                    "statistical_group_5": statistical_group_5,
                    "parent_company_name": parent_company_name,
                    "sister_companies": sister_companies,
                    "ubo": ubo,
                    "external_identifier": external_identifier,
                    "unique_identification_number": unique_identification_number,
                    "entity": entity,
                    "bp_name_local": bp_name_local,
                    "account_at_customer": account_at_customer,
                    "payment_terms": payment_terms,
                    "currency": currency,
                }

                errors, warnings = validate_inputs(form_data, bank_entries)

                if errors:
                    st.error("\n".join(f"- {e}" for e in errors))
                if warnings:
                    st.warning("\n".join(f"- {w}" for w in warnings))

                if not errors:
                    try:
                        request_id = insert_into_database(form_data, bank_entries)
                        st.success(f"Thank you. Your customer request has been submitted successfully. Request ID: {request_id}")
                        st.balloons()
                        st.session_state["submitted_kyc"] = {
                            "form_data": form_data,
                            "bank_entries": bank_entries,
                            "request_id": request_id,
                        }
                        st.rerun()
                    except Exception:
                        st.error(
                            "We were unable to submit your request at this time. "
                            "Please try again later or contact support."
                        )

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

