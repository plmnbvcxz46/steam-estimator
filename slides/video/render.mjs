// 逐帧录制讲解视频：无头浏览器打开 film.html，每一帧调一次 renderFrame(t) 再截图，
// 截图直接喂给 ffmpeg 压成 MP4。每镜单独一个文件，改了一镜只重录这一镜，最后拼起来。
//
// 用法（在仓库根目录）：
//   node slides/video/render.mjs <构建目录> <首镜>-<末镜>                 录视频
//   node slides/video/render.mjs <构建目录> <首镜>-<末镜> --at 3.2,10-12/8   只截这些时刻的图（秒；a-b/n 是 a 到 b 均匀取 n 张）
//   node slides/video/render.mjs <构建目录> <首镜>-<末镜> --beats              打印每个动作的时刻
//   node slides/video/render.mjs <构建目录> <首镜>-<末镜> --audio              不重录画面，用 shots/ 里已有的镜重新配声音（配音 + sfx.js 里的音效）
//   加 --keep-sfx 留下单独的音效轨 film_a-b_sfx.wav，核对音效时刻用
//   以上都可以加 --eval "<代码>"，打开页面后先执行，出样品切换画法用
// 构建目录里要先有 data.json（export_data.py 导出）和 fonts/（NotoSansSC.ttf、Inter.ttf）。
// 有 voice/（voice.py 合成）时按配音排时间、成片带声音；没有就按估算的语速排、成片无声。

import { readFileSync, writeFileSync, mkdirSync, existsSync, unlinkSync } from "node:fs";
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
// 构建目录里有 voice/（voice.py 合成的配音）就用配音里每个字的真实时刻；
// 没有就按语速估每个字什么时候念到，先排画面用。
const RATE = 4.2;  // 估算用：每秒念几个“字”，约每分钟 250 字

// 每镜在旁白前后留的时间（秒），给画面动作让出空间。没写的用默认值
const LEAD = { default: 0.35, 2: 1.1, 4: 0.7, 5: 0.8, 6: 0.5, 7: 0.6, 10: 1.0, 13: 0.9, 14: 0.9, 16: 0.8, 17: 0.8, 18: 1.1, 22: 0.7, 23: 0.8, 24: 0.9, 25: 0.9, 26: 0.9, 27: 0.6 };   // 开口前
const EXTRA = { default: 0.35, 1: 1.6, 5: 0.6, 6: 1.4, 7: 1.0, 8: 0.6, 9: 1.6, 10: 1.0, 12: 1.6, 15: 1.0, 16: 1.8, 17: 0.8, 19: 0.5, 20: 0.6, 21: 0.8, 22: 2.0, 23: 1.4, 24: 1.6, 25: 2.0, 26: 0.8, 27: 1.0, 28: 3.0 };  // 念完后

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
function readStoryboard(voiceDir) {
  const text = readFileSync(join(HERE, "storyboard.md"), "utf8");
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
    // times[i]：第 i 个字开始念的时刻；times[字数] 是念完的时刻
    if (voiceDir) {
      // 有配音：开口的那一刻落在镜头开始后 lead 秒，每个字的时刻照配音来。
      // 半边真时间、半边估算的片子对不上，所以缺了哪镜的配音、或者分镜改了字没重配，都直接报错
      const path = join(voiceDir, `shot${String(shot.n).padStart(2, "0")}.json`);
      if (!existsSync(path)) throw new Error(`镜 ${shot.n} 还没有配音：先跑 voice.py`);
      const v = JSON.parse(readFileSync(path, "utf8"));
      if (v.text !== shot.voice) throw new Error(`镜 ${shot.n} 的旁白改过了，配音是旧的：重跑 voice.py`);
      shot.audio = { path: path.replace(/\.json$/, ".wav"), at: lead - v.voiced_start };  // 音频第 0 秒在镜内的时刻
      shot.times = v.times.map((t) => start + shot.audio.at + t);
    } else {
      const weights = speechWeights(shot.voice);
      shot.times = [start + lead];
      for (const w of weights) shot.times.push(shot.times[shot.times.length - 1] + w / RATE);
    }
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

// ---------- 声音 ----------

// 拼出一段和画面一样长的配音：每镜的音频放到它在镜内的时刻，前后补静音，截成正好一镜长，再一镜接一镜
async function buildAudio(shots, outPath) {
  const args = ["-y", "-loglevel", "error"];
  const filters = [];
  shots.forEach((s, i) => {
    args.push("-i", s.audio.path);
    const cut = Math.max(0, -s.audio.at);  // 音频开头的静音比 lead 还长时，剪掉多出来的那一点
    const delay = Math.round(Math.max(0, s.audio.at) * 1000);
    filters.push(`[${i}:a]atrim=start=${cut.toFixed(4)},asetpts=PTS-STARTPTS,adelay=${delay}:all=1,apad,atrim=end=${s.secs.toFixed(4)}[a${i}]`);
  });
  // 接好后统一响度：配音原样偏小（平均约 -24 dB），拉到网络视频常用的 -16 LUFS，峰值压在 -1.5 dB 以下
  filters.push(`${shots.map((_, i) => `[a${i}]`).join("")}concat=n=${shots.length}:v=0:a=1,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[out]`);
  await run("ffmpeg", [...args, "-filter_complex", filters.join(";"), "-map", "[out]", "-c:a", "pcm_s16le", outPath]);
}

// 读 48 kHz 单声道 16 位的 wav，返回 -1 到 1 的采样
function readWav(path) {
  const buf = readFileSync(path);
  let p = 12;
  let fmt = null;
  while (p < buf.length) {
    const id = buf.toString("ascii", p, p + 4);
    const size = buf.readUInt32LE(p + 4);
    if (id === "fmt ") fmt = { channels: buf.readUInt16LE(p + 10), rate: buf.readUInt32LE(p + 12), bits: buf.readUInt16LE(p + 22) };
    if (id === "data") {
      if (!fmt || fmt.channels !== 1 || fmt.rate !== 48000 || fmt.bits !== 16) throw new Error(`${path} 不是 48 kHz 单声道 16 位`);
      const out = new Float32Array(size / 2);
      for (let i = 0; i < out.length; i++) out[i] = buf.readInt16LE(p + 8 + i * 2) / 32768;
      return out;
    }
    p += 8 + size + (size % 2);
  }
  throw new Error(`${path} 里没有音频数据`);
}

function writeWav(path, samples) {
  const buf = Buffer.alloc(44 + samples.length * 2);
  buf.write("RIFF", 0);
  buf.writeUInt32LE(36 + samples.length * 2, 4);
  buf.write("WAVEfmt ", 8);
  buf.writeUInt32LE(16, 16);
  buf.writeUInt16LE(1, 20);       // PCM
  buf.writeUInt16LE(1, 22);       // 单声道
  buf.writeUInt32LE(48000, 24);
  buf.writeUInt32LE(96000, 28);   // 每秒字节数
  buf.writeUInt16LE(2, 32);
  buf.writeUInt16LE(16, 34);
  buf.write("data", 36);
  buf.writeUInt32LE(samples.length * 2, 40);
  for (let i = 0; i < samples.length; i++) buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, samples[i])) * 32767), 44 + i * 2);
  writeFileSync(path, buf);
}

