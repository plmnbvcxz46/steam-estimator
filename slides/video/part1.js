// 第一段：k 存在，但不稳定（镜 1–6）
// 一个连续的场景：公式 → 散点图 → 带子 → 直接在散点图上分档，画出每档的波动和中位数 → 剔除评测 1–9 条。
// 左边是图表，右边一栏放公式和一个数字。

// ---------- 坐标 ----------
// 图表在自己的“世界坐标”里画：横轴评测数、纵轴玩家数，都取对数，每大格（×10）100 个单位。
// 横纵一样长，所以“玩家数 = k × 评测数”画出来正好是 45 度。镜头再把世界坐标搬到屏幕上。
const DEC = 100;
const X_MAX = 5e6;   // 横轴画到这里，最多的游戏评测 232 万条
const Y_MAX = 1e8;
function wx(reviews) {
  return Math.log10(reviews) * DEC;
}
function wy(players) {
  return -Math.log10(players) * DEC;
}

// 镜头：屏幕上 ANCHOR 这一点对准世界坐标里的 (cx, cy)，放大 zoom 倍
const ANCHOR = { x: 600, y: 505 };
const FULL = { zoom: 1, cx: 335, cy: -400 };  // 看整张图

// 右栏
const COL = 1090;
// 公式和数字作为一组，放在右半边的垂直中间，和左边的图平衡
const HEADER_Y = 440;  // 公式停靠的位置
const BIG_Y = 590;     // 右栏数字的基线：在公式下面

const TICK_NAMES = ["1", "10", "100", "1000", "1万", "10万", "100万", "1000万", "1亿"];

// ---------- 预先算好的东西 ----------
let dots = null;    // 每个散点：世界坐标、出场先后、是不是评测 1–9 条
let bins = null;    // 11 档：中心位置、百分位换成的世界坐标、波动倍数
let band = null;    // 带子上下沿（平滑后的折线）
let tenfold = null; // 镜 3 量“10 倍”的那一档
let sprites = null;
let B = null;       // 每个动作发生的时刻（秒）
let MOVES = null;   // 镜头的几次移动

function makeDot(color) {
  const c = document.createElement("canvas");
  c.width = 10;
  c.height = 10;
  const g = c.getContext("2d");
  g.fillStyle = color;
  g.beginPath();
  g.arc(5, 5, 2.1, 0, Math.PI * 2);
  g.fill();
  return c;
}

function preparePart1(data) {
  const rand = seededRandom(7);
  dots = data.points.map(([reviews, players]) => ({
    x: wx(reviews),
    y: wy(players),
    small: reviews < 10,
    order: wx(reviews) / wx(X_MAX),  // 从左往右扫出来
    jitter: rand(),
  }));

  bins = data.bins.map((b) => {
    // 矩形画在这一档游戏评测数的中位数处（export_data.py 算好的）
    const center = b.center;
    return {
      label: b.label,
      left: wx(b.start),
      x: wx(center),
      // k 的百分位乘上这一档中间的评测数，就是玩家数，画在散点图上正好落在这一档的点群里
      top: wy(b.high * center),
      mid: wy(b.median * center),
      bottom: wy(b.low * center),
      ratio: Math.round(b.high / b.low),
    };
  });

  band = {
    upper: smoothThrough(data.band.map((e) => [wx(e.reviews), wy(e.high)])),
    lower: smoothThrough(data.band.map((e) => [wx(e.reviews), wy(e.low)])),
  };
  // 评测 1000–1999 条这一档：带子上下沿差多少倍
  const e = data.band.find((d) => d.reviews > 1000 && d.reviews < 2000);
  tenfold = { x: wx(e.reviews), top: wy(e.high), bottom: wy(e.low), ratio: e.high / e.low };

  sprites = { ink: makeDot(COLOR.ink), acc: makeDot(COLOR.acc) };
  B = buildBeats();
  MOVES = buildMoves();
}

