import redis
import os
from dotenv import load_dotenv
import sys
sys.path.append("..")
from logger import logger

log=logger.get_logger("redis_configuration")
dot_env_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dot_env_path)


redis_host=os.getenv('REDIS_HOST')
redis_port=os.getenv('REDIS_PORT')


try:
    # Connect to the Redis server
    redis_conn = redis.Redis(host=redis_host, port=redis_port, db=0)
    
    # Check the connection
    if redis_conn.ping():
        log.info("Connected to Redis!")
    
except redis.ConnectionError as e:
    log.error(f"Redis connection error: {e}")
    sys.exit(0)


def get_redis_connection():
    return redis_conn