// 音效轨：每个声音按 sfx.js 里定的峰值缩放，让它的落点对准画面动作，全部叠到一条和画面一样长的轨上。
// offset 是这段成片在全片里的起点，cues 里的时刻是全片时刻
function buildSfx(cues, sounds, offset, secs, outPath) {
  const track = new Float32Array(Math.round(secs * 48000));
  const loaded = {};
  for (const { t, sound, dur } of cues) {
    if (!(sound in sounds)) throw new Error(`sfx.js 里没有叫 ${sound} 的声音`);
    const s = sounds[sound];
    if (s === null) continue;  // 设成 null 的声音是这一版不用的
    if (!loaded[sound]) {
      const samples = readWav(join(HERE, "sfx", s.file));
      const peak = samples.reduce((m, x) => Math.max(m, Math.abs(x)), 0);
      const gain = Math.pow(10, s.db / 20) / peak;
      loaded[sound] = samples.map((x) => x * gain);
    }
    const samples = loaded[sound];
    const at = Math.round((t - offset - s.hit) * 48000);
    // 只放文件的一段：lead 是落点前留几秒（上升音太长，只要最后一截，开头 0.25 秒淡入）；
    // cut 是落点后留几秒、dur 是动作多长（截断处 0.12 秒淡出，免得戛然而止）
    const from = s.lead ? Math.max(0, Math.round((s.hit - s.lead) * 48000)) : 0;
    const after = dur ?? s.cut;
    const end = after != null ? Math.min(samples.length, Math.round((s.hit + after) * 48000)) : samples.length;
    const fadeIn = s.lead ? Math.round(0.25 * 48000) : 0;
    const fadeOut = after != null ? Math.round(0.12 * 48000) : 0;
    for (let i = Math.max(from, -at); i < end && at + i < track.length; i++) {
      let g = 1;
      if (fadeIn && i < from + fadeIn) g = (i - from) / fadeIn;
      if (fadeOut && i > end - fadeOut) g = Math.min(g, (end - i) / fadeOut);
      track[at + i] += samples[i] * g;
    }
  }
  writeWav(outPath, track);
}

