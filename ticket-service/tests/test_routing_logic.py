"""
Isolates and tests the routing DECISION logic itself (auto_duplicate /
human_review / new_ticket branching) by mocking the similarity score,
rather than depending on real embedding/ChromaDB behavior. This is the
"routing decisions" half of requirement #11 -- fast, deterministic,
and independent of what's actually in the database.
"""

from unittest.mock import patch

from src.services import ticket_service


def _fake_result(score, matched_id=1):
    return [
        {
            "ticket_id": str(matched_id),
            "similarity_score": score,
            "postgres": {"id": matched_id, "title": "Existing ticket", "description": "desc"},
        }
    ]


@patch("src.services.ticket_service.search_similar_tickets")
def test_high_similarity_routes_to_auto_duplicate(mock_search):
    mock_search.return_value = _fake_result(0.90)
    result = ticket_service.process_new_ticket("some title", "some description")
    assert result["decision"] == "auto_duplicate"


@patch("src.services.ticket_service.search_similar_tickets")
def test_mid_similarity_routes_to_human_review(mock_search):
    mock_search.return_value = _fake_result(0.70)
    result = ticket_service.process_new_ticket("some title", "some description")
    assert result["decision"] == "human_review"


@patch("src.services.ticket_service.search_similar_tickets")
def test_low_similarity_routes_to_new_ticket(mock_search):
    mock_search.return_value = _fake_result(0.30)
    result = ticket_service.process_new_ticket("some title", "some description")
    assert result["decision"] == "new_ticket"


@patch("src.services.ticket_service.search_similar_tickets")
def test_no_results_routes_to_new_ticket_with_no_match(mock_search):
    mock_search.return_value = []
    result = ticket_service.process_new_ticket("some title", "some description")
    assert result["decision"] == "new_ticket"
    assert result["matched_ticket"] is None


@patch("src.services.ticket_service.search_similar_tickets")
def test_boundary_score_at_auto_duplicate_threshold(mock_search):
    """Score exactly AT the threshold should count as auto_duplicate (>=, not >)."""
    mock_search.return_value = _fake_result(ticket_service.AUTO_DUPLICATE_THRESHOLD)
    result = ticket_service.process_new_ticket("some title", "some description")
    assert result["decision"] == "auto_duplicate"


@patch("src.services.ticket_service.search_similar_tickets")
def test_boundary_score_at_human_review_threshold(mock_search):
    mock_search.return_value = _fake_result(ticket_service.HUMAN_REVIEW_THRESHOLD)
    result = ticket_service.process_new_ticket("some title", "some description")
    assert result["decision"] == "human_review"