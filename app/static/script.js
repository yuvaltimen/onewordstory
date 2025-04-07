window.onload = function () {

    const storyEl = document.getElementById("story");
    const timerEl = document.getElementById("timer");
    const cooldownEl = document.getElementById("cooldown");
    const wordInput = document.getElementById("wordInput");
    const wordForm = document.getElementById("wordForm");
    const submitButton = document.getElementById("submitButton");

    function startgame() {
        console.log("HIT startgame");
        cooldownEl.style.display = "none";
        cooldownEl.textContent = "";
        wordInput.disabled = false;
        submitButton.disabled = false;
        wordInput.focus();
    };

    function endgame(cooldownTime) {
        console.log(`HIT endgame ${cooldownTime}`);
        cooldownEl.style.display = "block";
        cooldownEl.textContent = `Game is cooling down. Try again in ${cooldownTime}s.`;
        timerEl.textContent = "";
        wordInput.disabled = true;
        submitButton.disabled = true;
    };

    // Maintain focus on input when page loads or form is submitted
    setTimeout(() => wordInput.focus(), 500);
    wordForm.addEventListener("submit", function () {
        setTimeout(() => wordInput.focus(), 100);
    });

    const eventSource = new EventSource("/stream");
    eventSource.onmessage = function (event) {
        console.log("STREAM:", event.data);

        const [story, timer] = event.data.split("|");
        const parsedTimer = parseInt(timer);
        const isCooldown = parsedTimer <= 0;

        storyEl.textContent = story.trim() ? story : "Waiting for game start...";

        if (!isCooldown) {
            timerEl.textContent = "Time left: " + parsedTimer + "s.";
        } else {
            wordInput.disabled = true;
        }
    };

    const timerSource = new EventSource("/timer");
    timerSource.onmessage = function (event) {
        const data = event.data;
        console.log("TIMER:", data);

        if (data.startsWith("cooldown:")) {
            const cooldownTime = parseInt(data.split(":")[1]);
            endgame(cooldownTime);

            if (cooldownTime === 0) {
                startgame();
            }
            return
        }

        const timeLeft = parseInt(data);

        if (!isNaN(timeLeft)) {
            timerEl.textContent = "Time left: " + timeLeft + "s.";

            if (timeLeft === 0) {
                wordInput.disabled = true;
                endgame(10);
            }
        }
    };

    // Handle word submission without full page reload
    wordForm.onsubmit = async function (event) {
        event.preventDefault();
        const word = wordInput.value.trim();

        if (word) {
            const response = await fetch("/", {
                method: "POST",
                body: new URLSearchParams({ word })
            });
            if (response.ok) {
                wordInput.value = "";
                wordInput.focus();
            }
        }
    };
}