// 第五段：第二路估计与融合（镜 17–22）
// 镜 17：第四段的两栏图退场。顶上留一行信号 A，下面写出信号 B 的公式：分子连到一款游戏每月在线人数的折线（面积是总小时），
//        分母连到评测者时长换算成人均小时的散点框；右边是能算信号 B 的款数。
// 镜 18–21：左右两栏（误差、估对比例），横轴 5 档评测数，四条线依次画出：信号 A、信号 B、简单平均、按档加权。
// 镜 22：两栏收起，换成两组柱子：有信号 B 的游戏、全部游戏，只用 A 和按档加权的估对比例。
// 数字都从 data.json 的 fusion 读。变量都带 5 结尾。

let B5 = null;
let layer5 = null;  // 第四段最后一帧先画在这一层，整层退场
let FIT5 = null;    // 换算框：点按横坐标排好、坐标范围

// 镜 17
const ROW_A5 = { y: 170, size: 40 };
const ROW_B5 = { y: 290, size: 52 };
const ONLINE5 = { x0: 150, x1: 880, yTop: 470, yBase: 800, max: 36000 };
const FITBOX5 = { x0: 1030, x1: 1360, y0: 470, y1: 800 };
const COUNT5 = { x: 1480, y: 680 };
const WIRE_Y5 = 365;  // 公式往下连线时拐弯的高度

// 镜 18–21 的两栏
const PY5 = { top: 300, base: 820 };
const PANEL5 = [
  { key: "rmse", title: "误差", x0: 170, x1: 880, lo: 0.2, hi: 1.05, ticks: [0.4, 0.6, 0.8, 1.0] },
  { key: "hit", title: "估对比例", x0: 1100, x1: 1810, lo: 0.25, hi: 0.8, ticks: [0.3, 0.5, 0.7] },
];
// 四条线：A、B 是近黑，融合是朱红；实线、虚线区分同色的两条
const LINES5 = [
  { key: "signal_a", name: "信号 A", dash: null, width: 4 },
  { key: "signal_b", name: "信号 B", dash: [14, 10], width: 4 },
  // 简单平均画粗虚线、按档加权画细实线：两条几乎重合，细实线压在粗虚线中间，两条都看得见
  { key: "simple_mean", name: "简单平均", dash: [16, 10], width: 7 },
  { key: "binned_weighted", name: "按档加权", dash: null, width: 3 },
];

// 镜 22 的柱子
const BARS5 = { base: 790, scale: 560, w: 130, gap: 190, centers: [640, 1290] };

function preparePart5(data) {
  layer5 = document.createElement("canvas");
  layer5.width = W;
  layer5.height = H;
  B5 = buildBeats5();
  // 换算框：横纵轴同一个范围（都是对数小时），去掉两头各 0.5% 的极端点定范围
  const pts = data.fusion.fit.points.slice().sort((p, q) => p[0] - q[0]);
  const all = pts.flatMap((p) => p).sort((a, b) => a - b);
  const q = (f) => all[Math.floor(f * (all.length - 1))];
  FIT5 = { pts, lo: q(0.005) - 0.3, hi: q(0.995) + 0.3 };
}

function buildBeats5() {
  const b = { s17: shot(17).start, s18: shot(18).start, s19: shot(19).start, s20: shot(20).start, s21: shot(21).start, s22: shot(22).start };
  // 镜 17
  b.treeA5 = word(17, "树模型");
  b.second5 = word(17, "第二路");
  b.online5 = word(17, "在线人数");
  b.hours5 = word(17, "总游玩小时");
  b.perHead5 = word(17, "人均小时");
  b.rarely5 = word(17, "两路很少");
  // 镜 18
  b.bins5 = word(18, "五档");
  b.lineA5 = word(18, "第一路信号");
  b.less5 = word(18, "误差越小");
  b.higher5 = word(18, "估对比例越高");
  // 镜 19（“第一路”“两百条”都出现两次，用更长的词定位）
  b.lineB5 = word(19, "第二路信号");
  b.below5 = word(19, "两百条评测以下");
  b.above5 = word(19, "两百条以上");
  // 镜 20
  b.corr5 = word(20, "很少往同一边错");
  b.mean5 = word(20, "简单平均");
  b.better5 = word(20, "各档表现");
  // 镜 21
  b.weights5 = word(21, "平时准确度");
  b.weighted5 = word(21, "加权后");
  b.errLow5 = word(21, "误差都比");
  b.hitSame5 = word(21, "估对比例与");
  // 镜 22
  b.withB5 = word(22, "有第二路数据");
  b.ten5 = word(22, "十个");
  b.small5 = word(22, "因小游戏");
  b.four5 = word(22, "四个");
  return b;
}

