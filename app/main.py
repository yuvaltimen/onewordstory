from datetime import datetime
import json
import os
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from zibbit import ZibbitGame, GAME_EVENTS_CHANNEL_PREFIX

REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_USERNAME = os.getenv('REDIS_USERNAME', 'user')
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'pass')

APP_HOST = os.getenv('APP_HOST', '0.0.0.0')
APP_PORT = int(os.getenv('APP_PORT', '8000'))
zg = ZibbitGame(redis_host=REDIS_HOST, redis_port=REDIS_PORT, redis_user=REDIS_USERNAME, redis_pass=REDIS_PASSWORD)
static_dir = os.path.join(os.path.dirname(__file__), "static")

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up FastAPI app...")
    asyncio.create_task(zg.timer_loop())
    yield
    print("Shutting down FastAPI app...")

app = FastAPI(
    title="Zibbit!",
    description="The consensus-based game",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_client_ip(req: Request):
    client_ip = req.client.host
    forwarded_for = req.headers.get("x-forwarded-for")
    print(f"host=({client_ip})/x-forward-for=({forwarded_for})")
    return forwarded_for or client_ip


@app.get('/events')
async def sse_events(request: Request):
    client_ip = get_client_ip(request)
    await zg.register_user(client_ip)

    pubsub = zg.pubsub()
    await pubsub.psubscribe(f"{GAME_EVENTS_CHANNEL_PREFIX}:*")

    async def event_generator():
        try:
            print(f"[CONNECT] {client_ip} connected")
            # Give the client the live game state
            initial_game_state = await zg.get_game_state()
            yield ServerSentEvent(event="game_state", data=json.dumps({
                "server_time": datetime.now().timestamp(),
                **initial_game_state
            }))

            while True:
                # Timeout every 5 seconds so we can check if client disconnected
                try:
                    message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=5)
                except asyncio.TimeoutError:
                    message = None

                if await request.is_disconnected():
                    print("hit disconnect")
                    break
                if message:
                    event_type = message["channel"].split(":")[-1]
                    yield ServerSentEvent(event=event_type, data=json.dumps({
                        "server_time": datetime.now().timestamp(),
                        **json.loads(message['data'])
                    }))
        finally:
            print("entered finally")
            asyncio.create_task(zg.deregister_user(client_ip))
            await pubsub.punsubscribe(f"{GAME_EVENTS_CHANNEL_PREFIX}:*")
            await pubsub.close()

    return EventSourceResponse(event_generator())

@app.post('/submit_candidate')
async def submit_candidate(request: Request):
    client_ip = get_client_ip(request)
    print(f"{client_ip} -> /submit_candidate")
    request_data = await request.json()
    phrase = request_data["phrase"]
    if await zg.handle_phrase_submission(client_ip, phrase):
        print("successful submit_candidate")
        return JSONResponse(status_code=200, content='Success')
    else:
        print("failed submit_candidate")
        return JSONResponse(status_code=400, content=f'Unable to submit candidate: {phrase}')

@app.post('/vote')
async def vote(request: Request):
    client_ip = get_client_ip(request)
    print(f"{client_ip} -> /vote")
    request_data = await request.json()
    candidate_id = request_data["candidate_id"]
    if not candidate_id:
        return 'Empty', 400
    if await zg.handle_vote(client_ip, candidate_id):
        return JSONResponse(status_code=200, content='Success')
    else:
        return JSONResponse(status_code=400, content=f'Unable to submit vote: {candidate_id}')

@app.post('/flag_word')
async def submit_word_flag(request: Request):
    client_ip = get_client_ip(request)
    print(f"{client_ip} -> /flag_word")
    request_data = await request.json()
    word_id = int(request_data["word_id"])
    if await zg.handle_word_flag(client_ip, word_id):
        return JSONResponse(status_code=200, content='Success')
    else:
        return JSONResponse(status_code=400, content=f'Unable to submit flag: {word_id}')


app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=APP_HOST,
        port=APP_PORT,
        log_level="debug",
        reload=True,
    )