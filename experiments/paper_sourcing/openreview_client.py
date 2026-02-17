"""OpenReview API client wrapper for paper sourcing."""

import logging
from typing import Any, NamedTuple

import openreview  # type: ignore[import-untyped]
from openreview.api import OpenReviewClient  # type: ignore[import-untyped]

from .models import Conference, PresentationTier, ReviewerScore

logger = logging.getLogger(__name__)


class VenueConfig(NamedTuple):
    """Configuration for a specific venue."""

    venue_id: str
    api_version: int  # 1 or 2
    submission_invitation: str


# Mapping of (conference, year) to venue configuration
# Some older conferences use API V1 with different invitation patterns
VENUE_CONFIGS: dict[tuple[Conference, int], VenueConfig] = {
    # ICLR
    (Conference.ICLR, 2025): VenueConfig(
        venue_id="ICLR.cc/2025/Conference",
        api_version=2,
        submission_invitation="ICLR.cc/2025/Conference/-/Submission",
    ),
    (Conference.ICLR, 2024): VenueConfig(
        venue_id="ICLR.cc/2024/Conference",
        api_version=2,
        submission_invitation="ICLR.cc/2024/Conference/-/Submission",
    ),
    # NeurIPS
    (Conference.NEURIPS, 2025): VenueConfig(
        venue_id="NeurIPS.cc/2025/Conference",
        api_version=2,
        submission_invitation="NeurIPS.cc/2025/Conference/-/Submission",
    ),
    (Conference.NEURIPS, 2024): VenueConfig(
        venue_id="NeurIPS.cc/2024/Conference",
        api_version=2,
        submission_invitation="NeurIPS.cc/2024/Conference/-/Submission",
    ),
    # ICML - reviewer scores not public, but accepted papers with decisions available
    (Conference.ICML, 2025): VenueConfig(
        venue_id="ICML.cc/2025/Conference",
        api_version=2,
        submission_invitation="ICML.cc/2025/Conference/-/Submission",
    ),
    (Conference.ICML, 2024): VenueConfig(
        venue_id="ICML.cc/2024/Conference",
        api_version=2,
        submission_invitation="ICML.cc/2024/Conference/-/Submission",
    ),
}


def get_venue_config(*, conference: Conference, year: int) -> VenueConfig | None:
    """Get venue configuration for a conference-year.

    Args:
        conference: The conference venue
        year: The conference year

    Returns:
        VenueConfig or None if not supported
    """
    key = (conference, year)
    if key in VENUE_CONFIGS:
        return VENUE_CONFIGS[key]

    # Default fallback for unknown years - try V2 API
    venue_id = f"{conference.value}.cc/{year}/Conference"
    if conference == Conference.NEURIPS:
        venue_id = f"NeurIPS.cc/{year}/Conference"

    return VenueConfig(
        venue_id=venue_id,
        api_version=2,
        submission_invitation=f"{venue_id}/-/Submission",
    )


def create_client_v1() -> openreview.Client:
    """Create an OpenReview API V1 client."""
    return openreview.Client(baseurl="https://api.openreview.net")


def create_client_v2() -> OpenReviewClient:
    """Create an OpenReview API V2 client."""
    return openreview.api.OpenReviewClient(  # pyright: ignore[reportAttributeAccessIssue]
        baseurl="https://api2.openreview.net"
    )


def fetch_submissions(
    *,
    config: VenueConfig,
) -> list[Any]:
    """Fetch all submissions for a venue.

    Args:
        config: Venue configuration

    Returns:
        List of submission Note objects
    """
    logger.info(f"Fetching submissions for {config.venue_id} (API V{config.api_version})")

    if config.api_version == 1:
        client = create_client_v1()
        submissions = client.get_all_notes(
            invitation=config.submission_invitation,
            details="directReplies",
        )
    else:
        client = create_client_v2()
        submissions = client.get_all_notes(
            invitation=config.submission_invitation,
            details="replies",
        )

    logger.info(f"Found {len(submissions)} submissions")
    return list(submissions)  # Cast to list[Any]


def extract_reviewer_scores(
    *, note: Any, api_version: int  # noqa: ANN401 - openreview-py is untyped
) -> list[ReviewerScore]:
    """Extract reviewer scores from a submission note.

    Args:
        note: Submission note with replies
        api_version: API version (1 or 2)

    Returns:
        List of ReviewerScore tuples
    """
    scores: list[ReviewerScore] = []

    # Get replies based on API version
    if api_version == 1:
        replies = getattr(note, "details", {}).get("directReplies", []) or []
    else:
        replies = getattr(note, "details", {}).get("replies", []) or []

    for reply in replies:
        # Handle both dict (V2) and Note object (V1)
        if hasattr(reply, "content"):
            content = reply.content or {}
            signatures = reply.signatures or ["unknown"]
        else:
            content = reply.get("content", {}) or {}
            signatures = reply.get("signatures", ["unknown"])

        # Try common field names for overall score
        score_value = None
        for field in ["rating", "recommendation", "overall_score", "score", "soundness"]:
            if field in content:
                raw_value = content[field]
                if isinstance(raw_value, dict):
                    raw_value = raw_value.get("value")
                if raw_value is not None:
                    # Extract numeric part from strings like "8: Strong Accept"
                    if isinstance(raw_value, str):
                        parts = raw_value.split(":")
                        try:
                            score_value = float(parts[0].strip())
                            break
                        except ValueError:
                            continue
                    else:
                        try:
                            score_value = float(raw_value)
                            break
                        except (ValueError, TypeError):
                            continue

        if score_value is None:
            continue

        # Extract confidence
        confidence_value = 3.0  # Default confidence
        if "confidence" in content:
            raw_conf = content["confidence"]
            if isinstance(raw_conf, dict):
                raw_conf = raw_conf.get("value")
            if raw_conf is not None:
                if isinstance(raw_conf, str):
                    parts = raw_conf.split(":")
                    try:
                        confidence_value = float(parts[0].strip())
                    except ValueError:
                        pass
                else:
                    try:
                        confidence_value = float(raw_conf)
                    except (ValueError, TypeError):
                        pass

        reviewer_id = signatures[0]
        scores.append(
            ReviewerScore(
                reviewer_id=str(reviewer_id),
                score=score_value,
                confidence=confidence_value,
            )
        )

    return scores


