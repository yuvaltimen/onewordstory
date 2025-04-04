docker build --platform linux/amd64 -t yuvaltimen/onewordstory . 

docker push yuvaltimen/onewordstory 

gcloud run deploy onewordstory \
  --image=docker.io/yuvaltimen/onewordstory \
  --platform=managed \
  --region=us-east1 \
  --allow-unauthenticated \
  --set-env-vars REDIS_HOST=<redis-host>