// ---------- 镜 16 → 17：第四段的两栏图退场 ----------

function drawHandoff5(ctx, t) {
  const p = ease.inOutCubic(ramp(t, B5.s17, B5.s17 + 0.5));
  if (p >= 1) return;
  const g = layer5.getContext("2d");
  g.clearRect(0, 0, W, H);
  // 第四段是 t 的纯函数，停在镜 16 的最后一帧画一遍
  drawPart4(g, chartCtx, B5.s17 - 1 / 120);
  ctx.save();
  ctx.globalAlpha = 1 - p;
  ctx.translate(W / 2, H / 2);
  ctx.scale(1 - 0.06 * p, 1 - 0.06 * p);
  ctx.translate(-W / 2, -H / 2 - 30 * p);
  ctx.drawImage(layer5, 0, 0);
  ctx.restore();
}

// ---------- 镜 17：两条路的公式 ----------

function rowASegs5(color) {
  const S = ROW_A5.size;
  return [disp("信号 A", S, color), num(" = ", S, color), disp("评测数", S, color), num(" × ", S, color), disp("k", S, color)];
}

function rowBSegs5(t) {
  const S = ROW_B5.size;
  const top = mix4(COLOR.ink, COLOR.acc, ramp(t, B5.hours5, B5.hours5 + 0.3));
  const bottom = mix4(COLOR.ink, COLOR.acc, ramp(t, B5.perHead5, B5.perHead5 + 0.3));
  return [disp("信号 B", S), num(" = ", S), disp("总游玩小时", S, top), num(" ÷ ", S), disp("人均小时", S, bottom)];
}

// 信号 B 公式里分子、分母的中点横坐标
function rowBAnchors5(ctx, segs) {
  const width = measureSegs(ctx, segs);
  const x = W / 2 - width / 2;
  const upTo = (n) => measureSegs(ctx, segs.slice(0, n));
  return {
    x,
    top: x + (upTo(2) + upTo(3)) / 2,
    bottom: x + (upTo(4) + upTo(5)) / 2,
  };
}

// 镜 17 的整体退场（镜 18 开头）
function exit17(t) {
  return ramp(t, B5.s18, B5.s18 + 0.35);
}

