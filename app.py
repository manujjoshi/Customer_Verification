import os
import re
from datetime import date

import pandas as pd
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
        </style>
    """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)


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
                    except Exception:
                        st.error(
                            "We were unable to submit your request at this time. "
                            "Please try again later or contact support."
                        )

        st.markdown("</div>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()

