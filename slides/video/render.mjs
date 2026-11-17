// 逐帧录制讲解视频：无头浏览器打开 film.html，每一帧调一次 renderFrame(t) 再截图，
// 截图直接喂给 ffmpeg 压成 MP4。每镜单独一个文件，改了一镜只重录这一镜，最后拼起来。
//
// 用法（在仓库根目录）：
//   node slides/video/render.mjs <构建目录> <首镜>-<末镜>                 录视频
//   node slides/video/render.mjs <构建目录> <首镜>-<末镜> --at 3.2,10-12/8   只截这些时刻的图（秒；a-b/n 是 a 到 b 均匀取 n 张）
//   node slides/video/render.mjs <构建目录> <首镜>-<末镜> --beats              打印每个动作的时刻
//   以上都可以加 --eval "<代码>"，打开页面后先执行，出样品切换画法用
// 构建目录里要先有 data.json（export_data.py 导出）和 fonts/（NotoSansSC.ttf、Inter.ttf）。

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { homedir } from "node:os";
import { spawn } from "node:child_process";

// Playwright 用截图技能目录里装好的那一份，不往项目里装
const SKILL_DIR = join(homedir(), ".claude/skills/browser-screenshot");
const { chromium } = await import(join(SKILL_DIR, "node_modules/playwright/index.mjs"));

const HERE = dirname(fileURLToPath(import.meta.url));
const FPS = 60;

// ---------- 语速和每镜的时长 ----------
// 还没有配音，先按语速估每个字什么时候念到；以后有了真配音，用配音的时间替换 times 即可。
const RATE = 4.2;  // 每秒念几个“字”，约每分钟 250 字

// 每镜在旁白前后留的时间（秒），给画面动作让出空间。没写的用默认值
const LEAD = { default: 0.35, 2: 1.1, 4: 0.7, 5: 0.8, 6: 0.5, 7: 0.6 };   // 开口前
const EXTRA = { default: 0.35, 1: 1.6, 5: 0.6, 6: 1.4, 7: 1.0, 8: 0.6, 9: 1.6 };  // 念完后

// 每个字念起来占多少“字”的时间：汉字算 1；一串英文字母按一个词算；一串数字按位数算；标点是停顿
function speechWeights(text) {
  const weights = new Array(text.length).fill(1);
  for (const m of text.matchAll(/[A-Za-z]+|[0-9]+/g)) {
    const isWord = /[A-Za-z]/.test(m[0]);
    const total = isWord ? 1.2 + 0.15 * m[0].length : 0.3 + 0.9 * m[0].length;
    for (let i = 0; i < m[0].length; i++) weights[m.index + i] = total / m[0].length;
  }
  const pause = { "，": 0.9, "。": 1.3, "；": 1.1, "、": 0.6, " ": 0 };
  for (let i = 0; i < text.length; i++) if (text[i] in pause) weights[i] = pause[text[i]];
  return weights;
}

// ---------- 读分镜 ----------

// 分镜表的一行长这样：| 镜 | 秒 | 画面与动效 | 屏幕字 | 配音 / 字幕 |
// 单元格里的竖线都是全角“｜”，所以按半角 | 切开是安全的
function readStoryboard() {
  const text = readFileSync(join(HERE, "../video_storyboard.md"), "utf8");
  const shots = [];
  for (const line of text.split("\n")) {
    if (!/^\| \d+ \| \d+ \|/.test(line)) continue;
    const cells = line.split("|").slice(1, -1).map((c) => c.trim());
    if (cells.length !== 5) throw new Error(`分镜这一行不是 5 列：${line}`);
    shots.push({ n: Number(cells[0]), voice: cells[4] });
  }

  let start = 0;
  for (const shot of shots) {
    const lead = LEAD[shot.n] ?? LEAD.default;
    const extra = EXTRA[shot.n] ?? EXTRA.default;
    const weights = speechWeights(shot.voice);
    // times[i]：第 i 个字开始念的时刻；times[字数] 是念完的时刻
    shot.times = [start + lead];
    for (const w of weights) shot.times.push(shot.times[shot.times.length - 1] + w / RATE);
    shot.start = start;
    shot.secs = Math.round((shot.times[shot.times.length - 1] - start + extra) * FPS) / FPS;
    shot.subs = splitSubtitles(shot);
    start += shot.secs;
  }
  return shots;
}

