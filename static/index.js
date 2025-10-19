function get_jwt_from_element() {
    return document.getElementById("login-field").value;
}

async function save_jwt() {
    jwt = get_jwt_from_element();
    document.cookie = `JWT=${jwt}`;
    result = await validate_jwt();
    set_login_with(result);
}

async function validate_jwt() {
    resp = await fetch("/validate");
    if (!resp.ok) {
        return null;
    }
    return await resp.json().user_id;
}

function set_login_with(user_id) {
    if (result === null) {
        document.getElementById("login-err").innerHTML = "Invalid JWT";
    } else {
        document.getElementById("login-err").innerHTML = "";
        document.getElementById("login").style.visibility = false;
        document.getElementById("authenticated").style.visibility = true;
        document.getElementById("user-id").innerHTML = user_id;
    }
}

window.save_jwt = save_jwt;

window.addEventListener("load", 
    async () => {
        user_id = await validate_jwt();
        set_login_with(user_id);
    }
);