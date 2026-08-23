import express from "express";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createProxyMiddleware } from "http-proxy-middleware";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const port = Number(process.env.PORT || 3000);
const apiUrl = process.env.API_URL || "http://api:8000";

app.use(
  ["/v1", "/healthz"],
  createProxyMiddleware({
    target: apiUrl,
    changeOrigin: true,
  }),
);

app.use(express.static(path.join(__dirname, "dist")));
app.get("*", (_req, res) => {
  res.sendFile(path.join(__dirname, "dist", "index.html"));
});

app.listen(port, "0.0.0.0", () => {
  console.log(JSON.stringify({ msg: "web_listen", port, apiUrl }));
});
