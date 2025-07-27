import { loginAndGetToken } from "./msalInit";

document.getElementById("scan-btn").onclick = async function() {
    const token = await loginAndGetToken();
    if (!token) return; // Login will redirect

    fetch("/scan/orphaned", {
        method: "GET",
        headers: {
            "Authorization": `Bearer ${token}`
        }
    })
    .then(resp => resp.json())
    .then(data => {
        // handle data
    })
    .catch(err => {
        // handle error
    });
};