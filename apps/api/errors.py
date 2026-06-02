from ninja import Schema


class ErrorDetail(Schema):
    code:         str
    message:      str
    field:        str | None = None
    valid_values: list[str] | None = None


class ErrorResponse(Schema):
    error: ErrorDetail


def not_found(resource: str, identifier: str) -> dict:
    return {"error": {"code": "not_found", "message": f"{resource} '{identifier}' not found"}}


def invalid_field(field: str, got: str, valid_values: list[str]) -> dict:
    return {
        "error": {
            "code": f"invalid_{field}",
            "message": f"{field} must be one of: {', '.join(valid_values)} (got: \"{got}\")",
            "field": field,
            "valid_values": valid_values,
        }
    }
