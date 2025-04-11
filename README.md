
## Zibbit! - The Realtime Consensus Building Game

<img src="app/static/zibbit_frog_icon.png" alt="Zibbit the Frog" width="200"/>


The goal is to build up a story with other players. 
This is done by continuously proposing the next phrase to the story, 
and users continuously vote to add phrases or remove words from the story.
The goal is realtime collaboration, with a tinge of chaos.

How to Play:
- Word phrases are proposed on a continuous basis.
- Each proposal begins to "decay" after being proposed.
- If players vote for a proposal, it pauses the decay by its number of votes.
    - Ie. the first vote pauses for 1 second, the third vote for 3 seconds...
- A candidate phrase that decays to 0 gets removed from consideration.
- After a candidate phrase is proposed, it's put in a "cooldown" period, where it can't be proposed again.
- If a candidate phrase gets enough votes, it gets tokenized and added to the story.
- Words can be flagged on a continuous basis.
    - If enough players flag the same word, it gets sliced out.
- If a user taps a word they flagged, it 'un-flags' it.

Game timer is set to 2 minutes. At the end, there's a 1 minute cooldown timer.

```json
{
    "game_start_utc_time": <timestamp>,
    "game_end_utc_time": <timestamp>,
    "next_game_start_utc_time": <timestamp>,
    "game_status": "IN_PLAY",
    "story": [
        {
            "word_id": <str>,
            "word": "The",
            "flags": 0
        },
        {
            "word_id": <str>,
            "word": "story",
            "flags": 0
        },
        {
            "word_id": <str>,
            "word": "starts",
            "flags": 1
        }
    ],
    "candidates": [
        {
            "candidate_id": <str>,
            "phrase": "with a very short",
            "votes": 1,
            "expiration_utc_time": <timestamp>
        },
        {
            "candidate_id": <str>,
            "phrase": "on a dark and stormy",
            "votes": 1,
            "expiration_utc_time": <timestamp>
        },
        {
            "candidate_id": <str>,
            "phrase": "off on a",
            "votes": 1,
            "expiration_utc_time": <timestamp>
        },
        {
            "candidate_id": <str>,
            "phrase": "to sound like",
            "votes": 1,
            "expiration_utc_time": <timestamp>
        }
    ]
}
```