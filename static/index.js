let countdownInterval = null;
let reconnectTimer = null;

function get_jwt_from_element() {
    return document.getElementById("login-field").value;
}

async function save_jwt() {
    jwt = get_jwt_from_element();
    document.cookie = `JWT=${jwt}`;
    await login();
}

async function login() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    user_id = await validate_jwt();
    set_login_with(user_id);
    if (user_id !== null) {
        const turnStatus = await get_turn_status();
        if (turnStatus.status === "ERROR") {
            updateClientSecret("No active game found.");
            updateTurnStatus({ status: "Waiting for an active game..." });
            scheduleLoginAttempt();
        } else {
            updateClientSecret(await get_client_secret());
            updateTurnStatus(turnStatus);
            connect_ws();
        }
    }
}

async function validate_jwt() {
    resp = await fetch("/validate");
    if (!resp.ok) {
        return null;
    }
    return (await resp.json())["user_id"];
}

async function get_client_secret() {
    resp = await fetch("/client-secret");
    if (!resp.ok) {
        return null;
    }
    return (await resp.json())["client_secret"];
}

async function get_turn_status() {
    const resp = await fetch("/turn-status");
    if (!resp.ok) {
        return { status: "ERROR" };
    }
    return await resp.json();
}

function set_login_with(user_id, is_init=false) {
    if (user_id === null) {
        if (!is_init)
            document.getElementById("login-err").innerHTML = "Invalid JWT";
    } else {
        document.getElementById("login-err").innerHTML = "";
        document.getElementById("login").style.display = "none";
        document.getElementById("authenticated").style.display = "unset";
        document.getElementById("user_id").innerHTML = user_id;
    }
}

function updateClientSecret(newValue) {
    const container = document.getElementById("client-secret-container");
    const oldValueSpan = container.querySelector("span:not(.roll-out)");

    if (oldValueSpan && oldValueSpan.textContent === newValue) {
        return;
    }

    const newValueSpan = document.createElement("span");
    newValueSpan.textContent = newValue;
    newValueSpan.classList.add("roll-in");
    newValueSpan.classList.add("client-transaction");

    newValueSpan.addEventListener('animationend', () => {
        newValueSpan.classList.remove('roll-in');
    }, { once: true });

    container.appendChild(newValueSpan);

    if (oldValueSpan) {
        oldValueSpan.classList.add("roll-out");
        oldValueSpan.addEventListener('animationend', () => {
            oldValueSpan.remove();
        }, { once: true });
    }
}

function updateTurnStatus(turnData) {
    const statusDisplay = document.getElementById('turn-status-display');
    const countdownContainer = document.getElementById('countdown-container');
    const countdownDisplay = document.getElementById('countdown-display');

    if (countdownInterval) {
        clearInterval(countdownInterval);
        countdownInterval = null;
    }
    countdownDisplay.classList.remove('flash-red');

    const userName = turnData.user_name || turnData.user_id || 'N/A';

    if (turnData.status === 'IN_PROGRESS' && turnData.endTime) {
        statusDisplay.textContent = `Live: ${userName}`;
        countdownContainer.style.display = 'unset';

        const updateTimer = () => {
            const secondsRemaining = turnData.endTime - (Date.now() / 1000);

            if (secondsRemaining <= 0) {
                clearInterval(countdownInterval);
                countdownDisplay.textContent = "00:00.00";
                countdownDisplay.classList.add('flash-red');
                return;
            }

            if (secondsRemaining <= 10) {
                countdownDisplay.classList.add('flash-red');
            } else {
                countdownDisplay.classList.remove('flash-red');
            }

            const totalSeconds = Math.floor(secondsRemaining);
            const minutes = Math.floor(totalSeconds / 60);
            const seconds = totalSeconds % 60;
            const centiseconds = Math.floor((secondsRemaining * 100) % 100);

            countdownDisplay.textContent = 
                `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(centiseconds).padStart(2, '0')}`;
        };

        updateTimer();
        countdownInterval = setInterval(updateTimer, 10);
    } else if (turnData.status === 'PENDING') {
        statusDisplay.textContent = `Waiting for: ${userName}`;
        countdownContainer.style.display = 'none';
    } else {
        countdownContainer.style.display = 'none';
        statusDisplay.textContent = turnData.status;
    }
}

function scheduleLoginAttempt() {
    if (reconnectTimer) {
        return;
    }
    console.log("No active game found. Checking again in 5 seconds...");
    reconnectTimer = setTimeout(async () => {
        await login();
    }, 5000);
}

function connect_ws() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host;

    const secret_ws_url = `${wsProtocol}//${wsHost}/client-secret-ws`;
    const secret_ws = new WebSocket(secret_ws_url);

    secret_ws.onmessage = async function(event) {
        let rawData = event.data;
        if (rawData instanceof Blob) {
            rawData = await rawData.text();
        }
        try {
            const message = JSON.parse(rawData);
            if (message.type === 'secret') {
                updateClientSecret(message.value);
            }
        } catch (e) {
            updateClientSecret(rawData);
        }
    };

    secret_ws.onclose = async function() {
        updateClientSecret("Websocket disconnected. Retrying...");
        scheduleLoginAttempt();
    };

    const turn_ws_url = `${wsProtocol}//${wsHost}/turn-ws`;
    const turn_ws = new WebSocket(turn_ws_url);

    turn_ws.onmessage = async function(event) {
        let rawData = event.data;
        if (rawData instanceof Blob) {
            rawData = await rawData.text();
        }
        try {
            const message = JSON.parse(rawData);
            if (message.type === 'turn_update') {
                updateTurnStatus(message);
            }
        } catch (e) {
            console.error("Failed to parse turn update message:", e);
        }
    };

    turn_ws.onclose = async function() {
        updateTurnStatus({ status: "Websocket disconnected. Retrying..." });
        scheduleLoginAttempt();
    };
}

window.save_jwt = save_jwt;
window.updateClientSecret = updateClientSecret;

window.addEventListener("load", 
    async () => {
        await login();
    }
);