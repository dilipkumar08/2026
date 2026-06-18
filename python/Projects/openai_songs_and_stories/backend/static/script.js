const promptBox = document.getElementById("prompt");
const messages = document.getElementById("messages");

promptBox.addEventListener("keydown", function(e) {

    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }

});

function addUserMessage(text) {

    messages.querySelector(".welcome")?.remove();

    messages.innerHTML += `
        <div class="message-row user-row">
            <div class="message user-message">
                ${text}
            </div>
        </div>
    `;

    messages.scrollTop = messages.scrollHeight;
}

function addAssistantMessage(text, audioBase64) {

    let audioHTML = "";

    if (audioBase64) {
        audioHTML = `
            <div class="audio-container">
                <audio controls>
                    <source src="data:audio/mp3;base64,${audioBase64}" type="audio/mpeg">
                </audio>
            </div>
        `;
    }

    messages.innerHTML += `
        <div class="message-row assistant-row">
            <div class="message assistant-message">
                ${text}
                ${audioHTML}
            </div>
        </div>
    `;

    messages.scrollTop = messages.scrollHeight;
}

async function sendMessage() {

    const prompt = promptBox.value.trim();

    if (!prompt) return;

    addUserMessage(prompt);

    promptBox.value = "";

    messages.innerHTML += `
        <div id="loading" class="message-row assistant-row">
            <div class="message assistant-message loading">
                Generating...
            </div>
        </div>
    `;

    messages.scrollTop = messages.scrollHeight;

    try {

        const response = await fetch(
            "http://127.0.0.1:8000/api/process",
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    input: prompt
                })
            }
        );

        const data = await response.json();

        document.getElementById("loading").remove();

        addAssistantMessage(
            data.content,
            data.audio
        );

    } catch (error) {

        document.getElementById("loading").remove();

        addAssistantMessage(
            "Error connecting to backend.",
            null
        );

        console.error(error);
    }
}