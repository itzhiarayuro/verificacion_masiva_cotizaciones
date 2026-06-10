@echo off
REM Start one or more Celery workers for Auditor de Cotizaciones
REM Requires Redis running (docker compose up -d redis)

echo Starting Celery worker(s)...
echo Make sure Redis is reachable on localhost:6379

REM Single worker with 4 concurrent processes
celery -A workers.celery_app worker -Q default -c 4 --loglevel=info

REM To run multiple dedicated workers, open several terminals and use -n:
REM celery -A workers.celery_app worker --concurrency=2 -n worker1@%h
REM celery -A workers.celery_app worker --concurrency=2 -n worker2@%h
