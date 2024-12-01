from flask import Flask, request, jsonify, render_template
from flask_bcrypt import Bcrypt
import sys
sys.path.append("..")
import os
import pika
import uuid
from dotenv import load_dotenv
from flask_cors import CORS
from configurations import database_configuration, redis_configuration  
from helper import helper


dot_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dot_env_path)


app = Flask(__name__)
CORS(app)


app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['ALLOWED_EXTENSIONS'] = {'csv', 'xlsx'}

max_content_length = int(os.getenv('MAX_CONTENT_LENGTH', 10 * 1024 * 1024 * 1024))  # Default 10 GB


redis_conn = redis_configuration.get_redis_connection()

rabbitmq_host = os.getenv('RABBITMQ_HOST')
connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
channel = connection.channel()


bcrypt = Bcrypt(app)




@app.route('/register', methods=['POST'])
def register():
    """
    Endpoint to register a new user.

    **Purpose**:
    - Allows a new user to create an account with a username and password.

    **Process**:
    1. Accepts a JSON payload containing `username` and `password`.
    2. Validates that both fields are provided.
    3. Checks if the username already exists in the database.
    4. Hashes the password and stores the user in the database.
    5. Generates a JWT token for the newly registered user.

    **Request**:
    - Method: POST
    - Payload: 
      {
          "username": "example_user",
          "password": "example_password"
      }

    **Response**:
    - Success (201): 
      {
          "message": "User registered successfully!",
          "token": "<JWT_token>"
      }
    - Error (400): Username and password missing or user already exists.

    **Returns**:
    - A success message with a token if registration is successful.
    - An error message if the username already exists or validation fails.
    """

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required!'}), 400

    users_collection = database_configuration.get_users_collection()
    if users_collection.find_one({'username': username}):
        return jsonify({'message': 'User already exists!'}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
    user_id = users_collection.insert_one({'username': username, 'password': hashed_password}).inserted_id
    token = helper.generate_token(str(user_id),app.config['SECRET_KEY'])

    return jsonify({'message': 'User registered successfully!', 'token': token}), 201



@app.route('/login', methods=['POST'])
def login():
    """
    Endpoint to log in an existing user.

    **Purpose**:
    - Authenticates a user with a valid username and password.

    **Process**:
    1. Accepts a JSON payload containing `username` and `password`.
    2. Validates the provided credentials against the database.
    3. If credentials are valid:
        - Stores the username in Redis with a 1-hour expiry.
        - Generates a JWT token for the user.
    4. If credentials are invalid:
        - Returns an error response.

    **Request**:
    - Method: POST
    - Payload: 
      {
          "username": "example_user",
          "password": "example_password"
      }

    **Response**:
    - Success (200): 
      {
          "message": "Login successful!",
          "token": "<JWT_token>"
      }
    - Error (400/401): Invalid credentials or missing fields.

    **Returns**:
    - A success message with a token if login is successful.
    - An error message if validation or authentication fails.
    """

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required!'}), 400

    users_collection = database_configuration.get_users_collection()
    user = users_collection.find_one({'username': username})
    if not user or not bcrypt.check_password_hash(user['password'], password):
        return jsonify({'message': 'Invalid credentials!'}), 401

    redis_conn.setex(f"user:{username}", 3600, str(username))  # 1-hour expiry
    token = helper.generate_token(str(user['username']),app.config['SECRET_KEY'])

    return jsonify({'message': 'Login successful!', 'token': token}), 200



@app.route('/welcome', methods=['GET'])
def welcome():
    """
    Endpoint to display a welcome page for logged-in users.

    **Purpose**:
    - Verifies the user's JWT token and displays a personalized welcome page.

    **Process**:
    1. Checks for an `Authorization` header containing a valid JWT token.
    2. Decodes the token to validate it.
    3. Retrieves the user's session data from Redis.
    4. If the token or session data is invalid, an error response is returned.
    5. Renders a `welcome.html` page with the user's username.

    **Request**:
    - Method: GET
    - Headers: 
      Authorization: "Bearer <JWT_token>"

    **Response**:
    - Success (200): Rendered HTML page with a personalized message.
    - Error (403/401): Token missing, invalid, or expired.

    **Returns**:
    - A rendered HTML welcome page if the user is authenticated.
    - An error message if the token or session data is invalid.
    """

    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token is missing!'}), 403

    token = token.split(" ")[1] if " " in token else token
    decoded_token = helper.decode_token(token,app.config['SECRET_KEY'])
    if not decoded_token:
        return jsonify({'message': 'Invalid or expired token!'}), 403

    user_id = decoded_token['user_id']
    username = redis_conn.get(f"user:{user_id}")
    if not username:
        return jsonify({'message': 'Session expired, please log in again.'}), 401

    return render_template('welcome.html', username=username.decode('utf-8'))



@app.route('/upload', methods=['POST'])
def upload_file():
    """
    Endpoint to handle file uploads.

    **Authorization**: Requires a valid token in the `Authorization` header.

    Validates:
    - Token validity.
    - File presence in the request.
    - File format (only CSV and XLSX allowed).
    - File size (maximum of 10GB).

    **Process**:
    - Checks for an active user session using Redis.
    - Queues the file for background processing via RabbitMQ.

    Returns:
        - 403: If token is missing or invalid.
        - 401: If the user's session has expired.
        - 400: If the file is missing, invalid, or exceeds the size limit.
        - 202: If the file is successfully queued for processing.
    """

    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token is missing!'}), 403

    token = token.split(" ")[1] if " " in token else token
    decoded_token = helper.decode_token(token, app.config['SECRET_KEY'])
    if not decoded_token:
        return jsonify({'message': 'Invalid or expired token!'}), 403
    
    user_id = decoded_token['user_id']
    username = redis_conn.get(f"user:{user_id}")
    if not username:
        return jsonify({'message': 'Session expired, please log in again.'}), 401

   
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'message': 'No selected file'}), 400

    if not helper.allowed_file(file.filename,app.config['ALLOWED_EXTENSIONS']):
        return jsonify({'message': 'Invalid file format. Only CSV and XLSX files are allowed.'}), 400
    
    file.seek(0, os.SEEK_END)  
    file_size = file.tell()   
    
    if file_size > max_content_length:
        return jsonify({'message': f'File size exceeds the maximum allowed limit of 10GB ({max_content_length / (1024 * 1024 * 1024)}GB).'}), 400

   
    file_id = str(uuid.uuid4())

    
    message = {'file_id': file_id, 'file_content': file.read().decode('latin1')}
    redis_conn.set(f'progress_{file_id}',0)
    channel.basic_publish(exchange='', routing_key='file_processing_queue', body=str(message))

    return jsonify({'file_id': file_id, 'status': 'File queued for processing'}), 202




