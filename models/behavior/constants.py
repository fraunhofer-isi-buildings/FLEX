# ---------------------------------------------------------------------------
# Named constants for person-type, activity, and technology IDs used across
# the FLEX-Behavior model.  Magic numbers in person.py / household.py should
# be replaced by these names so the intent is self-documenting.
# ---------------------------------------------------------------------------

# --- Person types ---
STUDENT_PERSON_TYPE = 3
RETIRED_PERSON_TYPE = 4
NON_WORKING_PERSON_TYPES = {STUDENT_PERSON_TYPE, RETIRED_PERSON_TYPE}

# --- Activity IDs ---
WORKING_ACTIVITY_ID = 11

# --- Technology IDs ---
HOT_WATER_TECHNOLOGY_ID = 23
MODEM_TECHNOLOGY_ID = 35
LIGHTING_TECHNOLOGY_ID = 36
REFRIGERATOR_TECHNOLOGY_ID = 37


def person_mark(id_person_type: int, id_teleworking_type: int, sample: int) -> str:
    """Return the canonical mark string that identifies a person sample column.

    Used both when *writing* person profiles (main.py) and when *reading* them
    (household.py), so the naming protocol is defined in exactly one place.
    """
    return f"p{id_person_type}t{id_teleworking_type}s{sample}"
