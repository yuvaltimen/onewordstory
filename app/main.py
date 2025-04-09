import os
import asyncio
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from zibbit import ZibbitGame, GAME_EVENTS_CHANNEL

REDIS_HOST = "yuvaltimen.xyz"  #os.getenv('REDIS_HOST', 'redis')
REDIS_PORT = 6379
zg = ZibbitGame(redis_host=REDIS_HOST, redis_port=REDIS_PORT)
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


@app.get('/events')
async def sse_events():
    pubsub = zg.pubsub()
    await pubsub.subscribe(GAME_EVENTS_CHANNEL)

    async def event_generator():
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield message['data']
        finally:
            await pubsub.unsubscribe(GAME_EVENTS_CHANNEL)
            await pubsub.close()

    return EventSourceResponse(event_generator())

@app.post('/submit_candidate')
async def submit_candidate(request: Request):
    print("requested /submit_candidate")
    request_data = await request.json()
    phrase = request_data["phrase"]
    if await zg.handle_phrase_submission(phrase):
        print("successful submit_candidate")
        return JSONResponse(status_code=200, content=(await zg.get_game_state()))
    else:
        print("failed submit_candidate")
        return JSONResponse(status_code=400, content='Unable to submit candidate')

@app.post('/vote')
async def vote(request: Request):
    print("requested /vote")
    request_data = await request.json()
    candidate = request_data["candidate"]
    if not candidate:
        return 'Empty', 400
    if await zg.handle_vote(candidate):
        return JSONResponse(status_code=200, content=(await zg.get_game_state()))
    else:
        return JSONResponse(status_code=400, content='Unable to submit vote')

@app.post('/flag_word')
async def submit_word_flag(request: Request):
    print("requested /flag_word")
    request_data = await request.json()
    word = request_data["word"]
    if await zg.handle_word_flag(word):
        return JSONResponse(status_code=200, content=(await zg.get_game_state()))
    else:
        return JSONResponse(status_code=400, content='Unable to submit flag')


app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="localhost",
        port=8080,
        log_level="debug",
        reload=True,
    )