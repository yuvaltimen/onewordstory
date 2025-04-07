

function handleGameStart() {

}

function handleGameEnd() {

}

function handleGameStateUpdate(gameState) {

}

document.addEventListener("DOMContentLoaded", () => {
    console.log("Content loaded");

    const storyEl = document.getElementById("story");
    const timerEl = document.getElementById("game-timer");
    const candidateListEl = document.getElementById("candidate-list");
    const candidateInput = document.getElementById("candidate-input");
    const submitBtn = document.getElementById("submit-btn");

    // Set up SSE connection
    const source = new EventSource("/events");

    // Listen for custom events
    source.addEventListener("", (event) => {

    });
    //
    // source.onmessage = (e) => {
    //
    //     // const data = JSON.parse(e.data);
    //     const data = {
    //         "game_start_utc_time":"2025-04-07T18:52:00Z",
    //         "game_start_end_time":"2025-04-07T18:54:00Z",
    //         "game_status":"IN_PLAY",
    //         "story":[
    //             {
    //                 "word":"The",
    //                 "flags":0
    //             },
    //             {
    //                 "word":"story",
    //                 "flags":0
    //             },
    //             {
    //                 "word":"starts",
    //                 "flags":1
    //             }
    //         ],
    //         "candidates":[
    //             {
    //                 "phrase":"with a very short",
    //                 "votes":1
    //             },
    //             {
    //                 "phrase":"on a dark and stormy",
    //                 "votes":1
    //             },
    //             {
    //                 "phrase":"off on a",
    //                 "votes":1
    //             },
    //             {
    //                 "phrase":"to sound like",
    //                 "votes":1
    //             }
    //         ]
    //     };
    //
    //
    //
    //     switch (data.type) {
    //         case "timer_update":
    //             timerEl.textContent = `⏳ ${data.timer}s`;
    //             break;
    //         case "game_start":
    //             timerEl.textContent = `⏳ ${data.timer}s`;
    //             candidateInput.disabled = false;
    //             submitBtn.disabled = false;
    //             candidateListEl.innerHTML = ""; // Clear any leftover phrases
    //             break;
    //         case "game_end":
    //             timerEl.textContent = "Done!";
    //             candidateInput.disabled = true;
    //             submitBtn.disabled = true;
    //             break;
    //         case "story_update":
    //             storyEl.textContent = data.story;
    //             break;
    //         case "new_candidate":
    //             addCandidateToList(data.phrase);
    //             break;
    //         case "vote_update":
    //             updateVoteCount(data.phrase, data.votes);
    //             break;
    //         case "winner_chosen":
    //             // Optional: highlight winner
    //             highlightWinner(data.phrase);
    //             break;
    //     }
    // };

    // Submit candidate
    submitBtn.addEventListener("click", () => {
        const value = candidateInput.value.trim();
        if (value) {
            fetch("/submit_candidate", {
                method: "POST",
                body: new URLSearchParams({ candidate: value }),
            });
            candidateInput.value = "";
        }
    });

    // Helpers
    function addCandidateToList(phrase) {
        const item = document.createElement("div");
        item.className = "candidate-item";
        item.dataset.phrase = phrase;

        const text = document.createElement("span");
        text.textContent = phrase;

        const vote = document.createElement("span");
        vote.className = "vote-count";
        vote.textContent = "0";

        item.appendChild(text);
        item.appendChild(vote);
        candidateListEl.appendChild(item);

        item.addEventListener("click", () => {
            fetch("/vote", {
                method: "POST",
                body: new URLSearchParams({ phrase }),
            });
        });
    }

    function updateVoteCount(phrase, votes) {
        const items = document.querySelectorAll(".candidate-item");
        items.forEach(item => {
            if (item.dataset.phrase === phrase) {
                const voteSpan = item.querySelector(".vote-count");
                if (voteSpan) voteSpan.textContent = votes;
            }
        });
    }

    function highlightWinner(phrase) {
        const items = document.querySelectorAll(".candidate-item");
        items.forEach(item => {
            if (item.dataset.phrase === phrase) {
                item.classList.add("winner");
            }
        });
    }
});
