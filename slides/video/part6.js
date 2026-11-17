// 第六段：校准、区间与单款查询（镜 23–25）
// 镜 23：右边“近年 116 款”三根柱子（原样、校准后、融合），虚线是 2018 年训练集上的 46.2%；
//        左边 k 随游戏年龄的变化：2018 年训练集一路往上，近年游戏基本持平。
// 镜 24：上面是留一法的“真值 ÷ 估计”，有信号 B、没有信号 B 各一行，括出中间八成；下面一把对比尺，两路相差超过 1.65 倍标“低”。
// 镜 25：单款查询：顶上四步连线，中间 Vampire Survivors 的估计、80% 区间和置信标签。
// 数字都从 data.json 的 calibration 读。变量都带 6 结尾。

let B6 = null;
let layer6 = null;
let STRIP6 = null;  // 镜 24 每个点的位置（固定种子错开）

// 镜 23
const AGE6 = { x0: 150, x1: 900, top: 320, base: 790, lo: 20, hi: 250, ticks: [30, 50, 100, 200] };
const AGE_LABELS6 = ["0–0.1", "0.1–0.5", "0.5–2", "2–5", "5+"];
const BAR6 = { base: 790, scale: 900, w: 120, xs: [1270, 1470, 1670], refX0: 1190, refX1: 1750 };

// 镜 24
const RATIO6 = { x0: 260, x1: 1460, lo: 0.15, hi: 1 / 0.15, rows: [370, 510], axis: 600, ticks: [0.2, 0.5, 1, 2, 5] };
const RULER6 = { x0: 420, x1: 1260, lo: 15, hi: 120, y: 800 };

// 镜 25
const STEPS6 = ["采集", "清洗", "两路估计", "合并"];
const QAXIS6 = { x0: 560, x1: 1360, lo: 4e6, hi: 3e7, y: 720 };

function preparePart6(data) {
  layer6 = document.createElement("canvas");
  layer6.width = W;
  layer6.height = H;
  B6 = buildBeats6();
  // 点在自己那一行里上下错开一点，免得叠成一条线
  const rand = seededRandom(7);
  const C = data.calibration;
  STRIP6 = [C.ratios_b, C.ratios_no_b].map((list) => list.map((r) => ({ r, dy: (rand() - 0.5) * 70, order: rand() })));
}

function buildBeats6() {
  const b = { s23: shot(23).start, s24: shot(24).start, s25: shot(25).start };
  // 镜 23
  b.recent6 = word(23, "近年公布");
  b.raw6 = word(23, "原模型");
  b.drop6 = word(23, "下降");
  b.older6 = word(23, "越老");
  b.noLonger6 = word(23, "不再成立");
  b.ageFix6 = word(23, "年龄修正");
  b.fused6 = word(23, "融合后回升");
  // 镜 24
  b.eighty6 = word(24, "八成把握");
  b.interval6 = word(24, "预测区间");
  b.differ6 = word(24, "两路估计相差");
  b.low6 = word(24, "标为低");
  // 镜 25
  b.minute6 = word(25, "一分钟");
  b.crawl6 = word(25, "采集");
  b.clean6 = word(25, "清洗");
  b.merge6 = word(25, "两路合并");
  b.units6 = word(25, "估算销量");
  b.range6 = word(25, "区间及");
  b.label6 = word(25, "置信标签");
  return b;
}

// 镜 22 → 23：第五段的柱子退场
function drawHandoff6(ctx, t) {
  const p = ease.inOutCubic(ramp(t, B6.s23, B6.s23 + 0.5));
  if (p >= 1) return;
  const g = layer6.getContext("2d");
  g.clearRect(0, 0, W, H);
  drawPart5(g, chartCtx, B6.s23 - 1 / 120);
  ctx.save();
  ctx.globalAlpha = 1 - p;
  ctx.translate(W / 2, H / 2);
  ctx.scale(1 - 0.06 * p, 1 - 0.06 * p);
  ctx.translate(-W / 2, -H / 2 - 30 * p);
  ctx.drawImage(layer6, 0, 0);
  ctx.restore();
}

