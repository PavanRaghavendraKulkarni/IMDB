from quart import Quart, request, jsonify, render_template
import pika
from quart_bcrypt import Bcrypt 
import os
import aio_pika
import uuid
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from quart_cors import cors
import sys
sys.path.append("..")
from configurations import database_configuration,redis_configuration
from helper import helper

# Load environment variables
dot_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dot_env_path)

app = Quart(__name__)
app = cors(app)

# Configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY')
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH',16*1024*1024))

# Initialize async bcrypt
bcrypt = Bcrypt(app)

# Initialize MongoDB
db_client = AsyncIOMotorClient(os.getenv('MONGO_URI'))
users_collection = database_configuration.get_users_collection()
movies_collection = database_configuration.get_movies_collection

# Initialize Redis
redis_conn = redis_configuration.get_redis_connection()

rabbitmq_host = os.getenv('RABBITMQ_HOST')
connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
channel = connection.channel()

# Initialize RabbitMQ




# Asynchronous Routes
@app.route('/register', methods=['POST'])
async def register():
    data = await request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required!'}), 400

    existing_user = await users_collection.find_one({'username': username})
    if existing_user:
        return jsonify({'message': 'User already exists!'}), 400

    hashed_password = await bcrypt.generate_password_hash(password).decode('utf-8')
    user_id = (await users_collection.insert_one({'username': username, 'password': hashed_password})).inserted_id

    token = helper.generate_token(str(user_id),app.config['SECRET_KEY'] )
    return jsonify({'message': 'User registered successfully!', 'token': token}), 201

@app.route('/login', methods=['POST'])
async def login():
    data = await request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required!'}), 400

    user = await users_collection.find_one({'username': username})
    if not user:
        return jsonify({'message': 'User not found!'}), 404

    if bcrypt.check_password_hash(user['password'], password):
        redis_conn.setex(f"user:{username}", 3600, str(username))
        token = helper.generate_token(str(user['_id']),app.config['SECRET_KEY'] )
        return jsonify({'message': 'Login successful!', 'token': token, 'welcome': f'Welcome {username}'}), 200
    else:
        return jsonify({'message': 'Invalid credentials!'}), 401

@app.route('/upload', methods=['POST'])
async def upload_file():
    if 'file' not in (await request.files):
        return jsonify({'error': 'No file part'}), 400

    file = (await request.files)['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    file_id = str(uuid.uuid4())
    message = {'file_id': file_id, 'file_content': (file.read()).decode('latin1')}

    channel.basic_publish(exchange='', routing_key='file_processing_queue', body=str(message))
    print(f'========progress_{file_id}========')
    await redis_conn.set(f'progress_{file_id}',0)

    return jsonify({'file_id': file_id, 'status': 'File queued for processing'}), 202

@app.route('/progress/<file_id>', methods=['GET'])
async def check_progress(file_id):
    progress = await redis_conn.get(f'progress_{file_id}')
    if not progress:
        return jsonify({'error': 'File not being processed'}), 404

    return jsonify({'progress': float(progress)})

@app.route('/welcome', methods=['GET'])
async def welcome():
    token = request.headers.get('Authorization')

    if not token:
        return jsonify({'message': 'Token is missing!'}), 403

    decoded_token = helper.decode_token(token,app.config['SECRET_KEY'] )
    if not decoded_token:
        return jsonify({'message': 'Invalid or expired token!'}), 403

    user_id = decoded_token['user_id']

    # Check user session in Redis
    username = redis_conn.get(f"user:{user_id}")
    if not username:
        return jsonify({'message': 'Session expired, please log in again.'}), 401

    # Render the welcome page
    return await render_template('welcome.html', username=username)

@app.route('/')
async def index():
    return await render_template('index.html')





if __name__ == '__main__':
    app.run(debug=True)