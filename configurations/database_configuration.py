from pymongo import MongoClient
from dotenv import load_dotenv
import os


dot_env_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dot_env_path)
mongo_uri=os.getenv('MONGO_URI')
mongo_client = MongoClient(mongo_uri)
db=mongo_client["imdb"]

def get_movies_collection():
    return db['movies']


def get_users_collection():
    return db['users']