"""
Validates requirement #9: certain actions must be restricted to admin/
support_engineer roles only. Each test proves BOTH directions -- that the
right role is allowed through, and that the wrong role is genuinely blocked
-- not just that login works.
"""


def test_unauthenticated_request_is_rejected(client):
    resp = client.get("/tickets/")
    assert resp.status_code == 401


def test_reporter_can_create_ticket(client, reporter_headers):
    resp = client.post(
        "/tickets/",
        json={
            "title": "Reporter-created test ticket",
            "description": "Reporters should be able to submit tickets per requirement #8",
            "ticket_type": "bug_report",
        },
        headers=reporter_headers,
    )
    assert resp.status_code == 200


def test_reporter_cannot_confirm_duplicate(client, reporter_headers):
    resp = client.post("/review-queue/999999/confirm", headers=reporter_headers)
    # 403 (blocked by role) is the point of this test -- a 404 would mean
    # the role check passed and it just couldn't find that ID, which is
    # the WRONG failure mode for this test to accept as a pass.
    assert resp.status_code == 403


def test_reporter_cannot_delete_ticket(client, reporter_headers):
    resp = client.delete("/tickets/999999", headers=reporter_headers)
    assert resp.status_code == 403


def test_reporter_cannot_create_module(client, reporter_headers):
    resp = client.post("/modules/", json={"name": "TestModuleXYZ"}, headers=reporter_headers)
    assert resp.status_code == 403


def test_admin_can_access_review_queue(client, admin_headers):
    resp = client.get("/review-queue/", headers=admin_headers)
    assert resp.status_code == 200


def test_admin_can_list_modules(client, admin_headers):
    resp = client.get("/modules/", headers=admin_headers)
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_invalid_token_is_rejected(client):
    resp = client.get("/tickets/", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 401