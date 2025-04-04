from flask import Flask, render_template, request, Response
import redis
import os


REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = 6379

STORY_KEY = "story"
CHANNEL = "story_updates"
RATE_LIMIT_PREFIX = "user:"

app = Flask(__name__)
r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)


def event_stream():
    pubsub = r.pubsub()
    pubsub.subscribe(CHANNEL)

    for message in pubsub.listen():
        if message['type'] == 'message':
            story = " ".join(r.lrange(STORY_KEY, 0, -1))
            yield f"data: {story}\n\n"


@app.route("/stream")
def stream():
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/", methods=["GET", "POST"])
def index():
    ip = request.remote_addr
    rate_key = f"{RATE_LIMIT_PREFIX}{ip}"

    if request.method == "POST":
        if r.exists(rate_key):
            return "Rate limited!", 429  # Prevent spam

        word = request.form.get("word", "").strip()
        if word:
            r.rpush(STORY_KEY, word)
            r.publish(CHANNEL, "update")
            r.setex(rate_key, 3, "1")  # 3-second cooldown per IP

        return "", 204

    story = " ".join(r.lrange(STORY_KEY, 0, -1))
    return render_template("index.html", story=story)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)