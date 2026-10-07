#!/usr/bin/env node
/**
 * AI News 英文站版式门禁（抬头/横向溢出自动拦截）
 * =================================================
 * 用本机 Chrome headless + CDP 实测每个英文 HTML 页面，
 * 在手机(390)与桌面(1440)两档视口下断言：
 *   1) 文档不产生横向溢出（scrollWidth > 视口宽度即 FAIL）；
 *   2) 顶部导航/页头不越出视口左右边界；
 *   3) 页头内容未被挤成异常高列（height 超过阈值即 FAIL）。
 *
 * 抗误报：等待 load 事件 + 布局稳定；首次判定失败后再复测一次，
 * 只有连续两次都失败才计入 FAIL（避免抓到导航中间态）。
 *
 * 依赖：仅需要本机 Google Chrome；Node >= 18（自带 fetch / WebSocket）。
 * 用法：
 *   node scripts/check_en_layout.mjs                 # 扫描 ./en，自起静态服务
 *   node scripts/check_en_layout.mjs --dir en        # 指定扫描目录
 *   node scripts/check_en_layout.mjs --base http://127.0.0.1:8912   # 复用已在跑的服务
 *   node scripts/check_en_layout.mjs --file en/2026-10/2026-10-06.html   # 只查单页
 * 退出码：0 = 全绿；1 = 有 FAIL；2 = 环境/启动异常
 */
import { spawn } from "node:child_process";
import { readdirSync, statSync, existsSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";
import { createServer } from "node:http";

const CHROME_CANDIDATES = [
  process.env.CHROME,
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome",
  "/usr/bin/chromium",
].filter(Boolean);

const args = process.argv.slice(2);
const getArg = (name, def) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : def;
};
const ROOT = process.cwd();
const SCAN_DIR = join(ROOT, getArg("--dir", "en"));
const EXTERNAL_BASE = getArg("--base", null);
const ONLY_FILE = getArg("--file", null);
const VIEWPORTS = [390, 1440];
const HEADER_MAX_H = { 390: 240, 1440: 260 };

if (!existsSync(SCAN_DIR)) { console.error(`扫描目录不存在: ${SCAN_DIR}`); process.exit(2); }
const CHROME = CHROME_CANDIDATES.find((p) => existsSync(p));
if (!CHROME) { console.error("未找到 Chrome，可设置环境变量 CHROME"); process.exit(2); }

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
function walk(dir) {
  let out = [];
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    const st = statSync(p);
    if (st.isDirectory()) out = out.concat(walk(p));
    else if (e.endsWith(".html")) out.push(p);
  }
  return out.sort();
}

const MIME = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp", ".svg": "image/svg+xml", ".ico": "image/x-icon", ".woff2": "font/woff2" };

function startStaticServer() {
  return new Promise((resolve) => {
    const srv = createServer((req, res) => {
      try {
        const url = decodeURIComponent(req.url.split("?")[0]);
        let fp = join(ROOT, url);
        if (statSync(fp).isDirectory()) fp = join(fp, "index.html");
        const ext = fp.slice(fp.lastIndexOf(".")).toLowerCase();
        res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
        res.end(readFileSync(fp));
      } catch {
        res.writeHead(404); res.end("not found");
      }
    });
    srv.listen(0, "127.0.0.1", () => resolve(srv));
  });
}

// 探测文档级横向溢出 + 页头几何
const DOC_PROBE = `(() => {
  const de = document.documentElement;
  return JSON.stringify({ vw: innerWidth, doc: de.scrollWidth, ready: document.readyState });
})()`;
// 探测页头是否越界/被挤成高列
const HEADER_PROBE = `(() => {
  const hdr = document.querySelector('.site-header, .site-nav, .site-header-inner, .site-nav-inner, .site-nav-lite, header');
  if (!hdr) return JSON.stringify({ hasHeader: false });
  const r = hdr.getBoundingClientRect();
  return JSON.stringify({ hasHeader: true, left: Math.round(r.left), right: Math.round(r.right), h: Math.round(r.height) });
})()`;
// 定位溢出元凶（仅失败时调用，便于排查）
const OFFENDER_PROBE = `(() => {
  const vw = innerWidth, out = [];
  document.querySelectorAll('body *').forEach((el) => {
    const r = el.getBoundingClientRect();
    if (r.width <= 0 || r.height <= 0) return;
    if (r.right > vw + 1 || r.left < -1) {
      out.push(el.tagName.toLowerCase() + '.' + String(el.className || '').split(' ')[0] + '[' + Math.round(r.left) + '..' + Math.round(r.right) + ']');
    }
  });
  return out.slice(0, 6).join(' | ');
})()`;

