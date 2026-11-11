// Records the Vouch demo video: intro slides, live demo on the deployed site, outro slides.
//   node record.js            -> out/intro.webm, out/demo.webm, out/outro.webm (+ timelines)
//   node record.js --nocap    -> same without burned-in captions (suffix -clean)
const puppeteer = require("puppeteer-core");
const path = require("path");
const fs = require("fs");

const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const SITE = "https://vouch-theta-one.vercel.app";
const OUT = path.join(__dirname, "out");
const NOCAP = process.argv.includes("--nocap");
const SUF = NOCAP ? "-clean" : "";
const PDF = path.resolve(__dirname, "../test-inputs/07-tortured-phrases.pdf");
fs.mkdirSync(OUT, { recursive: true });

const W = (t) => Math.max(3.2, t.split(/\s+/).length / 2.35 + 0.9);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function slides(browser, part) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1920, height: 1080 });
  await page.goto(`file:///${path.join(__dirname, "scenes.html").replace(/\\/g, "/")}?part=${part}${NOCAP ? "&cap=0" : ""}`, { waitUntil: "networkidle0" });
  await page.evaluate(() => document.fonts.ready);
  await sleep(500);
  const rec = await page.screencast({ path: path.join(OUT, `${part}${SUF}.webm`), fps: 30, quality: 18 });
  await sleep(300);
  const timeline = await page.evaluate(() => window.play());
  await sleep(400);
  await rec.stop();
  await page.close();
  return timeline;
}

// ---------- live demo ----------
const OVERLAY = (nocap) => `
(() => {
  if (document.getElementById('__ov')) return;
  const st = document.createElement('style');
  st.textContent = \`
    #__cap{position:fixed;left:0;right:0;bottom:0;height:120px;z-index:99998;display:flex;align-items:center;justify-content:center;padding:0 120px;
      background:rgba(28,26,22,.93);color:#fbf8f2;font:500 29px/1.3 "Public Sans",sans-serif;text-align:center;transition:opacity .25s}
    #__cur{position:fixed;left:700px;top:420px;width:30px;height:30px;z-index:99999;pointer-events:none;transition:left .75s cubic-bezier(.4,.1,.2,1),top .75s cubic-bezier(.4,.1,.2,1)}
    #__cur.click::after{content:"";position:absolute;left:-14px;top:-14px;width:30px;height:30px;border-radius:50%;border:3px solid #a8640f;animation:__p .5s ease-out}
    @keyframes __p{from{transform:scale(.3);opacity:1}to{transform:scale(1.8);opacity:0}}
    #__tag{position:fixed;top:14px;right:18px;z-index:99998;font:500 13px "IBM Plex Mono",monospace;letter-spacing:.18em;text-transform:uppercase;color:#fbf8f2;background:#9e2b25;padding:6px 12px;border-radius:3px}
    \${${nocap} ? '#__cap{display:none}' : 'body{padding-bottom:120px}'}\`;
  document.head.appendChild(st);
  const ov = document.createElement('div'); ov.id = '__ov';
  ov.innerHTML = '<div id="__cap"></div><div id="__tag">● live demo</div><svg id="__cur" viewBox="0 0 24 24"><path d="M3 2l7.5 19 2.6-7.9L21 10.5z" fill="#1c1a16" stroke="#fbf8f2" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  document.body.appendChild(ov);
  window.__setCap = (t) => { const c = document.getElementById('__cap'); c.style.opacity = 0; setTimeout(() => { c.textContent = t; c.style.opacity = 1; }, 180); };
})();`;

