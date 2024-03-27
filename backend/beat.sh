#! /bin/sh

python3 -m celery -A app.celery beat --max-interval 1 -l info