function pct6(v, size, color) {
  return [num((v * 100).toFixed(1), size, color), num("%", size * 0.6, color)];
}

// 对数坐标：v 在 [lo, hi] 里的位置换成 [a, b]
function logPos6(v, lo, hi, a, b) {
  return lerp(a, b, Math.log(v / lo) / Math.log(hi / lo));
}

// 一个镜头的整体退场：下一镜开头升出去、淡掉
function shotExit6(t, next) {
  return ease.inCubic(ramp(t, next, next + 0.35));
}

// ---------- 镜 23 ----------

function drawBars6(ctx, t) {
  const exit = shotExit6(t, B6.s24);
  if (t < B6.recent6 - 0.1 || exit >= 1) return;
  const C = DATA.calibration;
  const { base, scale, w, xs } = BAR6;
  ctx.save();
  ctx.globalAlpha = 1 - exit;

  riseSegs(ctx, [disp("近年 ", 40), num(String(C.n), 40), disp(" 款", 40)], BAR6.refX0, 250, ramp(t, B6.recent6, B6.recent6 + 0.4));
  growLine(ctx, [[BAR6.refX0, base], [BAR6.refX1, base]], ease.outQuint(ramp(t, B6.recent6, B6.recent6 + 0.4)), { color: COLOR.dim, width: 2, cap: "butt" });

  // 2018 年训练集上的估对比例：念到“原模型”时一道虚线
  const train = DATA.methods.tree.hit_rate;
  const refY = base - train * scale;
  growLine(ctx, [[BAR6.refX0, refY], [BAR6.refX1, refY]], ease.outQuint(ramp(t, B6.raw6, B6.raw6 + 0.5)), { color: COLOR.dim, width: 2.5, cap: "butt", dash: [10, 8] });
  riseSegs(ctx, [cjk("2018 年 ", 22, COLOR.dim), ...pct6(train, 26, COLOR.dim)], BAR6.refX1, refY - 14, ramp(t, B6.raw6 + 0.2, B6.raw6 + 0.5), 0, "right");

  const bars = [
    { name: "原样", v: C.scores.tree_raw.hit, at: B6.drop6, color: COLOR.ink, alpha: 0.35 },
    { name: "校准后", v: C.scores.signal_a.hit, at: B6.ageFix6 + 0.3, color: COLOR.ink, alpha: 0.6 },
    { name: "融合", v: C.scores.fused.hit, at: B6.fused6 + 0.2, color: COLOR.acc, alpha: 0.85 },
  ];
  bars.forEach((b, i) => {
    const p = spring(t - b.at, 2.6, 0.6);
    if (p <= 0) return;
    const top = base - b.v * scale * p;
    ctx.save();
    ctx.globalAlpha *= b.alpha;
    ctx.fillStyle = b.color;
    ctx.fillRect(xs[i] - w / 2, top, w, base - top);
    ctx.restore();
    const enter = ramp(t, b.at + 0.15, b.at + 0.45);
    riseSegs(ctx, pct6(b.v, 46, b.color), xs[i], base - b.v * scale - 20, enter, 0, "center");
    riseSegs(ctx, [cjk(b.name, 26, b.color, 600)], xs[i], base + 40, enter, 0, "center");
  });
  ctx.restore();
}

function ageX6(i) {
  return lerp(AGE6.x0, AGE6.x1, (i + 0.5) / 5);
}
function ageY6(k) {
  return logPos6(k, AGE6.lo, AGE6.hi, AGE6.base, AGE6.top);
}

