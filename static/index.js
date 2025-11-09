let countdownInterval = null;
let reconnectTimer = null;

function get_jwt_from_element() {
    return document.getElementById("login-field").value;
}

async function save_jwt() {
    const jwt = get_jwt_from_element();
    document.cookie = `JWT=${jwt}`;
    await login();
}

async function login() {
    if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
    }

    const user_id = await validate_jwt();
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
            let result = await fetchLeaderboard();
            updateLeaderboard(result);
            updateGrid(result);
        }
    }
}

async function validate_jwt() {
    const resp = await fetch("/validate");
    if (!resp.ok) {
        return null;
    }
    return (await resp.json())["user_id"];
}

async function get_client_secret() {
    const resp = await fetch("/client-secret");
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

    if (turnData.status === "IN_PROGRESS" && turnData.endTime && (turnData.endTime - (Date.now() / 1000)) < 0) {
        document.getElementById("approval_panel").classList.remove("hidden")
    } else {
        document.getElementById("approval_panel").classList.add("hidden")
    }

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
        let countdownInterval = setInterval(updateTimer, 10);
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

    const ticket_ws_url = `${wsProtocol}//${wsHost}/ticket-ws`;
    const ticket_ws = new WebSocket(ticket_ws_url);

    ticket_ws.onmessage = async function(event) {
        let rawData = event.data;
        if (rawData instanceof Blob) {
            rawData = await rawData.text();
        }
        console.log("Received notification for ticket update");
        result = await fetchLeaderboard();
        updateLeaderboard(result);
        updateGrid(result);
    };

    ticket_ws.onclose = async function() {
        console.log("Ticket websocket disconnected. Retrying...");
        scheduleLoginAttempt();
    };
}

function reset_grid() {
    const grid = document.getElementById("grid-container");
    grid.replaceChildren();
}

function append_grid_ticket(name, avatar_url, ticket_id) {
    const grid = document.getElementById("grid-container");
    const avatar_outer = document.createElement("div");
    avatar_outer.classList.add("grid-avatar");

    const avatar_inner = document.createElement("img");
    avatar_inner.src = avatar_url;
    avatar_inner.alt = `@${name} slack profile picture`;

    const tooltip = document.createElement("span");
    tooltip.classList.add("grid-hover-tooltip");
    tooltip.textContent = `@${name} | Ticket ID: #${ticket_id}`

    avatar_outer.appendChild(avatar_inner);
    avatar_outer.appendChild(tooltip);
    grid.appendChild(avatar_outer);
}

async function fetchLeaderboard() {
    try {
        const resp = await fetch("/tickets-no-update");
        if (!resp.ok) {
            console.error("Failed to fetch leaderboard data:", resp.statusText);
            return [];
        }
        const data = await resp.json();
        const leaderboardData = Object.entries(data).map(([userId, [name, tickets, avatar]]) => ({
            id: userId,
            name: name,
            tickets: tickets,
            avatar: avatar
        }));

        leaderboardData.forEach(user => {
            user.hours = (user.tickets - 10) / 10.0;
        });

        return leaderboardData.sort((a, b) => b.hours - a.hours);

    } catch (error) {
        console.error("Error fetching leaderboard:", error);
        return [];
    }
}

function updateLeaderboard(leaderboardData) {
    const leaderboardList = document.getElementById('leaderboard');
    if (!leaderboardList) return;

    const itemHeight = 50;
    const existingItems = new Set();

    leaderboardData.slice(0, 10).forEach((user, index) => {
        const userId = user.id;
        const elementId = `leaderboard-item-${userId}`;
        existingItems.add(elementId);

        let userElement = document.getElementById(elementId);
        if (!userElement) {
            userElement = document.createElement('li');
            userElement.id = elementId;
            userElement.className = 'leaderboard-item';
            leaderboardList.appendChild(userElement);
        }

        userElement.innerHTML = `
            <span class="leaderboard-rank">${index + 1}</span>
            <img class="leaderboard-avatar" src="${user.avatar || 'empty.png'}" alt="${user.name}" />
            <span class="leaderboard-name">${user.name}</span>
            <span class="leaderboard-score">${user.hours.toFixed(1)}h</span>
        `;

        userElement.style.top = `${index * itemHeight}px`;
    });

    Array.from(leaderboardList.children).forEach(child => {
        if (!existingItems.has(child.id)) {
            child.remove();
        }
    });

    leaderboardList.style.height = `${Math.min(leaderboardData.length, 10) * itemHeight}px`;
}

function updateGrid(gridData) {
    gridData = gridData.sort((a, b) => a.id.localeCompare(b.id));
    let ticket_id = 0;
    reset_grid();
    gridData.forEach((user) => {
        for (let i = 0; i < user.tickets; i++) {
            append_grid_ticket(user.name, user.avatar, ticket_id);
            ticket_id++;
        }
    })
}

async function accept() {
    await fetch("/accept")
}

async function reject() {
    await fetch("/reject")
}

window.save_jwt = save_jwt;
window.updateClientSecret = updateClientSecret;

window.addEventListener("load", 
    async () => {
        await login();
        document.getElementById("current-container").addEventListener("click", async () => {
            const component = document.getElementById("current-container");
            if (component.innerHTML == "Leaderboard") {
                component.innerHTML = "Grid";
                document.getElementById("grid-container").classList.remove("hidden");
                document.getElementById("leaderboard-container").classList.add("hidden");
            } else {
                component.innerHTML = "Leaderboard";
                document.getElementById("leaderboard-container").classList.remove("hidden");
                document.getElementById("grid-container").classList.add("hidden");
            }
        })
    }
);