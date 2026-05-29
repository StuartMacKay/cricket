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


def snapshot_in_progress(snapshot_id: int) -> dict:
    return {
        "error": {
            "code": "snapshot_in_progress",
            "message": (
                "A snapshot is already running. "
                "Poll the job for status, or pass \"force\": true to start a new one."
            ),
            "job_id": snapshot_id,
            "poll_url": f"/api/jobs/{snapshot_id}/",
        }
    }


def no_complete_snapshot(site_slug: str) -> dict:
    return {
        "error": {
            "code": "no_complete_snapshot",
            "message": f"No complete snapshot found for site '{site_slug}'",
        }
    }
