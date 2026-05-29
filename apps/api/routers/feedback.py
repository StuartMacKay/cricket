from django.http import HttpRequest
from ninja import Router

from ..auth import bearer_auth
from ..errors import ErrorResponse, not_found
from ..models import APIFeedback
from ..schemas import FeedbackIn, FeedbackOut

router = Router(tags=["feedback"])


@router.post("/", auth=bearer_auth, response=FeedbackOut, summary="Submit API feedback")
def create_feedback(request: HttpRequest, body: FeedbackIn):
    feedback = APIFeedback.objects.create(
        api_key=request.auth,
        endpoint=body.endpoint,
        message=body.message,
    )
    return {
        "id": feedback.pk,
        "endpoint": feedback.endpoint,
        "message": feedback.message,
        "created": feedback.created,
    }


@router.get("/", auth=bearer_auth, response={200: list[FeedbackOut], 403: ErrorResponse}, summary="List feedback (admin only)")
def list_feedback(request: HttpRequest):
    if not request.auth or not request.auth.is_admin:
        return 403, {"error": {"code": "forbidden", "message": "Admin key required"}}
    qs = APIFeedback.objects.select_related("api_key").order_by("-created")[:100]
    return [
        {
            "id": fb.pk,
            "endpoint": fb.endpoint,
            "message": fb.message,
            "created": fb.created,
        }
        for fb in qs
    ]