// 所有动作的时刻都从旁白里的词算出来：念到这个词，画面就做这个动作
function buildBeats() {
  const b = {
    s1: shot(1).start,
    s2: shot(2).start,
    s3: shot(3).start,
    s4: shot(4).start,
    s5: shot(5).start,
    s6: shot(6).start,
  };
  // 镜 1：公式一块块出来
  b.formulaIn = b.s1 + 0.25;
  b.review = word(1, "评测数") - 0.05;
  b.times = word(1, "乘以");
  b.k = word(1, "k");
  b.morph = word(1, "k", "end") + 0.45;
  // 镜 2：坐标轴、散点、45 度线
  b.fly = b.s2;
  b.axes = b.s2 + 0.1;
  b.dots = word(2, "已知");
  b.logWave = word(2, "双对数");
  b.kline = word(2, "四十五度");
  // 镜 3：带子和 10 倍
  // 斜线留到带子出来才收：念“并非紧贴斜线”时，点和线还能对照着看
  b.retract = word(3, "左宽") - 0.1;
  b.band = word(3, "左宽") - 0.1;
  b.wide = word(3, "左宽");
  b.narrow = word(3, "右窄");
  b.bracket = word(3, "差距");
  b.ten = word(3, "十倍");
  // 镜 4：分档、波动、中位数
  b.byReviews = word(4, "按评测数");
  b.div = word(4, "分档") - 0.15;
  b.bars = word(4, "百分位");
  b.medians = word(4, "中位数");
  // 镜 5：倍数从 39 一路收到 4，再圈出第一档到第二档的跳变
  b.r39 = word(5, "39");
  b.seqStart = word(5, "随评测");
  b.seqEnd = word(5, "4 倍");
  b.stable = word(5, "评测越多");
  b.jump = word(5, "第一档");
  // 镜 6：收起标注，剔除评测 1–9 条
  b.clear = b.s6 + 0.05;
  b.small = word(6, "个位数");
  b.remove = word(6, "剔除");
  b.keep = word(6, "保留");
  return b;
}

// 第 i 档的倍数什么时候弹出来：第一档在念到“39”时，其余几档在“随评测增多逐步收窄至 4 倍”这句里依次弹出
function popTime(i) {
  if (i === 0) return B.r39;
  return lerp(B.seqStart, B.seqEnd, (i - 1) / (bins.length - 2));
}

// ---------- 镜头 ----------
// 一次移动：从 t 开始，用 dur 秒移到 to。缩放按对数插值，推近和拉远的速度感才一致
function buildMoves() {
  const near5 = { zoom: 1.9, cx: 105, cy: -290 };  // 镜 5 推近前三档
  return [
    { t: B.s2 - 0.01, dur: 0.01, to: { zoom: 1.7, cx: 110, cy: -150 } },
    { t: B.axes, dur: 1.9, to: FULL, easing: ease.outQuint },  // 一边画坐标轴一边拉开
    { t: B.s5, dur: 0.75, to: near5 },
    { t: B.seqStart - 0.1, dur: B.seqEnd - B.seqStart + 0.3, to: FULL },
    { t: B.keep, dur: 0.6, to: { zoom: 1, cx: 385, cy: -400 } },
  ];
}

function cameraAt(t) {
  let cam = { ...FULL };
  for (const m of MOVES) {
    if (t < m.t) break;
    const p = (m.easing || ease.inOutCubic)(ramp(t, m.t, m.t + m.dur));
    cam = {
      zoom: Math.exp(lerp(Math.log(cam.zoom), Math.log(m.to.zoom), p)),
      cx: lerp(cam.cx, m.to.cx, p),
      cy: lerp(cam.cy, m.to.cy, p),
    };
  }
  // 整幅画面只在每段最要紧的结论上顶一下，第一段是“39 倍”
  cam.zoom *= 1 + 0.022 * kick(t, B.r39);
  return cam;
}

// ---------- 镜 1：公式 ----------

const F_SIZE = 120;
function formulaSegs(key) {
  const text = { P: "玩家数", EQ: "=", R: "评测数", Q: "?", TIMES: "×", DIV: "÷", K: "k" }[key];
  if (key === "Q") return [num("?", F_SIZE, COLOR.dim)];
  if (key === "K") return [disp(text, F_SIZE, COLOR.acc)];
  return [disp(text, F_SIZE, COLOR.ink)];
}
// 一种写法里每块的左边位置（从 0 量起）和总宽
function layout(ctx, keys) {
  const gap = 34;
  const pos = {};
  let x = 0;
  for (const k of keys) {
    pos[k] = x;
    x += measureSegs(ctx, formulaSegs(k)) + gap;
  }
  return { pos, width: x - gap };
}

