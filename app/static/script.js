
function handleGameStartEvent(event) {
    handleGameTimerUpdate(event["game_end_utc_time"]);
}

function updateTimer(utcTimestamp, interval) {
    const now = Date.now();
    const diffMs = utcTimestamp - now;

    if (diffMs <= 0) {
        clearInterval(interval);
        return "Time's up!";
    }

    const seconds = Math.floor((diffMs / 1000) % 60);
    const minutes = Math.floor((diffMs / (1000 * 60)) % 60);
    const parts = [
        minutes > 0 ? `${minutes}m` : '',
        `${seconds}s`
    ].filter(Boolean);

    return parts.join(' ');
}


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

    const now = new Date().getTime();
    const secondsLeft = nextGameStartUtcTime - (now / 1000);
    console.log("Cooling off: " + nextGameStartUtcTime);
    console.log("Cooling off: " + secondsLeft);


    const timerEl = document.getElementById("game-timer");
    const cooldownTimerEl = document.getElementById("cooldown-timer");
    const candidates = document.getElementById("candidate-list-section");
    const candidateInput = document.getElementById("candidate-input-section");
    const submitBtn = document.getElementById("submit-btn");
    const cooldown = document.getElementById("cooldown");


    cooldown.hidden = false;
    timerEl.textContent = "Done!";
    cooldownTimerEl.textContent = `${secondsLeft}`;
    candidates.hidden = true;
    candidateInput.hidden = true;
    submitBtn.hidden = true;
}

function handleGameTimerUpdate(gameEndUtcTime) {
    const utcTimestamp = gameEndUtcTime < 1e12 ? gameEndUtcTime * 1000 : gameEndUtcTime;
    const timerEl = document.getElementById("game-timer");

    const interval = setInterval(updateTimer, 200);
    timerEl.textContent = updateTimer(utcTimestamp, interval);
}

function handleGameStateUpdate(gameState) {
    switch (gameState["game_status"]) {
        case "COOLDOWN":
            handleCooldownUpdate(gameState["next_game_start_utc_time"]);
            break;
        case "IN_PLAY":
            handleGameTimerUpdate(gameState["game_end_utc_time"]);
            handleStoryUpdate(gameState["story"]);
            handleCandidateListUpdate(gameState["candidates"]);
            break;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("Content loaded");

    // First, set up SSE connection to follow live updates
    const source = new EventSource("/events");
    source.addEventListener("game_start", (e) => {
        console.log("game started!");
        handleGameStartEvent(JSON.parse(e.data));
    });
    source.addEventListener("game_end", (e) => {
        console.log("game ended!");
        // handleCooldownUpdate(JSON.parse(e.data));
    });
    source.addEventListener("game_state", (e) => {
        console.log("game state sent!");
        handleGameStateUpdate(JSON.parse(e.data));
    });

    // Make site interactive
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
                    candidateInput.textContent = "";
                    handleGameStateUpdate(result);
                })
                .catch((error) => console.error(error));
        }
    };
});
