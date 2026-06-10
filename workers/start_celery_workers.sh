#!/bin/bash
# Start Celery workers (Linux/Mac)
# redis must be running first

echo "Starting Celery worker with concurrency 4..."
celery -A workers.celery_app worker -Q default -c 4 --loglevel=info

# For multiple workers in background example:
# celery -A workers.celery_app worker -c 2 -n worker1@%h &
# celery -A workers.celery_app worker -c 2 -n worker2@%h &
