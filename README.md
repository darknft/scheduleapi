#Scheduling API

Simulates a legacy Electronic Health Record / Scheduling system for the
Salesforce Healthcare Patient schedule project. MuleSoft integrates with
this API the same way it would integrate with a real EHR like Epic or Cerner.

## Data model correspondence with Salesforce

| Mock EHR field   | Salesforce field                          |
|-------------------|--------------------------------------------|
| `npi`              | `Provider__c.NPI_Number__c`                |
| `mrn`              | `Patient__c.MRN__c`                        |
| `external_appointment_id` | `Appointment__c.External_Appointment_Id__c` |

Keeping these aligned is what makes the MuleSoft matching/sync logic realistic.

## 1. How to run locally

```bash
# from inside the mock-ehr-api folder
pip install -r requirements.txt
uvicorn main:app --reload
```

Then open:
- **http://127.0.0.1:8000/docs** — interactive Swagger UI (test every endpoint from the browser)
- **http://127.0.0.1:8000/redoc** — alternative documentation view

## 2. Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/` | Health check |
| GET | `/providers` | List all providers |
| GET | `/providers/{npi}/availability` | Get open appointment slots for a provider |
| GET | `/patients/{mrn}` | Get patient demographics |
| GET | `/patients/{mrn}/history` | Get patient visit history |
| POST | `/appointments` | Book a new appointment |
| GET | `/appointments/{id}` | Look up an appointment |
| DELETE | `/appointments/{id}` | Cancel an appointment (frees the slot) |

## 3. Seed data included

- **3 providers**: Dr. Sarah Chen (Primary Care), Dr. James Okafor (Cardiology), Dr. Maria Lopez (Pediatrics)
- **2 patients**: Amanda Perez (MRN-00001), Carlos Ramirez (MRN-00002)
- **7 days of availability** per provider, 9am–4pm in 30-minute slots (regenerates fresh each time you restart the server)


## 4. Example: booking flow (what MuleSoft/Agentforce Voice will do)

```bash
# 1. Check availability
curl "http://127.0.0.1:8000/providers/1234567890/availability"

# 2. Book the first open slot
curl -X POST "http://127.0.0.1:8000/appointments" \
  -H "Content-Type: application/json" \
  -d '{
    "patient_mrn": "MRN-00001",
    "provider_npi": "1234567890",
    "appointment_datetime": "2026-08-13T09:00:00",
    "reason": "Annual checkup",
    "appointment_type": "Annual Wellness"
  }'
```
