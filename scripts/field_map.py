"""Maps semantic Everglades field names to RLS custom_field UUIDs.

Derived by hydrating approved tasks and inspecting their custom_fields. These
UUIDs are stable per-campaign — the STEM Software campaign uses these.
"""

FIELD_MAP = {
    "domain": "field_9b4032885629",
    "subdomain": "field_32989c76ab03",
    "directionality": "field_4199620c61b3",
    "tool": "field_19a38bddb2ad",
    "tolerance": "field_d0d1331db6c7",
    "reasoning_trap": "field_00727231ef43",
    "grading_guidance": "field_6a2b00c0923a",
    "packages": "field_9e93e1b24a10",
    "explanation": "field_bdb262162384",
    "oracle_file": "field_d3feecad1958",
    "verification_code": "field_f05eba6aa8e7",
}

REVERSE_FIELD_MAP = {v: k for k, v in FIELD_MAP.items()}


def semantic_to_field_id(name: str) -> str:
    if name in FIELD_MAP:
        return FIELD_MAP[name]
    if name.startswith("field_"):
        return name  # already a UUID
    raise KeyError(f"Unknown semantic field: {name}. Known: {list(FIELD_MAP.keys())}")


def field_id_to_semantic(field_id: str) -> str | None:
    return REVERSE_FIELD_MAP.get(field_id)
