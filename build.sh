#!/usr/bin/env bash
# Render build script
set -o errexit

pip install -r requirements.txt

cd fashion_ecommerce_api
python manage.py collectstatic --no-input
python manage.py migrate