function drawFormula(ctx, t) {
  const A = layout(ctx, ["P", "EQ", "R", "TIMES", "K"]);
  const Bl = layout(ctx, ["K", "EQ", "P", "DIV", "R"]);
  const morph = ease.inOutCubic(ramp(t, B.morph, B.morph + 0.6));
  const fly = ease.inOutCubic(ramp(t, B.fly, B.fly + 0.7));

  // 飞到右栏顶上：缩小到三分之一，左边对齐右栏。
  // 公式一块块出来时，只按已经出来的部分居中，整行跟着往左让位
  const scale = lerp(1, 0.36, fly);
  const upToR = A.pos.TIMES - 34;      // “玩家数 = 评测数”的宽
  const upToTimes = A.pos.K - 34;      // 再加上“×”
  const partial = upToR +
    ease.outQuint(ramp(t, B.times, B.times + 0.5)) * (upToTimes - upToR) +
    ease.outQuint(ramp(t, B.k, B.k + 0.5)) * (A.width - upToTimes);
  const width = lerp(partial, Bl.width, morph);
  const x0 = lerp(W / 2 - width / 2, COL, fly);
  const y0 = lerp(575, HEADER_Y, fly);
  const punch = 1 + 0.04 * kick(t, B.k + 0.05) * (1 - fly);

  ctx.save();
  ctx.translate(x0 + (width / 2) * scale, y0);
  ctx.scale(scale * punch, scale * punch);
  ctx.translate(-width / 2, 0);

  // 变形时“k”从上面绕到最前面，其余两块平移，× 换成 ÷
  const at = (key) => lerp(A.pos[key], Bl.pos[key], morph);
  const arc = Math.sin(morph * Math.PI);

  // “玩家数”和“评测数”往右挪时从下面绕过去，不和往左走的“=”、刚弹出的“÷”撞在一起
  riseSegs(ctx, formulaSegs("P"), at("P"), arc * 85, ramp(t, B.formulaIn, B.formulaIn + 0.5));
  riseSegs(ctx, formulaSegs("EQ"), at("EQ"), 0, ramp(t, B.formulaIn + 0.12, B.formulaIn + 0.6));
  // “评测数”还没念到时，它的位置先放一个问号
  const qWidth = measureSegs(ctx, formulaSegs("Q"));
  const rWidth = measureSegs(ctx, formulaSegs("R"));
  riseSegs(ctx, formulaSegs("Q"), A.pos.R + (rWidth - qWidth) / 2, 0,
    ramp(t, B.formulaIn + 0.25, B.formulaIn + 0.7), ramp(t, B.review, B.review + 0.25));
  riseSegs(ctx, formulaSegs("R"), at("R"), arc * 85, ramp(t, B.review + 0.12, B.review + 0.6));
  // × 落下去，÷ 弹出来
  riseSegs(ctx, formulaSegs("TIMES"), A.pos.TIMES, 0, ramp(t, B.times, B.times + 0.4), ramp(t, B.morph - 0.1, B.morph + 0.12));
  const divPop = spring(t - (B.morph + 0.45), 3, 0.5);
  if (divPop > 0) {
    const w = measureSegs(ctx, formulaSegs("DIV"));
    ctx.save();
    ctx.translate(Bl.pos.DIV + w / 2, -40);
    ctx.scale(divPop, divPop);
    drawSegs(ctx, formulaSegs("DIV"), -w / 2, 40);
    ctx.restore();
  }
  // k 砸下来：从 1.8 倍大弹到原大小
  const kIn = t - B.k;
  if (kIn > 0) {
    const w = measureSegs(ctx, formulaSegs("K"));
    const s = 1.8 - 0.8 * spring(kIn, 2.6, 0.45);
    ctx.save();
    ctx.globalAlpha *= ramp(t, B.k, B.k + 0.06);
    ctx.translate(at("K") + w / 2, -40 - arc * 190);
    ctx.scale(s, s);
    drawSegs(ctx, formulaSegs("K"), -w / 2, 40);
    ctx.restore();
  }
  ctx.restore();

  // 停靠以后，下面画一条细线，把右栏的“标题”和下面的数字隔开
  const rule = ease.outQuint(ramp(t, B.fly + 0.55, B.fly + 1.1));
  if (rule > 0) {
    ctx.save();
    ctx.strokeStyle = COLOR.line;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(COL, HEADER_Y + 30);
    ctx.lineTo(COL + 700 * rule, HEADER_Y + 30);
    ctx.stroke();
    ctx.restore();
  }
}

// ---------- 坐标轴 ----------

// 画刻度字：字号除以镜头倍数，镜头推近时刻度字在屏幕上大小不变。
// hi 从 0 到 1 是被点亮的程度：变成强调色、放大一点
function tickText(c, z, text, x, y, align, enter, exit = 0, hi = 0) {
  const size = (21 * (1 + 0.35 * hi)) / z;
  riseSegs(c, [cjk(text, size, COLOR.dim, 400)], x, y, enter, exit, align);
  if (hi > 0.01) {
    c.save();
    c.globalAlpha *= Math.min(1, hi * 1.5);
    riseSegs(c, [cjk(text, size, COLOR.acc, 400)], x, y, enter, exit, align);
    c.restore();
  }
}

