// 第二段：三种估 k 的方法（镜 7–9）
// 接着第一段最后的画面：散点图留在左边不动，右栏顶上换成当前方法的公式，下面三根柱子。
// 每种方法：公式升起 → 它的 k 线在散点图上一笔画出 → 估对的游戏从左到右染成朱红 → 柱子跟着长到估对比例。
// 坐标、镜头、坐标轴直接用第一段的（part1.js），这里只画第二段新加的东西。
// 几个页面脚本共用一个全局作用域，所以这一段的变量都带 2 或 M 结尾，不和第一段重名。

const METHOD_NAMES = ["固定 k", "线性回归", "树模型"];

// 右栏的柱子：底线、三根柱子的中心、高度比例
const BAR_BASE = 868;       // 底线
const BAR_W = 128;
const BAR_GAP = 250;        // 相邻两根柱子中心的距离
const BAR_X0 = COL + 70;    // 第一根柱子的中心
const BAR_SCALE = 560;      // 估对比例 100% 时柱子多高（46.3% 约 260 像素）
const RATE_SIZE = 52;       // 柱顶数字的字号：三个数字并排，比第一段的单个数字小
const HEAD_SIZE = 43;       // 右栏公式的字号，和第一段停靠后的公式一样大
const HIT_ALPHA = 0.42;     // 估对的点的常亮度：太亮会在点群中间糊成一条红带，看不出 26% 和 46% 的差别

let dotsM = null;   // 剔除后的 9623 款游戏：世界坐标、扫到的先后、三种方法各估对没有
let linesM = null;  // 三种方法的 k 线（世界坐标）
let B2 = null;      // 这一段每个动作的时刻（秒）

function preparePart2(data) {
  const x0 = wx(10);
  const x1 = wx(X_MAX);
  dotsM = [];
  data.points.forEach(([reviews, players, ...hits], i) => {
    if (reviews < 10) return;  // 第一段已经剔除了
    const x = wx(reviews);
    dotsM.push({ x, y: wy(players), hits, order: (x - x0) / (x1 - x0), jitter: dots[i].jitter });
  });
  // 固定 k 是一条 45 度直线，从横轴左端（评测 10 条）画到图的顶上；另两种用导出的滑动中位数
  const k = DATA.methods.fixed.line[0][1] / DATA.methods.fixed.line[0][0];
  const top = Y_MAX / k / 1.3;
  linesM = [
    [[wx(10), wy(10 * k)], [wx(top), wy(top * k)]],
    smoothThrough(data.methods.linear.line.map(([r, p]) => [wx(r), wy(p)]), 4),
    smoothThrough(data.methods.tree.line.map(([r, p]) => [wx(r), wy(p)]), 4),
  ];
  B2 = buildBeats2();
}

function buildBeats2() {
  const b = { s7: shot(7).start, s8: shot(8).start, s9: shot(9).start };
  b.slots = word(7, "三种预测方法");
  b.clear = b.slots - 0.45;  // 第一段留下的公式和“9623 款”收起，给柱子让位
  // 每种方法四个时刻：公式升起、k 线画出、估对的点扫出来、收起
  b.head = [word(7, "固定 k"), word(8, "线性回归"), word(9, "树模型")];
  b.line = [word(7, "共用同一个"), word(8, "直接相加"), word(9, "多个条件")];
  b.sweep = [word(7, "估对比例"), word(8, "估对比例"), word(9, "估对比例")];
  b.done = [b.s8, b.s9, Infinity];
  b.band = b.line[0] + 0.55;        // 45 度线画完，±30% 的带子张开
  b.rise = word(8, "有所上升");
  b.fixedEffect = word(8, "依然固定");
  b.best = word(9, "最高");
  b.beat = word(9, "优于");
  b.handoff = Infinity;  // 第三段登记时改成镜 10 的开头
  return b;
}

// 估对比例这个数什么时候落定：点从左往右扫完
const SWEEP = 0.9;
function landed(m) {
  return B2.sweep[m] + SWEEP + 0.15;
}

function camera2(t) {
  const cam = cameraAt(t);  // 第一段最后停下的位置
  // 整幅画面只在树模型的估对比例落定时顶一下（念“最高”也在这一刻），前两种方法不顶
  cam.zoom *= 1 + 0.018 * kick(t, landed(2));
  return cam;
}

