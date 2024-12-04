import aioredis
import os
from dotenv import load_dotenv
import sys
sys.path.append("..")
from logger import logger

    
log=logger.get_logger("redis_configuration")
dot_env_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dot_env_path)






try:
    redis_conn = aioredis.from_url('redis://localhost', decode_responses=True)
    # Check the connection
    if redis_conn.ping():
        log.info("Connected to Redis!")
    
except aioredis.ConnectionError as e:
    log.error(f"Redis connection error: {e}")
    sys.exit(0)


def get_redis_connection():
    """
    Retrieves the Redis connection object.

    **Purpose**:
    - Provides a centralized way to access the Redis connection instance, which is used for caching, session management, and other high-speed data storage tasks.

    **Returns**:
    - `Redis`: The Redis connection object.
    """
    return redis_conn





