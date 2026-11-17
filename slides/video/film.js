// 整片的时间轴：给一个时刻 t（秒），画出这一帧。
// 录制脚本读分镜、按语速排好每镜的时长和每个字大约什么时候念到，通过 setup 传进来。
// 画面的动作都挂在“念到某个词”的时刻上，以后换成真配音，只要换掉时间表，画面自动对上。

const W = 1920;
const H = 1080;

let ctx = null;
let chartCanvas = null;  // 图表单独画在这一层，镜头推拉只动这一层
let chartCtx = null;
let background = null;
let STORY = null;  // {shots: [{n, start, secs, voice, times, subs}]}
let DATA = null;   // export_data.py 导出的真实数字

// 每一段的画法，各段文件把自己登记进来：{first, last, prepare(data), draw(ctx, chartCtx, t)}
const PARTS = [];

async function setup(story, data, fontBase) {
  STORY = story;
  DATA = data;
  for (const family of Object.keys(FONT_FILES)) {
    const [file, weight] = FONT_FILES[family];
    const f = new FontFace(family, `url(${fontBase}/${file})`, { weight });
    await f.load();
    document.fonts.add(f);
  }
  const canvas = document.getElementById("film");
  canvas.width = W;
  canvas.height = H;
  ctx = canvas.getContext("2d");
  chartCanvas = document.createElement("canvas");
  chartCanvas.width = W;
  chartCanvas.height = H;
  chartCtx = chartCanvas.getContext("2d");
  background = makeBackground();
  for (const part of PARTS) part.prepare(DATA);
}

// 底色：上浅下深的渐变，四角再压暗一点，画面有纵深，视线落在中间
function makeBackground() {
  const c = document.createElement("canvas");
  c.width = W;
  c.height = H;
  const g = c.getContext("2d");
  const linear = g.createLinearGradient(0, 0, 0, H);
  linear.addColorStop(0, COLOR.bgTop);
  linear.addColorStop(1, COLOR.bgBottom);
  g.fillStyle = linear;
  g.fillRect(0, 0, W, H);
  const radial = g.createRadialGradient(W * 0.45, H * 0.45, H * 0.3, W * 0.5, H * 0.5, H * 1.05);
  radial.addColorStop(0, "rgba(0,0,0,0)");
  radial.addColorStop(1, COLOR.vignette);
  g.fillStyle = radial;
  g.fillRect(0, 0, W, H);
  return c;
}

// ---------- 时间表 ----------

function shot(n) {
  return STORY.shots.find((s) => s.n === n);
}

// 第 n 镜的旁白里，keyword 这个词大约什么时候开始念（which = "end" 时取念完的时刻）
function word(n, keyword, which = "start") {
  const s = shot(n);
  const index = s.voice.indexOf(keyword);
  if (index < 0) throw new Error(`镜 ${n} 的旁白里没有“${keyword}”`);
  return s.times[which === "end" ? index + keyword.length : index];
}

function currentShot(t) {
  let found = STORY.shots[0];
  for (const s of STORY.shots) if (t >= s.start) found = s;
  return found;
}

// ---------- 每一帧 ----------

function renderFrame(t) {
  ctx.drawImage(background, 0, 0);
  chartCtx.clearRect(0, 0, W, H);

  const now = currentShot(t);
  for (const part of PARTS) {
    if (now.n < part.first || now.n > part.last) continue;
    part.draw(ctx, chartCtx, t);
  }
  drawSubtitle(ctx, t);
}

// 把图表层贴到画面上。图表右边缘渐隐，镜头推近时图表不会压住右边的说明文字
function composeChart(ctx, fadeFrom, fadeTo) {
  chartCtx.save();
  chartCtx.globalCompositeOperation = "destination-in";
  const g = chartCtx.createLinearGradient(fadeFrom, 0, fadeTo, 0);
  g.addColorStop(0, "rgba(0,0,0,1)");
  g.addColorStop(1, "rgba(0,0,0,0)");
  chartCtx.fillStyle = g;
  chartCtx.fillRect(0, 0, W, H);
  chartCtx.restore();
  ctx.drawImage(chartCanvas, 0, 0);
}

// ---------- 字幕：底部居中，一次一句，衬一块半透明的底 ----------

const SUB_SIZE = 36;
const SUB_Y = 1022;

function drawSubtitle(ctx, t) {
  for (const s of STORY.shots) {
    for (const sub of s.subs) {
      if (t < sub.start || t >= sub.end) continue;
      const segs = [cjk(sub.text, SUB_SIZE, COLOR.subInk, 500)];
      const width = measureSegs(ctx, segs);
      const enter = ramp(t, sub.start, sub.start + 0.22);
      const exit = ramp(t, sub.end - 0.12, sub.end);
      ctx.save();
      // 底板和字一起出来：底板跟着字的进度淡入，不会先冒出一块空底
      ctx.globalAlpha = Math.min(ease.outQuint(enter) * 1.5, 1) * (1 - exit);
      ctx.fillStyle = COLOR.subBg;
      roundRect(ctx, W / 2 - width / 2 - 26, SUB_Y - SUB_SIZE - 10, width + 52, SUB_SIZE + 30, 12);
      ctx.fill();
      riseSegs(ctx, segs, W / 2, SUB_Y, enter, 0, "center");
      ctx.restore();
    }
  }
}