// ---------- 散点：估对的染成朱红 ----------

// 第 m 种方法“亮着”的程度：扫到这个点时亮起，下一镜开头收起
function litM(m, d, t) {
  const at = B2.sweep[m] + d.order * SWEEP + d.jitter * 0.12;
  const off = B2.done[m] + d.jitter * 0.2;
  return ramp(t, at, at + 0.08) * (1 - ramp(t, off, off + 0.3));
}

function drawDots2(c, t) {
  // 有方法在亮的时候，没估对的点压暗，估对的点才看得出多少
  let active = 0;
  for (const m of [0, 1, 2]) active = Math.max(active, ramp(t, B2.sweep[m], B2.sweep[m] + 0.3) * (1 - ramp(t, B2.done[m], B2.done[m] + 0.3)));
  const missAlpha = COLOR.pointAlpha * (1 - 0.4 * active);
  for (const d of dotsM) {
    let lit = 0;
    let flash = 0;
    for (const m of [0, 1, 2]) {
      if (!d.hits[m]) continue;
      const l = litM(m, d, t);
      if (l > lit) {
        lit = l;
        // 刚亮起时闪一下再落到常亮度：一道光从左往右扫过去
        const age = t - (B2.sweep[m] + d.order * SWEEP + d.jitter * 0.12);
        flash = age > 0 ? Math.exp(-age / 0.15) : 0;
      }
    }
    if (lit < 1) {
      c.globalAlpha = missAlpha * (1 - lit);
      c.drawImage(sprites.ink, d.x - 5, d.y - 5, 10, 10);
    }
    if (lit > 0) {
      c.globalAlpha = lit * (HIT_ALPHA + (1 - HIT_ALPHA) * flash);
      c.drawImage(sprites.acc, d.x - 5, d.y - 5, 10, 10);
    }
  }
  c.globalAlpha = 1;
}

// ---------- k 线和 ±30% 的带子 ----------

function drawLines2(c, t, z) {
  // 固定 k 的 45 度线：镜 7 是朱红实线；镜 8 起退成灰色虚线，留着当参照，看后两条线往哪弯
  const grow0 = ease.outQuint(ramp(t, B2.line[0], B2.line[0] + 0.55));
  const toRef = ease.inOutCubic(ramp(t, B2.done[0], B2.done[0] + 0.4));
  if (toRef < 1) growLine(c, linesM[0], grow0, { color: COLOR.acc, width: 4.5, head: 7, alpha: 1 - toRef });
  if (toRef > 0) growLine(c, linesM[0], 1, { color: COLOR.ink, width: 2 / z, alpha: 0.45 * toRef, dash: [10 / z, 8 / z], cap: "butt" });

  for (const m of [1, 2]) {
    const grow = ease.outQuint(ramp(t, B2.line[m], B2.line[m] + 0.8));
    const gone = ease.inExpo(ramp(t, B2.done[m], B2.done[m] + 0.4));
    // 先描一道纸色的宽边，线压在染红的点上也看得清
    growLine(c, linesM[m], grow, { color: COLOR.bgTop, width: 10, from: gone, alpha: 0.9 });
    growLine(c, linesM[m], grow, { color: COLOR.acc, width: 4.5, head: 7, from: gone });
  }
}

// 镜 7：45 度线两边张开 ±30% 的带子，落在里面就算估对
function drawBand2(c, t) {
  const open = ease.outQuint(ramp(t, B2.band, B2.band + 0.5));
  if (open <= 0) return;
  const gone = ease.inExpo(ramp(t, B2.done[0], B2.done[0] + 0.3));
  if (gone >= 1) return;
  const [[xa, ya], [xb, yb]] = linesM[0];
  // 玩家数乘 1.3、乘 0.7，在对数坐标里就是整条线往上、往下平移
  const up = -Math.log10(Math.pow(1.3, open)) * DEC;
  const down = -Math.log10(Math.pow(0.7, open)) * DEC;
  c.save();
  c.globalAlpha = 1 - gone;
  c.fillStyle = COLOR.accFill;
  c.beginPath();
  c.moveTo(xa, ya + up);
  c.lineTo(xb, yb + up);
  c.lineTo(xb, yb + down);
  c.lineTo(xa, ya + down);
  c.closePath();
  c.fill();
  c.restore();
  for (const dy of [up, down]) {
    growLine(c, [[xa, ya + dy], [xb, yb + dy]], 1, { color: COLOR.acc, width: 1.4, alpha: 0.7 * (1 - gone) });
  }
  // “±30%”标在带子右上方，那里点稀，不压点群
  const at = wx(2e5);
  const y = wy(2e5 * DATA.fixed_k);
  pill(c, [num("±30%", 24, COLOR.acc)], at - 62, y - 22, B2.band + 0.25, B2.done[0]);
}

