// Hidden wearer client: joins the call so routing confirmation (and the AI takeover) works.
import { chromium } from "playwright-core";
const url = process.argv[2];
const b = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true,
  args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"] });
const p = await (await b.newContext()).newPage();
await p.goto(url);
await p.getByRole("button", { name: /join call/i }).first().click();
console.log("wearer joined", new Date().toISOString());
setInterval(() => {}, 60000); // stay open
