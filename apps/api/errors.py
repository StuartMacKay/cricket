from ninja import Schema


class ErrorDetail(Schema):
    code: str
    message: str
    field: str | None = None
    valid_values: list[str] | None = None
    poll_url: str | None = None
    job_id: int | None = None


class ErrorResponse(Schema):
    error: ErrorDetail


def not_found(resource: str, identifier: str) -> dict:
    return {
        "error": {
            "code": "not_found",
            "message": f"{resource} '{identifier}' not found",
        }
    }


def invalid_field(field: str, got: str, valid_values: list[str]) -> dict:
    valid_str = ", ".join(valid_values)
    return {
        "error": {
            "code": f"invalid_{field}",
            "message": f"{field} must be one of: {valid_str} (got: \"{got}\")",
            "field": field,
            "valid_values": valid_values,
        }
    }


def scan_in_progress(scan_id: int) -> dict:
    return {
        "error": {
            "code": "scan_in_progress",
            "message": (
                "A scan is already running. "
                "Poll the job for status, or pass \"force\": true to start a new one."
            ),
            "job_id": scan_id,
            "poll_url": f"/api/jobs/{scan_id}/",
        }
    }


def no_complete_scan(site_slug: str) -> dict:
    return {
        "error": {
            "code": "no_complete_scan",
            "message": f"No complete scan found for site '{site_slug}'",
        }
    }