function drawRows5(ctx, t) {
  const exit = exit17(t);
  if (exit >= 1 || t < B5.s17) return;
  // 念到“两路很少往同一边错”：两行一起顶一下
  const pulse = kick(t, B5.rarely5);

  // 信号 A：念到“第二路”时退成次要灰，k 后面跟一棵小树
  const colorA = mix4(COLOR.ink, COLOR.dim, ramp(t, B5.second5, B5.second5 + 0.4));
  const segsA = rowASegs5(colorA);
  const wA = measureSegs(ctx, segsA) + 44;
  const xA = W / 2 - wA / 2;
  ctx.save();
  ctx.translate(W / 2, ROW_A5.y - 14);
  ctx.scale(1 + 0.05 * pulse, 1 + 0.05 * pulse);
  ctx.translate(-W / 2, -ROW_A5.y + 14);
  riseSegs(ctx, segsA, xA, ROW_A5.y, ramp(t, B5.s17 + 0.35, B5.s17 + 0.75), exit);
  const treeIn = spring(t - B5.treeA5, 3, 0.5);
  if (treeIn > 0 && exit < 1) {
    ctx.save();
    ctx.globalAlpha *= 1 - ease.inCubic(exit);
    ctx.translate(xA + wA - 18, ROW_A5.y - 15);
    ctx.scale(1.6 * treeIn, 1.6 * treeIn);
    smallTree3(ctx, 0, 0, colorA);
    ctx.restore();
  }
  ctx.restore();

  // 信号 B
  const segsB = rowBSegs5(t);
  const a = rowBAnchors5(ctx, segsB);
  ctx.save();
  ctx.translate(W / 2, ROW_B5.y - 18);
  ctx.scale(1 + 0.05 * pulse, 1 + 0.05 * pulse);
  ctx.translate(-W / 2, -ROW_B5.y + 18);
  riseSegs(ctx, segsB, a.x, ROW_B5.y, ramp(t, B5.second5, B5.second5 + 0.4), exit);
  ctx.restore();

  // 分子、分母各连一根线下去：分子连到在线人数图，分母连到换算框
  ctx.save();
  ctx.globalAlpha = 1 - ease.inCubic(exit);
  const wire = (x, toX, toY, at) => {
    const p = ease.outQuint(ramp(t, at, at + 0.55));
    growLine(ctx, [[x, ROW_B5.y + 20], [x, WIRE_Y5], [toX, WIRE_Y5], [toX, toY]], p, { color: COLOR.acc, width: 3, head: 6 });
    if (p >= 1) {
      ctx.fillStyle = COLOR.acc;
      ctx.beginPath();
      ctx.arc(toX, toY, 6, 0, Math.PI * 2);
      ctx.fill();
    }
  };
  wire(a.top, (ONLINE5.x0 + ONLINE5.x1) / 2, ONLINE5.yTop - 62, B5.hours5);
  wire(a.bottom, (FITBOX5.x0 + FITBOX5.x1) / 2, FITBOX5.y0 - 62, B5.perHead5);
  ctx.restore();
}

// 在线人数图：一款游戏截止日以前每个月的平均在线人数；念到“总游玩小时”时折线下面的面积从左往右涂满
function onlineX5(i) {
  const n = DATA.fusion.example.months.length;
  return lerp(ONLINE5.x0, ONLINE5.x1, (i + 0.5) / n);
}
function onlineY5(v) {
  return lerp(ONLINE5.yBase, ONLINE5.yTop, v / ONLINE5.max);
}

function drawOnline5(ctx, t) {
  const exit = exit17(t);
  if (t < B5.online5 - 0.2 || exit >= 1) return;
  const ex = DATA.fusion.example;
  const { x0, x1, yTop, yBase } = ONLINE5;
  ctx.save();
  ctx.globalAlpha = 1 - ease.inCubic(exit);

  const axis = ease.outQuint(ramp(t, B5.online5 - 0.2, B5.online5 + 0.3));
  growLine(ctx, [[x0, yBase], [x1, yBase]], axis, { color: COLOR.dim, width: 2, cap: "butt" });
  // 横线：1 万、2 万、3 万人
  for (let k = 1; k <= 3; k++) {
    const y = onlineY5(k * 10000);
    growLine(ctx, [[x0, y], [x1, y]], axis, { color: COLOR.line, width: 1.5, cap: "butt" });
    riseSegs(ctx, [num(String(k), 20, COLOR.dim), cjk(" 万", 18, COLOR.dim)], x0 - 12, y + 7, ramp(t, B5.online5, B5.online5 + 0.3), 0, "right");
  }
  // 年份：每年 1 月处标一下
  ex.months.forEach(([m], i) => {
    if (!m.endsWith("-01")) return;
    riseSegs(ctx, [num(m.slice(0, 4), 22, COLOR.dim)], onlineX5(i), yBase + 36, ramp(t, B5.online5 + 0.1, B5.online5 + 0.4), 0, "center");
  });
  riseSegs(ctx, [cjk("每月平均在线人数", 22, COLOR.dim)], x0, yTop - 26, ramp(t, B5.online5, B5.online5 + 0.35));
  riseSegs(ctx, [cjk(ex.name, 22, COLOR.dim)], x1, yTop - 26, ramp(t, B5.online5 + 0.1, B5.online5 + 0.45), 0, "right");

  const pts = ex.months.map(([, v], i) => [onlineX5(i), onlineY5(v)]);
  // 面积：总游玩小时就是把每个月的人数 × 小时数加起来，涂满折线下面
  const fill = ease.inOutCubic(ramp(t, B5.hours5, B5.hours5 + 1.0));
  if (fill > 0) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(x0, yTop - 20, (x1 - x0) * fill, yBase - yTop + 20);
    ctx.clip();
    ctx.beginPath();
    ctx.moveTo(pts[0][0], yBase);
    for (const [x, y] of pts) ctx.lineTo(x, y);
    ctx.lineTo(pts[pts.length - 1][0], yBase);
    ctx.closePath();
    ctx.fillStyle = COLOR.accFill.replace("0.18", "0.32");
    ctx.fill();
    ctx.restore();
  }
  const line = ease.outQuint(ramp(t, B5.online5, B5.online5 + 1.1));
  growLine(ctx, pts, line, { color: COLOR.ink, width: 3, head: 5 });
  ctx.restore();
}