// 三条轨相加：配音（已统一响度）、音效、背景音乐。不再整体调响度，免得音效一响把配音压下去；
// 最后用限幅器兜底，峰值不超过 -1.5 dB。
// 背景音乐：从全片第 from 秒对应的位置接着放（不够长就循环），先统一到 music.lufs，
// 有人声时再自动压低一截（侧链压缩：用配音的音量去控制音乐的音量），开头淡入、结尾淡出
async function mixAll(voiceWav, sfxWav, music, from, secs, outPath) {
  const args = ["-y", "-loglevel", "error", "-i", voiceWav, "-i", sfxWav];
  const stereo = "aformat=sample_rates=48000:channel_layouts=stereo";
  let graph = `[0:a]${stereo},asplit=2[voice][key];[1:a]${stereo}[sfx];`;
  if (music) {
    args.push("-stream_loop", "-1", "-i", join(HERE, music.file));
    const fadeIn = from === 0 ? "afade=t=in:d=1.5," : "";
    graph += `[2:a]${stereo},loudnorm=I=${music.lufs}:TP=-6,aresample=48000,` +
      `atrim=start=${from.toFixed(3)}:duration=${secs.toFixed(3)},asetpts=PTS-STARTPTS,` +
      `${fadeIn}afade=t=out:st=${Math.max(0, secs - 2.5).toFixed(3)}:d=2.5[bed];` +
      `[bed][key]sidechaincompress=threshold=0.02:ratio=4:attack=30:release=500[music];` +
      `[voice][sfx][music]amix=inputs=3:normalize=0:duration=first`;
  } else {
    graph += `[key]anullsink;[voice][sfx]amix=inputs=2:normalize=0:duration=first`;
  }
  graph += ",alimiter=limit=0.84:level=false[out]";
  await run("ffmpeg", [...args, "-filter_complex", graph, "-map", "[out]", "-c:a", "pcm_s16le", outPath]);
}

// 画面原样拷过去，只加一条声音
async function mux(video, audio, out) {
  await run("ffmpeg", ["-y", "-loglevel", "error", "-i", video, "-i", audio,
    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", out]);
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

const voiceDir = existsSync(join(buildDir, "voice")) ? join(buildDir, "voice") : null;
const all = readStoryboard(voiceDir);
const chosen = all.filter((s) => s.n >= first && s.n <= last);
for (const s of chosen) console.log(`镜 ${s.n}：${s.start.toFixed(2)} 秒起，${s.secs.toFixed(2)} 秒`);
const { browser, page } = await openFilm(buildDir, { shots: all });
// --eval "<代码>"：打开页面后先执行一段代码，出样品时切换画法用，比如 --eval "BOX_STYLE='slant'"
const evalIndex = process.argv.indexOf("--eval");
if (evalIndex > 0) await page.evaluate(process.argv[evalIndex + 1]);

if (process.argv.includes("--beats")) {
  // 打印每个动作的时刻（秒），抽帧检查时对准用
  // 每段的动作时刻表叫 B、B2、B3……，有几段就合几段
  // 顶层的 let 不挂在 window 上，只能按名字 eval 取，没有这一段就跳过
  const beats = await page.evaluate(() => Object.assign({}, B, ...[2, 3, 4, 5, 6, 7].map((n) => {
    try { return eval(`B${n}`); } catch { return {}; }
  })));
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
  const audioOnly = process.argv.includes("--audio");
  const list = [];
  for (const shot of chosen) {
    const out = join(buildDir, "shots", `shot${String(shot.n).padStart(2, "0")}.mp4`);
    if (!audioOnly) {
      const began = Date.now();
      await renderShot(page, shot, out);
      console.log(`镜 ${shot.n} 录完，用了 ${((Date.now() - began) / 1000).toFixed(0)} 秒`);
    }
    list.push(`file '${out}'`);
  }
  const name = `film_${first}-${last}`;
  const final = join(buildDir, `${name}.mp4`);
  const silent = voiceDir ? join(buildDir, `${name}_silent.mp4`) : final;
  writeFileSync(join(buildDir, `${name}.txt`), list.join("\n") + "\n");
  await run("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
    "-i", join(buildDir, `${name}.txt`), "-c", "copy", silent]);
  if (voiceDir) {
    const wav = join(buildDir, `${name}.wav`);
    await buildAudio(chosen, wav);
    // 音效：取落在这几镜里的，时刻是无穷大（这次没发生的动作）的跳过
    const from = chosen[0].start;
    const secs = chosen.reduce((sum, s) => sum + s.secs, 0);
    const { cues, sounds, music } = await page.evaluate(() => ({ cues: soundCues(), sounds: SOUNDS, music: MUSIC }));
    // 写错了动作名会得到 undefined/NaN，直接报错；Infinity 是这次没发生的动作，跳过
    const bad = cues.filter((c) => typeof c.t !== "number" || Number.isNaN(c.t));
    if (bad.length) throw new Error(`sfx.js 里有 ${bad.length} 个音效的时刻不是数：${JSON.stringify(bad)}`);
    const inRange = cues.filter((c) => Number.isFinite(c.t) && c.t >= from && c.t < from + secs);
    console.log(`音效 ${inRange.length} 个，背景音乐 ${music ? music.file : "无"}`);
    const sfx = join(buildDir, `${name}_sfx.wav`);
    const mixed = join(buildDir, `${name}_mix.wav`);
    buildSfx(inRange, sounds, from, secs, sfx);
    await mixAll(wav, sfx, music, from, secs, mixed);
    await mux(silent, mixed, final);
    for (const f of [silent, wav, mixed]) unlinkSync(f);
    if (!process.argv.includes("--keep-sfx")) unlinkSync(sfx);
  }
  writeSrt(chosen, join(buildDir, `${name}.srt`), chosen[0].start);
  console.log("成片：", join(buildDir, `${name}.mp4`));
}
await browser.close();