def extract_decision(
    *, note: Any, api_version: int  # noqa: ANN401 - openreview-py is untyped
) -> tuple[str, PresentationTier]:
    """Extract decision and presentation tier from a submission.

    Args:
        note: Submission note with replies
        api_version: API version (1 or 2)

    Returns:
        Tuple of (decision_string, PresentationTier)
    """
    # Get replies based on API version
    if api_version == 1:
        replies = getattr(note, "details", {}).get("directReplies", []) or []
    else:
        replies = getattr(note, "details", {}).get("replies", []) or []

    for reply in replies:
        # Handle both dict (V2) and Note object (V1)
        if hasattr(reply, "content"):
            content = reply.content or {}
            invitations = getattr(reply, "invitations", []) or getattr(reply, "invitation", "")
            if isinstance(invitations, str):
                invitations = [invitations]
        else:
            content = reply.get("content", {}) or {}
            # V1 uses "invitation" (singular), V2 uses "invitations" (plural)
            invitations = reply.get("invitations", []) or reply.get("invitation", "")
            if isinstance(invitations, str):
                invitations = [invitations]

        # Check if this is a decision reply
        is_decision = any("Decision" in str(inv) for inv in invitations)
        if not is_decision:
            continue

        decision_raw = content.get("decision")
        if isinstance(decision_raw, dict):
            decision_raw = decision_raw.get("value")

        if decision_raw is None:
            continue

        decision_str = str(decision_raw)
        tier = parse_presentation_tier(decision_string=decision_str)

        return decision_str, tier

    # Fallback: check venue_id in content
    content = getattr(note, "content", {}) or {}
    venueid = content.get("venueid", {})
    if isinstance(venueid, dict):
        venueid = venueid.get("value", "")

    if venueid:
        venueid_str = str(venueid).lower()
        if "reject" in venueid_str:
            return "Reject", PresentationTier.REJECT
        if "withdrawn" in venueid_str:
            return "Withdrawn", PresentationTier.UNKNOWN
        if "retracted" in venueid_str:
            return "Retracted", PresentationTier.UNKNOWN
        if "oral" in venueid_str:
            return "Accept (Oral)", PresentationTier.ORAL
        if "spotlight" in venueid_str:
            return "Accept (Spotlight)", PresentationTier.SPOTLIGHT
        if "poster" in venueid_str:
            return "Accept (Poster)", PresentationTier.POSTER
        # ICML venueid pattern: "ICML.cc/YEAR/Conference" indicates accepted (tier unknown)
        # This happens when no explicit Decision reply exists
        if venueid_str.endswith("/conference"):
            return "Accept", PresentationTier.POSTER  # Default to poster tier

    return "Unknown", PresentationTier.UNKNOWN


def parse_presentation_tier(*, decision_string: str) -> PresentationTier:
    """Parse presentation tier from decision string.

    Args:
        decision_string: Raw decision string from OpenReview

    Returns:
        Parsed PresentationTier enum value
    """
    decision_lower = decision_string.lower()

    if "reject" in decision_lower:
        return PresentationTier.REJECT
    if "withdrawn" in decision_lower:
        return PresentationTier.UNKNOWN  # Filter out withdrawn papers
    if "best paper" in decision_lower or "outstanding" in decision_lower:
        return PresentationTier.BEST_PAPER
    if "oral" in decision_lower:
        return PresentationTier.ORAL
    # ICLR uses "notable-top-5%" and "notable-top-25%" for top papers
    if "notable-top-5" in decision_lower:
        return PresentationTier.ORAL  # Top 5% = oral equivalent
    if "notable-top-25" in decision_lower or "spotlight" in decision_lower:
        return PresentationTier.SPOTLIGHT
    if "poster" in decision_lower or "accept" in decision_lower:
        return PresentationTier.POSTER

    return PresentationTier.UNKNOWN


def get_pdf_url(*, note: Any) -> str:  # noqa: ANN401 - openreview-py is untyped
    """Get PDF URL from a submission note.

    Args:
        note: Submission note

    Returns:
        PDF URL string or empty string if not available
    """
    content = getattr(note, "content", {}) or {}
    pdf_field = content.get("pdf")

    if pdf_field is None:
        return ""

    if isinstance(pdf_field, dict):
        pdf_path = pdf_field.get("value")
    else:
        pdf_path = pdf_field

    if pdf_path is None:
        return ""

    # OpenReview stores relative paths, construct full URL
    if pdf_path.startswith("/"):
        return f"https://openreview.net{pdf_path}"

    return str(pdf_path)


def get_title(*, note: Any) -> str:  # noqa: ANN401 - openreview-py is untyped
    """Get title from a submission note.

    Args:
        note: Submission note

    Returns:
        Paper title
    """
    content = getattr(note, "content", {}) or {}
    title = content.get("title")

    if isinstance(title, dict):
        title = title.get("value")

    return str(title) if title else "Unknown"
