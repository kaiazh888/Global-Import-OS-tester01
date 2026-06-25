# Customs Workflow Platform MVP - Fixed Version

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Fixes in this version

- Submit Case now shows a clear success message
- Saves ETA as text instead of a raw date object
- Reloads the case table after submit
- Shows full error message if submit fails
- Handles empty or broken CSV more safely