function drawAge6(ctx, t) {
  const exit = shotExit6(t, B6.s24);
  const start = B6.older6 - 0.3;
  if (t < start || exit >= 1) return;
  const C = DATA.calibration;
  const { x0, x1, top, base } = AGE6;
  ctx.save();
  ctx.globalAlpha = 1 - exit;

  const axis = ease.outQuint(ramp(t, start, start + 0.5));
  growLine(ctx, [[x0, top - 10], [x0, base], [x1, base]], axis, { color: COLOR.dim, width: 2, cap: "butt" });
  for (const k of AGE6.ticks) {
    const y = ageY6(k);
    growLine(ctx, [[x0, y], [x1, y]], axis, { color: COLOR.line, width: 1.5, cap: "butt" });
    riseSegs(ctx, [num(String(k), 22, COLOR.dim)], x0 - 14, y + 8, ramp(t, start + 0.1, start + 0.4), 0, "right");
  }
  riseSegs(ctx, [disp("k", 30, COLOR.dim)], x0, top - 30, ramp(t, start + 0.1, start + 0.4));
  AGE_LABELS6.forEach((label, i) => {
    riseSegs(ctx, [num(label, 21, COLOR.dim)], ageX6(i), base + 34, ramp(t, start + 0.15 + i * 0.05, start + 0.45 + i * 0.05), 0, "center");
  });
  riseSegs(ctx, [cjk("游戏年龄（年）", 22, COLOR.dim)], (x0 + x1) / 2, base + 74, ramp(t, start + 0.3, start + 0.6), 0, "center");

  // 2018 年训练集：越老 k 越大；近年：基本持平
  const lines = [
    { values: C.age_train, at: B6.older6, color: COLOR.ink, name: "2018 年" },
    { values: C.age_calib, at: B6.noLonger6, color: COLOR.acc, name: "近年" },
  ];
  for (const L of lines) {
    if (t < L.at) continue;
    const pts = L.values.map((k, i) => [ageX6(i), ageY6(k)]);
    const p = ease.inOutCubic(ramp(t, L.at, L.at + 0.9));
    growLine(ctx, pts, p, { color: L.color, width: 4 });
    pts.forEach(([x, y], i) => {
      const r = 7 * spring(t - (L.at + 0.9 * (i / 4) * 0.95), 3, 0.5);
      if (r <= 0) return;
      ctx.fillStyle = L.color;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    });
    const [lx, ly] = pts[pts.length - 1];
    riseSegs(ctx, [cjk(L.name, 26, L.color, 600)], lx + 22, ly + 9, ramp(t, L.at + 0.8, L.at + 1.1));
  }
  ctx.restore();
}

// ---------- 镜 24 ----------

function ratioX6(r) {
  return logPos6(Math.min(Math.max(r, RATIO6.lo), RATIO6.hi), RATIO6.lo, RATIO6.hi, RATIO6.x0, RATIO6.x1);
}

