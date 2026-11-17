// 第七段：全方法总览（镜 26–28）
// 一张横向的大对比图：三块（全部 9623 款、有信号 B 的 3722 款、近年 116 款），共 13 列，
// 上轨误差、下轨估对比例，三块共用同一套纵轴。每块最后一列是最终融合，朱红。
// 镜 26：镜头放大看左块，念到哪种方法长出哪一列。镜 27：镜头往右平移，长出中块、右块。
// 镜 28：镜头拉远到全图，其余方法压淡，只留三组最终融合，静止收尾。
// 数字都从 data.json 的 overview 读。变量都带 7 结尾。

let B7 = null;
let layer7 = null;
let COLS7 = null;  // 13 列：所在块、在块里第几列、横坐标、出场时刻

const OV7 = {
  x0: 200, x1: 1840, gap: 0.8,         // gap：块与块之间空几列宽
  titleY: 150,
  errBase: 440, errH: 230, errMax: 1.1,  // 上轨：误差 0–1.1
  hitBase: 790, hitH: 250, hitMax: 0.75, // 下轨：估对比例 0–75%
  nameY: 830, noteY: 856, barW: 62,
};
const ZOOM7 = 1.2;  // 镜 26、27 的镜头放大倍数；再大的话上下会被字幕挡住
const CY7 = 510;

function preparePart7(data) {
  layer7 = document.createElement("canvas");
  layer7.width = W;
  layer7.height = H;
  B7 = buildBeats7();
  const blocks = data.overview;
  const total = blocks.reduce((n, b) => n + b.cols.length, 0) + OV7.gap * (blocks.length - 1);
  const step = (OV7.x1 - OV7.x0) / total;
  // 每列出场的时刻：挂在念到这种方法的词上
  const times = [
    [B7.fixed7, B7.linear7, B7.tree7, B7.fusion7, B7.fusion7 + 0.35],
    [B7.withB7, B7.withB7 + 0.3, B7.withB7 + 0.6, B7.weighted7],
    [B7.recent7, B7.recent7 + 0.3, B7.ageCal7, B7.refuse7],
  ];
  COLS7 = [];
  let slot = 0;
  blocks.forEach((b, bi) => {
    b.cols.forEach((c, ci) => {
      COLS7.push({ ...c, block: bi, index: ci, last: ci === b.cols.length - 1, x: OV7.x0 + step * (slot + 0.5), at: times[bi][ci] });
      slot += 1;
    });
    slot += OV7.gap;
  });
  COLS7.step = step;
}

function buildBeats7() {
  const b = { s26: shot(26).start, s27: shot(27).start, s28: shot(28).start };
  // 镜 26
  b.fixed7 = word(26, "固定倍数");
  b.linear7 = word(26, "线性回归");
  b.tree7 = word(26, "树模型");
  b.fusion7 = word(26, "两路融合");
  b.errDown7 = word(26, "误差逐级下降");
  b.hitUp7 = word(26, "估对比例持续上升");
  // 镜 27
  b.withB7 = word(27, "有第二路数据");
  b.weighted7 = word(27, "加权融合");
  b.recent7 = word(27, "近年校准集");
  b.ageCal7 = word(27, "年龄校准");
  b.refuse7 = word(27, "再融合");
  b.lowest7 = word(27, "最低误差");
  b.highest7 = word(27, "最高估对比例");
  // 镜 28
  b.treeEnd7 = word(28, "树模型");
  b.secondEnd7 = word(28, "第二路融合");
  b.ageEnd7 = word(28, "年龄校准");
  return b;
}

// 镜 25 → 26：第六段的画面退场
function drawHandoff7(ctx, t) {
  const p = ease.inOutCubic(ramp(t, B7.s26, B7.s26 + 0.5));
  if (p >= 1) return;
  const g = layer7.getContext("2d");
  g.clearRect(0, 0, W, H);
  drawPart6(g, chartCtx, B7.s26 - 1 / 120);
  ctx.save();
  ctx.globalAlpha = 1 - p;
  ctx.translate(W / 2, H / 2);
  ctx.scale(1 - 0.06 * p, 1 - 0.06 * p);
  ctx.translate(-W / 2, -H / 2 - 30 * p);
  ctx.drawImage(layer7, 0, 0);
  ctx.restore();
}

// 一块的中心横坐标
function blockCenter7(bi) {
  const cols = COLS7.filter((c) => c.block === bi);
  return (cols[0].x + cols[cols.length - 1].x) / 2;
}

// 镜头：放大 1.2 倍跟着正在画的那一块，镜 28 拉远到全图。镜头中心不越过画面边，左右不留空
function camera7(t) {
  const half = W / 2 / ZOOM7;
  const clampX = (x) => Math.min(Math.max(x, half), W - half);
  let cx = clampX(blockCenter7(0));
  cx = lerp(cx, clampX(blockCenter7(1)), ease.inOutCubic(ramp(t, B7.withB7 - 0.3, B7.withB7 + 0.6)));
  cx = lerp(cx, clampX(blockCenter7(2)), ease.inOutCubic(ramp(t, B7.recent7 - 0.3, B7.recent7 + 0.6)));
  const out = ease.inOutCubic(ramp(t, B7.s28 + 0.1, B7.s28 + 1.4));
  return { zoom: lerp(ZOOM7, 1, out), cx: lerp(cx, W / 2, out), cy: lerp(CY7, H / 2, out) };
}

function errTop7(v) {
  return OV7.errBase - (v / OV7.errMax) * OV7.errH;
}
function hitTop7(v) {
  return OV7.hitBase - (v / OV7.hitMax) * OV7.hitH;
}

