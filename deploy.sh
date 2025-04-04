gcloud run deploy onewordstory \
  --image=docker.io/yuvaltimen/onewordstory \
  --platform=managed \
  --region=us-east1 \
  --allow-unauthenticated \
  --set-env-vars REDIS_HOST=<redis-host>
