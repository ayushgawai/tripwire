// Hidden caller page that listens on the REAL laptop mic (live captions) for the demo.
import { chromium } from "playwright-core";
const url = process.argv[2];
const b = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true,
  args: ["--use-fake-ui-for-media-stream", "--autoplay-policy=no-user-gesture-required"] });
const p = await (await b.newContext({ permissions: ["microphone"] })).newPage();
p.on("console", (m) => { if (m.type() === "error") console.log("[caller err]", m.text().slice(0, 140)); });
await p.goto(url);
await p.getByRole("button", { name: /join call/i }).first().click();
console.log("caller joined; captions should be live", new Date().toISOString());
setInterval(async () => { try { const t = await p.evaluate(() => document.body.innerText.match(/Live captions[\s\S]{0,80}/i)?.[0]); console.log("captions:", (t||"").replace(/\s+/g," ").slice(0,100)); } catch {} }, 5000);
await new Promise(() => {});
