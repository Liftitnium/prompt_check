// Where the two APIs live. This is the local (docker compose) setting; a deployment
// replaces this file with its own URLs, so app.js never hardcodes an address.
window.PROMPTCHECK_CONFIG = {
  promptsUrl: "http://localhost:8001",
  evalsUrl: "http://localhost:8002",
};
