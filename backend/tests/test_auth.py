def test_register_login_and_refresh(client):
    test_client, _, _, _ = client

    register = test_client.post(
        "/auth/register",
        json={"email": "USER@example.com", "password": "password123"},
    )
    assert register.status_code == 201
    tokens = register.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]

    login = test_client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )
    assert login.status_code == 200
    assert login.json()["access_token"]

    refresh = test_client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refresh.status_code == 200
    assert refresh.json()["access_token"]


def test_duplicate_registration_is_rejected(client):
    test_client, _, _, _ = client
    body = {"email": "dup@example.com", "password": "password123"}

    assert test_client.post("/auth/register", json=body).status_code == 201
    response = test_client.post("/auth/register", json=body)

    assert response.status_code == 409

