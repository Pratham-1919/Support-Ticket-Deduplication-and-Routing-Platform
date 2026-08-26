"""
Validates requirements #5, #6, #7: full CRUD on tickets, search/filter,
and pagination. Runs a real end-to-end lifecycle against the live app +
database (not mocked), since the point is confirming the whole stack --
API, ORM, Postgres -- actually works together.
"""


def test_full_ticket_lifecycle(client, admin_headers):
    create_resp = client.post(
        "/tickets/",
        json={
            "title": "CRUD lifecycle test ticket",
            "description": "Exercises create, read, status-update, and delete in one pass",
            "module": "Platform",
            "ticket_type": "bug_report",
        },
        headers=admin_headers,
    )
    assert create_resp.status_code == 200
    ticket_id = create_resp.json()["ticket_id"]

    get_resp = client.get(f"/tickets/{ticket_id}", headers=admin_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == ticket_id
    assert get_resp.json()["title"] == "CRUD lifecycle test ticket"

    update_resp = client.put(
        f"/tickets/{ticket_id}/status", json={"status": "resolved"}, headers=admin_headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "resolved"

    confirm_resp = client.get(f"/tickets/{ticket_id}", headers=admin_headers)
    assert confirm_resp.json()["status"] == "resolved"

    delete_resp = client.delete(f"/tickets/{ticket_id}", headers=admin_headers)
    assert delete_resp.status_code == 200
    assert delete_resp.json()["deleted"] is True

    missing_resp = client.get(f"/tickets/{ticket_id}", headers=admin_headers)
    assert missing_resp.status_code == 404


def test_invalid_status_update_is_rejected(client, admin_headers):
    create_resp = client.post(
        "/tickets/",
        json={
            "title": "Invalid status test ticket",
            "description": "Used to test that bad status values are rejected",
            "module": "Platform",
            "ticket_type": "bug_report",
        },
        headers=admin_headers,
    )
    ticket_id = create_resp.json()["ticket_id"]

    resp = client.put(
        f"/tickets/{ticket_id}/status", json={"status": "not_a_real_status"}, headers=admin_headers
    )
    assert resp.status_code == 400

    client.delete(f"/tickets/{ticket_id}", headers=admin_headers)  # cleanup


def test_unknown_module_is_rejected(client, admin_headers):
    resp = client.post(
        "/tickets/",
        json={
            "title": "Bad module test",
            "description": "Should be rejected because the module does not exist",
            "module": "NotARealModuleXYZ",
            "ticket_type": "bug_report",
        },
        headers=admin_headers,
    )
    assert resp.status_code == 422


def test_pagination_and_filtering(client, admin_headers):
    resp = client.get("/tickets/?module=Platform&page=1&page_size=5", headers=admin_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["page_size"] == 5
    assert len(body["results"]) <= 5
    for ticket in body["results"]:
        assert ticket["module"].lower() == "platform"


def test_pagination_rejects_invalid_page(client, admin_headers):
    resp = client.get("/tickets/?page=0", headers=admin_headers)
    assert resp.status_code == 400

    resp = client.get("/tickets/?page_size=500", headers=admin_headers)
    assert resp.status_code == 400


def test_module_crud(client, admin_headers):
    create_resp = client.post("/modules/", json={"name": "PytestTempModule"}, headers=admin_headers)
    assert create_resp.status_code == 200
    module_id = create_resp.json()["id"]

    get_resp = client.get(f"/modules/{module_id}", headers=admin_headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "PytestTempModule"

    update_resp = client.put(
        f"/modules/{module_id}", json={"name": "PytestTempModuleRenamed"}, headers=admin_headers
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "PytestTempModuleRenamed"

    delete_resp = client.delete(f"/modules/{module_id}", headers=admin_headers)
    assert delete_resp.status_code == 200


def test_duplicate_module_name_rejected(client, admin_headers):
    resp = client.post("/modules/", json={"name": "Platform"}, headers=admin_headers)
    assert resp.status_code == 409