def test_health_check(client):
    """Test that the health endpoint returns OK."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_api_docs_available(client):
    """Test that API docs are accessible."""
    response = client.get("/docs")
    assert response.status_code == 200
