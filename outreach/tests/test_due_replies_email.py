from datetime import date, datetime, timezone

from eliora_outreach.config import SenderSettings
from eliora_outreach.due import add_business_days, decide_due, within_send_window
from eliora_outreach.email.render import build_mime, deterministic_message_id
from eliora_outreach.email.replies import classify_reply
from eliora_outreach.enums import EventClass
from eliora_outreach.models import DraftContent


def sender() -> SenderSettings:
    return SenderSettings(
        display_name="EliOra",
        title="Co-Founder",
        email="owner@eliora.example",
        reply_to="owner@eliora.example",
        owner_bcc="owner@eliora.example",
        postal_address="100 Demo Way, New York, NY",
    )


def test_due_logic_and_business_days() -> None:
    assert add_business_days(date(2026, 8, 7), 1) == date(2026, 8, 10)
    noon = datetime(2026, 8, 10, 20, 0, tzinfo=timezone.utc)
    decision = decide_due(
        noon,
        timezone="America/New_York",
        research_time="07:45",
        send_start="09:05",
        send_end="15:30",
    )
    assert decision.research_due and not decision.dispatch_allowed
    assert not within_send_window(datetime(2026, 8, 9, 15, tzinfo=timezone.utc))


def test_reply_precedence_and_mime_headers() -> None:
    assert classify_reply("Delivery failure", "550 user unknown").event_class is EventClass.BOUNCE
    assert classify_reply("Re: hello", "No thanks, remove me").event_class is EventClass.UNSUBSCRIBE
    assert classify_reply("Question", "Could we talk?").event_class is EventClass.QUESTION
    content = DraftContent(
        subject="A question",
        body="Hello team\n\nObserved fact.\n\nBusiness outreach from EliOra Tech Solutions LLC.\n100 Demo Way, New York, NY\nNot relevant? Reply no thanks.",
        html_body="<p>Hello team</p>",
        source_fact_ids=["s1"],
    )
    raw = build_mime(
        content=content,
        sender=sender(),
        recipient="operations@northstarhealth.example",
        message_id=deterministic_message_id("key", sender().email),
    ).as_bytes()
    assert b"Bcc:" not in raw
    assert b"List-Unsubscribe:" in raw
    assert b"text/plain" in raw and b"text/html" in raw
    assert b"tracking" not in raw.lower()
