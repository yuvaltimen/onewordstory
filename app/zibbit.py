import json
import datetime
import asyncio
import redis.asyncio as redis

"""
Zibbit is a consensus-building game. 
It's implemented as a wrapper around Redis.

- Word phrases are proposed on a continuous basis. (Max of 8 candidates allowed at once.) 
- Each proposal begins to "decay" for 10 seconds.
- If players vote for a proposal, it pauses the decay by num_votes.
    - Ie. the first vote pauses for 1 second, the third vote for 3 seconds...
- A candidate phrase that decays to 0 gets removed from consideration.
- After a candidate phrase is proposed, it's put in a "cooldown" period of 20 seconds where it can't be proposed again.
- If a candidate phrase gets 2+ votes, it gets added to the story.
- If a user taps a phrase they voted for already, it 'unvotes' for it.
- Words can be flagged on a continuous basis.
    - If 2+ players flag the same word, it gets sliced out.
- If a user taps a word they flagged, it 'un-flags' it.

Game timer is set to 2 minutes. At the end, there's a 1 minute cooldown timer. 


Game state looks like:
{
    "game_start_utc_time": <timestamp>,
    "game_end_utc_time": <timestamp>,
    "next_game_start_utc_time": <timestamp>,
    "game_status": "IN_PLAY",
    "story": [
        {
            "word": "The",
            "flags": 0
        },
        {
            "word": "story",
            "flags": 0
        },
        {
            "word": "starts",
            "flags": 1
        }
    ],
    "candidates": [
        {
            "phrase": "with a very short",
            "votes": 1,
            "expiration_utc_time": <timestamp>
        },
        {
            "phrase": "on a dark and stormy",
            "votes": 1,
            "expiration_utc_time": <timestamp>
        },
        {
            "phrase": "off on a",
            "votes": 1,
            "expiration_utc_time": <timestamp>
        },
        {
            "phrase": "to sound like",
            "votes": 1,
            "expiration_utc_time": <timestamp>
        }
    ]
}
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
# Predix for users
USER_RATE_LIMIT_PREFIX = "user"
# Stores the game ttl
GAME_TTL_KEY = "game_ttl"
# Prefix for storing story words to flag counter
STORY_FLAG_KEY_PREFIX = "story_flag"

# Denotes the channel prefix to subscribe to for game updates
GAME_EVENTS_CHANNEL_PREFIX = "game_events"
# Channels that store pub/sub for game events
EVENT_GAME_START_CHANNEL = "game_start"
EVENT_GAME_END_CHANNEL = "game_end"
EVENT_CANDIDATE_UPDATE_CHANNEL = "candidate_update"
EVENT_CANDIDATE_VOTE_CHANNEL = "candidate_vote"
EVENT_STORY_UPDATE_CHANNEL = "story_update"
EVENT_WORD_FLAG_CHANNEL = "word_flag"

# Length of a game
GAME_LENGTH_SECONDS = 5
# Length of cooldown between games
GAME_COOLDOWN_SECONDS = 5
# TTL for candidate
CANDIDATE_DECAY_SECONDS = 10
# TTL for restriction on submitting the same phrase again
CANDIDATE_SUBMISSION_COOLDOWN_SECONDS = 20


class ZibbitGame:

    def __init__(self, redis_host="redis", redis_port=6379):
        self.game_status = "COOLDOWN"
        self.game_start_utc_time = None
        self.game_end_utc_time = None
        self.next_game_start_utc_time = None
        self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)


    def pubsub(self):
        return self.redis.pubsub()


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
        story = await self.redis.get(STORY_KEY) or []
        word_flags = await self.redis.mget(story)
        candidates = await self.redis.keys(f"{CANDIDATES_KEY_PREFIX}:*")
        candidate_votes = await self.redis.mget(candidates)
        game_status = await self.redis.get(GAME_STATUS_KEY) or "ERROR"

        return {
            "story": [{
                "word": word,
                "flags": word_flags[idx] or 0
            } for idx, word in enumerate(story)],
            "candidates": [{
                "phrase": candidate,
                "votes": candidate_votes[idx] or 0,
                "expiration_utc_time": await self.redis.ttl(candidate)
            } for idx, candidate  in enumerate(candidates)],
            "game_status": game_status,
            "game_start_utc_time": self.game_start_utc_time,
            "game_end_utc_time": self.game_end_utc_time,
            "next_game_start_utc_time": self.next_game_start_utc_time
        }


    async def handle_start_game(self) -> None:
        # Handle clearing previous game state data from Redis
        await self.clear_redis()
        await self.redis.set(GAME_STATUS_KEY, "IN_PLAY")

        # Set the game state data to a new game
        now = datetime.datetime.now(datetime.UTC)
        self.game_start_utc_time = now.timestamp()
        self.game_end_utc_time = (now + datetime.timedelta(seconds=GAME_LENGTH_SECONDS)).timestamp()
        self.next_game_start_utc_time = None

        await self.publish_event(EVENT_GAME_START_CHANNEL, {
            GAME_STATUS_KEY: "IN_PLAY",
            "game_start_utc_time": self.game_start_utc_time,
            "game_end_utc_time": self.game_end_utc_time
        })


    async def handle_end_game(self) -> None:
        await self.redis.set(GAME_STATUS_KEY, "COOLDOWN")
        now = datetime.datetime.now(datetime.UTC)
        self.next_game_start_utc_time = (now + datetime.timedelta(seconds=GAME_COOLDOWN_SECONDS)).timestamp()
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
        # Clear word flags
        word_flags = await self.redis.keys(f"{STORY_FLAG_KEY_PREFIX}:*")
        if word_flags:
            await self.redis.delete(*word_flags)


    async def handle_phrase_submission(self, phrase: str) -> bool:
        # Check if phrase has a cooldown submission time, if so reject it
        cooldown_key = f"{COOLDOWN_PHRASES_KEY_PREFIX}:{phrase}"
        if await self.redis.get(cooldown_key):
            return False
        else:
            candidate_key = f"{CANDIDATES_KEY_PREFIX}:{phrase}"
            await self.redis.setex(candidate_key, CANDIDATE_DECAY_SECONDS, 0)
            await self.redis.setex(cooldown_key, CANDIDATE_SUBMISSION_COOLDOWN_SECONDS, "cooldown")
            await self.publish_event(EVENT_CANDIDATE_UPDATE_CHANNEL, {
                "phrase": phrase,
                "votes": 0,
                "expiration_utc_time": (
                        datetime.datetime.now()
                        + datetime.timedelta(seconds=CANDIDATE_DECAY_SECONDS)
                ).timestamp()
            })
            return True


    async def handle_vote(self, candidate: str) -> bool:
        # Check if phrase is actually a candidate
        candidate_key = f"{CANDIDATES_KEY_PREFIX}:{candidate}"
        candidate_num_votes = await self.redis.get(candidate_key)
        if candidate_num_votes:
            remaining_ttl = await self.redis.ttl(candidate_key)
            cooldown_key = f"{COOLDOWN_PHRASES_KEY_PREFIX}:{candidate}"
            updated_num_votes = candidate_num_votes + 1
            # Votes keep the candidate alive for longer
            updated_ttl = remaining_ttl + updated_num_votes
            await self.redis.setex(candidate_key, updated_ttl, updated_num_votes)
            # Since the candidate is being kept alive for longer, it should also have its cooldown time reset
            await self.redis.setex(cooldown_key, CANDIDATE_SUBMISSION_COOLDOWN_SECONDS, "cooldown")
            await self.publish_event(EVENT_CANDIDATE_VOTE_CHANNEL, {
                "candidate": candidate,
                "votes": updated_num_votes,
                "expiration_utc_time": (
                    datetime.datetime.now()
                    + datetime.timedelta(seconds=updated_ttl)
                ).timestamp()
            })
            return True
        else:
            return False


    async def handle_word_flag(self, word: str) -> bool:
        # Check if word has already been flagged
        story = await self.redis.lrange(STORY_KEY, 0, -1)
        if not word.encode("utf-8") in story:
            return False
        word_flag_key = f"{STORY_FLAG_KEY_PREFIX}:{word}"
        word_flags_counter = await self.redis.get(word_flag_key)
        if word_flags_counter:
            # Remove the word from the story
            # TODO: Make words id-based, right now this filters out all identical words
            new_story = filter(lambda x: x.decode("utf-8") != word, story)
            await self.redis.delete(STORY_KEY, word_flag_key)
            await self.redis.rpush(STORY_KEY, *new_story)
            await self.publish_event(EVENT_STORY_UPDATE_CHANNEL, {
                "story": new_story
            })
        else:
            num_flags = await self.redis.incr(word_flag_key)
            await self.publish_event(EVENT_WORD_FLAG_CHANNEL, {
                "word": word,
                "flags": num_flags
            })
        return True
