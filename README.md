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

Demo sign-in. For these accounts the password is the same as the username:

- `admin` · Admin. Sees Cost, edits every column, and manages users
- `quality` · Quality
- `production` · Production
- `purchase` · Purchase
- `ppc` · PPC (production planning and control)
- `toolroom` · Tool room
- `engineering` · Engineering
- `npd` · NPD (new product development)
- `ipqc` · In process QC

Admin can add, update, and delete users from the Users page. A person belongs to one department, and that department decides which columns they can edit. Everyone can view every column except Cost, which only Admin can view or edit. Review and Deviation can be edited by every department. Only Admin can add or delete rows.

## Menu

- Dashboard
- Master table: edit, save, and download the workbook
- Users, for Admin: add a person, set their department, reset a password, or delete an account
- Rejection data: parts rejected inside the shop
- Customer wise: one view for each customer
- All open orders: completed status is not Completed
- All closed: completed orders
- RMA orders: customer rejected the part and it needs remanufacture

Aerospace orders are shaded light blue. The workbook columns are APM NO, PO date, PO number, part number, part photo, quantity, dispatch date, specification, risk, raw-material size and status, process, tooling, enquiry, program status, planning, machining status, review, deviation, customer, completed status, RMA status, aerospace, and cost. Rows saved before Cost existed are given a placeholder of quantity × 25, which Admin can change.

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

- The login is a demo: passwords are stored in `data/users.json` on the machine running the app, and the sample accounts above are created the first time the app starts. Use only dummy data on a public deployment.
- Workbook edits are written to the deployed container. Streamlit Cloud may restart that container, so saved changes are not durable. Download the edited workbook before leaving the app.
- A database and proper authentication are required before using real company or customer data.
