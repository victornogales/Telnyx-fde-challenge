# Synthetic patient data for RefillLine pharmacy
# Keys are E.164 phone numbers (used to lookup by caller_key hash).
# All data is fictional and for demonstration only.

PATIENTS: dict[str, dict] = {
    # User's mobile — primary demo/test number
    "+15550000001": {
        "first_name": "Maria",
        "dob": "1962-03-15",
        "prescriptions": [
            {
                "id": "rx-mar-001",
                "name": "Lisinopril",
                "strength": "10 mg",
                "refills_left": 2,
                "controlled": False,
            },
            {
                "id": "rx-mar-002",
                "name": "Oxycodone",
                "strength": "5 mg",
                "refills_left": 0,
                "controlled": True,
            },
            {
                "id": "rx-mar-003",
                "name": "Metformin",
                "strength": "500 mg",
                "refills_left": 1,
                "controlled": False,
            },
        ],
    },
    # User's assigned Telnyx number — secondary test number
    "+442045202115": {
        "first_name": "James",
        "dob": "1985-07-22",
        "prescriptions": [
            {
                "id": "rx-jam-001",
                "name": "Atorvastatin",
                "strength": "20 mg",
                "refills_left": 3,
                "controlled": False,
            },
            {
                "id": "rx-jam-002",
                "name": "Amoxicillin",
                "strength": "500 mg",
                "refills_left": 0,
                "controlled": False,
            },
        ],
    },
    # Synthetic numbers for negative-path / multi-caller testing
    "+15551112222": {
        "first_name": "David",
        "dob": "1978-11-03",
        "prescriptions": [
            {
                "id": "rx-dav-001",
                "name": "Sertraline",
                "strength": "50 mg",
                "refills_left": 2,
                "controlled": False,
            },
            {
                "id": "rx-dav-002",
                "name": "Albuterol",
                "strength": "90 mcg inhaler",
                "refills_left": 1,
                "controlled": False,
            },
        ],
    },
    "+15552223333": {
        "first_name": "Sarah",
        "dob": "1991-06-08",
        "prescriptions": [
            {
                "id": "rx-sar-001",
                "name": "Levothyroxine",
                "strength": "75 mcg",
                "refills_left": 5,
                "controlled": False,
            },
            {
                "id": "rx-sar-002",
                "name": "Ibuprofen",
                "strength": "400 mg",
                "refills_left": 2,
                "controlled": False,
            },
            {
                "id": "rx-sar-003",
                "name": "Lorazepam",
                "strength": "1 mg",
                "refills_left": 1,
                "controlled": True,
            },
        ],
    },
    "+15553334444": {
        "first_name": "Robert",
        "dob": "1955-09-19",
        "prescriptions": [
            {
                "id": "rx-rob-001",
                "name": "Warfarin",
                "strength": "5 mg",
                "refills_left": 0,
                "controlled": False,
            },
            {
                "id": "rx-rob-002",
                "name": "Furosemide",
                "strength": "40 mg",
                "refills_left": 3,
                "controlled": False,
            },
        ],
    },
}


def find_patient(e164: str) -> dict | None:
    """Look up a patient by their E.164 phone number."""
    return PATIENTS.get(e164)
