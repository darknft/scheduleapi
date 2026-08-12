"""
Mock EHR / Scheduling System API
----------------------------------
Simulates a legacy Electronic Health Record + Scheduling system
(the kind of system a MuleSoft "System API" would sit in front of
in a real healthcare integration project).

This is intentionally simple: everything lives in memory and resets
when the server restarts. That's fine for this project — the goal is
to give MuleSoft (and eventually Agentforce Voice, via MuleSoft) a
realistic, independent system to integrate with.

Run locally with:
    pip install -r requirements.txt
    uvicorn main:app --reload

Then open http://127.0.0.1:8000/docs for interactive Swagger docs.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(
    title="Mock EHR & Scheduling API",
    description="Simulated legacy healthcare system for the Salesforce Healthcare Patient Engagement project.",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# In-memory "database"
# ---------------------------------------------------------------------------
# Keys use the same style of external IDs your Salesforce objects reference
# (NPI_Number__c on Provider__c, MRN__c on Patient__c, External_Appointment_Id__c
# on Appointment__c) so the data lines up cleanly when you build the MuleSoft
# integration later.

providers_db = {
    "1234567890": {
        "npi": "1234567890",
        "name": "Dr. Sarah Chen",
        "specialty": "Primary Care",
        "location": "Main Clinic - Suite 200",
        "active": True,
    },
    "9876543210": {
        "npi": "9876543210",
        "name": "Dr. James Okafor",
        "specialty": "Cardiology",
        "location": "Main Clinic - Suite 310",
        "active": True,
    },
    "5556667777": {
        "npi": "5556667777",
        "name": "Dr. Maria Lopez",
        "specialty": "Pediatrics",
        "location": "West Clinic - Suite 105",
        "active": True,
    },
}

patients_db = {
    "MRN-00001": {
        "mrn": "MRN-00001",
        "first_name": "Amanda",
        "last_name": "Pineda",
        "date_of_birth": "1990-04-12",
        "email": "amanda.pineda@example.com",
        "phone": "+50370000001",
    },
    "MRN-00002": {
        "mrn": "MRN-00002",
        "first_name": "Carlos",
        "last_name": "Ramirez",
        "date_of_birth": "1985-11-02",
        "email": "carlos.ramirez@example.com",
        "phone": "+50370000002",
    },
}

# Appointments keyed by external_appointment_id
appointments_db = {}

# Simple visit history per patient (used by GET /patients/{id}/history)
visit_history_db = {
    "MRN-00001": [
        {
            "date": "2026-05-10",
            "provider_npi": "1234567890",
            "reason": "Annual wellness visit",
            "notes_summary": "Routine checkup, no concerns.",
        }
    ],
    "MRN-00002": [
        {
            "date": "2026-06-02",
            "provider_npi": "9876543210",
            "reason": "Follow-up: hypertension",
            "notes_summary": "Blood pressure improved, continue current medication.",
        }
    ],
}

# Pre-generate some availability slots for the next 7 days, 9am-4pm, 30-min blocks
def _seed_availability():
    slots = {}
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    for npi in providers_db:
        provider_slots = []
        for day_offset in range(1, 8):
            day = now + timedelta(days=day_offset)
            day = day.replace(hour=9)
            for half_hour in range(14):  # 9:00 to 16:00 in 30-min increments
                slot_time = day + timedelta(minutes=30 * half_hour)
                provider_slots.append(
                    {"datetime": slot_time.isoformat(), "available": True}
                )
        slots[npi] = provider_slots
    return slots


availability_db = _seed_availability()


# ---------------------------------------------------------------------------
# Pydantic models (request/response shapes)
# ---------------------------------------------------------------------------

class AvailabilitySlot(BaseModel):
    datetime: str
    available: bool


class AppointmentCreateRequest(BaseModel):
    patient_mrn: str = Field(..., description="Patient's MRN, e.g. MRN-00001")
    provider_npi: str = Field(..., description="Provider's NPI, e.g. 1234567890")
    appointment_datetime: str = Field(..., description="ISO 8601 datetime, must match an available slot")
    reason: Optional[str] = Field(None, description="Reason for visit")
    appointment_type: Optional[str] = Field("Follow-Up", description="New Patient, Follow-Up, Annual Wellness, Urgent")


class AppointmentResponse(BaseModel):
    external_appointment_id: str
    patient_mrn: str
    provider_npi: str
    appointment_datetime: str
    status: str
    reason: Optional[str]
    appointment_type: Optional[str]


class VisitHistoryEntry(BaseModel):
    date: str
    provider_npi: str
    reason: str
    notes_summary: str


class ErrorResponse(BaseModel):
    detail: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
def root():
    """Basic health check — useful for MuleSoft connectivity testing."""
    return {"status": "ok", "system": "Mock EHR & Scheduling API"}


@app.get(
    "/providers",
    tags=["Providers"],
    summary="List all providers",
)
def list_providers():
    return list(providers_db.values())


@app.get(
    "/providers/{npi}/availability",
    response_model=list[AvailabilitySlot],
    tags=["Providers"],
    summary="Get a provider's open appointment slots",
    responses={404: {"model": ErrorResponse}},
)
def get_provider_availability(npi: str, only_open: bool = True):
    if npi not in providers_db:
        raise HTTPException(status_code=404, detail=f"No provider found with NPI {npi}")

    slots = availability_db.get(npi, [])
    if only_open:
        slots = [s for s in slots if s["available"]]
    return slots


@app.get(
    "/patients/{mrn}",
    tags=["Patients"],
    summary="Get a patient's demographic record",
    responses={404: {"model": ErrorResponse}},
)
def get_patient(mrn: str):
    patient = patients_db.get(mrn)
    if not patient:
        raise HTTPException(status_code=404, detail=f"No patient found with MRN {mrn}")
    return patient


@app.get(
    "/patients/{mrn}/history",
    response_model=list[VisitHistoryEntry],
    tags=["Patients"],
    summary="Get a patient's visit history",
    responses={404: {"model": ErrorResponse}},
)
def get_patient_history(mrn: str):
    if mrn not in patients_db:
        raise HTTPException(status_code=404, detail=f"No patient found with MRN {mrn}")
    return visit_history_db.get(mrn, [])


@app.post(
    "/appointments",
    response_model=AppointmentResponse,
    status_code=201,
    tags=["Appointments"],
    summary="Book a new appointment",
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def create_appointment(req: AppointmentCreateRequest):
    if req.patient_mrn not in patients_db:
        raise HTTPException(status_code=404, detail=f"No patient found with MRN {req.patient_mrn}")
    if req.provider_npi not in providers_db:
        raise HTTPException(status_code=404, detail=f"No provider found with NPI {req.provider_npi}")

    # Find and lock the matching slot
    provider_slots = availability_db.get(req.provider_npi, [])
    matching_slot = next(
        (s for s in provider_slots if s["datetime"] == req.appointment_datetime),
        None,
    )
    if not matching_slot:
        raise HTTPException(
            status_code=404,
            detail=f"No slot found at {req.appointment_datetime} for provider {req.provider_npi}",
        )
    if not matching_slot["available"]:
        raise HTTPException(
            status_code=409,
            detail=f"Slot at {req.appointment_datetime} is already booked",
        )

    matching_slot["available"] = False

    appointment_id = f"APT-EHR-{uuid4().hex[:8].upper()}"
    appointment = {
        "external_appointment_id": appointment_id,
        "patient_mrn": req.patient_mrn,
        "provider_npi": req.provider_npi,
        "appointment_datetime": req.appointment_datetime,
        "status": "Scheduled",
        "reason": req.reason,
        "appointment_type": req.appointment_type,
    }
    appointments_db[appointment_id] = appointment
    return appointment


@app.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentResponse,
    tags=["Appointments"],
    summary="Get an appointment by its EHR ID",
    responses={404: {"model": ErrorResponse}},
)
def get_appointment(appointment_id: str):
    appointment = appointments_db.get(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail=f"No appointment found with ID {appointment_id}")
    return appointment


@app.delete(
    "/appointments/{appointment_id}",
    tags=["Appointments"],
    summary="Cancel an appointment (frees the slot back up)",
    responses={404: {"model": ErrorResponse}},
)
def cancel_appointment(appointment_id: str):
    appointment = appointments_db.get(appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail=f"No appointment found with ID {appointment_id}")

    appointment["status"] = "Cancelled"

    # free the slot back up
    provider_slots = availability_db.get(appointment["provider_npi"], [])
    for s in provider_slots:
        if s["datetime"] == appointment["appointment_datetime"]:
            s["available"] = True
            break

    return {"detail": f"Appointment {appointment_id} cancelled"}