// 换算框：一款游戏一个点，横轴评测者时长 t，纵轴人均小时 h，都是对数；朱红线是拟合的 ln h = a + b·ln t
function fitX5(v) {
  return lerp(FITBOX5.x0, FITBOX5.x1, (v - FIT5.lo) / (FIT5.hi - FIT5.lo));
}
function fitY5(v) {
  return lerp(FITBOX5.y1, FITBOX5.y0, (v - FIT5.lo) / (FIT5.hi - FIT5.lo));
}

function drawFitBox5(ctx, t) {
  const exit = exit17(t);
  const start = B5.perHead5 + 0.2;
  if (t < start || exit >= 1) return;
  const { x0, x1, y0, y1 } = FITBOX5;
  ctx.save();
  ctx.globalAlpha = 1 - ease.inCubic(exit);

  const frame = ease.outQuint(ramp(t, start, start + 0.45));
  growLine(ctx, [[x0, y0], [x0, y1], [x1, y1]], frame, { color: COLOR.dim, width: 2, cap: "butt" });
  riseSegs(ctx, [cjk("评测者时长", 22, COLOR.dim)], (x0 + x1) / 2, y1 + 36, ramp(t, start + 0.1, start + 0.4), 0, "center");

  // 点从左往右扫进来
  const sweep = ramp(t, start + 0.15, start + 0.95);
  const n = FIT5.pts.length;
  const shown = Math.floor(n * sweep);
  ctx.save();
  ctx.beginPath();
  ctx.rect(x0 + 2, y0, x1 - x0, y1 - y0 - 2);
  ctx.clip();
  ctx.fillStyle = COLOR.ink;
  ctx.globalAlpha *= 0.2;
  for (let i = 0; i < shown; i++) {
    const [lt, lh] = FIT5.pts[i];
    ctx.beginPath();
    ctx.arc(fitX5(lt), fitY5(lh), 2.4, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.restore();

  // 拟合线
  const { a, b } = DATA.fusion.fit;
  const lo = FIT5.lo + 0.3;
  const hi = FIT5.hi - 0.3;
  const line = ease.outQuint(ramp(t, start + 0.8, start + 1.3));
  growLine(ctx, [[fitX5(lo), fitY5(a + b * lo)], [fitX5(hi), fitY5(a + b * hi)]], line, { color: COLOR.acc, width: 4, head: 6 });
  ctx.restore();

  // 右边：能算信号 B 的款数，点扫满时升起来
  const countIn = ramp(t, start + 0.9, start + 1.3);
  const pop = 1 + 0.08 * kick(t, start + 1.1);
  ctx.save();
  ctx.translate(COUNT5.x, COUNT5.y);
  ctx.scale(pop, pop);
  riseSegs(ctx, [num(String(DATA.fusion.n_with_b), BIG, COLOR.acc), disp(" 款", 40, COLOR.acc)], 0, 0, countIn, exit);
  ctx.restore();
}

// ---------- 镜 18–21：按评测数分档的两栏图 ----------

function binX5(p, i) {
  return lerp(p.x0, p.x1, (i + 0.5) / 5);
}
function valY5(p, v) {
  return lerp(PY5.base, PY5.top, (v - p.lo) / (p.hi - p.lo));
}

function binLabel5(i) {
  const s = DATA.fusion.bin_starts;
  return i < s.length - 1 ? `${s[i]}–${s[i + 1] - 1}` : `${s[i]}+`;
}

// 第 i 条线什么时候开始画
function lineAt5(i) {
  return [B5.lineA5, B5.lineB5, B5.mean5, B5.weighted5][i];
}

// 第 i 条线此刻的颜色：A、B 从镜 20 起退成次要灰
function lineColor5(i, t) {
  if (i >= 2) return COLOR.acc;
  return mix4(COLOR.ink, COLOR.dim, ramp(t, B5.s20, B5.s20 + 0.4));
}

// 两栏图的退场（镜 22 开头）：往中间收、淡掉
function panelsExit5(t) {
  return ease.inExpo(ramp(t, B5.s22, B5.s22 + 0.45));
}

function drawPanels5(ctx, t) {
  if (t < B5.s18) return;
  const exit = panelsExit5(t);
  if (exit >= 1) return;
  ctx.save();
  ctx.globalAlpha = 1 - exit;
  ctx.translate(W / 2, H / 2);
  ctx.scale(1 - 0.12 * exit, 1 - 0.12 * exit);
  ctx.translate(-W / 2, -H / 2);

  const start = B5.s18 + 0.25;
  const axis = ease.outQuint(ramp(t, start, start + 0.6));
  for (const p of PANEL5) {
    growLine(ctx, [[p.x0, PY5.top - 10], [p.x0, PY5.base], [p.x1, PY5.base]], axis, { color: COLOR.dim, width: 2, cap: "butt" });
    for (const v of p.ticks) {
      const y = valY5(p, v);
      growLine(ctx, [[p.x0, y], [p.x1, y]], axis, { color: COLOR.line, width: 1.5, cap: "butt" });
      const label = p.key === "hit" ? [num(String(Math.round(v * 100)), 22, COLOR.dim), num("%", 16, COLOR.dim)] : [num(v.toFixed(1), 22, COLOR.dim)];
      riseSegs(ctx, label, p.x0 - 14, y + 8, ramp(t, start + 0.2, start + 0.5), 0, "right");
    }
    riseSegs(ctx, [disp(p.title, 32)], p.x0, PY5.top - 38, ramp(t, start + 0.1, start + 0.45));
    // 5 档的名字：念到“五档”时依次升起
    for (let i = 0; i < 5; i++) {
      riseSegs(ctx, [num(binLabel5(i), 21, COLOR.dim)], binX5(p, i), PY5.base + 34, ramp(t, B5.bins5 + i * 0.08, B5.bins5 + 0.3 + i * 0.08), 0, "center");
    }
    riseSegs(ctx, [cjk("评测数", 22, COLOR.dim)], (p.x0 + p.x1) / 2, PY5.base + 74, ramp(t, B5.bins5 + 0.3, B5.bins5 + 0.6), 0, "center");
  }

  drawSplit5(ctx, t);
  for (let i = 0; i < LINES5.length; i++) drawLine5(ctx, t, i);
  drawLineNames5(ctx, t);
  drawCorr5(ctx, t);
  drawShares5(ctx, t);
  ctx.restore();
}

// 一条线在两栏里同时一笔画出，每到一档点一个圆点
function drawLine5(ctx, t, i) {
  const at = lineAt5(i);
  if (t < at) return;
  const L = LINES5[i];
  const values = DATA.fusion.lines[L.key];
  const p = ease.inOutCubic(ramp(t, at, at + 0.9));
  const color = lineColor5(i, t);
  for (const panel of PANEL5) {
    const pts = values[panel.key].map((v, j) => [binX5(panel, j), valY5(panel, v)]);
    growLine(ctx, pts, p, { color, width: L.width, dash: L.dash, cap: L.dash ? "butt" : "round" });
    pts.forEach(([x, y], j) => {
      const age = t - (at + 0.9 * (j / 4) * 0.95);
      if (age < 0) return;
      // 镜 19：念到“两百条评测以下”时 B 的左两档、念到“两百条以上”时 A 的右三档顶一下
      let hit = 0;
      if (i === 1 && j < 2) hit = kick(t, B5.below5 + j * 0.08);
      if (i === 0 && j >= 2) hit = kick(t, B5.above5 + (j - 2) * 0.08);
      const r = (i === 3 ? 5 : 7) * spring(age, 3, 0.5) * (1 + 0.7 * hit);
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fill();
    });
    drawEndValues5(ctx, t, i, panel, pts, values[panel.key]);
  }
}

// 这条线头尾两档的数：画这条线的那一镜里弹出来，下一镜开头收掉
function drawEndValues5(ctx, t, i, panel, pts, values) {
  const timing = [
    { rmse: B5.less5, hit: B5.higher5, out: B5.s19 },
    { rmse: B5.lineB5 + 1.0, hit: B5.lineB5 + 1.15, out: B5.s20 },
    { rmse: B5.better5, hit: B5.better5 + 0.15, out: B5.s21 },
    { rmse: B5.errLow5, hit: B5.hitSame5, out: B5.s22 },
  ][i];
  const color = i >= 2 ? COLOR.acc : COLOR.ink;
  for (const j of [0, 4]) {
    const v = values[j];
    const segs = panel.key === "hit"
      ? [num((v * 100).toFixed(1), 30, color), num("%", 20, color)]
      : [num(v.toFixed(3), 30, color)];
    const [x, y] = pts[j];
    // 左栏线尾的右边写着线名，最后一档的数往左挪开
    const dx = panel.key === "rmse" && j === 4 ? -46 : 0;
    pill(ctx, segs, x + dx, y + endOffset5(i, panel, j, y), timing[panel.key] + (j ? 0.12 : 0), timing.out);
  }
}

// 数字放在点的上面还是下面：哪边离已经画出的其他线远放哪边
function endOffset5(i, panel, j, y) {
  let best = -34;
  let bestGap = -1;
  for (const dy of [-34, 38]) {
    let gap = Infinity;
    for (let k = 0; k < i; k++) {
      const other = valY5(panel, DATA.fusion.lines[LINES5[k].key][panel.key][j]);
      gap = Math.min(gap, Math.abs(y + dy - other));
    }
    if (gap > bestGap) {
      bestGap = gap;
      best = dy;
    }
  }
  return best;
}

// 线名只写在左栏线尾的右边；两条挨得太近时往下错开
function drawLineNames5(ctx, t) {
  const p = PANEL5[0];
  const shown = [];
  for (let i = 0; i < LINES5.length; i++) {
    const at = lineAt5(i) + 0.8;
    if (t < at) continue;
    const v = DATA.fusion.lines[LINES5[i].key].rmse[4];
    shown.push({ i, y: valY5(p, v) + 8, at });
  }
  shown.sort((a, b) => a.y - b.y || a.i - b.i);
  for (let k = 1; k < shown.length; k++) shown[k].y = Math.max(shown[k].y, shown[k - 1].y + 32);
  for (const s of shown) {
    const color = lineColor5(s.i, t);
    riseSegs(ctx, [cjk(LINES5[s.i].name, 24, color, 600)], binX5(p, 4) + 22, s.y, ramp(t, s.at, s.at + 0.3));
  }
}

// 镜 19：200 条的分界线，两栏各一道虚线；镜 20 开头收掉
function drawSplit5(ctx, t) {
  const at = B5.below5;
  if (t < at) return;
  const out = ramp(t, B5.s20, B5.s20 + 0.3);
  if (out >= 1) return;
  ctx.save();
  ctx.globalAlpha *= 1 - out;
  for (const p of PANEL5) {
    const x = lerp(p.x0, p.x1, 2 / 5);
    growLine(ctx, [[x, PY5.top - 6], [x, PY5.base]], ease.outQuint(ramp(t, at, at + 0.4)), { color: COLOR.dim, width: 2.5, cap: "butt", dash: [10, 8] });
    riseSegs(ctx, [num("200", 24, COLOR.ink), cjk(" 条", 20, COLOR.ink)], x, PY5.top - 14, ramp(t, at + 0.1, at + 0.4), 0, "center");
  }
  ctx.restore();
}

// 镜 20：两路误差的相关系数，写在图的上方；镜 21 开头收掉
function drawCorr5(ctx, t) {
  const at = B5.corr5;
  const segs = [cjk("误差相关系数  ", 30, COLOR.dim), num(DATA.fusion.corr.toFixed(2), 46, COLOR.acc)];
  ctx.save();
  const pop = 1 + 0.08 * kick(t, at + 0.3);
  ctx.translate(W / 2, 190);
  ctx.scale(pop, pop);
  riseSegs(ctx, segs, 0, 0, ramp(t, at, at + 0.35), ramp(t, B5.s21, B5.s21 + 0.3), "center");
  ctx.restore();
}

// 镜 21：每档 A 的占比，画在左栏上方：一根短条，近黑是 A、浅灰是 B
function drawShares5(ctx, t) {
  const at = B5.weights5;
  if (t < at) return;
  const out = ramp(t, B5.s22, B5.s22 + 0.3);
  const p = PANEL5[0];
  const bw = 96;
  const y = 186;
  riseSegs(ctx, [cjk("A 占比", 22, COLOR.dim)], p.x0 - 14, y + 9, ramp(t, at, at + 0.3), out, "right");
  DATA.fusion.shares.forEach((share, i) => {
    const grow = ease.outQuint(ramp(t, at + 0.1 + i * 0.07, at + 0.5 + i * 0.07));
    if (grow <= 0) return;
    const x = binX5(p, i) - bw / 2;
    ctx.save();
    ctx.globalAlpha *= 1 - out;
    ctx.fillStyle = COLOR.line;
    ctx.fillRect(x, y, bw * grow, 12);
    ctx.fillStyle = COLOR.ink;
    ctx.fillRect(x, y, bw * share * grow, 12);
    ctx.restore();
    riseSegs(ctx, [num(share.toFixed(2), 22, COLOR.ink)], binX5(p, i), y - 12, ramp(t, at + 0.25 + i * 0.07, at + 0.55 + i * 0.07), out, "center");
  });
}

// ---------- 镜 22：两组柱子 ----------

function drawBars5(ctx, t) {
  if (t < B5.s22) return;
  const F = DATA.fusion;
  const groups = [
    { data: F.with_b, title: [disp("有信号 B", 30), num(` ${F.n_with_b}`, 30), disp(" 款", 30)], at: B5.withB5, jump: B5.ten5 },
    { data: F.all, title: [disp("全部", 30), num(` ${F.n_all}`, 30), disp(" 款", 30)], at: B5.small5, jump: B5.four5 },
  ];
  const { base, scale, w, gap } = BARS5;
  groups.forEach((g, gi) => {
    const cx = BARS5.centers[gi];
    const at = g.at;
    if (t < at - 0.1) return;
    // 底线和组名
    growLine(ctx, [[cx - gap / 2 - w, base], [cx + gap / 2 + w, base]], ease.outQuint(ramp(t, at - 0.1, at + 0.3)), { color: COLOR.dim, width: 2, cap: "butt" });
    riseSegs(ctx, g.title, cx, base + 96, ramp(t, at, at + 0.35), 0, "center");
    const bars = [
      { name: "信号 A", v: g.data.signal_a.hit, color: COLOR.ink, alpha: 0.35, x: cx - gap / 2 },
      { name: "按档加权", v: g.data.binned_weighted.hit, color: COLOR.acc, alpha: 0.85, x: cx + gap / 2 },
    ];
    const tops = bars.map((b, bi) => {
      const p = spring(t - (at + 0.1 + bi * 0.18), 2.6, 0.6);
      const top = base - b.v * scale * Math.max(0, p);
      if (p > 0) {
        ctx.save();
        ctx.globalAlpha *= b.alpha;
        ctx.fillStyle = b.color;
        ctx.fillRect(b.x - w / 2, top, w, base - top);
        ctx.restore();
      }
      const enter = ramp(t, at + 0.25 + bi * 0.18, at + 0.55 + bi * 0.18);
      riseSegs(ctx, [num((b.v * 100).toFixed(1), 50, b.color), num("%", 30, b.color)], b.x, base - b.v * scale - 22, enter, 0, "center");
      riseSegs(ctx, [cjk(b.name, 26, b.color, 600)], b.x, base + 42, enter, 0, "center");
      return base - b.v * scale;
    });

    // 念到“十个”“四个”：从 A 的数字上方拉一道弧到加权的数字上方，弧顶写涨了几个百分点
    const jump = ease.outQuint(ramp(t, g.jump - 0.15, g.jump + 0.4));
    if (jump > 0) {
      const ax = bars[0].x;
      const bx = bars[1].x;
      const ay = tops[0] - 84;
      const by = tops[1] - 84;
      const peak = Math.min(ay, by) - 60;
      const curve = [];
      for (let k = 0; k <= 24; k++) {
        const u = k / 24;
        // 二次贝塞尔：起点、控制点、终点
        const cxp = (ax + bx) / 2;
        const x = (1 - u) * (1 - u) * ax + 2 * (1 - u) * u * cxp + u * u * bx;
        const y = (1 - u) * (1 - u) * ay + 2 * (1 - u) * u * peak + u * u * by;
        curve.push([x, y]);
      }
      growLine(ctx, curve, jump, { color: COLOR.acc, width: 3.5 });
      if (jump >= 1) {
        // 箭头
        const [px, py] = curve[curve.length - 2];
        const ang = Math.atan2(by - py, bx - px);
        ctx.save();
        ctx.fillStyle = COLOR.acc;
        ctx.translate(bx, by);
        ctx.rotate(ang);
        ctx.beginPath();
        ctx.moveTo(4, 0);
        ctx.lineTo(-14, -9);
        ctx.lineTo(-14, 9);
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }
      const gain = (g.data.binned_weighted.hit - g.data.signal_a.hit) * 100;
      pill(ctx, [num(`+${gain.toFixed(1)}`, 56, COLOR.acc), cjk(" 个百分点", 26, COLOR.acc, 600)], (ax + bx) / 2, (Math.min(ay, by) + peak) / 2 - 42, g.jump + 0.1, Infinity);
    }
  });
}

// ---------- 整段 ----------

function drawPart5(ctx, chart, t) {
  drawHandoff5(ctx, t);
  t_now = t;
  // 融合各档都更好、两个“提高”落地时整幅画面顶一下
  const punch = kick(t, B5.better5) + kick(t, B5.ten5 + 0.3) + kick(t, B5.four5 + 0.3);
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(1 + 0.012 * punch, 1 + 0.012 * punch);
  ctx.translate(-W / 2, -H / 2);
  drawRows5(ctx, t);
  drawOnline5(ctx, t);
  drawFitBox5(ctx, t);
  drawPanels5(ctx, t);
  drawBars5(ctx, t);
  ctx.restore();
}

PARTS.push({ first: 17, last: 22, prepare: preparePart5, draw: drawPart5 });
