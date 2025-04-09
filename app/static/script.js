
function handleStoryUpdate(storyData) {
    const storyEl = document.getElementById("story");

    const wordListHtml = storyData.map((wordItem) => {
        const word = wordItem["word"];
        const flags = wordItem["flags"];
        return (flags > 0
                ? `<span class=\"story-word\" data-word=\"${word}\">${word}</span>`
                : `<span class=\"story-word\" data-word=\"${word}\">${word}</span>`
        );
    });

    storyEl.innerHTML = wordListHtml.join(" ");
}


function handleCandidateListUpdate(candidateData) {
    const candidateListEl = document.getElementById("candidate-list");

    const candidateListHtml = candidateData.map((candidateItem) => {
        const phrase = candidateItem["phrase"];
        const votes = candidateItem["votes"];
        return (`
            <li data-phrase="${phrase}">
                <button class="vote-btn">
                    <span class="phrase-text">${phrase}</span>
                    <span class="vote-count">${votes}</span>
                </button>
            </li>
        `);
    });

    candidateListEl.innerHTML = candidateListHtml.join(" ");
}


function handleCooldownUpdate(nextGameStartUtcTime) {
    console.log("Cooling off: " + nextGameStartUtcTime);
    // const timerEl = document.getElementById("game-timer");
    // const candidateInput = document.getElementById("candidate-input");
    // const submitBtn = document.getElementById("submit-btn");
    //
    // timerEl.textContent = "Done!";
    // candidateInput.disabled = true;
    // submitBtn.disabled = true;
}

function handleTimerUpdate(gameStartUtcTime, gameEndUtcTime) {
    const timerEl = document.getElementById("game-timer");

    const now = new Date().getTime();
    const secondsLeft = (gameEndUtcTime - now) / 1000;

    timerEl.textContent = `⏳ ${secondsLeft} s.`;
}

function handleGameStateUpdate(gameState) {
    switch (gameState.game_status) {
        case "COOLDOWN":
            handleCooldownUpdate();
            break;
        case "IN_PLAY":
            handleTimerUpdate(gameState.game_start_utc_time, gameState.game_end_utc_time);
            handleStoryUpdate(gameState.story);
            handleCandidateListUpdate(gameState.candidates);
            break;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("Content loaded");

    const candidateInput = document.getElementById("candidate-input");
    const submitBtn = document.getElementById("submit-btn");
    submitBtn.onclick = (e) => {
        e.preventDefault();
        const value = candidateInput.value.trim();
        if (value) {
            const headers = new Headers();
            headers.append("Content-Type", "application/json");
            // validateCandidatePhrase(value);
            fetch("http://localhost:8080/submit_candidate", {
                method: "POST",
                headers: headers,
                body: JSON.stringify({
                    "phrase": value
                }),
                redirect: "follow"
            }).then((response) => response.json())
                .then((result) => {
                    console.log(result);
                    handleGameStateUpdate(JSON.parse(result));
                })
                .catch((error) => console.error(error));
        }
    };

    // Set up SSE connection
    const source = new EventSource("/events");
    source.onmessage = (e) => {

        const data = JSON.parse(e.data);
        console.log(data);

        // const data = {
        //     "game_start_utc_time":"1744151834.322104",
        //     "game_end_utc_time":"1744151855.322104",
        //     "next_game_start_utc_time": "1744151865.322104",
        //     "game_status":"IN_PLAY",
        //     "story":[
        //         {
        //             "word":"The",
        //             "flags":0
        //         },
        //         {
        //             "word":"story",
        //             "flags":0
        //         },
        //         {
        //             "word":"starts",
        //             "flags":1
        //         }
        //     ],
        //     "candidates":[
        //         {
        //             "phrase":"with a very short",
        //             "votes":1
        //         },
        //         {
        //             "phrase":"on a dark and stormy",
        //             "votes":1
        //         },
        //         {
        //             "phrase":"off on a",
        //             "votes":1
        //         },
        //         {
        //             "phrase":"to sound like",
        //             "votes":1
        //         }
        //     ]
        // };
        handleGameStateUpdate(data);
    };
});