async function main() {
  const files = (ONLY_FILE
    ? [ONLY_FILE]
    : walk(SCAN_DIR).map((p) => relative(ROOT, p))
  ).map((f) => f.replace(/^\.\//, ""));
  if (ONLY_FILE) {
    const abs = join(ROOT, files[0]);
    if (!existsSync(abs)) { console.error(`单页不存在: ${abs}`); process.exit(2); }
  }
  let srv = null;
  let base = EXTERNAL_BASE;
  if (!base) {
    srv = await startStaticServer();
    base = `http://127.0.0.1:${srv.address().port}/`;
  } else if (!base.endsWith("/")) base += "/";

  const CDP = 9222 + Math.floor(Math.random() * 2000);
  const chrome = spawn(CHROME, [
    "--headless=new", "--disable-gpu", "--no-first-run", "--no-sandbox",
    "--disable-background-timer-throttling", "--disable-renderer-backgrounding",
    "--remote-allow-origins=*", `--remote-debugging-port=${CDP}`, "about:blank",
  ]);
  const cleanup = () => { try { chrome.kill(); } catch {} if (srv) { try { srv.close(); } catch {} } };

  let list = null;
  for (let attempt = 0; attempt < 8; attempt++) {
    await sleep(800);
    try {
      const res = await fetch(`http://127.0.0.1:${CDP}/json/list`);
      if (res.ok) { list = await res.json(); break; }
    } catch {}
  }
  if (!list) { console.error("无法连接 Chrome CDP"); cleanup(); process.exit(2); }
  const target = list.find((t) => t.type === "page") || list[0];
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));

  let id = 0; const pending = new Map(); const loadWaiters = [];
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.method === "Page.loadEventFired") { while (loadWaiters.length) loadWaiters.shift()(); return; }
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  const send = (method, params = {}) => new Promise((resolve) => { const n = ++id; pending.set(n, resolve); ws.send(JSON.stringify({ id: n, method, params })); });
  const evalJson = async (expr) => {
    const ev = await send("Runtime.evaluate", { expression: expr, returnByValue: true });
    if (!ev.result || !ev.result.result || ev.result.result.value == null) return null;
    try { return JSON.parse(ev.result.result.value); } catch { return null; }
  };
  const waitLoad = (ms) => new Promise((resolve) => {
    let done = false;
    const t = setTimeout(() => { if (!done) { done = true; resolve(false); } }, ms);
    loadWaiters.push(() => { if (!done) { done = true; clearTimeout(t); resolve(true); } });
  });

  await send("Page.enable"); await send("Runtime.enable");

  const measure = async (w, rel) => {
    const url = base + rel;
    const p = waitLoad(6000);
    await send("Page.navigate", { url });
    await p;
    const d1 = await evalJson(DOC_PROBE);
    await sleep(120);
    const d2 = await evalJson(DOC_PROBE);
    const h = await evalJson(HEADER_PROBE);
    const why = [];
    const doc = Math.max(d1?.doc ?? 0, d2?.doc ?? 0);
    if (doc > w + 1) why.push(`h-overflow(${doc}>${w})`);
    if (!h || !h.hasHeader) why.push("no-header");
    else {
      if (h.right > w + 1 || h.left < -1) why.push(`header-out(${h.left}..${h.right})`);
      if (h.h > HEADER_MAX_H[w]) why.push(`header-too-tall(${h.h})`);
    }
    if (why.length) {
      const off = await evalJson(OFFENDER_PROBE);
      if (off) why.push(`offenders: ${off}`);
    }
    return why;
  };

  const failures = []; let checked = 0;
  for (const w of VIEWPORTS) {
    await send("Emulation.setDeviceMetricsOverride", { width: w, height: 900, deviceScaleFactor: 1, mobile: w < 600 });
    for (const rel of files) {
      checked++;
      let why = await measure(w, rel);
      if (why.length) {
        // 首次失败 → 给布局一次稳定机会后复测；连续两次才算真 FAIL
        await sleep(900);
        const retry = await measure(w, rel);
        if (retry.length) failures.push({ rel, w, why: retry.join(", "), first: why.join(", ") });
      }
    }
  }
  try { ws.close(); } catch {}
  cleanup();

  console.log(`\n[check_en_layout] 视口 ${VIEWPORTS.join("/")}px  页面 ${files.length}  检查 ${checked} 次`);
  if (failures.length) {
    for (const f of failures.slice(0, 60)) console.log(`  FAIL  ${f.w}px  ${f.rel}  ::  ${f.why}`);
    console.log(`\n结论：FAIL —— ${failures.length} 项版式问题（抬头歪斜 / 横向溢出）。`);
    process.exit(1);
  }
  console.log("结论：PASS —— 全部页面抬头端正、无横向溢出。");
  process.exit(0);
}

main().catch((e) => { console.error("门禁异常：", e.message); process.exit(2); });