// 一块的框架什么时候出来：它的第一列出场前一点
// 左块在镜 26 一开头、念“回顾全部游戏”时就出来
function blockAt7(bi) {
  if (bi === 0) return B7.s26 + 0.5;
  return COLS7.find((c) => c.block === bi).at - 0.35;
}

// 镜 28 念到“树模型”“第二路融合”“年龄校准”时，对应的列顶一下
function finalKick7(c, t) {
  if (c.block === 0 && c.index === 2) return kick(t, B7.treeEnd7);
  if (!c.last) return 0;
  if (c.block < 2) return kick(t, B7.secondEnd7 + c.block * 0.12);
  return kick(t, B7.ageEnd7);
}

function drawOverview7(ctx, t) {
  const blocks = DATA.overview;
  // 镜 28：其余方法压淡
  const fade = ramp(t, B7.s28 + 0.6, B7.s28 + 1.4);

  // 左边两轨的名字
  const frame0 = blockAt7(0);
  riseSegs(ctx, [disp("误差", 28, COLOR.dim)], OV7.x0 - 34, OV7.errBase - OV7.errH / 2, ramp(t, frame0, frame0 + 0.35), 0, "right");
  riseSegs(ctx, [disp("估对比例", 28, COLOR.dim)], OV7.x0 - 34, OV7.hitBase - OV7.hitH / 2, ramp(t, frame0 + 0.1, frame0 + 0.45), 0, "right");

  blocks.forEach((b, bi) => {
    const at = blockAt7(bi);
    if (t < at) return;
    const cols = COLS7.filter((c) => c.block === bi);
    const l = cols[0].x - COLS7.step / 2 + 6;
    const r = cols[cols.length - 1].x + COLS7.step / 2 - 6;
    const grow = ease.outQuint(ramp(t, at, at + 0.5));
    for (const y of [OV7.errBase, OV7.hitBase]) growLine(ctx, [[l, y], [r, y]], grow, { color: COLOR.dim, width: 2, cap: "butt" });
    riseSegs(ctx, [disp(b.title + " ", 28), num(String(b.n), 28), disp(" 款", 28)], (l + r) / 2, OV7.titleY, ramp(t, at, at + 0.4), 0, "center");
    // 块与块之间一道竖虚线
    if (bi > 0) {
      const x = l - (COLS7.step * OV7.gap) / 2 - 6;
      growLine(ctx, [[x, OV7.titleY - 30], [x, OV7.noteY]], grow, { color: COLOR.dim, width: 2, cap: "butt", dash: [10, 8] });
    }
  });

  for (const c of COLS7) {
    if (t < c.at) continue;
    const p = spring(t - c.at, 2.6, 0.6);
    const color = c.last ? COLOR.acc : COLOR.ink;
    const alpha = c.last ? 0.85 : lerp(0.32, 0.16, fade);
    const textColor = c.last ? COLOR.acc : mix4(COLOR.ink, COLOR.dim, fade);
    const w = OV7.barW;
    const pop = finalKick7(c, t);

    ctx.save();
    ctx.globalAlpha *= alpha;
    ctx.fillStyle = color;
    for (const [base, top] of [[OV7.errBase, errTop7(c.rmse)], [OV7.hitBase, hitTop7(c.hit)]]) {
      const y = lerp(base, top, Math.max(0, p));
      ctx.fillRect(c.x - w / 2, y, w, base - y);
    }
    ctx.restore();

    const enter = ramp(t, c.at + 0.15, c.at + 0.45);
    // 镜 26 念到“误差逐级下降”“估对比例持续上升”时，左块的数依次顶一下；镜 27 念到“最低误差”“最高估对比例”时，中块、右块的融合顶一下
    let kickErr = 0;
    let kickHit = 0;
    if (c.block === 0) {
      kickErr = kick(t, B7.errDown7 + c.index * 0.12);
      kickHit = kick(t, B7.hitUp7 + c.index * 0.12);
    } else if (c.last) {
      kickErr = kick(t, B7.lowest7 + (c.block - 1) * 0.15);
      kickHit = kick(t, B7.highest7 + (c.block - 1) * 0.15);
    }
    const label = (segs, y, k) => {
      ctx.save();
      ctx.translate(c.x, y - 10);
      const s = 1 + 0.15 * (k + pop);
      ctx.scale(s, s);
      riseSegs(ctx, segs, 0, 10, enter, 0, "center");
      ctx.restore();
    };
    label([num(c.rmse.toFixed(3), 24, textColor)], errTop7(c.rmse) - 14, kickErr);
    label([num((c.hit * 100).toFixed(1), 24, textColor), num("%", 15, textColor)], hitTop7(c.hit) - 14, kickHit);
    riseSegs(ctx, [cjk(c.name, 21, textColor, c.last ? 700 : 500)], c.x, OV7.nameY, enter, 0, "center");
    if (c.note) riseSegs(ctx, [cjk(c.note, 17, COLOR.dim)], c.x, OV7.noteY, enter, 0, "center");
  }
}

function drawPart7(ctx, chart, t) {
  drawHandoff7(ctx, t);
  t_now = t;
  if (t < B7.s26 + 0.2) return;
  const cam = camera7(t);
  const punch = kick(t, B7.refuse7 + 0.3);
  const z = cam.zoom * (1 + 0.012 * punch);
  ctx.save();
  ctx.translate(W / 2, H / 2);
  ctx.scale(z, z);
  ctx.translate(-cam.cx, -cam.cy);
  drawOverview7(ctx, t);
  ctx.restore();
}

PARTS.push({ first: 26, last: 28, prepare: preparePart7, draw: drawPart7 });
