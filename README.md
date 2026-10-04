# Helix Precision

A local web app for a part machining order workbook. Sign in, review the dashboard, edit the master table, and open the order views from the left menu.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501.

Demo sign-in:

- Blank username and password, or planner: `admin` / `machining`
- Elevated user, who can set Completed Status: `lead` / `precision`

## Menu

- Dashboard
- Master table: edit, save, and download the workbook
- Rejection data: parts rejected inside the shop
- Customer wise: one view for each customer
- All open orders: completed status is not Completed
- All closed: completed orders
- RMA orders: customer rejected the part and it needs remanufacture

Aerospace orders are shaded light blue. The workbook columns are APM NO, PO date, PO number, part number, part photo, quantity, dispatch date, specification, risk, raw-material size and status, process, tooling, enquiry, program status, planning, machining status, review, deviation, customer, completed status, RMA status, and aerospace.

The sample file is `data/part_machining_orders.xlsx`. To replace it with a fresh sample:

```bash
python workbook.py --force
```

Close the workbook in Excel before saving from the app. The company name is a stand-in in `brand.py`.

## Deploy on Streamlit Community Cloud

This repository is ready to deploy from GitHub:

1. Create an empty GitHub repository. Do not add a README, `.gitignore`, or license on GitHub because those files already exist locally.
2. Push this local repository to GitHub using the commands shown by GitHub under **push an existing repository from the command line**.
3. Open [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
4. Select **Create app**, choose the repository and `main` branch, and set the entry point to `app.py`.
5. Deploy. Streamlit will provide a public `streamlit.app` URL.

No system packages or secrets are required for this demo deployment.

### Demo limitations

- The login is intentionally not secure: blank credentials work and the sample passwords are stored in source code. Use only dummy data on a public deployment.
- Workbook edits are written to the deployed container. Streamlit Cloud may restart that container, so saved changes are not durable. Download the edited workbook before leaving the app.
- A database and proper authentication are required before using real company or customer data.
