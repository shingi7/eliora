from datetime import datetime, timezone

from eliora_outreach.config import TargetingSettings
from eliora_outreach.enums import SignalType, SourceType
from eliora_outreach.models import ContactRecord, PainHypothesis, SourceEvidence
from eliora_outreach.research.contacts import validate_public_contact
from eliora_outreach.scoring import LeadInputs, score_lead


def test_official_mailto_and_rejections() -> None:
    accepted = validate_public_contact(
        "operations@northstarhealth.example",
        "northstarhealth.example",
        source_url="https://northstarhealth.example/contact",
        extraction_method="mailto",
        role="Operations",
    )
    assert accepted.valid and accepted.quality == 13
    assert not validate_public_contact(
        "person@gmail.com",
        "northstarhealth.example",
        source_url="https://northstarhealth.example/contact",
        extraction_method="visible_text",
    ).valid
    assert not validate_public_contact(
        "sales@other.example",
        "northstarhealth.example",
        source_url="https://northstarhealth.example/contact",
        extraction_method="mailto",
    ).valid
    assert not validate_public_contact(
        "support@northstarhealth.example",
        "northstarhealth.example",
        source_url="https://northstarhealth.example/contact",
        extraction_method="mailto",
    ).valid
    assert not validate_public_contact(
        "first.last@northstarhealth.example",
        "northstarhealth.example",
        source_url=None,
        extraction_method=None,
    ).valid


def _inputs(**overrides):
    source = SourceEvidence(
        id="s1",
        url="https://northstarhealth.example/news",
        title="Expansion",
        publisher="northstarhealth.example",
        source_type=SourceType.OFFICIAL_PRESS,
        retrieved_at=datetime.now(timezone.utc),
        excerpt="The company announced an operations expansion.",
        source_quality=1,
    )
    contact = ContactRecord(
        id="c1",
        company_id="co",
        email="operations@northstarhealth.example",
        source_id="s1",
        source_url="https://northstarhealth.example/contact",
        extraction_method="mailto",
        official_domain=True,
        syntactic_valid=True,
        appropriateness_status="eligible",
        appropriateness_reason="official",
        contact_quality=13,
    )
    pain = PainHypothesis(
        id="p1",
        company_id="co",
        category=SignalType.MANUAL_REPORTING,
        pain_hypothesis="The expansion may add recurring reporting handoffs.",
        confidence=0.9,
        service_match="Reporting Automation Sprint",
        supporting_signal_ids=["sig"],
    )
    values = dict(
        country="United States",
        employee_band="50-99",
        sources=[source],
        fresh_signal_count=1,
        service_fit=24,
        hypotheses=[pain],
        contact=contact,
        research_confidence=0.9,
    )
    values.update(overrides)
    return LeadInputs(**values)


def test_score_has_deterministic_gates() -> None:
    result = score_lead(_inputs(), TargetingSettings())
    assert result.score_version == "2026-08-01"
    assert result.disposition.value == "needs_review"  # one source cannot auto-send
    result = score_lead(_inputs(active_suppression=True), TargetingSettings())
    assert result.disposition.value == "disqualified"
    result = score_lead(_inputs(country="Canada"), TargetingSettings())
    assert not result.hard_gates["us_only"]
