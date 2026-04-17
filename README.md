## Customer Verification App

Streamlit-based customer verification data collection form that writes submissions into a Databricks SQL warehouse. The form is designed to mimic an SAP-style “Customer Request Form” and is suitable for public-facing deployment (e.g. Azure App Service, Streamlit Community Cloud).

---

## Project Structure

- `app.py` – Main Streamlit application
- `requirements.txt` – Python dependencies
- `.env` – Environment variables for Databricks and schema (not for source control)
- `README.md` – Setup and deployment instructions

---

## Prerequisites

- Python 3.10 or later
- A Databricks workspace with:
  - A SQL Warehouse
  - Existing tables:
    - `{CATALOG}.{SCHEMA}.customer_requests`
    - `{CATALOG}.{SCHEMA}.bank_details`
- A Databricks Personal Access Token (PAT) with permission to insert into the above tables.

---

## Local Development

1. **Clone or download the project**

   Place the project in a folder, for example:

   ```text
   customer-verification-app/
   ```

2. **Create and activate a virtual environment (recommended)**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # macOS / Linux
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file in the project root (or edit the existing template) with the following keys:

   ```env
   DATABRICKS_SERVER_HOSTNAME=adb-2391512199535380.0.azuredatabricks.net
   DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/dea5497f16b23613
   DATABRICKS_TOKEN=<your-pat-token>
   CATALOG=dbw_adh_dev_01
   SCHEMA=customer_verification
   ```

   - Replace `<your-pat-token>` with your Databricks Personal Access Token.
   - Ensure `CATALOG` and `SCHEMA` match where your `customer_requests` and `bank_details` tables exist.

5. **Run the app locally**

   ```bash
   streamlit run app.py
   ```

   The app will start at `http://localhost:8501` by default.

---

## Azure App Service Deployment

You can deploy this app to Azure App Service using a Linux web app and the Streamlit CLI.

### 1. Prepare a Git repository

1. Initialize a git repository (if not already):

   ```bash
   git init
   git add .
   git commit -m "Initial commit - customer verification app"
   ```

2. Push to a remote repository (e.g. GitHub, Azure Repos) if desired.

### 2. Create an Azure App Service (Linux, Python)

1. In the Azure Portal, create a new **Web App**:
   - **Publish**: Code
   - **Runtime stack**: Python 3.x (Linux)
   - **Region**: Choose your preferred region

2. Complete the wizard and let Azure provision the resource.

### 3. Configure Deployment

You can use any of:

- GitHub Actions
- Azure DevOps
- Local Git/VS Code deployment

Ensure your project files (`app.py`, `requirements.txt`, etc.) are deployed to the App Service.

### 4. Set the Startup Command

In the **Configuration → General settings** of your Web App, set the **Startup Command** to:

```bash
python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0 --server.headless true
```

Azure will then start Streamlit on port `8000`, listening on all interfaces.

### 5. Configure Environment Variables in Azure

In **Configuration → Application settings**, add the following settings (App Settings / environment variables):

- `DATABRICKS_SERVER_HOSTNAME`
- `DATABRICKS_HTTP_PATH`
- `DATABRICKS_TOKEN`
- `CATALOG`
- `SCHEMA`

Use the same values you used in your local `.env` file. Do **not** commit your `.env` file or secrets to source control.

### 6. Restart the App and Test

1. Restart the App Service after changing configuration.
2. Browse to the Web App URL (e.g. `https://<your-app-name>.azurewebsites.net`).
3. Fill in the customer verification form and submit.

If everything is configured correctly, the submission will be written to the Databricks tables and you’ll see a success message with the Request ID.

---

## Streamlit Community Cloud (Alternative Deployment)

As an alternative to Azure App Service:

1. Push your repository to GitHub.
2. Go to Streamlit Community Cloud and create a new app pointing to your repo and `app.py`.
3. In the app’s **Secrets** section, add:

   ```toml
   DATABRICKS_SERVER_HOSTNAME="..."
   DATABRICKS_HTTP_PATH="..."
   DATABRICKS_TOKEN="..."
   CATALOG="dbw_adh_dev_01"
   SCHEMA="customer_verification"
   ```

4. Deploy the app. Streamlit will install from `requirements.txt` and run `app.py`.

---

## Notes

- The app hides default Streamlit chrome (sidebar, toolbar, header, footer) and uses a centered, bordered form layout with SAP-style sectioning.
- All database credentials and configuration are read from environment variables; nothing is hard-coded in the source.
- The app validates all required fields and common formats (email, phone, IBAN, date consistency) before inserting into Databricks.
- If Databricks/API access is unavailable, use the built-in **Offline Demo Risk Assessment** section to run a Moody's-style provisional rating using dummy customer profiles.