// ---------- 右栏 ----------

// 三种方法的公式。下标用小一号的字往下挪
function headSegs(m) {
  const S = HEAD_SIZE;
  const sub = (text, color = COLOR.ink) => ({ ...num(text, S * 0.6, color), dy: S * 0.18 });
  const k = String(Math.round(DATA.fixed_k));
  if (m === 0) return [disp("k", S), num(" = ", S), num(k, S, COLOR.acc)];
  if (m === 1) {
    return [num("ln ", S), disp("k", S), num(" = a + ", S), num("b", S, COLOR.acc), num("×", S),
      disp("价格", S), num(" + ", S), num("c", S, COLOR.acc), num("×", S), disp("好评率", S), num(" + …", S)];
  }
  return [num("ln ", S), disp("k", S), num(" = ", S), disp("树", S), sub("1"), num(" + ", S),
    disp("树", S), sub("2"), num(" + … + ", S), disp("树", S, COLOR.acc), sub("400", COLOR.acc)];
}

// 线性回归的 b、c 在念到“依然固定”时闪一下：系数是定死的，和别的条件怎么搭配都不变
function flashCoefficients(segs, t) {
  const f = kick(t, B2.fixedEffect);
  if (f <= 0.01) return segs;
  return segs.map((s) => (s.text === "b" || s.text === "c" ? { ...s, size: s.size * (1 + 0.35 * f) } : s));
}

function drawHeader2(ctx, t) {
  // 第一段停在这里的“k = 玩家数 ÷ 评测数”升出去：照原样画，再往上挪、裁掉
  const out = ease.inCubic(ramp(t, B2.clear, B2.clear + 0.3));
  if (out < 1) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(COL - 20, HEADER_Y - 62, 820, 76);
    ctx.clip();
    ctx.translate(0, -out * 60);
    drawFormula(ctx, t);
    ctx.restore();
  }
  // 公式下面那条细线一直留着
  ctx.save();
  ctx.strokeStyle = COLOR.line;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(COL, HEADER_Y + 30);
  ctx.lineTo(COL + 700, HEADER_Y + 30);
  ctx.stroke();
  ctx.restore();

  for (const m of [0, 1, 2]) {
    // 第三段开头，树模型的公式交给 part3.js 接着画（它要飞到顶上）
    if (m === 2 && t >= B2.handoff) continue;
    let segs = headSegs(m);
    if (m === 1) segs = flashCoefficients(segs, t);
    // 太长就整体缩小，不超出右栏
    const width = measureSegs(ctx, headSegs(m));
    const s = Math.min(1, 700 / width);
    ctx.save();
    ctx.translate(COL, HEADER_Y);
    ctx.scale(s, s);
    riseSegs(ctx, segs, 0, 0, ramp(t, B2.head[m], B2.head[m] + 0.45), ramp(t, B2.done[m], B2.done[m] + 0.28));
    ctx.restore();
  }
}

