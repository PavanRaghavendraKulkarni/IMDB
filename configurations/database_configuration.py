from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

# Load environment variables
dot_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dot_env_path)

# Get MongoDB URI
mongo_uri = os.getenv('MONGO_URI')

# Initialize Motor client for asynchronous MongoDB operations
mongo_client = AsyncIOMotorClient(mongo_uri)
db = mongo_client["imdb"]

def get_movies_collection():
    """
    Retrieves the movies collection from the database asynchronously.

    **Purpose**:
    - Provides access to the `movies` collection in the database, which stores information about movies and shows.

    **Returns**:
    - `Collection`: A reference to the `movies` collection in the MongoDB database.
    """
    return db['movies']

def get_users_collection():
    """
    Retrieves the users collection from the database asynchronously.

    **Purpose**:
    - Provides access to the `users` collection in the database, which stores user credentials and authentication data.

    **Returns**:
    - `Collection`: A reference to the `users` collection in the MongoDB database.
    """
    return db['users']
