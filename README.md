# Customs Workflow Platform MVP

This is a simple Streamlit sample for a customs workflow platform.

## Core workflow

Customer uploads manifest → case is created → broker updates clearance status → OP tracks cases → billing updates fees.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## MVP Roles

### Customer Portal
- Upload manifest / invoice / packing list
- Create clearance case
- View submitted cases

### Broker Dashboard
- Receive assigned cases
- Update clearance status
- Add notes

### OP Dashboard
- Track all shipments
- Filter by status
- View exception cases

### Billing Dashboard
- Add broker fee, duty, MPF
- Update billing status
- Preview invoice

## Suggested GitHub structure

```text
customs_platform_streamlit_mvp/
├── app.py
├── requirements.txt
├── README.md
└── data/
    ├── cases.csv
    └── uploads/
```

## Next step ideas

- Add user login
- Add role-based permissions
- Use PostgreSQL instead of CSV
- Add AI OCR for uploaded manifests
- Add email notifications
- Add PDF invoice generation
- Add API for WMS/TMS integration
