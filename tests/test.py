import pytest
import sys
sys.path.append("..")
from app import app
import io

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def auth_token(client):
   
    response = client.post('/login', json={"username": "Pavan", "password": "123"})
    return response.json.get("token")


def test_login_success(client):
    response = client.post('/login', json={"username": "Pavan", "password": "123"})
    assert response.status_code == 200
    assert "token" in response.json

def test_login_invalid_credentials(client):
    response = client.post('/login', json={"username": "wronguser", "password": "wrongpass"})
    assert response.status_code == 401
    assert response.json["message"] == "Invalid credentials!"

def test_login_missing_fields(client):
    response = client.post('/login', json={"username": "Pavan"})
    assert response.status_code == 400
    assert response.json["message"] == "Username and password are required!"


def test_upload_success(client, auth_token):
    file_data = io.BytesIO(b"title,release_date,duration\nMovie A,2023-01-01,120")
    response = client.post(
        '/upload',
        headers={"Authorization": f"Bearer {auth_token}"},
        data={"file": (file_data, "movies.csv")},
        content_type="multipart/form-data"
    )
    assert response.status_code == 202
    assert "file_id" in response.json

def test_upload_missing_auth(client):
    file_data = io.BytesIO(b"title,release_date,duration\nMovie A,2023-01-01,120")
    response = client.post(
        '/upload',
        data={"file": (file_data, "movies.csv")},
        content_type="multipart/form-data"
    )
    assert response.status_code == 403
    assert response.json["message"] == "Token is missing!"

def test_upload_invalid_format(client, auth_token):
    file_data = io.BytesIO(b"Invalid content")
    response = client.post(
        '/upload',
        headers={"Authorization": f"Bearer {auth_token}"},
        data={"file": (file_data, "movies.txt")},
        content_type="multipart/form-data"
    )
    assert response.status_code == 400
    assert response.json["message"] == "Invalid file format. Only CSV and XLSX files are allowed."


    



def test_query_movies_invalid_page(client, auth_token):
    response = client.get('/movies?page=0&sort=release_date', headers={"Authorization": f"Bearer {auth_token}"})
    assert response.status_code == 400

    assert response.json["message"] == "Invalid page number! Page must be a positive integer."

def test_query_movies_missing_auth(client):
    response = client.get('/movies?page=1&sort=release_date')
    assert response.status_code == 403
    assert response.json["message"] == "Token is missing!"



def test_missing_file_upload(client, auth_token):
    response = client.post(
        '/upload',
        headers={"Authorization": f"Bearer {auth_token}"},
        data={},
        content_type="multipart/form-data"
    )
    assert response.status_code == 400
    assert response.json["message"] == "No file part"
