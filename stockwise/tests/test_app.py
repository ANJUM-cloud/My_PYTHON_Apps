import re

CREATE = {"title": "Widget", "description": "Steel", "quantity": "10", "unit_price": "2.50", "reorder_level": "5"}
UPDATE = {"title": "Widget Pro", "description": "Steel", "quantity": "3", "unit_price": "3.75", "reorder_level": "5"}
BAD = {"title": "Bad", "quantity": "abc", "unit_price": "1", "reorder_level": "5"}
PASSWORD = "correct-horse-battery"


def register(client, email="learner@example.com", password=PASSWORD):
    return client.post("/register", data={"email": email, "password": password}, follow_redirects=True)


def first_item_id(client):
    html = client.get("/dashboard").data.decode()
    match = re.search(r"/items/(\d+)/update", html)
    assert match, "no record found on dashboard"
    return int(match.group(1))


def test_home_and_health(client):
    assert client.get("/").status_code == 200
    result = client.get("/health")
    assert result.status_code == 200
    assert result.json["status"] == "ok"
    assert result.json["database"] == "ok"


def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_registration_and_dashboard(client):
    response = register(client)
    assert response.status_code == 200
    assert b"learner@example.com" in response.data


def test_short_password_rejected(client):
    response = register(client, "short@example.com", "tiny")
    assert b"at least 10 characters" in response.data


def test_duplicate_email_rejected(client, other_client):
    register(client)
    response = register(other_client)
    assert b"unused email" in response.data


def test_login_logout_flow(client):
    register(client)
    assert client.post("/logout", follow_redirects=True).status_code == 200
    assert client.get("/dashboard").status_code == 302
    bad = client.post("/login", data={"email": "learner@example.com", "password": "wrong-password"}, follow_redirects=True)
    assert b"not recognised" in bad.data
    good = client.post("/login", data={"email": "learner@example.com", "password": PASSWORD}, follow_redirects=True)
    assert b"learner@example.com" in good.data


def test_create_and_read(client):
    register(client)
    response = client.post("/items/create", data=CREATE, follow_redirects=True)
    assert b"Record created." in response.data
    assert b'Widget' in response.data


def test_update(client):
    register(client)
    client.post("/items/create", data=CREATE)
    item_id = first_item_id(client)
    response = client.post(f"/items/{item_id}/update", data=UPDATE, follow_redirects=True)
    assert b"Record updated." in response.data
    assert b'Low stock' in response.data


def test_delete(client):
    register(client)
    client.post("/items/create", data=CREATE)
    item_id = first_item_id(client)
    response = client.post(f"/items/{item_id}/delete", follow_redirects=True)
    assert b"Record deleted." in response.data
    assert b"No records yet" in response.data


def test_invalid_input_rejected(client):
    register(client)
    response = client.post("/items/create", data=BAD, follow_redirects=True)
    assert b"whole number" in response.data
    assert b"No records yet" in response.data
    blank = client.post("/items/create", data={**CREATE, "title": "   "}, follow_redirects=True)
    assert b"is required" in blank.data


def test_users_cannot_access_each_other_records(client, other_client):
    register(client, "owner@example.com")
    client.post("/items/create", data=CREATE)
    item_id = first_item_id(client)

    register(other_client, "intruder@example.com")
    assert b"No records yet" in other_client.get("/dashboard").data
    assert other_client.post(f"/items/{item_id}/update", data=UPDATE).status_code == 404
    assert other_client.post(f"/items/{item_id}/delete").status_code == 404

    # the owner's record is untouched
    assert b'Widget' in client.get("/dashboard").data


def test_csrf_is_enforced(csrf_client):
    response = csrf_client.post("/register", data={"email": "x@example.com", "password": PASSWORD})
    assert response.status_code == 400
