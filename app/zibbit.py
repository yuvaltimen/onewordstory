import json
from datetime import datetime, UTC, timedelta
import asyncio
import redis.asyncio as redis

"""
Story keys: [
    {
        "word_id": 2,
        "word": "the",
        "flags": ["112.3.2.1", "165.32.1.1"],
        "creator": "172.0.0.1"
    },
    ...
]

Candidates: [
    {
        "candidate_id": 3,
        "phrase": "monkey went to",
        "votes": ["112.3.2.1", "172.0.0.1"],
        "creator": "165.32.1.1",
        "expiration_utc_time": 123456.123
    },
    ...
]
"""

# Game status (ex. COOLDOWN or IN_PLAY)
GAME_STATUS_KEY = "game_status"
# Stores current time remaining in game cooldown timer
GAME_IN_PLAY_TIMER_SECONDS = "game_in_play_timer"
# Stores current time remaining in game cooldown timer
GAME_COOLDOWN_TIMER_SECONDS = "game_cooldown_timer"
# Stores the story as a list
STORY_KEY = "story"
# Prefix for phrases that are in cooldown period
COOLDOWN_PHRASES_KEY_PREFIX = "cooldown_phrases"
# Prefix for candidate phrases
CANDIDATES_KEY_PREFIX = "candidates"
CANDIDATES_VOTES_KEY_PREFIX = "candidate_votes"
# Predix for users
USER_RATE_LIMIT_PREFIX = "user"
# Stores the game ttl
GAME_TTL_KEY = "game_ttl"
# Prefix for storing story words to flag counter
STORY_FLAG_KEY_PREFIX = "story_flag"
# Stores the incrementing ids for candidates
CANDIDATE_AUTOINCR_KEY = "candidate_autoincr"
# Stores the incrementing ids for words
WORD_AUTOINCR_KEY = "word_autoincr"
# Stores the set of connected users
CONNECTED_USERS_KEY = "connected_users"

# Denotes the channel prefix to subscribe to for game updates
GAME_EVENTS_CHANNEL_PREFIX = "game_events"
# Channels that store pub/sub for game events
EVENT_GAME_START_CHANNEL = "game_start"
EVENT_GAME_END_CHANNEL = "game_end"
EVENT_STORY_UPDATE_CHANNEL = "story_update"
EVENT_CANDIDATE_UPDATE_CHANNEL = "candidate_update"
EVENT_CANDIDATE_VOTE_CHANNEL = "candidate_vote"
EVENT_WORD_FLAG_CHANNEL = "word_flag"
EVENT_USER_CONNECTIONS = "user_connections"

# Length of a game
GAME_LENGTH_SECONDS = 120
# Length of cooldown between games
GAME_COOLDOWN_SECONDS = 10
# TTL for candidate
CANDIDATE_DECAY_SECONDS = 10
# Max number of words allowed per candidate
MAX_PHRASE_WORD_LENGTH = 5
# TTL for restriction on submitting the same phrase again
CANDIDATE_SUBMISSION_COOLDOWN_SECONDS = 20
# Number of unique votes required for a candidate phrase to be appended to the story
CANDIDATE_VOTE_THRESHOLD = 3
# Number of unique word flags required for a word to be removed from the story
WORD_FLAG_THRESHOLD = 3


def validate_phrase(inp: str):
    if "|" in inp:
        raise ValueError(f"bad input: {inp}")
    if len(inp.strip().split(" ")) > MAX_PHRASE_WORD_LENGTH:
        raise ValueError(f"Too big of an input: {inp}")