function drawAxes(c, t, z) {
  // 镜 6：横轴左端截到评测 10 条，纵轴跟着右移，散点不动
  const trim = ease.inOutCubic(ramp(t, B.keep, B.keep + 0.6));
  const xl = lerp(wx(1), wx(10), trim);
  const xr = wx(X_MAX) + 30;
  const yt = wy(Y_MAX) - 30;

  // 网格：每个 ×10 一条，先于坐标轴淡淡地长出来
  for (let i = 1; i <= 6; i++) {
    const p = ease.outQuint(ramp(t, B.axes + 0.25 + i * 0.05, B.axes + 0.85 + i * 0.05));
    if (wx(Math.pow(10, i)) < xl) continue;
    growLine(c, [[wx(Math.pow(10, i)), 0], [wx(Math.pow(10, i)), wy(Y_MAX)]], p, { color: COLOR.line, width: 1 / z, cap: "butt" });
  }
  for (let j = 1; j <= 8; j++) {
    const p = ease.outQuint(ramp(t, B.axes + 0.3 + j * 0.04, B.axes + 0.9 + j * 0.04));
    growLine(c, [[xl, wy(Math.pow(10, j))], [wx(X_MAX), wy(Math.pow(10, j))]], p, { color: COLOR.line, width: 1 / z, cap: "butt" });
  }

  const ax = ease.outQuint(ramp(t, B.axes, B.axes + 0.6));
  const ay = ease.outQuint(ramp(t, B.axes + 0.1, B.axes + 0.7));
  growLine(c, [[xl, 0], [xr, 0]], ax, { color: COLOR.dim, width: 2 / z, cap: "butt" });
  growLine(c, [[xl, 0], [xl, yt]], ay, { color: COLOR.dim, width: 2 / z, cap: "butt" });

  // 镜 4 念到“按评测数”：横轴从左到右扫过一道强调色，接下来就沿着它分档
  const sweep = ease.outQuint(ramp(t, B.byReviews, B.byReviews + 0.6));
  const sweepFade = 1 - ramp(t, B.byReviews + 0.9, B.byReviews + 1.5);
  if (sweep > 0 && sweepFade > 0) {
    growLine(c, [[xl, 0], [xr, 0]], sweep, { color: COLOR.acc, width: 4 / z, cap: "butt", alpha: sweepFade });
  }

  for (let i = 0; i <= 6; i++) {
    const enter = ramp(t, B.axes + 0.2 + i * 0.05, B.axes + 0.6 + i * 0.05);
    // 被截掉的那格（1）跟着退场
    const exit = i === 0 ? ramp(t, B.keep, B.keep + 0.25) : 0;
    const hi = kick(t, B.logWave + i * 0.09) + kick(t, B.byReviews + i * 0.07);
    tickText(c, z, TICK_NAMES[i], wx(Math.pow(10, i)), 36 / z, "center", enter, exit, Math.min(1, hi));
  }
  for (let j = 0; j <= 8; j++) {
    const enter = ramp(t, B.axes + 0.25 + j * 0.04, B.axes + 0.65 + j * 0.04);
    const hi = kick(t, B.logWave + 0.05 + j * 0.08);
    tickText(c, z, TICK_NAMES[j], xl - 14 / z, wy(Math.pow(10, j)) + 7 / z, "right", enter, 0, hi);
  }
  const titles = ramp(t, B.axes + 0.5, B.axes + 1.0);
  riseSegs(c, [disp("评测数", 26 / z, COLOR.ink)], xr + 14 / z, 9 / z, titles);
  riseSegs(c, [disp("玩家数", 26 / z, COLOR.ink)], xl, yt - 16 / z, titles, 0, "center");
}

// ---------- 散点 ----------