// 一镜的旁白切成几句字幕，一次显示一句：先按逗号、句号切成小句，
// 再把相邻的小句拼起来，每句不超过 MAX_CHARS 个字。每句在念到它的第一个字时出现
const MAX_CHARS = 24;
function splitSubtitles(shot) {
  const pieces = [...shot.voice.matchAll(/[^，。；]+[，。；]?/g)].map((m) => ({ text: m[0], index: m.index }));
  const lines = [];
  for (const p of pieces) {
    const last = lines[lines.length - 1];
    if (last && (last.text + p.text).length <= MAX_CHARS) last.text += p.text;
    else lines.push({ ...p });
  }
  const shotEnd = shot.start + shot.secs;
  const speakEnd = shot.times[shot.times.length - 1];
  return lines.map((l, i) => ({
    // 字幕习惯：句末标点去掉，句中的逗号、句号换成空格
    text: l.text.replace(/[，。；]$/, "").replace(/[，。；]/g, " "),
    start: shot.times[l.index],
    end: i + 1 < lines.length ? shot.times[lines[i + 1].index] : Math.min(speakEnd + 0.5, shotEnd - 0.05),
  }));
}

// ---------- 字幕文件（以后配音、或上传视频网站时用） ----------

function srtTime(sec) {
  const ms = Math.max(0, Math.round(sec * 1000));
  const pad = (n, w = 2) => String(n).padStart(w, "0");
  return `${pad(Math.floor(ms / 3600000))}:${pad(Math.floor(ms / 60000) % 60)}:${pad(Math.floor(ms / 1000) % 60)},${pad(ms % 1000, 3)}`;
}
function writeSrt(shots, path, offset) {
  const blocks = [];
  for (const shot of shots) {
    for (const sub of shot.subs) {
      blocks.push(`${blocks.length + 1}\n${srtTime(sub.start - offset)} --> ${srtTime(sub.end - offset)}\n${sub.text}\n`);
    }
  }
  writeFileSync(path, blocks.join("\n"));
}

// ---------- 浏览器 ----------

async function openFilm(buildDir, story) {
  const browser = await chromium.launch({
    env: { ...process.env, LD_LIBRARY_PATH: join(SKILL_DIR, "vendor-lib") },
  });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => console.error("页面出错：", e));
  page.on("console", (m) => m.type() === "error" && console.error("页面报错：", m.text()));

  // 页面用一个假域名打开，请求由这里从硬盘上取：页面代码在仓库里，数据和字体在构建目录里
  await page.route("http://film.local/**", (route) => {
    const name = new URL(route.request().url()).pathname.slice(1);
    const fromBuild = name === "data.json" || name.startsWith("fonts/");
    route.fulfill({ path: fromBuild ? join(buildDir, name) : join(HERE, name) });
  });
  await page.goto("http://film.local/film.html");
  const data = JSON.parse(readFileSync(join(buildDir, "data.json"), "utf8"));
  await page.evaluate(async ([s, d]) => await setup(s, d, "http://film.local/fonts"), [story, data]);
  return { browser, page };
}

async function frameJpeg(page, t) {
  await page.evaluate((time) => renderFrame(time), t);
  return page.screenshot({ type: "jpeg", quality: 94 });
}

