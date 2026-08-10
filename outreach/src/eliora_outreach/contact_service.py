"""Owner-controlled attachment of a provenance-backed contact to a lead."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

from sqlalchemy import select

from .db import AuditEvent, Company, Contact, Database, Draft, LeadScore, Source
from .enums import SourceType
from .research.canonicalize import registrable_domain, url_hash, validate_public_url
from .research.contacts import normalized_email, validate_public_contact
from .score_service import recompute_reachability_for_company

APPROVED_EXTRACTION_METHODS = frozenset({"visible_text", "mailto", "jsonld"})
APPROVED_SOURCE_TYPES = frozenset(item.value for item in SourceType)


class ContactAttachError(ValueError):
    """A safe, actionable contact-attachment error."""


@dataclass(frozen=True)
class ContactAttachResult:
    status: str
    company_id: str
    company: str
    contact_id: str
    email: str
    display_name: str | None
    title: str | None
    source_url: str
    source_type: str
    source_verification_status: str
    draft_id: str | None
    reachability_before: int | None
    reachability_after: int | None
    reachability_grade: str | None
    permission_basis: str


def _clean(value: str | None) -> str | None:
    cleaned = value.strip() if value else None
    return cleaned or None


def _bounded(value: str | None, field: str, maximum: int) -> str | None:
    cleaned = _clean(value)
    if cleaned and len(cleaned) > maximum:
        raise ContactAttachError(f"{field} must be {maximum} characters or fewer")
    return cleaned


def _canonical_existing_source(source: Source | None) -> str | None:
    if source is None:
        return None
    try:
        return validate_public_url(source.url, resolve=False)
    except ValueError:
        return source.url


def attach_contact(
    database: Database,
    *,
    company_id: str,
    email: str,
    display_name: str | None,
    title: str | None,
    source_url: str,
    source_type: str,
    extraction_method: str = "visible_text",
    draft_id: str | None = None,
) -> ContactAttachResult:
    """Attach one owner-supplied public contact without creating send work.

    The existing public-contact validator remains authoritative.  This command
    records provenance but deliberately leaves source verification as
    ``not_checked`` and contact appropriateness as ``review``.
    """
    if source_type not in APPROVED_SOURCE_TYPES:
        allowed = ", ".join(sorted(APPROVED_SOURCE_TYPES))
        raise ContactAttachError(f"source_type must be one of: {allowed}")
    if extraction_method not in APPROVED_EXTRACTION_METHODS:
        allowed = ", ".join(sorted(APPROVED_EXTRACTION_METHODS))
        raise ContactAttachError(f"extraction_method must be one of: {allowed}")
    try:
        canonical_source_url = validate_public_url(source_url, resolve=False)
    except ValueError as exc:
        raise ContactAttachError(f"source_url rejected: {exc}") from exc
    email = normalized_email(email)
    display_name = _bounded(display_name, "name", 255)
    title = _bounded(title, "title", 255)
    source_digest = url_hash(canonical_source_url)

    database.create()
    with database.session() as session:
        company = session.get(Company, company_id)
        if company is None:
            score = session.get(LeadScore, company_id)
            company = session.get(Company, score.company_id) if score else None
        if company is None:
            raise ContactAttachError("Company/lead not found")
        if company.data_origin in {"synthetic", "owner_test"}:
            raise ContactAttachError("Synthetic/demo leads cannot receive production contacts")

        validation = validate_public_contact(
            email,
            company.registrable_domain,
            source_url=canonical_source_url,
            extraction_method=extraction_method,
            role=title,
            mx_valid=None,
            mx_result="not_checked",
        )
        if not validation.valid:
            raise ContactAttachError(f"Contact rejected: {validation.reason}")

        contact = session.scalar(select(Contact).where(Contact.email == validation.email))
        status = "added"
        persisted_source_type = source_type
        if contact is not None:
            if contact.company_id != company.id:
                raise ContactAttachError(
                    f"Contact email already belongs to another company: {validation.email}"
                )
            existing_source = session.get(Source, contact.source_id)
            if _canonical_existing_source(existing_source) != canonical_source_url:
                raise ContactAttachError(
                    "This email already has different provenance; refusing to overwrite it"
                )
            if existing_source is not None:
                persisted_source_type = existing_source.source_type
            status = "already_exists"
        else:
            source = session.scalar(
                select(Source).where(
                    Source.company_id == company.id,
                    Source.canonical_url_hash == source_digest,
                )
            )
            if source is None:
                source = Source(
                    company_id=company.id,
                    url=canonical_source_url,
                    canonical_url_hash=source_digest,
                    source_type=source_type,
                    title="Owner-recorded public contact source",
                    publisher=registrable_domain(urlparse(canonical_source_url).hostname or ""),
                    excerpt=(
                        "Contact provenance recorded by the owner; this command did not fetch "
                        "or independently verify the source."
                    ),
                    source_quality=0,
                    data_origin=company.data_origin,
                    source_tier="C",
                    freshness_category="unknown",
                    claim_type="observed_fact",
                    date_confidence="unknown",
                )
                session.add(source)
                session.flush()
            contact = Contact(
                company_id=company.id,
                email=validation.email,
                display_name=display_name,
                title=title,
                source_id=source.id,
                source_url=canonical_source_url,
                extraction_method=extraction_method,
                official_domain=validation.official_domain,
                role_inbox_category=validation.category,
                syntactic_valid=True,
                mx_valid=None,
                mx_result="not_checked",
                appropriateness_status="review",
                appropriateness_reason=(
                    f"Email/domain validation passed ({validation.category}); "
                    "source verification=not_checked"
                ),
                first_seen_at=datetime.now(timezone.utc),
                data_origin=company.data_origin,
                source_title="Owner-recorded public contact source",
                source_context=(
                    "Owner-provided provenance; independent source verification was not checked."
                ),
                no_guessed_address=True,
                source_verification_status="not_checked",
                source_verification_reason=(
                    "Source URL was recorded; independent source verification was not performed."
                ),
            )
            session.add(contact)
            session.flush()

        selected_draft: Draft | None = None
        if draft_id:
            selected_draft = session.get(Draft, draft_id)
            if selected_draft is None:
                raise ContactAttachError("Draft not found")
            if selected_draft.company_id != company.id:
                raise ContactAttachError("Draft does not belong to this company")
            if selected_draft.contact_id and selected_draft.contact_id != contact.id:
                raise ContactAttachError("Draft already has a different persisted contact")
        else:
            candidates = session.scalars(
                select(Draft)
                .where(Draft.company_id == company.id, Draft.contact_id.is_(None))
                .order_by(Draft.created_at.desc(), Draft.id.desc())
            ).all()
            if len(candidates) > 1:
                raise ContactAttachError(
                    "Multiple drafts have no contact; pass --draft-id to choose one"
                )
            selected_draft = candidates[0] if candidates else None
        if selected_draft is not None and selected_draft.contact_id is None:
            selected_draft.contact_id = contact.id

        session.add(
            AuditEvent(
                actor="owner",
                action="lead_contact_attached"
                if status == "added"
                else "lead_contact_attach_repeated",
                entity_type="contact",
                entity_id=contact.id,
                metadata_json={
                    "company_id": company.id,
                    "email": contact.email,
                    "source_url": canonical_source_url,
                    "source_type": persisted_source_type,
                    "extraction_method": extraction_method,
                    "source_verification_status": contact.source_verification_status,
                    "draft_id": selected_draft.id if selected_draft else None,
                    "outbox_rows_created": 0,
                    "prospect_messages_sent": 0,
                },
            )
        )
        permission_basis = company.permission_basis
        company_name = company.name
        contact_id = contact.id
        contact_email = contact.email
        contact_name = contact.display_name
        contact_title = contact.title
        contact_source_url = contact.source_url
        verification_status = contact.source_verification_status
        attached_draft_id = selected_draft.id if selected_draft else None

    reachability = recompute_reachability_for_company(database, company.id)
    return ContactAttachResult(
        status=status,
        company_id=company.id,
        company=company_name,
        contact_id=contact_id,
        email=contact_email,
        display_name=contact_name,
        title=contact_title,
        source_url=contact_source_url,
        source_type=persisted_source_type,
        source_verification_status=verification_status,
        draft_id=attached_draft_id,
        reachability_before=reachability["reachability_before"],
        reachability_after=reachability["reachability_after"],
        reachability_grade=reachability["reachability_grade"],
        permission_basis=permission_basis,
    )