function drawDots(c, t) {
  const start = B.dots;
  // 镜 4 画波动时散点压暗一些（不擦掉），镜 6 收起标注时恢复
  const dim = 1 - 0.45 * ease.outQuint(ramp(t, B.bars, B.bars + 0.4)) * (1 - ramp(t, B.clear, B.clear + 0.3));
  for (const d of dots) {
    const appear = start + d.order * 0.9 + d.jitter * 0.18;
    const age = t - appear;
    if (age < 0) continue;
    // 刚出来时是亮的，随后落到常亮度：一道亮光从左往右扫过点群
    const base = COLOR.pointAlpha * dim;
    let alpha = base + (1 - base) * Math.exp(-age / 0.12);
    let orange = 0;
    let size = 10;
    if (d.small) {
      orange = ramp(t, B.small + d.jitter * 0.35, B.small + d.jitter * 0.35 + 0.1);
      const gone = ramp(t, B.remove + d.jitter * 0.3, B.remove + d.jitter * 0.3 + 0.18);
      alpha = lerp(alpha, 0.9, orange) * (1 - gone);
      size = 10 * (1 - 0.7 * gone);
      if (alpha <= 0.002) continue;
    }
    if (orange < 1) {
      c.globalAlpha = alpha * (1 - orange);
      c.drawImage(sprites.ink, d.x - size / 2, d.y - size / 2, size, size);
    }
    if (orange > 0) {
      c.globalAlpha = alpha * orange;
      c.drawImage(sprites.acc, d.x - size / 2, d.y - size / 2, size, size);
    }
  }
  c.globalAlpha = 1;
}

// ---------- 图上的小标注 ----------

// 图上的小标签，弹出来；popAt、exitAt 是时刻。
// 不用底板，字的四周描一圈纸色的边，压在散点上也看得清
function pill(c, segs, x, y, popAt, exitAt, opts = {}) {
  const age = t_now - popAt;
  if (age <= 0) return;
  const exit = ease.inCubic(ramp(t_now, exitAt, exitAt + 0.25));
  if (exit >= 1) return;
  const s = (0.5 + 0.5 * spring(age, 3.2, 0.5)) * (1 - 0.4 * exit);
  const w = measureSegs(c, segs);
  const h = Math.max(...segs.map((g) => g.size));
  c.save();
  c.globalAlpha *= ramp(t_now, popAt, popAt + 0.05) * (1 - exit) * (opts.alpha === undefined ? 1 : opts.alpha);
  c.translate(x, y);
  c.scale(s, s);
  drawSegs(c, segs, -w / 2, h * 0.36, true);
  c.restore();
}
let t_now = 0;  // pill 要用当前时刻，画每帧时更新

// ---------- 镜 2–3：45 度线和带子 ----------

function drawKLine(c, t) {
  const k = DATA.fixed_k;
  const r1 = Y_MAX / k / 1.3;
  const grow = ease.outQuint(ramp(t, B.kline, B.kline + 0.5));
  const gone = ease.inExpo(ramp(t, B.retract, B.retract + 0.4));
  growLine(c, [[wx(1), wy(k)], [wx(r1), wy(k * r1)]], grow, { color: COLOR.acc, width: 4.5, head: 7, from: gone });
}

function drawBand(c, t) {
  const grow = ease.outQuint(ramp(t, B.band, B.band + 1.0));
  if (grow <= 0) return;
  // 镜 4 起带子退到背景，镜 6 收起
  // 镜 4 矩形长出来时，带子完全退掉，免得两种范围叠在一起
  const fade = 1 - ramp(t, B.bars, B.bars + 0.4);
  const gone = ease.inExpo(ramp(t, B.clear, B.clear + 0.35));
  const right = lerp(band.upper[0][0], band.upper[band.upper.length - 1][0], grow);

  // 带子里面填一层很淡的白，随着上下沿从左往右铺开
  c.save();
  c.beginPath();
  c.rect(-50, wy(Y_MAX) - 100, right + 50, 1000);
  c.clip();
  c.globalAlpha = 0.07 * fade * (1 - gone);
  c.fillStyle = COLOR.ink;
  c.beginPath();
  band.upper.forEach(([x, y], i) => (i === 0 ? c.moveTo(x, y) : c.lineTo(x, y)));
  for (let i = band.lower.length - 1; i >= 0; i--) c.lineTo(band.lower[i][0], band.lower[i][1]);
  c.closePath();
  c.fill();
  c.restore();

  const style = { color: COLOR.ink, width: 1.6, alpha: 0.6 * fade, from: gone };
  growLine(c, band.upper, grow, style);
  growLine(c, band.lower, ease.outQuint(ramp(t, B.band + 0.1, B.band + 1.1)), style);

  // “宽”“窄”标在带子两头
  const u0 = band.upper[0];
  const l1 = band.lower[band.lower.length - 1];
  pill(c, [disp("宽", 28, COLOR.ink)], u0[0] + 10, u0[1] - 34, B.wide, B.s4);
  pill(c, [disp("窄", 28, COLOR.ink)], l1[0] + 10, l1[1] + 52, B.narrow, B.s4);
}

