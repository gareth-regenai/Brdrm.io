"""End-to-end tests only (E9): the emails the capture mailer kept for one address, so a
journey can follow an invitation link. Mounted only when MAILER=capture, which production
refuses."""

from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from boardroom.modules.notify.mailer import captured

router = APIRouter()

PATH = "/e2e/mail"


class MailOut(BaseModel):
    subject: str
    body: str


@router.get(PATH, response_model=list[MailOut], tags=["e2e"])
def mail(to: EmailStr) -> list[MailOut]:
    return [MailOut(subject=e.subject, body=e.body) for e in captured(str(to))]
