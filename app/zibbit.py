import datetime
import json
import redis.asyncio as redis

"""
Zibbit is a consensus-building game. 
It's implemented as a wrapper around Redis.

- Word phrases are proposed on a continuous basis. Max of 8 candidates allowed at once. 
- Each proposal begins to "decay" for 10 seconds.
- If players vote for a proposal, it pauses the decay by num_votes.
    - Ie. the first vote pauses for 1 second, the third vote for 3 seconds...
- A candidate phrase that decays to 0 gets removed from consideration. 
- After a candidate phrase is proposed, it's put in a "cooldown" period of 20 seconds where it can't be proposed again.
- If a candidate phrase gets 2+ votes, it gets added to the story.
- Words can be flagged on a continuous basis.
    - If 2+ players flag the same word, it gets sliced out.  

Game timer is set to 2 minutes. At the end, there's a 1 minute cooldown timer. 


Game state looks like:
{
    "game_start_utc_time": "2025-04-07T18:52:00Z",
    "game_start_end_time": "2025-04-07T18:54:00Z",
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
            "votes": 1
        },
        {
            "phrase": "on a dark and stormy",
            "votes": 1
        },
        {
            "phrase": "off on a",
            "votes": 1
        },
        {
            "phrase": "to sound like",
            "votes": 1
        }
    ]
}
"""

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
# Denotes the channel to subscribe to for game updates
GAME_EVENTS_CHANNEL = "game_events"
# Prefix for storing story words to flag counter
STORY_FLAG_KEY_PREFIX = "story_flag"

# Length of a game
GAME_LENGTH_SECONDS = 120
# Length of cooldown between games
GAME_COOLDOWN_SECONDS = 60
# TTL for candidate
CANDIDATE_DECAY_SECONDS = 10
# TTL for restriction on submitting the same phrase again
CANDIDATE_SUBMISSION_COOLDOWN_SECONDS = 20


class ZibbitGame:

    # async def set_data(self, key, value):
    #     await self.redis.set(key, value)
    #     await self.redis.publish("updates", f"{key}={value}")
    #
    # async def get_data(self, key):
    #     return await self.redis.get(key)

    def pubsub(self):
        return self.redis.pubsub()

    def __init__(self, redis_host="redis", redis_port=6379):
        self.game_status = "COOLDOWN"
        self.game_start_utc_time = None
        self.game_end_utc_time = None
        self.redis = redis.StrictRedis(host=redis_host, port=redis_port, decode_responses=True)

    async def get_game_state(self):
        story = await self.redis.get(STORY_KEY) or []
        candidates = await self.redis.keys(CANDIDATES_KEY_PREFIX) or []

        gs = json.dumps({
            "story": " ".join(story),
            "candidates": candidates,
            "game_status": self.game_status,
            "game_start_utc_time": self.game_start_utc_time,
            "game_end_utc_time": self.game_end_utc_time
        })

        print(f"serialized: {gs}")
        return gs


    async def start_game(self) -> None:
        # Handle clearing previous game state data from Redis
        await self.clear_redis()

        # Set the game state data to a new game
        now = datetime.datetime.now(datetime.UTC)
        self.game_start_utc_time = now
        self.game_end_utc_time = now + datetime.timedelta(seconds=GAME_LENGTH_SECONDS)
        self.game_status = "IN_PLAY"

        # Broadcast state
        await self.redis.publish(GAME_EVENTS_CHANNEL, await self.get_game_state())

    async def clear_redis(self) -> None:
        # Clear story
        await self.redis.delete(STORY_KEY)
        # Clear candidates
        candidates = await self.redis.keys(CANDIDATES_KEY_PREFIX)
        await self.redis.delete(*candidates)
        # Clear candidates cooldown set
        candidates_cooldown = await self.redis.keys(COOLDOWN_PHRASES_KEY_PREFIX)
        await self.redis.delete(*candidates_cooldown)
        # Clear word flags
        word_flags = await self.redis.keys(STORY_FLAG_KEY_PREFIX)
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
            await self.redis.publish(GAME_EVENTS_CHANNEL, await self.get_game_state())
            return True

    async def handle_vote(self, candidate: str) -> bool:
        # Check if phrase is actually a candidate
        candidate_key = f"{CANDIDATES_KEY_PREFIX}:{candidate}"
        candidate_num_votes = await self.redis.get(candidate_key)
        if candidate_num_votes:
            remaining_ttl = await self.redis.ttl(candidate_key)
            cooldown_key = f"{COOLDOWN_PHRASES_KEY_PREFIX}:{candidate}"
            await self.redis.setex(candidate_key, remaining_ttl + (candidate_num_votes + 1), candidate_num_votes + 1)
            await self.redis.setex(cooldown_key, CANDIDATE_SUBMISSION_COOLDOWN_SECONDS, "cooldown")
            await self.redis.publish(GAME_EVENTS_CHANNEL, await self.get_game_state())
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
            new_story = filter(lambda x: x.decode("utf-8") != word, story)
            await self.redis.delete(STORY_KEY)
            await self.redis.rpush(STORY_KEY, *new_story)
        else:
            await self.redis.incr(word_flag_key)
        await self.redis.publish(GAME_EVENTS_CHANNEL, json.dumps(self.get_game_state()))
        return True