@app.route('/progress/<file_id>', methods=['GET'])
def check_progress(file_id):
    """
    Endpoint to fetch the progress of a file upload.

    **Authorization**: Requires a valid token in the `Authorization` header.

    **Process**:
    - Retrieves the progress of the given file ID from Redis.

    Args:
        file_id (str): Unique ID of the uploaded file.

    Returns:
        - 403: If token is missing or invalid.
        - 200: Progress status of the file upload.
    """

    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token is missing!'}), 403

    token = token.split(" ")[1] if " " in token else token
    decoded_token = helper.decode_token(token,app.config['SECRET_KEY'])
    if not decoded_token:
        return jsonify({'message': 'Invalid or expired token!'}), 403
    
    user_id = decoded_token['user_id']
    username = redis_conn.get(f"user:{user_id}")
    if not username:
        return jsonify({'message': 'Session expired, please log in again.'}), 401
    
    progress = redis_conn.get(f'progress_{file_id}')
    if not progress:
        return jsonify({'error': 'File not being processed'}), 404

    return jsonify({'progress': float(progress)})


@app.route('/movies', methods=['GET'])
def list_movies():
    """
    Endpoint to fetch a paginated and sortable list of movies/shows.

    **Authorization**: Requires a valid token in the `Authorization` header.

    **Query Parameters**:
    - `page` (int): Page number for pagination (default: 1).
    - `limit` (int): Number of items per page (default: 10).
    - `sort_by` (str): Field to sort by (e.g., 'date_added', 'release_year', 'duration').

    **Process**:
    - Fetches data from the database.
    - Supports pagination and sorting.

    Returns:
        - 403: If token is missing or invalid.
        - 200: Paginated list of movies/shows.
    """

    token = request.headers.get('Authorization')
    if not token:
        return jsonify({'message': 'Token is missing!'}), 403

    token = token.split(" ")[1] if " " in token else token
    decoded_token = helper.decode_token(token, app.config['SECRET_KEY'])
    if not decoded_token:
        return jsonify({'message': 'Invalid or expired token!'}), 403
    
    user_id = decoded_token['user_id']
    username = redis_conn.get(f"user:{user_id}")
    if not username:
        return jsonify({'message': 'Session expired, please log in again.'}), 401

    
    try:
        page = int(request.args.get('page', 1))
        if page < 1:
            return jsonify({'message': 'Invalid page number! Page must be a positive integer.'}), 400
    except ValueError:
        return jsonify({'message': 'Invalid page number! Must be an integer.'}), 400


    try:
        per_page = int(request.args.get('per_page', 10))
        if per_page < 1:
            return jsonify({'message': 'Invalid per_page number! Must be a positive integer.'}), 400
    except ValueError:
        return jsonify({'message': 'Invalid per_page number! Must be an integer.'}), 400

    sort_by = request.args.get('sort_by', 'date_added')
    order = request.args.get('order', 'asc')

    valid_sort_fields = ['date_added', 'release_year', 'duration']
    if sort_by not in valid_sort_fields:
        return jsonify({'message': f"Invalid sort field! Must be one of {valid_sort_fields}."}), 400

    sort_order = 1 if order == 'asc' else -1
    skip_count = (page - 1) * per_page

    
    movies_collection = database_configuration.get_movies_collection()
    total_movies = movies_collection.count_documents({})

    
    total_pages = (total_movies + per_page - 1) // per_page
    if page > total_pages:
        return jsonify({'message': f'Page number exceeds total pages! Total pages: {total_pages}.'}), 400

    
    movies_cursor = movies_collection.find().sort(sort_by, sort_order).skip(skip_count).limit(per_page)

    movies = [
        {
               "title": movie.get('title'),
                    "release_year": movie.get('release_year'),
                    "duration": movie.get('duration', 0),
                    "date_added": movie.get('date_added'),
                    "description": movie.get('description'),
                    "director": movie.get('director'),
                    "cast": movie.get('cast', []),
                    "country": movie.get('country'),
                    "rating": movie.get('rating'),
                    "listed_in": movie.get('listed_in', []),
                    "show_id": movie.get('show_id'),
                    "type": movie.get('type')
        }
        for movie in movies_cursor
    ]

    return jsonify({
        'movies': movies,
        'pagination': {
            'current_page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'total_movies': total_movies
        }
    }), 200


@app.route('/')
def index():
    """
    Endpoint for the application's homepage.

    **Purpose**:
    - Serves the main HTML page of the application.

    **Process**:
    - Renders the `index.html` template.

    Returns:
        - HTML content for the homepage.
    """
    
    return render_template('index.html')



if __name__ == '__main__':
    app.run(debug=True)
