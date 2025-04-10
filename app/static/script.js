
const ZibbitClient = (function () {
    let eventSource = null;
    let isCooldown = false;

    const connectedUsers = {};
    const story = [];
    const candidates = [];

    const $story = document.getElementById("story");
    const $cooldown = document.getElementById("cooldown");
    const $cooldownTimer = document.getElementById("cooldown-timer");
    const $submitBtn = document.getElementById("submit-btn");
    const $candidatesListSection = document.getElementById("candidate-list-section");
    const $candidatesInputSection = document.getElementById("candidate-input-section");
    const $gameTimer = document.getElementById("game-timer");
    const $topBar = document.getElementById("top-bar");
    const $candidateList = document.getElementById("candidate-list");
    const $candidateForm = document.getElementById("candidateForm");
    const $candidateInput = document.getElementById("candidate-input");

    function init() {
        setupSSE();
        setupInteractivity();
        console.log("Zibbit initialized");
    }

    function setupSSE() {
        eventSource = new EventSource("/events");
        eventSource.onerror = () => {
            console.warn("SSE connection lost. Retrying...");
        }
        eventSource.addEventListener("game_state", (e) => {
            console.log("game state sent!");
            console.log(JSON.parse(e.data));
            handleGameStateUpdate(JSON.parse(e.data));
        });
        eventSource.addEventListener("game_start", (e) => {
            console.log("game started!");
            handleGameStartEvent(JSON.parse(e.data));
        });
        eventSource.addEventListener("game_end", (e) => {
            console.log("game ended!");
            handleCooldownUpdate(JSON.parse(e.data));
            setStoryData([]);
            setCandidateListData([]);
        });
        eventSource.addEventListener("candidate_update", (e) => {
           console.log("candidate update");
           handleAppendCandidate(JSON.parse(e.data));
        });

        // ... more handlers
    }

    function setupInteractivity() {
        setupCandidateSubmissionForm();
        setupCandidateVoteHandlers();
        setupWordFlagHandlers();
    }

    function setupCandidateSubmissionForm() {
        $candidateForm.addEventListener("submit", e => {
            e.preventDefault();
            const text = $candidateInput.value.trim();
            if (!text) {
                return;
            }
            submitCandidate(text);
        })
    }

    function setupCandidateVoteHandlers() {

    }


    function submitCandidate(value) {
        fetch("/submit_candidate", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                "phrase": value
            }),
        }).then((response) => response.json())
            .then((result) => {
                console.log(result);
                $candidateInput.value = "";
            }, (error) => console.log(error));
    }

    function vote(phrase) {
        fetch("/submit-vote", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ phrase })
        }).catch(err => console.error("Failed to submit vote", err))
    }

    function handleAppendCandidate(candidateData) {
        candidates.push(candidateData);
        renderCandidate(candidateData);
    }

    function interpolateColor(color1, color2, factor) {
        const c1 = parseInt(color1.slice(1), 16);
        const c2 = parseInt(color2.slice(1), 16);

        const r1 = (c1 >> 16) & 0xff;
        const g1 = (c1 >> 8) & 0xff;
        const b1 = c1 & 0xff;

        const r2 = (c2 >> 16) & 0xff;
        const g2 = (c2 >> 8) & 0xff;
        const b2 = c2 & 0xff;

        const r = Math.round(r1 + (r2 - r1) * factor);
        const g = Math.round(g1 + (g2 - g1) * factor);
        const b = Math.round(b1 + (b2 - b1) * factor);

        return `rgb(${r}, ${g}, ${b})`;
    }

    function renderCandidate(candidateItem) {
        const phrase = candidateItem["phrase"];
        const votes = candidateItem["votes"];
        let expirationTimestamp = candidateItem["expiration_utc_time"];

        if (expirationTimestamp < 1e12) {
            expirationTimestamp *= 1000;
        }
        let millisRemaining = expirationTimestamp - Date.now();

        if (millisRemaining <= 0) {
            return;
        }

        // Create innermost elements
        const phraseTextSpan = document.createElement("span");
        const voteCountSpan = document.createElement("span");
        phraseTextSpan.className = "phrase-text";
        phraseTextSpan.textContent = phrase;
        voteCountSpan.className = "vote-count";
        voteCountSpan.textContent = votes;

        // Create intermediary element
        const voteBtn = document.createElement("button");
        voteBtn.className = "vote-btn";
        voteBtn.appendChild(phraseTextSpan);
        voteBtn.appendChild(voteCountSpan);

        const li = document.createElement("li");
        li.appendChild(voteBtn);
        $candidateList.appendChild(li);

        const styles = getComputedStyle(document.documentElement);
        const startColor = styles.getPropertyValue("--start-color").trim();
        const endColor = styles.getPropertyValue("--end-color").trim();

        function updateColor() {
            const progress = (10000 - millisRemaining) / 10000;
            const color = interpolateColor(startColor, endColor, progress);
            console.log(color);
            voteBtn.style.setProperty("background-color", color, "important");
        }

        updateColor();
        const interval = setInterval(() => {
            updateColor();
            if (millisRemaining <= 0) {
                clearInterval(interval);
                li.remove();
            }

            millisRemaining -= 500;
        }, 500);
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

    function startCountdown(utcTimestamp, serverTimestamp, timerElement) {
        // Convert timestamp to milliseconds if it looks like seconds
        if (utcTimestamp < 1e12) {
            utcTimestamp *= 1000;
        }

        if (serverTimestamp < 1e12) {
            // TODO use this
            serverTimestamp *= 1000;
        }

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

    function handleGameStartEvent(event) {
        isCooldown = false;

        // First hide cooldown specific stuff
        $cooldown.hidden = true;

        // Show game-specific stuff
        $candidatesListSection.hidden = false;
        $candidatesInputSection.hidden = false;
        $submitBtn.hidden = false;
        $topBar.hidden = false
        $candidateInput.value = "";

        startCountdown(event["game_end_utc_time"], event["server_time"], $gameTimer);
    }


    function setStoryData(storyData) {
        const wordListHtml = storyData.map((wordItem) => {
            const word = wordItem["word"];
            const flags = wordItem["flags"];
            return (flags > 0
                    ? `<span class=\"story-word\" data-word=\"${word}\">${word}</span>`
                    : `<span class=\"story-word\" data-word=\"${word}\">${word}</span>`
            );
        });

        $story.innerHTML = wordListHtml.join(" ");
    }


    function setCandidateListData(candidateListData) {
        candidates.length = 0;
        candidates.push(...candidateListData);
        candidates.forEach(renderCandidate);
    }


    function handleCooldownUpdate(event) {
        isCooldown = true;

        // First hide game-specific stuff
        $candidatesListSection.hidden = true;
        $candidatesInputSection.hidden = true;
        $submitBtn.hidden = true;
        $topBar.hidden = true
        $candidateInput.value = "";

        // Show cooldown specific stuff
        $cooldown.hidden = false;

        startCountdown(event["next_game_start_utc_time"], event["server_time"], $cooldownTimer);
    }

    return {
        init
    }

})()

window.addEventListener("DOMContentLoaded", ZibbitClient.init);