async function demo(browser) {
  const page = await browser.newPage();
  await page.setViewport({ width: 1536, height: 864 });
  await page.goto(SITE, { waitUntil: "networkidle0" });
  await page.evaluate(OVERLAY(NOCAP));
  await sleep(800);
  const rec = await page.screencast({ path: path.join(OUT, `demo${SUF}.webm`), fps: 30, quality: 18, scale: 1.25 });
  const t0 = Date.now();
  const timeline = [];

  const cursorTo = async (x, y) => { await page.evaluate((x, y) => { const c = document.getElementById("__cur"); c.style.left = x + "px"; c.style.top = y + "px"; }, x, y); await sleep(850); };
  const clickEl = async (handle) => {
    await handle.evaluate((el) => el.scrollIntoView({ behavior: "smooth", block: "center" }));
    await sleep(700);
    const b = await handle.boundingBox();
    if (!b) console.log("  no box for:", await handle.evaluate((e) => e.outerHTML.slice(0, 160)).catch(() => "detached"));
    await cursorTo(b.x + Math.min(b.width / 2, 120), b.y + b.height / 2);
    await page.evaluate(() => { const c = document.getElementById("__cur"); c.classList.remove("click"); void c.offsetWidth; c.classList.add("click"); });
    await handle.click();
  };
  const clickRow = async (i) => {
    for (let k = 0; k < 10; k++) {
      const all = await page.$$("li.ledger-row > button");
      const rows = [];
      for (const r of all) if (await r.evaluate((el) => el.offsetParent !== null && el.getClientRects().length > 0)) rows.push(r);
      const h = rows[i];
      if (h) {
        await h.evaluate((el) => el.scrollIntoView({ behavior: "smooth", block: "center" })).catch(() => {});
        await sleep(700);
        const b = await h.boundingBox().catch(() => null);
        if (b) { await cursorTo(b.x + Math.min(b.width / 2, 120), b.y + b.height / 2);
          await page.evaluate(() => { const c = document.getElementById("__cur"); c.classList.remove("click"); void c.offsetWidth; c.classList.add("click"); });
          try { await h.click(); return; } catch { /* re-rendered: retry */ } }
      }
      await sleep(500);
    }
    await page.screenshot({ path: path.join(OUT, "fail.png") });
    console.log("url:", page.url(), "rows:", (await page.$$("li.ledger-row")).length, "buttons:", (await page.$$("li.ledger-row > button")).length);
    throw new Error("row " + i + " never clickable");
  };
  const byText = async (sel, text) => {
    const hs = await page.$$(sel);
    for (const h of hs) if (await h.evaluate((e, t) => e.textContent.includes(t) && e.offsetParent !== null && !e.disabled, text)) return h;
    throw new Error(`not found: ${sel} ~ ${text}`);
  };
  const reportReady = async () => {
    await page.waitForFunction(() => location.pathname.startsWith("/report/") && [...document.querySelectorAll("li.ledger-row > button")].some((b) => b.offsetParent !== null) && ![...document.querySelectorAll(".shimmer")].some((b) => b.offsetParent !== null) && [...document.querySelectorAll("button")].some((b) => b.textContent.includes("JSON") && b.offsetParent !== null), { timeout: 60000 });
    await sleep(900);
  };
  const scrollTo = (sel, block = "center") => page.evaluate((sel, block) => document.querySelector(sel)?.scrollIntoView({ behavior: "smooth", block }), sel, block);
  const smoothY = (y) => page.evaluate((y) => window.scrollTo({ top: y, behavior: "smooth" }), y);

  async function step(text, action) {
    console.log("step:", text.slice(0, 50));
    const start = (Date.now() - t0) / 1000;
    await page.evaluate((t) => window.__setCap(t), text);
    const t1 = Date.now();
    await action();
    const left = W(text) * 1000 - (Date.now() - t1);
    if (left > 0) await sleep(left);
    timeline.push({ scene: "demo", start: +start.toFixed(1), end: +((Date.now() - t0) / 1000).toFixed(1), text });
  }

  await step("Let's see it live. This example mixes six fake citations from accepted NeurIPS 2025 papers with four real ones.", async () => {
    await sleep(2500);
    await clickEl(await byText("button", "NeurIPS 2025 fakes"));
    await reportReady();
  });
  await step("In seconds, all six fakes are flagged, and all four real references are verified.", async () => {
    await sleep(600);
    await smoothY(260);
  });
  await step("Here, a real paper, WebVoyager, was cited with invented authors: John Doe and Jane Smith. Vouch shows the real record, and exactly which field disagrees.", async () => {
    await clickRow(0);
    await sleep(900);
    await scrollTo("li.ledger-row", "start");
  });
  await step("And here, Kingma and Ba, the authors of the Adam optimizer, are credited with a paper they never wrote.", async () => {
    await clickRow(1);
    await sleep(700);
    const r = await page.$$("li.ledger-row");
    await r[1].evaluate((el) => el.scrollIntoView({ behavior: "smooth", block: "start" }));
  });
  await step("Vouch also catches retracted work, like the Wakefield vaccine paper and the Surgisphere COVID study, with the official retraction notice.", async () => {
    await smoothY(0);
    await sleep(700);
    await clickEl(await byText("header a", "Check"));
    await page.waitForFunction(() => [...document.querySelectorAll("button")].some((b) => b.textContent.includes("Retracted papers")));
    await sleep(500);
    await clickEl(await byText("button", "Retracted papers"));
    await reportReady();
    await sleep(900);
    await clickRow(0);
    await sleep(600);
    await scrollTo("li.ledger-row", "start");
  });
  await step("Upload a PDF, and Vouch reads the full text too, looking for paper-mill phrases.", async () => {
    await smoothY(0);
    await sleep(600);
    await clickEl(await byText("header a", "Check"));
    await page.waitForFunction(() => [...document.querySelectorAll("button[role=tab]")].some((b) => b.textContent.includes("PDF upload") && b.offsetParent !== null));
    await sleep(400);
    await clickEl(await byText("button[role=tab]", "PDF upload"));
    await sleep(500);
    const input = await page.$("input[type=file]");
    await input.uploadFile(PDF);
    await sleep(800);
    await clickEl(await byText("button[type=submit]", "Check citations"));
    await page.waitForFunction(() => location.pathname.startsWith("/report/") && [...document.querySelectorAll("p")].some((p) => p.textContent.includes("tortured phrase") && p.offsetParent !== null), { timeout: 120000 });
    await sleep(500);
  });
  await step("Here: 'counterfeit consciousness' instead of 'artificial intelligence', and 'irregular woodland' for 'random forest'. A reason to read closer, never an accusation.", async () => {
    await smoothY(380);
    await sleep(2500);
  });
  await sleep(1200);
  await rec.stop();
  await page.close();
  return timeline;
}

(async () => {
  const browser = await puppeteer.launch({ executablePath: EDGE, headless: true, args: ["--hide-scrollbars", "--disable-gpu"], defaultViewport: null });
  const which = process.argv.find((a) => ["intro", "demo", "outro"].includes(a));
  const out = {};
  try {
    if (!which || which === "intro") out.intro = await slides(browser, "intro");
    if (!which || which === "demo") out.demo = await demo(browser);
    if (!which || which === "outro") out.outro = await slides(browser, "outro");
  } finally {
    await browser.close();
  }
  for (const [k, v] of Object.entries(out)) fs.writeFileSync(path.join(OUT, `${k}${SUF}.timeline.json`), JSON.stringify(v, null, 1));
  console.log("recorded", Object.keys(out).join(", "));
})();
