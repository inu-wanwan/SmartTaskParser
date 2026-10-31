from urllib.parse import parse_qs

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.services.line_push_service import LinePushService
from app.services.reminder_service import ReminderService

router = APIRouter()


def get_reminder_service(request: Request) -> ReminderService:
    return request.app.state.reminder_service


def get_line_push_service(request: Request) -> LinePushService:
    return request.app.state.line_push_service


@router.post("/reminders/dispatch")
def dispatch_reminders(
    cron_token: str = Header(..., alias="X-Cron-Token"),
    reminder_service: ReminderService = Depends(get_reminder_service),
    line_push_service: LinePushService = Depends(get_line_push_service),
):
    """
    Cloud Scheduler から毎分呼ばれ、時刻が来たリマインドを送る。
    """
    try:
        line_push_service.verify_cron_token(cron_token)
    except PermissionError:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"results": reminder_service.dispatch()}


@router.post("/reminders/pushover-callback")
async def pushover_callback(
    request: Request,
    rid: str,
    reminder_service: ReminderService = Depends(get_reminder_service),
):
    """
    Pushover アプリで Acknowledge が押されたときに Pushover から POST される。
    """
    form = parse_qs((await request.body()).decode("utf-8"))
    receipt = (form.get("receipt") or [""])[0]
    if not reminder_service.handle_pushover_callback(rid, receipt):
        raise HTTPException(status_code=404, detail="Not found")
    return {"status": "ok"}