class ZibbitGame:

    def __init__(self, redis_host="redis", redis_port=6379):
        self.game_status = "COOLDOWN"
        self.game_start_utc_time = None
        self.game_end_utc_time = None
        self.next_game_start_utc_time = None
        self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)
        self.pubsub_redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)

    def pubsub(self):
        return self.pubsub_redis.pubsub()

    async def register_user(self, client_ip):
        print(f"registering {client_ip}")
        await self.redis.sadd(CONNECTED_USERS_KEY, client_ip)
        await self.publish_event(EVENT_USER_CONNECTIONS, {
            "connection_status": "user_connected",
            "client_ip": client_ip
        })

    async def deregister_user(self, client_ip):
        try:
            print(f"de-registering {client_ip}")
            await self.redis.srem(CONNECTED_USERS_KEY, client_ip)
            print(f"Removed {client_ip} from CONNECTED_USERS_KEY")
            await self.publish_event(EVENT_USER_CONNECTIONS, {
                "connection_status": "user_disconnected",
                "client_ip": client_ip
            })
            print("Published user_disconnected event")
        except Exception as e:
            print(f"Error in deregister_user: {e}")

    async def timer_loop(self):
        while True:
            # On server startup, the first phase should be cooldown
            await self.handle_end_game()
            # Start the cooldown timer
            await asyncio.sleep(GAME_COOLDOWN_SECONDS)

            # Call the function to set start game data
            await self.handle_start_game()
            # Start the game timer
            await asyncio.sleep(GAME_LENGTH_SECONDS)


    async def publish_event(self, event_type: str, payload: dict) -> None:
        await self.redis.publish(f"{GAME_EVENTS_CHANNEL_PREFIX}:{event_type}", json.dumps(payload))


    async def get_game_state(self):
        word_items = await self.redis.lrange(STORY_KEY, 0, -1)
        candidates_keys = await self.redis.keys(f"{CANDIDATES_KEY_PREFIX}:*")
        candidate_items = await self.redis.mget(candidates_keys)
        game_status = await self.redis.get(GAME_STATUS_KEY) or "ERROR"
        connected_users = await self.redis.smembers(CONNECTED_USERS_KEY)

        return {
            "story": [json.loads(itm) for itm in word_items],
            "candidates": [json.loads(itm) for itm in candidate_items],
            "game_status": game_status,
            "game_start_utc_time": self.game_start_utc_time,
            "game_end_utc_time": self.game_end_utc_time,
            "next_game_start_utc_time": self.next_game_start_utc_time,
            "connected_users": [*connected_users],
            "game_constants": {
                "CANDIDATE_DECAY_SECONDS": CANDIDATE_DECAY_SECONDS,
                "CANDIDATE_VOTE_THRESHOLD": CANDIDATE_VOTE_THRESHOLD,
                "WORD_FLAG_THRESHOLD": WORD_FLAG_THRESHOLD
            }
        }


    async def handle_start_game(self) -> None:
        # Handle clearing previous game state data from Redis
        await self.clear_redis()
        await self.redis.set(GAME_STATUS_KEY, "IN_PLAY")

        # Set the game state data to a new game
        now = datetime.now(UTC)
        self.game_start_utc_time = now.timestamp()
        self.game_end_utc_time = (now + timedelta(seconds=GAME_LENGTH_SECONDS)).timestamp()
        self.next_game_start_utc_time = None

        await self.publish_event(EVENT_GAME_START_CHANNEL, {
            GAME_STATUS_KEY: "IN_PLAY",
            "game_start_utc_time": self.game_start_utc_time,
            "game_end_utc_time": self.game_end_utc_time
        })


    async def handle_end_game(self) -> None:
        await self.redis.set(GAME_STATUS_KEY, "COOLDOWN")
        now = datetime.now(UTC)
        self.next_game_start_utc_time = (now + timedelta(seconds=GAME_COOLDOWN_SECONDS)).timestamp()
        self.game_start_utc_time = None
        self.game_end_utc_time = None

        await self.publish_event(EVENT_GAME_END_CHANNEL, {
            GAME_STATUS_KEY: "COOLDOWN",
            "next_game_start_utc_time": self.next_game_start_utc_time
        })


    async def clear_redis(self) -> None:
        # Clear story
        await self.redis.delete(STORY_KEY)
        # Clear candidates
        candidates = await self.redis.keys(f"{CANDIDATES_KEY_PREFIX}:*")
        if candidates:
            await self.redis.delete(*candidates)
        # Clear candidates cooldown set
        candidates_cooldown = await self.redis.keys(f"{COOLDOWN_PHRASES_KEY_PREFIX}:*")
        if candidates_cooldown:
            await self.redis.delete(*candidates_cooldown)
        # Reset autoincrement ids back to 1
        await self.redis.set(CANDIDATE_AUTOINCR_KEY, 1)
        await self.redis.set(WORD_AUTOINCR_KEY, 1)

    async def get_autoincr_candidate_ids(self, amount = 1) -> list[int]:
        return await self.autoincr_id_wrapper(CANDIDATE_AUTOINCR_KEY, amount)

    async def get_autoincr_word_ids(self, amount = 1) -> list[int]:
        return await self.autoincr_id_wrapper(WORD_AUTOINCR_KEY, amount)

    async def autoincr_id_wrapper(self, redis_key, amount = 1) -> list[int]:
        ending_key = await self.redis.incr(redis_key, amount=amount)
        starting_key = ending_key - amount
        return list(range(starting_key + 1, ending_key + 1))

    async def handle_phrase_submission(self, client_ip: str, phrase: str) -> bool:
        phrase = phrase.strip().lower()
        validate_phrase(phrase)
        # Check if phrase has a cooldown submission time, if so reject it
        cooldown_key = f"{COOLDOWN_PHRASES_KEY_PREFIX}:{phrase}"
        if await self.redis.get(cooldown_key):
            return False
        else:
            candidate_id = (await self.get_autoincr_candidate_ids())[0]
            candidate_key = f"{CANDIDATES_KEY_PREFIX}:{candidate_id}"
            candidate_item = {
                "candidate_id": candidate_id,
                "phrase": phrase,
                "votes": [],
                "creator": client_ip,
                "expiration_utc_time": (datetime.now() + timedelta(seconds=CANDIDATE_DECAY_SECONDS)).timestamp()
            }
            await self.redis.setex(candidate_key, CANDIDATE_DECAY_SECONDS, json.dumps(candidate_item))
            await self.redis.setex(cooldown_key, CANDIDATE_SUBMISSION_COOLDOWN_SECONDS, "cooldown")
            await self.publish_event(EVENT_CANDIDATE_UPDATE_CHANNEL, candidate_item)
            return True


    async def handle_vote(self, client_ip: str, candidate_id: int) -> bool:
        # Check if phrase is actually a candidate
        candidate_key = f"{CANDIDATES_KEY_PREFIX}:{candidate_id}"
        candidate_info = await self.redis.get(candidate_key)
        if not candidate_info:
            return False
        else:
            candidate_info = json.loads(candidate_info)
            candidate_phrase, candidate_votes, creator = candidate_info['phrase'], candidate_info['votes'], candidate_info['creator']
            if client_ip == creator:
                # Can't vote for your own phrase
                return False
            cooldown_key = f"{COOLDOWN_PHRASES_KEY_PREFIX}:{candidate_phrase}"
            if client_ip in candidate_votes:
                # If client already voted for this, voting again should un-vote
                updated_candidate_votes = list(filter(lambda ip_addr: ip_addr != client_ip, candidate_votes))
                vote_added = False
            else:
                # Reset candidate cooldown time
                await self.redis.setex(cooldown_key, CANDIDATE_SUBMISSION_COOLDOWN_SECONDS, "cooldown")
                updated_candidate_votes = [*candidate_votes, client_ip]
                vote_added = True

            if len(updated_candidate_votes) >= CANDIDATE_VOTE_THRESHOLD:
                await self.redis.delete(candidate_key)
                await self.publish_event(EVENT_CANDIDATE_VOTE_CHANNEL, {
                    "candidate_id": candidate_id,
                    "phrase": candidate_phrase,
                    "votes": updated_candidate_votes,
                    "creator": creator,
                    "expiration_utc_time": None
                })
                await self.handle_insert_phrase_to_story(candidate_info)
                return True
            else:

                remaining_ttl = await self.redis.ttl(candidate_key)
                if vote_added:
                    # Votes keep the candidate alive for longer
                    updated_ttl = remaining_ttl + len(updated_candidate_votes)
                    new_expiration_utc_time = (datetime.now() + timedelta(seconds=updated_ttl)).timestamp()
                else:
                    updated_ttl = remaining_ttl
                    new_expiration_utc_time = (datetime.now() + timedelta(seconds=updated_ttl)).timestamp()

                await self.redis.setex(candidate_key, updated_ttl, json.dumps({
                    "candidate_id": candidate_id,
                    "phrase": candidate_phrase,
                    "votes": updated_candidate_votes,
                    "creator": creator,
                    "expiration_utc_time": new_expiration_utc_time
                }))
                await self.publish_event(EVENT_CANDIDATE_VOTE_CHANNEL, {
                    "candidate_id": candidate_id,
                    "phrase": candidate_phrase,
                    "votes": updated_candidate_votes,
                    "creator": creator,
                    "expiration_utc_time": new_expiration_utc_time
                })
                return True


    async def send_full_story(self):
        full_story = await self.redis.lrange(STORY_KEY, 0, -1)
        word_items = [json.loads(itm) for itm in full_story]
        await self.publish_event(EVENT_STORY_UPDATE_CHANNEL, {
            "story": word_items
        })


    async def handle_insert_phrase_to_story(self, candidate_info: dict):
        # Tokenize phrase and insert
        candidate_phrase, creator = candidate_info['phrase'], candidate_info['creator']
        words = candidate_phrase.split(" ")
        next_word_ids = await self.get_autoincr_word_ids(len(words))
        word_items = [json.dumps({
            "word_id": next_word_ids[idx],
            "word": w,
            "flags": [],
            "creator": creator
        }) for idx, w in enumerate(words)]
        await self.redis.rpush(STORY_KEY, *word_items)

        # Send single update
        await self.send_full_story()


    async def handle_word_flag(self, client_ip: str, word_id: int) -> bool:
        # Check if word has already been flagged
        full_story = await self.redis.lrange(STORY_KEY, 0, -1)
        story_items = [json.loads(itm) for itm in full_story]
        if not (word_id in [itm["word_id"] for itm in story_items]):
            return False
        word_item = list(filter(lambda itm: itm["word_id"] == word_id, story_items))[0]
        word_flags = word_item["flags"]
        if client_ip in word_flags:
            # If client already flagged the word, remove the client's ip from the flag list (ie. un-flag it)
            updated_word_flags = list(filter(lambda flagged_ip: flagged_ip != client_ip, word_flags))
        else:
            updated_word_flags = [*word_flags, client_ip]

        if len(updated_word_flags) >= WORD_FLAG_THRESHOLD:
            # Remove the word from the story
            new_story = list(filter(lambda itm: itm["word_id"] != word_id, story_items))
            await self.redis.delete(STORY_KEY)
            if new_story:
                await self.redis.rpush(STORY_KEY, *[json.dumps(story_itm) for story_itm in new_story])
            # Send single update
            await self.send_full_story()
        else:
            # Update the word item in the story
            new_story = [word_item if word_item["word_id"] != word_id else {
                **word_item,
                "flags": updated_word_flags
            } for word_item in story_items]
            await self.redis.delete(STORY_KEY)
            if new_story:
                await self.redis.rpush(STORY_KEY, *[json.dumps(story_itm) for story_itm in new_story])
            await self.publish_event(EVENT_WORD_FLAG_CHANNEL, {
                "word_id": word_id,
                "flags": updated_word_flags
            })
        return True