// 镜 3：在评测 1000–1999 条处量一下带子的上下沿，差 10 倍
function drawTenfold(c, t) {
  const grow = ease.outQuint(ramp(t, B.bracket, B.bracket + 0.4));
  if (grow <= 0) return;
  const exit = ease.inExpo(ramp(t, B.s4, B.s4 + 0.3));
  if (exit >= 1) return;
  const mid = (tenfold.top + tenfold.bottom) / 2;
  const cap = 9 * (1 - exit);
  const half = ((tenfold.bottom - tenfold.top) / 2) * grow * (1 - exit);
  c.save();
  c.strokeStyle = COLOR.acc;
  c.lineWidth = 3.5;
  c.lineCap = "round";
  c.beginPath();
  c.moveTo(tenfold.x, mid - half);
  c.lineTo(tenfold.x, mid + half);
  c.moveTo(tenfold.x - cap, mid - half);
  c.lineTo(tenfold.x + cap, mid - half);
  c.moveTo(tenfold.x - cap, mid + half);
  c.lineTo(tenfold.x + cap, mid + half);
  c.stroke();
  c.restore();
}

// ---------- 镜 4–5：分档、波动、中位数、倍数 ----------

// 每档一个矩形，画在这一档的中间：上下沿是这一档 k 的第 10 和第 90 百分位（换成玩家数），
// 矩形越高，这一档的 k 越不稳定。
// 第一档（1–9 条）和最后一档（2 万条以上）在横轴上本来就跨得宽，矩形画宽些；
// 中间几档的中心最近只隔 30，矩形窄一些，相互留出间距
function boxWidth(i) {
  return i === 0 || i === bins.length - 1 ? 50 : 22;
}

// 第 i 档在镜 5 里亮不亮：推近时只亮第一档，其余几档轮到它的倍数弹出时才亮；圈跳变时只亮前两档
function binLight(i, t) {
  if (t < B.s5) return 1;
  let light = i === 0 ? 1 : lerp(1, 0.3, ramp(t, B.s5, B.s5 + 0.3));
  if (i > 0) light = Math.max(light, ramp(t, popTime(i), popTime(i) + 0.1));
  if (i > 1) light = Math.min(light, 1 - 0.65 * ramp(t, B.jump, B.jump + 0.3));
  return lerp(light, 1, ramp(t, B.clear, B.clear + 0.2));
}

// 第 i 档收起的进度。第一档留到镜 6 剔除时，和评测 1–9 条的点一起消失：39 倍的波动就是剔除它们的理由
function binGone(i, t) {
  const at = i === 0 ? B.remove : B.clear;
  return ease.inExpo(ramp(t, at, at + 0.35));
}

// 矩形此刻的上下沿：从中位数往上下长开
function boxEdges(b, i, t) {
  const p = ease.outQuint(ramp(t, B.bars + i * 0.06, B.bars + i * 0.06 + 0.45)) * (1 - binGone(i, t));
  return { p, top: lerp(b.mid, b.top, p), bottom: lerp(b.mid, b.bottom, p) };
}

// 画在散点下面的部分：分档线、矩形的底色。底色垫在下面，散点一个不少地画在上面
function drawBinShapes(c, t, z) {
  // 分档线：从上往下落，一根接一根；中位数出来时退场，画面不留辅助线
  const divOut = ease.inExpo(ramp(t, B.medians, B.medians + 0.4));
  bins.forEach((b, i) => {
    if (i === 0) return;
    const p = ease.outQuint(ramp(t, B.div + i * 0.045, B.div + i * 0.045 + 0.35));
    growLine(c, [[b.left, wy(Y_MAX)], [b.left, 0]], p, { color: COLOR.dim, width: 1.2 / z, alpha: 0.7 * (1 - divOut), cap: "butt" });
  });

  bins.forEach((b, i) => {
    const { p, top, bottom } = boxEdges(b, i, t);
    if (p <= 0) return;
    c.save();
    c.globalAlpha = binLight(i, t);
    c.fillStyle = COLOR.accFill;
    c.fillRect(b.x - boxWidth(i) / 2, top, boxWidth(i), bottom - top);
    // 镜 5 念到“评测越多”：从左到右依次亮一下，看着它们一个比一个矮
    const wave = kick(t, B.stable + i * 0.09);
    if (wave > 0.01) {
      c.globalAlpha = binLight(i, t) * 0.45 * wave;
      c.fillStyle = COLOR.acc;
      c.fillRect(b.x - boxWidth(i) / 2, top, boxWidth(i), bottom - top);
    }
    c.restore();
  });
}