// 录一镜：逐帧画、截图，图片从管道直接进 ffmpeg
async function renderShot(page, shot, outPath) {
  const ffmpeg = spawn("ffmpeg", [
    "-y", "-loglevel", "error",
    "-f", "image2pipe", "-vcodec", "mjpeg", "-framerate", String(FPS), "-i", "-",
    "-c:v", "libx264", "-preset", "medium", "-crf", "17", "-tune", "animation",
    "-pix_fmt", "yuv420p", outPath,
  ], { stdio: ["pipe", "inherit", "inherit"] });
  const frames = Math.round(shot.secs * FPS);
  for (let f = 0; f < frames; f++) {
    const jpeg = await frameJpeg(page, shot.start + f / FPS);
    if (!ffmpeg.stdin.write(jpeg)) await new Promise((r) => ffmpeg.stdin.once("drain", r));
  }
  ffmpeg.stdin.end();
  await new Promise((r, j) => ffmpeg.on("close", (code) => (code === 0 ? r() : j(new Error(`ffmpeg 退出码 ${code}`)))));
}

function run(cmd, args) {
  return new Promise((r, j) => {
    const p = spawn(cmd, args, { stdio: "inherit" });
    p.on("close", (code) => (code === 0 ? r() : j(new Error(`${cmd} 退出码 ${code}`))));
  });
}

// "3.2,10-12/8" → [3.2, 10, 10.29, …, 12]
function parseTimes(spec) {
  const out = [];
  for (const part of spec.split(",")) {
    const m = part.match(/^([\d.]+)-([\d.]+)\/(\d+)$/);
    if (!m) {
      out.push(Number(part));
      continue;
    }
    const [a, b, n] = [Number(m[1]), Number(m[2]), Number(m[3])];
    for (let i = 0; i < n; i++) out.push(a + ((b - a) * i) / Math.max(1, n - 1));
  }
  return out;
}

// ---------- 主流程 ----------

const buildDir = resolve(process.argv[2]);
const [first, last] = process.argv[3].split("-").map(Number);
const atIndex = process.argv.indexOf("--at");

const all = readStoryboard();
const chosen = all.filter((s) => s.n >= first && s.n <= last);
for (const s of chosen) console.log(`镜 ${s.n}：${s.start.toFixed(2)} 秒起，${s.secs.toFixed(2)} 秒`);
const { browser, page } = await openFilm(buildDir, { shots: all });
// --eval "<代码>"：打开页面后先执行一段代码，出样品时切换画法用，比如 --eval "BOX_STYLE='slant'"
const evalIndex = process.argv.indexOf("--eval");
if (evalIndex > 0) await page.evaluate(process.argv[evalIndex + 1]);

if (process.argv.includes("--beats")) {
  // 打印每个动作的时刻（秒），抽帧检查时对准用
  const beats = await page.evaluate(() => ({ ...B, ...(typeof B2 === "undefined" ? {} : B2) }));
  // 有的动作每种方法一个时刻，是个数组
  const show = (t) => (Array.isArray(t) ? t.map(show).join("  ") : Number.isFinite(t) ? t.toFixed(2) : "∞");
  for (const [name, t] of Object.entries(beats)) console.log(name.padEnd(10), show(t));
} else if (atIndex > 0) {
  const dir = join(buildDir, "stills");
  mkdirSync(dir, { recursive: true });
  for (const t of parseTimes(process.argv[atIndex + 1])) {
    await page.evaluate((time) => renderFrame(time), t);
    await page.screenshot({ path: join(dir, `t${t.toFixed(2).padStart(6, "0")}.png`) });
  }
} else {
  mkdirSync(join(buildDir, "shots"), { recursive: true });
  const list = [];
  for (const shot of chosen) {
    const out = join(buildDir, "shots", `shot${String(shot.n).padStart(2, "0")}.mp4`);
    const began = Date.now();
    await renderShot(page, shot, out);
    console.log(`镜 ${shot.n} 录完，用了 ${((Date.now() - began) / 1000).toFixed(0)} 秒`);
    list.push(`file '${out}'`);
  }
  const name = `film_${first}-${last}`;
  writeFileSync(join(buildDir, `${name}.txt`), list.join("\n") + "\n");
  await run("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
    "-i", join(buildDir, `${name}.txt`), "-c", "copy", join(buildDir, `${name}.mp4`)]);
  writeSrt(chosen, join(buildDir, `${name}.srt`), chosen[0].start);
  console.log("成片：", join(buildDir, `${name}.mp4`));
}
await browser.close();
