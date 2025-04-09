
function handleGameStartEvent(event) {
    // First hide cooldown specific stuff
    const cooldown = document.getElementById("cooldown");
    cooldown.hidden = true;

    // Show game-specific stuff
    const gameTimer = document.getElementById("top-bar");
    const candidates = document.getElementById("candidate-list-section");
    const candidateInput = document.getElementById("candidate-input-section");
    const submitBtn = document.getElementById("submit-btn");
    candidates.hidden = false;
    candidateInput.hidden = false;
    submitBtn.hidden = false;
    gameTimer.hidden = false
    candidateInput.value = "";

    startCountdown(event["game_end_utc_time"], event["server_time"], "game-timer");
}


function setStoryData(storyData) {
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


function setCandidateListData(candidateData) {
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


function handleCooldownUpdate(event) {

    // First hide game-specific stuff
    const gameTimer = document.getElementById("top-bar");
    const candidates = document.getElementById("candidate-list-section");
    const candidateInput = document.getElementById("candidate-input-section");
    const submitBtn = document.getElementById("submit-btn");
    candidates.hidden = true;
    candidateInput.hidden = true;
    submitBtn.hidden = true;
    gameTimer.hidden = true
    candidateInput.value = "";

    // Show cooldown specific stuff
    const cooldown = document.getElementById("cooldown");
    cooldown.hidden = false;

    startCountdown(event["next_game_start_utc_time"], event["server_time"],"cooldown-timer");
}

function handleGameStateUpdate(gameState) {
    switch (gameState["game_status"]) {
        case "ERROR":
            alert("ERROR: check sse data...")
            break;
        case "COOLDOWN":
            handleCooldownUpdate(gameState);
            setStoryData([]);
            setCandidateListData([]);
            break;
        case "IN_PLAY":
            handleGameStartEvent(gameState["game_end_utc_time"]);
            setStoryData(gameState["story"]);
            setCandidateListData(gameState["candidates"]);
            break;
        default:
            alert("UNKNOWN: check sse data...")
            break;
    }
}


document.addEventListener("DOMContentLoaded", () => {
    console.log("Content loaded");

    // First, set up SSE connection to follow live updates
    const source = new EventSource("/events");
    source.addEventListener("game_state", (e) => {
        console.log("game state sent!");
        console.log(JSON.parse(e.data));
        handleGameStateUpdate(JSON.parse(e.data));
    });
    source.addEventListener("game_start", (e) => {
        console.log("game started!");
        handleGameStartEvent(JSON.parse(e.data));
    });
    source.addEventListener("game_end", (e) => {
        console.log("game ended!");
        handleCooldownUpdate(JSON.parse(e.data));
        setStoryData([]);
        setCandidateListData([]);
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
            fetch("http://localhost:8080/submit_candidate", {
                method: "POST",
                headers: headers,
                body: JSON.stringify({
                    "phrase": value
                }),
            }).then((response) => response.json()).then((result) => {
                console.log(result);
                candidateInput.value = "";
            }, (error) => console.log(error));
        }
    };
});

/// ==================== CHATGPT ======

function startCountdown(utcTimestamp, serverTimestamp, elementId) {
    // Convert timestamp to milliseconds if it looks like seconds
    if (utcTimestamp < 1e12) {
        utcTimestamp *= 1000;
    }

    if (serverTimestamp < 1e12) {
        // TODO use this
        serverTimestamp *= 1000;
    }

    const timerElement = document.getElementById(elementId);

    function updateTimer() {
        const now = Date.now();
        const diffMs = utcTimestamp - now;

        if (diffMs <= 0) {
            timerElement.textContent = "Time's up!";
            clearInterval(interval);
            return;
        }

        const seconds = Math.floor((diffMs / 1000) % 60);
        const minutes = Math.floor((diffMs / (1000 * 60)) % 60);

        const parts = [
            minutes > 0 ? `${minutes}m` : '',
            `${seconds}s`
        ].filter(Boolean);

        timerElement.textContent = parts.join(' ');
    }

    updateTimer(); // Show immediately
    const interval = setInterval(updateTimer, 1000);
}