function drawBars2(ctx, t) {
  // 底线一笔画出，三个方法名依次升起
  const base = ease.outQuint(ramp(t, B2.slots, B2.slots + 0.6));
  if (base <= 0) return;
  growLine(ctx, [[COL, BAR_BASE], [COL + 700, BAR_BASE]], base, { color: COLOR.dim, width: 2, cap: "butt" });

  // 镜 9 念到“优于”：从树模型的柱顶往左拉一条虚线，前两根柱子比它矮多少一眼看出。
  // 先画，柱顶的数字压在它上面
  const reach = ease.outQuint(ramp(t, B2.beat, B2.beat + 0.6));
  if (reach > 0) {
    const y = BAR_BASE - DATA.methods.tree.hit_rate * BAR_SCALE;
    const x1 = BAR_X0 + 2 * BAR_GAP - BAR_W / 2;
    const x0 = BAR_X0 - BAR_W / 2;
    growLine(ctx, [[x1, y], [x0, y]], reach, { color: COLOR.acc, width: 2, dash: [8, 7], cap: "butt", alpha: 0.8 });
  }

  for (const m of [0, 1, 2]) {
    const cx = BAR_X0 + m * BAR_GAP;
    const rate = DATA.methods[["fixed", "linear", "tree"][m]].hit_rate;
    // 轮到它时方法名变黑，没轮到、已经过去的是灰的；最后树模型留朱红
    const on = ramp(t, B2.head[m], B2.head[m] + 0.2) * (1 - ramp(t, B2.done[m], B2.done[m] + 0.3));
    const nameColor = m === 2 && t >= B2.head[2] ? COLOR.acc : on > 0.5 ? COLOR.ink : COLOR.dim;
    riseSegs(ctx, [disp(METHOD_NAMES[m], 28, nameColor)], cx, BAR_BASE + 46,
      ramp(t, B2.slots + 0.15 + m * 0.12, B2.slots + 0.6 + m * 0.12), 0, "center");

    // 柱子：和点一起扫，点扫完它也长到位，弹一下落定
    const grow = spring(t - B2.sweep[m], 1.2, 0.62);
    if (grow <= 0) continue;
    const h = rate * BAR_SCALE * grow;
    // 当前这一根是朱红，过去的退成灰；树模型最后留朱红
    const past = m === 2 ? 0 : ramp(t, B2.done[m], B2.done[m] + 0.4);
    ctx.save();
    ctx.fillStyle = COLOR.acc;
    ctx.globalAlpha = 1 - past;
    ctx.fillRect(cx - BAR_W / 2, BAR_BASE - h, BAR_W, h);
    ctx.fillStyle = COLOR.dim;
    ctx.globalAlpha = past * 0.55;
    ctx.fillRect(cx - BAR_W / 2, BAR_BASE - h, BAR_W, h);
    ctx.restore();

    // 柱顶的数字跟着滚，落定时顶一下
    const shown = rate * 100 * ease.outExpo(ramp(t, B2.sweep[m], landed(m)));
    const color = past > 0.5 ? COLOR.dim : COLOR.acc;
    const segs = [num(shown.toFixed(1), RATE_SIZE, color), num("%", RATE_SIZE * 0.6, color)];
    const pop = 1 + 0.14 * kick(t, landed(m)) + (m === 2 ? 0.12 * kick(t, B2.best) : 0);
    const width = measureSegs(ctx, segs);
    const y = BAR_BASE - h - 22;
    ctx.save();
    ctx.translate(cx, y);
    ctx.scale(pop, pop);
    // 升完以后描一圈底色的边：镜 9 那条虚线从数字后面穿过去，不压住数字
    const enter = ramp(t, B2.sweep[m], B2.sweep[m] + 0.3);
    if (enter < 1) riseSegs(ctx, segs, -width / 2, 0, enter);
    else drawSegs(ctx, segs, -width / 2, 0, true);
    ctx.restore();
  }

}

// ---------- 整段 ----------

function drawPart2(ctx, chart, t) {
  t_now = t;
  const cam = camera2(t);
  chart.save();
  chart.setTransform(cam.zoom, 0, 0, cam.zoom, ANCHOR.x - cam.cx * cam.zoom, ANCHOR.y - cam.cy * cam.zoom);
  drawAxes(chart, t, cam.zoom);
  drawBand2(chart, t);
  drawDots2(chart, t);
  drawLines2(chart, t, cam.zoom);
  chart.restore();
  composeChart(ctx, 1062, 1088);

  // 第一段留下的“9623 款”升出去
  const nKept = dotsM.length;
  bigNumber(ctx, t, [num(String(nKept), BIG), disp(" 款", 40)], B.keep, B2.clear);
  drawHeader2(ctx, t);
  drawBars2(ctx, t);
}

PARTS.push({ first: 7, last: 9, prepare: preparePart2, draw: drawPart2 });
