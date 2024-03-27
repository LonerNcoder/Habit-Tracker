#! /bin/sh
python3 -m celery -A app.celery worker -l info