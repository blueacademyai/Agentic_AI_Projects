from pydantic import BaseModel

def serialize_input(data):
    """Recursively convert Pydantic models and complex types to JSON-safe dicts/lists"""
    if isinstance(data, BaseModel):
        return data.dict()
    if isinstance(data, dict):
        return {k: serialize_input(v) for k, v in data.items()}
    if isinstance(data, list):
        return [serialize_input(v) for v in data]
    return data
