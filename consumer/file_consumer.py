import pika
import csv
from pymongo import ASCENDING
import sys
sys.path.append("..")
import os
from configurations import database_configuration,redis_configuration
from dotenv import load_dotenv
from logger import logger

log=logger.get_logger("file_consumer")
# Load environment variables from .env file
dot_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dot_env_path)

# RabbitMQ and Redis connection details from environment variables
rabbitmq_host = os.getenv('RABBITMQ_HOST')
file_processing_queue = os.getenv('FILE_PROCESSING_QUEUE')
redis_host = os.getenv('REDIS_HOST')
redis_port = os.getenv('REDIS_PORT')

# Redis connection
redis_conn = redis_configuration.get_redis_connection()

# MongoDB collection for storing movie data
movies_collection = database_configuration.get_movies_collection()


worker_folder = os.getenv('WORKER_FOLDER')
os.makedirs(worker_folder, exist_ok=True)

#MongoDB index creation for fields `date_added`, `release_year`, `duration`
movies_collection.create_index([('date_added', ASCENDING), ('release_year', ASCENDING), ('duration', ASCENDING)])

def update_progress(file_id, progress):
    """
    Updates the file processing progress in Redis.
    """
    redis_conn.set(f'progress_{file_id}', progress)

def process_csv(file_id, file_content):
    """
    Processes the CSV file and inserts data into MongoDB.
    """
    try:
       
        file_path = os.path.join(worker_folder, f"{file_id}.csv")
        with open(file_path, 'wb') as f:
            f.write(file_content)

        
        with open(file_path, 'r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            total_rows = sum(1 for _ in reader) 
            csv_file.seek(0)  

            
            first_row_skipped = False

            
            rows_processed = 0
            for row in reader:
                if not first_row_skipped:
                    first_row_skipped = True
                    continue  
                

            
                movies_collection.insert_one({
                    "title": row.get('title'),
                    "release_year": row.get('release_year'),
                    "duration": row.get('duration'),
                    "date_added": row.get('date_added'),
                    "description": row.get('description'),
                    "director": row.get('director'),
                    "cast": row.get('cast'),
                    "country": row.get('country'),
                    "rating": row.get('rating'),
                    "listed_in": row.get('listed_in'),
                    "show_id": row.get('show_id'),
                    "type": row.get('type')
                })
                rows_processed += 1

                
                if rows_processed % 10 == 0 or rows_processed == total_rows:
                    progress = (rows_processed / total_rows) * 100
                    update_progress(file_id, int(progress))

        
        update_progress(file_id, 100)
        log.info(f"File {file_id} processed successfully.")

        
        os.remove(file_path)

    except Exception as e:
        log.error(f"Error processing file {file_id}: {e}")
        update_progress(file_id, -1)  # Use -1 to indicate an error

def callback(ch, method, properties, body):
   
    message = eval(body.decode('utf-8'))  # Convert message from RabbitMQ back to dictionary
    file_id = message.get('file_id')
    file_content = message.get('file_content').encode('latin1')  # Decode file content

    log.info(f"Processing file {file_id}...")
    process_csv(file_id, file_content)

   
    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_worker():
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
    channel = connection.channel()

    
    channel.queue_declare(queue=file_processing_queue)

 
    channel.basic_consume(queue=file_processing_queue, on_message_callback=callback)

    log.info(f'Waiting for messages in the {file_processing_queue} queue...')
    channel.start_consuming()

start_worker()
