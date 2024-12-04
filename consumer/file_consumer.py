import aio_pika
import aiofiles
import csv
import asyncio
import os
import sys
sys.path.append("..")
import logging
from pymongo import ASCENDING
import redis.asyncio as redis
from dotenv import load_dotenv
from configurations import database_configuration, redis_configuration
from logger import logger

# Load environment variables from .env file
dot_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dot_env_path)

# RabbitMQ and Redis connection details from environment variables
rabbitmq_host = os.getenv('RABBITMQ_HOST', 'localhost')
rabbitmq_port = os.getenv('RABBITMQ_PORT', '5672')
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = os.getenv('REDIS_PORT', '6379')
file_processing_queue = os.getenv('FILE_PROCESSING_QUEUE')

# Redis connection (Asynchronous)
redis_conn = redis_configuration.get_redis_connection()

# MongoDB collection for storing movie data
movies_collection = database_configuration.get_movies_collection()

# Create worker folder if it doesn't exist
worker_folder = os.getenv('WORKER_FOLDER')
os.makedirs(worker_folder, exist_ok=True)

# MongoDB index creation for fields `date_added`, `release_year`, `duration`
movies_collection.create_index([('date_added', ASCENDING), ('release_year', ASCENDING), ('duration', ASCENDING)])

# Initialize logger
log = logger.get_logger("file_consumer")

# Function to update processing progress in Redis
async def update_progress(file_id, progress):
    """
    Updates the file processing progress in Redis.
    """
    log.info(f'Progress for file {file_id}: {progress}%')
    await redis_conn.set(f'progress_{file_id}', progress)

# Function to process the CSV file and insert data into MongoDB
async def process_csv(file_id, file_content):
    """
    Processes the CSV file and inserts data into MongoDB.
    """
    try:
        # Save the file to disk
        file_path = os.path.join(worker_folder, f"{file_id}.csv")
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)

        # Read the CSV file and insert into MongoDB
        with open(file_path, 'r', encoding='utf-8') as csv_file:
            reader = csv.DictReader(csv_file)
            total_rows = sum(1 for _ in reader) 
            csv_file.seek(0)

            first_row_skipped = False
            rows_processed = 0
            for row in reader:
                if not first_row_skipped:
                    first_row_skipped = True
                    continue  # Skip the header

                # Insert each row into MongoDB
                await movies_collection.insert_one({
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

                # Update progress every 10 rows
                if rows_processed % 10 == 0 or rows_processed == total_rows:
                    progress = (rows_processed / total_rows) * 100
                    await update_progress(file_id, int(progress))

        await update_progress(file_id, 100)
        log.info(f"File {file_id} processed successfully.")

        # Clean up the file after processing
        os.remove(file_path)

    except Exception as e:
        log.error(f"Error processing file {file_id}: {e}")
        await update_progress(file_id, -1)  # Use -1 to indicate an error

# Callback function to process RabbitMQ messages
async def callback(message: aio_pika.IncomingMessage):
    async with message.process():
        file_id = message.body.get('file_id')
        file_content = message.body.get('file_content').encode('latin1')  # Decode file content

        log.info(f"Processing file {file_id}...")
        await process_csv(file_id, file_content)

# Function to start the worker that listens for RabbitMQ messages
async def start_worker():
    connection = await aio_pika.connect_robust(
        host=rabbitmq_host,
        port=int(rabbitmq_port)
    )
    channel = await connection.channel()

    # Declare the queue
    await channel.declare_queue(file_processing_queue, durable=False)

    # Start consuming messages from the queue
    await channel.basic_consume(callback, queue=file_processing_queue)

    log.info(f'Waiting for messages in the {file_processing_queue} queue...')
    # Start the event loop to process the queue
    await asyncio.Future()  # Keeps the worker running

# Main entry point for the worker
if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_worker())
