#!/bin/bash
gcloud run deploy nanami-products --source /home/risa/dev/nanami-products --region asia-northeast1 --allow-unauthenticated --remove-env-vars=DATABASE_URL --set-secrets=DATABASE_URL=DATABASE_URL:latest
