from flask import Flask, render_template, request, Response
import redis
import os
import time
import threading


REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = 6379


STORY_KEY = "story"
GAME_KEY = "game"
GAME_COOLDOWN_KEY = "game_cooldown"
STORY_CHANNEL = "story_updates"
TIMER_CHANNEL = "timer_updates"
GAME_TIMEOUT_SECONDS = 60
GAME_COOLDOWN_TTL = 10
RATE_LIMIT_SECONDS = 3
RATE_LIMIT_PREFIX = "user:"


app = Flask(__name__)
r = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True)


def event_stream():
    pubsub = r.pubsub()
    pubsub.subscribe(STORY_CHANNEL)

    for message in pubsub.listen():
        if message['type'] == 'message':
            if message['data'] == "clear":
                yield f"data: |\n\n"  # Send empty story to the client
            else:
                story = " ".join(r.lrange(STORY_KEY, 0, -1))
                timer = r.ttl(GAME_KEY)
                yield f"data: {story}|{timer if timer > 0 else 0}\n\n"


def timer_stream():
    pubsub = r.pubsub()
    pubsub.subscribe(TIMER_CHANNEL)

    for message in pubsub.listen():
        if message['type'] == 'message':
            yield f"data: {message['data']}\n\n"


@app.route("/stream")
def stream():
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/timer")
def timer():
    return Response(timer_stream(), mimetype="text/event-stream")


@app.route("/", methods=["GET", "POST"])
def index():
    ip = request.remote_addr
    rate_key = f"{RATE_LIMIT_PREFIX}{ip}"

    if request.method == "POST":
        if r.exists(rate_key) or r.exists(GAME_COOLDOWN_KEY):
            return "Rate limited!", 429

        word = request.form.get("word", "").strip()
        if word:
            r.rpush(STORY_KEY, word)
            r.publish(STORY_CHANNEL, "update")
            r.setex(rate_key, RATE_LIMIT_SECONDS, "1")
        
            # If the timer isn't already running, start it
            if not r.exists(GAME_KEY):
                r.setex(GAME_KEY, GAME_TIMEOUT_SECONDS, "1")
                threading.Thread(target=start_timer, daemon=True).start()

        return "", 204

    story = " ".join(r.lrange(STORY_KEY, 0, -1))
    timer = r.ttl(GAME_KEY)
    return render_template("index.html", story=story, timer=timer if timer > 0 else 0)


def start_timer():
    """Handles the countdown timer and triggers endgame()"""
    while r.ttl(GAME_KEY) > 0:
        time_left = r.ttl(GAME_KEY)
        r.publish(TIMER_CHANNEL, str(time_left))
        time.sleep(1)

    r.publish(TIMER_CHANNEL, "0")  # Ensure UI updates
    endgame()  # Call endgame when time runs out


def endgame():
    print("Game Over! Timer expired.")
    r.setex(GAME_COOLDOWN_KEY, GAME_COOLDOWN_TTL, "1")
    r.publish(STORY_CHANNEL, "clear")
    r.delete(STORY_KEY)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)