// 画在散点上面的部分：矩形的边、中位数、倍数、跳变
function drawBinMarks(c, t, z) {
  bins.forEach((b, i) => {
    const { p, top, bottom } = boxEdges(b, i, t);
    if (p <= 0) return;
    c.save();
    c.globalAlpha = binLight(i, t);
    c.strokeStyle = COLOR.acc;
    c.lineWidth = 2;
    c.strokeRect(b.x - boxWidth(i) / 2, top, boxWidth(i), bottom - top);
    c.restore();
  });

  // 中位数：黑色圆点弹出来，外面一圈底色把它和矩形的边分开
  bins.forEach((b, i) => {
    const s = spring(t - (B.medians + i * 0.05), 3.2, 0.5) * (1 - binGone(i, t));
    if (s <= 0) return;
    c.save();
    c.globalAlpha = binLight(i, t);
    c.fillStyle = COLOR.ink;
    c.strokeStyle = COLOR.bgTop;
    c.lineWidth = 2.5;
    c.beginPath();
    c.arc(b.x, b.mid, 6 * s, 0, Math.PI * 2);
    c.fill();
    c.stroke();
    c.restore();
  });

  // 镜 5：矩形顶上弹出波动倍数（第 90 ÷ 第 10 百分位），首尾两档带“倍”字，中间几档太挤只写数字
  bins.forEach((b, i) => {
    const edge = i === 0 || i === bins.length - 1;
    const color = edge ? COLOR.acc : COLOR.ink;
    const segs = [num(String(b.ratio), 28, color)];
    if (edge) segs.push(disp(" 倍", 20, color));
    // 第一档的“39 倍”比别的标签长，往左挪一点，别贴着第二档的“19”
    const x = i === 0 ? b.x - 8 : b.x;
    pill(c, segs, x, b.top - 26, popTime(i), i === 0 ? B.remove : B.clear, { alpha: binLight(i, t) });
  });

  // 镜 5：描出第一档和第二档的矩形，标“跳变”
  const ring = ease.outQuint(ramp(t, B.jump, B.jump + 0.5));
  if (ring > 0) {
    const exit = ease.inExpo(ramp(t, B.clear, B.clear + 0.3));
    for (const i of [0, 1]) {
      const b = bins[i];
      const l = b.x - boxWidth(i) / 2 - 5;
      const r = b.x + boxWidth(i) / 2 + 5;
      const top = b.top - 5;
      const bottom = b.bottom + 5;
      growLine(c, [[l, top], [r, top], [r, bottom], [l, bottom], [l, top]], ring, { color: COLOR.ink, width: 2.5, from: exit });
    }
    const x = (bins[0].x + bins[1].x) / 2;
    const y = Math.min(bins[0].top, bins[1].top) - 78;
    pill(c, [disp("跳变", 26, COLOR.ink)], x, y, B.jump + 0.3, B.clear);
  }
}

// 镜 6：在横轴上方标出评测 1–9 条的范围
function drawSmallRange(c, t) {
  const p = ease.outQuint(ramp(t, B.small, B.small + 0.4));
  if (p <= 0) return;
  const exit = ease.inExpo(ramp(t, B.keep, B.keep + 0.3));
  const y = -26;
  growLine(c, [[wx(1), y], [wx(9.5), y]], p, { color: COLOR.acc, width: 3, from: exit });
  pill(c, [disp("1–9 条", 22, COLOR.acc)], wx(3), y - 30, B.small + 0.2, B.keep);
}

// ---------- 右栏 ----------
// 右栏只放一个大数字（带单位），不写解释的小字：解释交给画面动作和字幕

const BIG = 88;  // 右栏数字的字号：比公式小，不抢图表

// 大号数字：在 tin 升起，在 tout 升出去；tin 和 pulses 里的每个时刻都猛地一顶再落定
function bigNumber(ctx, t, segs, tin, tout, pulses = []) {
  let s = 1;
  for (const at of [tin, ...pulses]) if (t >= at) s = 1 + 0.12 * (1 - spring(t - at, 3.4, 0.45));
  ctx.save();
  ctx.translate(COL, BIG_Y);
  ctx.scale(s, s);
  ctx.translate(-COL, -BIG_Y);
  riseSegs(ctx, segs, COL, BIG_Y, ramp(t, tin, tin + 0.45), ramp(t, tout, tout + 0.28));
  ctx.restore();
}

