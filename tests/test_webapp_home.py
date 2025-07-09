from starlette.testclient import TestClient


def test_home_contains_message(test_client: TestClient):
    response = test_client.get("/")
    assert response.status_code == 200
    target_message = "Hi there!"
    assert target_message in response.text
