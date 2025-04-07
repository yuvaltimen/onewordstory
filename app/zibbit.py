import datetime
import json

from redis import StrictRedis




"""
Zibbit is a consensus-building game. 
It's implemented as a wrapper around Redis.

Word phrases are proposed on a continuous basis. Max of 8 candidates allowed at once. 
Each proposal begins to "decay" for 10 seconds.
If players vote for a proposal, it pauses the decay by num_votes. 
    Ie. the first vote pauses for 1 second, the third vote for 3 seconds...
A candidate phrase that decays to 0 gets removed from consideration. 
    It"s put in a "cooldown" period of 20 seconds where it can't be proposed again.
If a candidate phrase gets 2+ votes, it gets added to the story.

Word removals are proposed on continuous basis.
If 2+ players requests to remove the same word, it gets sliced out.  

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

STORY_KEY = "story"
CANDIDATES_KEY = "candidates"
USER_RATE_LIMIT_PREFIX = "user:"
GAME_TTL_KEY = "game_ttl"
GAME_EVENTS_CHANNEL = "game_events"

GAME_LENGTH_SECONDS = 120
CANDIDATE_DECAY_SECONDS = 10



class ZibbitGame:

    def __init__(self, redis_host="redis", redis_port=6379):
        self.game_status = "COOLDOWN"
        self.game_start_utc_time = None
        self.game_end_utc_time = None
        self.redis = StrictRedis(host=redis_host, port=redis_port, db=0, decode_responses=True)

    def get_game_state(self):
        story = self.redis.get(STORY_KEY) or []
        candidates = self.redis.get(CANDIDATES_KEY) or []
        return {
            "story": " ".join(story),
            "candidates": candidates,
            "game_status": self.game_status,
            "game_start_utc_time": self.game_start_utc_time,
            "game_end_utc_time": self.game_end_utc_time
        }

    def event_stream(self):
        pubsub = self.redis.pubsub()
        pubsub.subscribe(GAME_EVENTS_CHANNEL)

        for message in pubsub.listen():
            print(message)
            if message["type"] == "message":
                data = json.loads(message["data"])
                yield f"data: {data}\n\n"

    def start_game(self):
        self.clear_redis()

        now = datetime.datetime.now(datetime.UTC)

        self.game_start_utc_time = now
        self.game_end_utc_time = now + datetime.timedelta(seconds=GAME_LENGTH_SECONDS)
        self.game_status = "IN_PLAY"

        self.redis.publish(GAME_EVENTS_CHANNEL, json.dumps(self.get_game_state()))

    def clear_redis(self):
        pass

    def handle_vote(self, candidate: str) -> bool:
        pass

    def handle_phrase_submission(self, phrase: str) -> bool:
        pass

    def handle_word_elimination_request(self, word: str) -> bool:
        pass