function drawColumn(ctx, t) {
  const unit = (text, color = COLOR.ink) => disp(text, 40, color);

  // 镜 2：散点扫出来时，款数从 0 滚到 11716
  const nPoints = DATA.points.length;
  const count = Math.round(nPoints * ease.outExpo(ramp(t, B.dots, B.dots + 1.1)));
  bigNumber(ctx, t, [num(String(count), BIG), unit(" 款")], B.dots, B.kline - 0.1);

  // 镜 2：45 度线画完，k ≈ 80
  const k = String(Math.round(DATA.fixed_k));
  bigNumber(ctx, t, [num("k ≈ " + k, BIG, COLOR.acc)], B.kline + 0.35, B.retract);

  // 镜 3：同样的评测数，玩家数差 10 倍
  bigNumber(ctx, t, [num(String(Math.round(tenfold.ratio)), BIG, COLOR.acc), unit(" 倍", COLOR.acc)], B.ten, B.s4);

  // 镜 4：分 11 档
  bigNumber(ctx, t, [num(String(bins.length), BIG), unit(" 档")], B.div, B.s5);

  // 镜 5：倍数跟着一档档弹出，从 39 滚到 4
  let current = 0;
  bins.forEach((b, i) => {
    if (t >= popTime(i)) current = i;
  });
  const pulses = bins.map((b, i) => popTime(i));
  bigNumber(ctx, t, [num(String(bins[current].ratio), BIG, COLOR.acc), unit(" 倍", COLOR.acc)], B.r39, B.jump, pulses);

  // 镜 5：第一档到第二档
  const leftWidth = measureSegs(ctx, [num(String(bins[0].ratio), BIG)]);
  bigNumber(ctx, t, [num(String(bins[0].ratio), BIG, COLOR.acc), { ...num("", BIG), gap: 92 }, num(String(bins[1].ratio), BIG)], B.jump, B.clear);
  drawJumpArrow(ctx, t, leftWidth);

  // 镜 6：先亮出要剔除的 2093 款，再从 11716 滚到 9623
  const nSmall = dots.filter((d) => d.small).length;
  bigNumber(ctx, t, [num(String(nSmall), BIG, COLOR.acc), unit(" 款", COLOR.acc)], B.small, B.keep);
  const left = Math.round(lerp(nPoints, nPoints - nSmall, ease.outExpo(ramp(t, B.keep + 0.1, B.keep + 0.9))));
  bigNumber(ctx, t, [num(String(left), BIG), unit(" 款")], B.keep, Infinity);
}

// “39 → 19”中间的箭头：从左往右一笔画出
function drawJumpArrow(ctx, t, leftWidth) {
  const p = ease.outQuint(ramp(t, B.jump + 0.15, B.jump + 0.55));
  const exit = ease.inExpo(ramp(t, B.clear, B.clear + 0.25));
  if (p <= 0 || exit >= 1) return;
  const x0 = COL + leftWidth + 18;
  const x1 = x0 + 56;
  const y = BIG_Y - BIG * 0.36;  // 数字高度的一半左右
  const tip = lerp(x0, x1, p);
  ctx.save();
  ctx.globalAlpha = 1 - exit;
  ctx.strokeStyle = COLOR.dim;
  ctx.lineWidth = 5;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.beginPath();
  ctx.moveTo(x0, y);
  ctx.lineTo(tip, y);
  ctx.moveTo(tip - 14 * p, y - 13 * p);
  ctx.lineTo(tip, y);
  ctx.lineTo(tip - 14 * p, y + 13 * p);
  ctx.stroke();
  ctx.restore();
}

// ---------- 整段 ----------

function drawPart1(ctx, chart, t) {
  t_now = t;
  if (t >= B.s2) {
    const cam = cameraAt(t);
    chart.save();
    chart.setTransform(cam.zoom, 0, 0, cam.zoom, ANCHOR.x - cam.cx * cam.zoom, ANCHOR.y - cam.cy * cam.zoom);
    drawAxes(chart, t, cam.zoom);
    drawBand(chart, t);
    drawBinShapes(chart, t, cam.zoom);  // 矩形的底色垫在散点下面
    drawDots(chart, t);
    drawKLine(chart, t);
    drawTenfold(chart, t);
    drawBinMarks(chart, t, cam.zoom);   // 矩形的边、中位数、倍数在散点上面
    drawSmallRange(chart, t);
    chart.restore();
    composeChart(ctx, 1062, 1088);  // 渐隐从横轴名“评测数”右边开始，不压到它
    drawColumn(ctx, t);
  }
  drawFormula(ctx, t);
}

PARTS.push({ first: 1, last: 6, prepare: preparePart1, draw: drawPart1 });
