const fs = require("fs");
let raw = process.env.API_PAYLOAD || "";
if (!raw) {
  raw = fs.readFileSync(0, "utf8") || "{}";
}
const payload = JSON.parse(raw);
const query = JSON.parse(process.env.API_QUERY || "{}");
process.stdout.write(JSON.stringify({ echo: payload, query }));
