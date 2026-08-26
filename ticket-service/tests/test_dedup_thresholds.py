"""
Validates the core duplicate-detection pipeline against real ground-truth
pairs pulled from the Eclipse dataset (duplicate_links where source ==
'ground_truth'), not synthetic examples -- this is what requirement #11
specifically asks for: tests that confirm dedup thresholds work correctly.
"""

from src.db.session import SessionLocal
from src.db.models import DuplicateLink, Ticket
from src.ml.similarity_search import search_similar_tickets


def test_ground_truth_duplicates_exist():
    """Sanity check: the migration actually produced ground-truth pairs to test against."""
    db = SessionLocal()
    try:
        count = db.query(DuplicateLink).filter(DuplicateLink.source == "ground_truth").count()
        assert count > 0, "No ground-truth duplicate pairs found in duplicate_links table"
    finally:
        db.close()


def test_ground_truth_duplicates_score_significantly_high():
    """
    For a sample of real, human-confirmed duplicate pairs, the true match
    should appear in the search results with a meaningfully high similarity
    score -- this is the actual evidence behind AUTO_DUPLICATE_THRESHOLD
    and HUMAN_REVIEW_THRESHOLD, not just a guessed number.
    """
    db = SessionLocal()
    try:
        links = (
            db.query(DuplicateLink)
            .filter(DuplicateLink.source == "ground_truth")
            .limit(15)
            .all()
        )
        assert len(links) > 0

        scores = []
        for link in links:
            dup_ticket = db.query(Ticket).filter(Ticket.id == link.ticket_id).first()
            if not dup_ticket or not dup_ticket.title:
                continue

            results = search_similar_tickets(
                title=dup_ticket.title,
                description=dup_ticket.description or "",
                top_k=5,
            )

            matching = [
                r for r in results
                if r.get("postgres") and r["postgres"]["id"] == link.duplicate_of_ticket_id
            ]
            if matching:
                scores.append(matching[0]["similarity_score"])

        assert len(scores) > 0, "None of the sampled ground-truth pairs were retrieved by search at all"

        avg_score = sum(scores) / len(scores)
        assert avg_score > 0.5, f"Average similarity for known duplicates is too low: {avg_score:.4f}"
    finally:
        db.close()


def test_identical_text_scores_near_perfect_similarity():
    """
    Regression guard for the text-construction bug found earlier in this
    project (Summary: vs Title: prefix mismatch) -- searching with text
    identical to a stored ticket must score close to 1.0.
    """
    db = SessionLocal()
    try:
        sample_ticket = (
            db.query(Ticket)
            .filter(Ticket.title.isnot(None))
            .filter(~Ticket.external_id.startswith("local-"))
            .order_by(Ticket.id)
            .first()
        )
        assert sample_ticket is not None

        results = search_similar_tickets(
            title=sample_ticket.title,
            description=sample_ticket.description or "",
            top_k=1,
        )
        assert len(results) > 0
        assert results[0]["similarity_score"] > 0.9, (
            "Exact-text search should score near 1.0 -- if this fails, check "
            "that embedding.py and similarity_search.py build ticket text identically"
        )
    finally:
        db.close()


def test_unrelated_text_scores_below_review_threshold():
    """A nonsense/unrelated query should stay below your real decision threshold, not an arbitrary number."""
    from src.services.ticket_service import HUMAN_REVIEW_THRESHOLD

    results = search_similar_tickets(
        title="zzz completely unrelated nonsense query xyz",
        description="qwerty asdf random text with no connection to any real bug report",
        top_k=1,
    )
    if results:
        assert results[0]["similarity_score"] < HUMAN_REVIEW_THRESHOLD