function drawRatios6(ctx, t) {
  const exit = shotExit6(t, B6.s25);
  const start = B6.s24 + 0.2;
  if (t < start || exit >= 1) return;
  const C = DATA.calibration;
  const { x0, x1, axis } = RATIO6;
  ctx.save();
  ctx.globalAlpha = 1 - exit;

  // 横轴：真值 ÷ 估计，1 在正中
  const grow = ease.outQuint(ramp(t, start, start + 0.5));
  growLine(ctx, [[x0, axis], [x1, axis]], grow, { color: COLOR.dim, width: 2, cap: "butt" });
  const one = ratioX6(1);
  growLine(ctx, [[one, RATIO6.rows[0] - 60], [one, axis]], grow, { color: COLOR.line, width: 2, cap: "butt" });
  for (const r of RATIO6.ticks) {
    riseSegs(ctx, [num(String(r), 22, COLOR.dim)], ratioX6(r), axis + 34, ramp(t, start + 0.1, start + 0.4), 0, "center");
  }
  riseSegs(ctx, [cjk("真值 ÷ 估计", 22, COLOR.dim)], (x0 + x1) / 2, axis + 72, ramp(t, start + 0.2, start + 0.5), 0, "center");

  // 两行点：有信号 B、没有信号 B；念到“八成把握”时括出中间八成，括号外的点压暗
  const names = ["有信号 B", "没有信号 B"];
  const brackets = [C.interval.b, C.interval.no_b];
  const cut = ease.outQuint(ramp(t, B6.eighty6, B6.eighty6 + 0.5));
  STRIP6.forEach((dots, row) => {
    const y = RATIO6.rows[row];
    riseSegs(ctx, [cjk(names[row], 24, COLOR.ink, 600)], x0 - 30, y + 9, ramp(t, start + row * 0.1, start + 0.35 + row * 0.1), 0, "right");
    const [lo, hi] = brackets[row];
    for (const d of dots) {
      const appear = ramp(t, start + 0.2 + d.order * 0.7 + row * 0.1, start + 0.35 + d.order * 0.7 + row * 0.1);
      if (appear <= 0) continue;
      const inside = d.r >= lo && d.r <= hi;
      ctx.globalAlpha = (1 - exit) * appear * (inside ? lerp(0.45, 0.6, cut) : lerp(0.45, 0.12, cut));
      ctx.fillStyle = inside ? mix4(COLOR.ink, COLOR.acc, cut) : COLOR.ink;
      ctx.beginPath();
      ctx.arc(ratioX6(d.r), y + d.dy, 6, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1 - exit;
    // 括号：两头竖一下，中间一道朱红横线，两头写倍数
    const ax = ratioX6(lo);
    const bx = ratioX6(hi);
    const by = y + 52;
    const p = ease.outQuint(ramp(t, B6.eighty6 + row * 0.12, B6.eighty6 + 0.5 + row * 0.12));
    growLine(ctx, [[ax, by - 14], [ax, by], [bx, by], [bx, by - 14]], p, { color: COLOR.acc, width: 3.5, cap: "butt" });
    const lab = ramp(t, B6.eighty6 + 0.3 + row * 0.12, B6.eighty6 + 0.6 + row * 0.12);
    riseSegs(ctx, [num(lo.toFixed(2), 24, COLOR.acc)], ax - 10, by + 8, lab, 0, "right");
    riseSegs(ctx, [num(hi.toFixed(2), 24, COLOR.acc)], bx + 10, by + 8, lab, 0, "left");
  });

  // 右边：80% 区间
  const big = ramp(t, B6.interval6, B6.interval6 + 0.4);
  const pop = 1 + 0.08 * kick(t, B6.interval6 + 0.2);
  ctx.save();
  ctx.translate(1560, 480);
  ctx.scale(pop, pop);
  riseSegs(ctx, [num("80", BIG, COLOR.acc), num("%", 50, COLOR.acc), disp(" 区间", 40, COLOR.acc)], 0, 0, big, 0);
  ctx.restore();
  ctx.restore();
}

function rulerX6(k) {
  return logPos6(k, RULER6.lo, RULER6.hi, RULER6.x0, RULER6.x1);
}

// 对比尺：Vampire Survivors 两路各估的 k，差 1.91 倍，超过 1.65 倍，标“低”
function drawRuler6(ctx, t) {
  const exit = shotExit6(t, B6.s25);
  const start = B6.differ6;
  if (t < start - 0.2 || exit >= 1) return;
  const Q = DATA.calibration.query;
  const y = RULER6.y;
  ctx.save();
  ctx.globalAlpha = 1 - exit;
  growLine(ctx, [[RULER6.x0, y], [RULER6.x1, y]], ease.outQuint(ramp(t, start - 0.2, start + 0.3)), { color: COLOR.dim, width: 2, cap: "butt" });

  const ax = rulerX6(Q.k_a);
  const bx = rulerX6(Q.k_b);
  const limitX = rulerX6(Q.k_a * Math.exp(0.5));
  // 1.65 倍的界线：从 A 量出去
  const limit = ease.outQuint(ramp(t, start + 0.5, start + 0.9));
  growLine(ctx, [[limitX, y - 34], [limitX, y + 34]], limit, { color: COLOR.dim, width: 2.5, cap: "butt", dash: [8, 6] });
  riseSegs(ctx, [num("1.65", 22, COLOR.dim), cjk(" 倍", 20, COLOR.dim)], limitX, y + 64, ramp(t, start + 0.6, start + 0.9), 0, "center");

  const dots = [
    { x: ax, name: "信号 A", at: start },
    { x: bx, name: "信号 B", at: start + 0.2 },
  ];
  for (const d of dots) {
    const r = 9 * spring(t - d.at, 3, 0.5);
    if (r <= 0) continue;
    ctx.fillStyle = COLOR.ink;
    ctx.beginPath();
    ctx.arc(d.x, y, r, 0, Math.PI * 2);
    ctx.fill();
    riseSegs(ctx, [cjk(d.name, 24, COLOR.ink, 600)], d.x, y - 26, ramp(t, d.at, d.at + 0.3), 0, "center");
  }
  // 两路之间的距离：一道朱红线，写差几倍
  const gap = ease.outQuint(ramp(t, start + 0.35, start + 0.75));
  growLine(ctx, [[ax, y], [bx, y]], gap, { color: COLOR.acc, width: 5, cap: "butt" });
  riseSegs(ctx, [num((Q.k_b / Q.k_a).toFixed(2), 26, COLOR.acc), cjk(" 倍", 22, COLOR.acc)], (ax + bx) / 2, y - 26, ramp(t, start + 0.6, start + 0.9), 0, "center");

  // 念到“标为低”：右边弹出“低”
  drawLowTag6(ctx, t, RULER6.x1 + 110, y, B6.low6, B6.s25);
  ctx.restore();
}

// “低”：朱红圆角框里一个字
function drawLowTag6(ctx, t, x, y, at, out) {
  const age = t - at;
  if (age <= 0) return;
  const e = ease.inCubic(ramp(t, out, out + 0.25));
  if (e >= 1) return;
  const s = (0.5 + 0.5 * spring(age, 3.2, 0.5)) * (1 - 0.4 * e);
  ctx.save();
  ctx.globalAlpha *= ramp(t, at, at + 0.05) * (1 - e);
  ctx.translate(x, y);
  ctx.scale(s, s);
  ctx.fillStyle = COLOR.acc;
  roundRect(ctx, -40, -40, 80, 80, 14);
  ctx.fill();
  drawSegs(ctx, [disp("低", 48, COLOR.bgTop)], -24, 17);
  ctx.restore();
}

// ---------- 镜 25 ----------

function drawSteps6(ctx, t) {
  const start = B6.s25 + 0.2;
  if (t < start) return;
  const y = 200;
  const S = 34;
  const widths = STEPS6.map((s) => measureSegs(ctx, [disp(s, S)]));
  const arrow = 90;
  const total = widths.reduce((a, b) => a + b, 0) + arrow * 3;
  let x = W / 2 - total / 2 - 120;
  const lit = [B6.crawl6, B6.clean6, B6.merge6, B6.merge6 + 0.5];
  STEPS6.forEach((name, i) => {
    const at = lit[i];
    const color = mix4(COLOR.dim, COLOR.acc, ramp(t, at, at + 0.25));
    const pop = 1 + 0.08 * kick(t, at);
    ctx.save();
    ctx.translate(x + widths[i] / 2, y - 12);
    ctx.scale(pop, pop);
    riseSegs(ctx, [disp(name, S, color)], -widths[i] / 2, 12, ramp(t, start + i * 0.08, start + 0.35 + i * 0.08));
    ctx.restore();
    x += widths[i];
    if (i < 3) {
      // 先长出浅色的连线，做到这一步时朱红从左往右走过去
      const seg = [[x + 18, y - 12], [x + arrow - 18, y - 12]];
      growLine(ctx, seg, ease.outQuint(ramp(t, start, start + 0.4)), { color: COLOR.line, width: 3 });
      growLine(ctx, seg, ease.outQuint(ramp(t, lit[i] + 0.1, lit[i] + 0.4)), { color: COLOR.acc, width: 3, head: 5 });
      x += arrow;
    }
  });
  // 右边：一次约 1 分钟
  riseSegs(ctx, [cjk("约 ", 28, COLOR.ink), num("1", 40, COLOR.ink), cjk(" 分钟", 28, COLOR.ink)], x + 90, y, ramp(t, B6.minute6, B6.minute6 + 0.35));
}

function qX6(v) {
  return logPos6(v, QAXIS6.lo, QAXIS6.hi, QAXIS6.x0, QAXIS6.x1);
}

function wan6(v) {
  return String(Math.round(v / 1e4));
}

function drawQuery6(ctx, t) {
  const start = B6.s25 + 0.3;
  if (t < start) return;
  const Q = DATA.calibration.query;
  // 游戏名和评测数
  riseSegs(ctx, [disp(Q.name, 44)], W / 2, 350, ramp(t, start, start + 0.4), 0, "center");
  riseSegs(ctx, [cjk("评测 ", 24, COLOR.dim), num((Q.reviews / 1e4).toFixed(1), 26, COLOR.dim), cjk(" 万条", 24, COLOR.dim)], W / 2, 396, ramp(t, start + 0.15, start + 0.5), 0, "center");

  // 估算销量
  const pop = 1 + 0.08 * kick(t, B6.units6 + 0.2);
  ctx.save();
  ctx.translate(W / 2, 540);
  ctx.scale(pop, pop);
  riseSegs(ctx, [cjk("约 ", 40, COLOR.acc), num(wan6(Q.units), BIG, COLOR.acc), disp(" 万份", 40, COLOR.acc)], 0, 0, ramp(t, B6.units6, B6.units6 + 0.4), 0, "center");
  ctx.restore();

  // 80% 区间：一道横线从估计值往两边长开，两头写上下限
  const r = ease.outQuint(ramp(t, B6.range6, B6.range6 + 0.6));
  if (r > 0) {
    const y = QAXIS6.y;
    const cx = qX6(Q.units);
    const lx = lerp(cx, qX6(Q.low), r);
    const hx = lerp(cx, qX6(Q.high), r);
    growLine(ctx, [[QAXIS6.x0, y], [QAXIS6.x1, y]], 1, { color: COLOR.line, width: 2, cap: "butt" });
    growLine(ctx, [[lx, y], [hx, y]], 1, { color: COLOR.acc, width: 6, cap: "butt" });
    for (const x of [lx, hx]) growLine(ctx, [[x, y - 16], [x, y + 16]], 1, { color: COLOR.acc, width: 3.5, cap: "butt" });
    ctx.fillStyle = COLOR.acc;
    ctx.beginPath();
    ctx.arc(cx, y, 10, 0, Math.PI * 2);
    ctx.fill();
    const lab = ramp(t, B6.range6 + 0.4, B6.range6 + 0.7);
    riseSegs(ctx, [num(wan6(Q.low), 28, COLOR.acc), cjk(" 万", 22, COLOR.acc)], qX6(Q.low), y + 50, lab, 0, "center");
    riseSegs(ctx, [num(wan6(Q.high), 28, COLOR.acc), cjk(" 万", 22, COLOR.acc)], qX6(Q.high), y + 50, lab, 0, "center");
    riseSegs(ctx, [num("80", 24, COLOR.dim), num("%", 16, COLOR.dim), cjk(" 区间", 22, COLOR.dim)], QAXIS6.x0 - 30, y + 8, lab, 0, "right");
  }

  // 置信标签：低（两路估计分歧大）
  drawLowTag6(ctx, t, QAXIS6.x1 + 140, QAXIS6.y, B6.label6, Infinity);
  riseSegs(ctx, [cjk("两路分歧大", 24, COLOR.acc, 600)], QAXIS6.x1 + 200, QAXIS6.y + 9, ramp(t, B6.label6 + 0.25, B6.label6 + 0.55));
}

// ---------- 整段 ----------

function drawPart6(ctx, chart, t) {
  drawHandoff6(ctx, t);
  t_now = t;
  const punch = kick(t, B6.fused6 + 0.4) + kick(t, B6.low6) + kick(t, B6.label6);
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(1 + 0.012 * punch, 1 + 0.012 * punch);
  ctx.translate(-W / 2, -H / 2);
  drawBars6(ctx, t);
  drawAge6(ctx, t);
  drawRatios6(ctx, t);
  drawRuler6(ctx, t);
  drawSteps6(ctx, t);
  drawQuery6(ctx, t);
  ctx.restore();
}

PARTS.push({ first: 23, last: 25, prepare: preparePart6, draw: drawPart6 });
