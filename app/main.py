import os
from app.zibbit import ZibbitGame
from flask import Flask, render_template, request, Response, stream_with_context

REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = 6379

app = Flask(__name__)
zg = ZibbitGame(redis_host=REDIS_HOST, redis_port=REDIS_PORT)

@app.route('/', methods=['GET'])
def index():
    global zg
    print("requested /")
    return render_template("index.html", **zg.get_game_state())

@app.route('/events')
def sse_events():
    global zg
    print("requested /events")
    return Response(stream_with_context(zg.event_stream()), mimetype="text/event-stream")

@app.route('/submit_candidate', methods=['POST'])
def submit_candidate():
    global zg
    print("requested /submit_candidate")
    phrase = request.form.get("candidate", "").strip()
    if zg.handle_phrase_submission(phrase):
        return '', 204
    else:
        return '', 400

@app.route('/vote', methods=['POST'])
def vote():
    print("requested /vote")
    global zg
    candidate = request.form.get("phrase", "").strip()
    if not candidate:
        return 'Empty', 400

    if zg.handle_vote(candidate):
        return '', 204
    else:
        return '', 400

@app.route('/flag_word', methods=['POST'])
def submit_word_flag():
    global zg
    print("requested /flag_word")
    word = request.form.get("word", "").strip()
    if zg.handle_word_flag(word):
        return '', 204
    else:
        return '', 400


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8080, debug=True)
