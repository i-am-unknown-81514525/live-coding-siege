function get_jwt_from_element() {
    return document.getElementById("login-field").value;
}

async function save_jwt() {
    jwt = get_jwt_from_element();
    document.cookie = `JWT=${jwt}`;
    
}

async function login() {
    user_id = await validate_jwt();
    set_login_with(user_id);
    if (user_id !== null) {
        connect_ws();
    }
}

async function validate_jwt() {
    resp = await fetch("/validate");
    if (!resp.ok) {
        return null;
    }
    return (await resp.json())["user_id"];
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

function connect_ws() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws_url = `${protocol}//${window.location.host}/client-secret-ws`;

    const ws = new WebSocket(ws_url);

    ws.onmessage = async function(event) {
        let messageData = event.data;
        if (messageData instanceof Blob) {
            messageData = await messageData.text();
        }
        updateClientSecret(messageData);
    };

    ws.onclose = async function() {
        updateClientSecret("Websocket disconnected");
        await login();
    };
}

window.save_jwt = save_jwt;
window.updateClientSecret = updateClientSecret;

window.addEventListener("load", 
    async () => {
        await login();
    }
);