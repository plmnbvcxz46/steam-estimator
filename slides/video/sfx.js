// 音效：什么时刻放哪个声音。时刻直接用各段的动作时刻（B、B2……），配音改了时间，音效跟着走。
// render.mjs 拼声音时调用 soundCues()，把这些声音叠在配音下面。声音文件和来源见 sfx/SOURCE.md。
//
// 规则（2026-11-18 让 agy 看完整片后定的：原来“有动画就配声”，185 个太密、太乱）：
// - 一个画面事件最多一个声音；退场、变灰、合回去这类“弱化”动作不配声
// - 一串元素依次出现，只在开头、结尾各响一下，不连打
// - 普通元素、灰柱子用 pop；关键结论（红柱、落定的数字）用 thud；6 处全幅震动用 impact
// - 数字滚动只配给单独的一次滚动，滚完补一声轻 pop 当句号

// 每个声音：文件、“落点”（文件里听起来最响的那一下在第几秒，对齐画面动作用）、放出来的峰值（dB，0 是满幅）。
// 配音统一到 -16 LUFS 后峰值在 -2 dB 上下
const SOUNDS = {
  pop:    { file: "pop.wav",    hit: 0,    db: -10 },  // 元素出现：柔和、没有明显音高，最不抢人声
  tick:   { file: "tick.wav",   hit: 0,    db: -14 },  // 慢慢一步步亮起（只剩流程四步）
  thud:   { file: "thud.wav",   hit: 0.005, db: -6 },  // 关键数字、结论落定
  impact: { file: "impact.wav", hit: 0.153, db: -8 },  // 整幅画面震一下（全片 6 处）：轻快的低频“咚”
  // 以下三个是用户从网上候选里试听选定的
  whoosh:     { file: "whoosh_soft.wav", hit: 0.13, db: -16 }, // 线画出、东西飞过：纸面刷过声，削掉 3.5 kHz 以上（原声太亮，压在女声齿音上）
  counter:    { file: "counter.wav",    hit: 0.04, db: -16 },  // 数字滚动：转轮滴答，越转越慢；按滚动时长截断
  transition: { file: "transition.wav", hit: 0.43, db: -10 },  // 换段：柔和的气流声，最响的一下对准画面变化
  // 上升音：试过 4 个，放进片子里让 agy 听，这几处旁白一直在说，扫频会盖住人声，不如不加。
  // 要再试就填 { file, hit: 顶点在第几秒, lead: 只放顶点前几秒, cut: 顶点后留几秒, db }
  riser: null,
};

// 背景音乐：整片从头铺到尾，不够长就循环。lufs 是没有人声时的响度，有人声时还会自动再压低一截。
// 成片不用（agy 对比过：教室里人声清楚最要紧，音效已经撑起节奏）；要试就 --eval "MUSIC = {...}"
let MUSIC = null;
const MUSIC_TRIED = { file: "music/in-the-lobby.ogg", lufs: -26 };

// 返回 [{ t: 画面动作的时刻, sound: 声音名, dur: 只放前几秒（可省） }]
function soundCues() {
  const cues = [];
  const add = (t, sound, dur) => cues.push({ t, sound, dur });
  // 6 处“震一下”：撞击（上升音现在是 null，不放）
  const big = (t) => { add(t, "riser"); add(t, "impact"); };
  // 单独一次数字滚动：滚的时候转轮滴答，停下时一声轻 pop
  const roll = (t, dur) => { add(t, "counter", dur); add(t + dur, "pop"); };

  // ---- 第一段：倍数 k（镜 1–6）----
  add(B.formulaIn, "pop");                  // 公式出现
  add(B.k + 0.05, "thud");                  // k 砸下来
  add(B.fly, "whoosh");                     // 公式飞到右栏
  roll(B.dots, 1.1);                        // 右栏款数 0 → 11716
  add(B.kline, "whoosh");                   // 朱红斜线射出
  add(B.ten, "thud");                       // 量出“10 倍”
  add(B.byReviews, "whoosh");               // 朱红扫过横轴
  add(B.medians, "pop");                    // 各档中位数圆点弹出
  big(B.r39);                               // “39 倍”，整幅震一下
  add(popTime(1), "pop");                   // 其余各档倍数依次弹出：只在第一个、最后一个响
  add(popTime(bins.length - 1), "pop");
  add(B.jump, "thud");                      // 圈出跳变
  add(B.small, "pop");                      // 2093 款染红
  roll(B.keep + 0.1, 0.8);                  // 11716 → 9623

  // ---- 换段：每段开头，加上段内整屏换掉的几镜（镜 11 树换成表，镜 18、24、25 前一镜升出去）----
  // 逐帧比过画面：换镜后 0.2–0.4 秒画面变得最多，转场声对准换镜后 0.3 秒；
  // 第二段例外，第一段的公式和款数要到 B.clear 才收起，对准它后 0.25 秒
  add(B.clear + 0.25, "transition");
  for (const t of [B3.s10, B3.s11, B4.s13, B5.s17, B5.s18, B6.s23, B6.s24, B6.s25, B7.s26]) add(t + 0.3, "transition");

  // ---- 第二段：三种方法比估对比例（镜 7–9）----
  add(B2.slots, "pop");                     // 三个方法名升起
  for (let m = 0; m < 3; m++) {
    add(B2.head[m], "pop");                 // 右栏换公式
    add(B2.line[m], "whoosh");              // 画出这种方法的 k 线
    add(B2.sweep[m], "counter", landed(m) - B2.sweep[m]);  // 柱顶估对比例滚上去
    if (m === 2) big(landed(m)); else add(landed(m), "thud");  // 落定；树模型那次整幅震一下
  }

  // ---- 第三段：树模型和样本表（镜 10–12）----
  add(B3.tree, "pop");                      // 第一棵树画出来
  add(B3.many, "whoosh");                   // 大树缩进小树格
  big(B3.gridEnd);                          // 400 棵长满，整幅震一下
  // 五个来源框差不多同时弹出、各自滚数：只给第一个和第二个配滚动，免得几条滚动声叠成一团
  const srcTimes = SOURCES3.map((src) => sourceAt3(src) + 0.1).sort((a, b) => a - b);
  roll(srcTimes[0], 0.7);
  roll(srcTimes[1], 1.2);
  add(B3.table, "thud");                    // 标出 9623 行 × 211 列
  add(B3.off, "thud");                      // 估错的款数弹出

  // ---- 第四段：打乱看哪组特征重要（镜 13–16）----
  add(B4.swap, "whoosh");                   // 年龄一列互换
  add(CYC4[0].roll, "counter", CYC4[0].rd); // 年龄打乱后的成绩滚出来
  big(CYC4[0].drop);                        // 年龄的成绩落进第 1 行（“影响最大”），整幅震一下
  add(B4.month, "thud");                    // 落下“11 月上线”竖线
  add(B4.before, "pop");                    // 此前的柱子变朱红
  add(B4.older, "pop");                     // 头尾两年的 k 弹出
  for (let i = 1; i < CYC4.length; i++) add(CYC4[i].drop, "pop");  // 其余 7 组成绩依次落进表里，每行一声
  add(B4.up, "whoosh");                     // 两栏线段长出来
  for (const t of [B4.age, B4.buy, B4.price16]) add(t, "pop");  // 前三行变朱红

  // ---- 第五段：第二路信号和融合（镜 17–22）----
  add(B5.second5, "pop");                   // 升起信号 B
  add(B5.rarely5, "thud");                  // 两行公式一起顶一下
  add(B5.lineA5, "whoosh");                 // 画出信号 A
  add(B5.lineB5, "whoosh");                 // 画出信号 B
  add(B5.corr5, "thud");                    // 相关系数 0.15
  add(B5.mean5, "whoosh");                  // 画出简单平均
  add(B5.small5, "pop");                    // 两组柱子
  big(B5.ten5 + 0.3);                       // +10.4 个百分点落地，整幅震一下
  add(B5.four5, "thud");                    // +4.0 个百分点

  // ---- 第六段：近年游戏、区间和单款查询（镜 23–25）----
  add(B6.recent6, "pop");                   // 近年 116 款
  add(B6.drop6, "pop");                     // 原样 33.6%（灰柱）
  add(B6.older6, "whoosh");                 // 两条折线：只给第一条
  add(B6.ageFix6, "pop");                   // 校准后 37.9%（灰柱）
  big(B6.fused6 + 0.4);                     // 融合 38.8%（红柱），整幅震一下
  add(B6.eighty6, "whoosh");                // 括出中间八成
  add(B6.interval6 + 0.2, "pop");           // 右边升起“80% 区间”
  add(B6.differ6, "whoosh");                // 对比尺
  add(B6.low6, "thud");                     // “低”
  for (const t of [B6.crawl6, B6.clean6, B6.merge6, B6.merge6 + 0.5]) add(t, "tick");  // 流程一步步变朱红
  add(B6.minute6, "pop");                   // 约 1 分钟
  add(B6.units6 + 0.2, "thud");             // 约 1121 万份
  add(B6.label6, "pop");                    // 置信标签“低”

  // ---- 第七段：总览（镜 26–28）----
  for (const c of COLS7) add(c.at, c.last ? "thud" : "pop");  // 13 列依次长出：每块最后的融合（红）用 thud
  add(blockAt7(1), "whoosh");               // 镜头平移到中块
  add(blockAt7(2), "whoosh");               // 再平移到右块
  add(B7.treeEnd7, "pop");                  // 收尾：树模型、第二路融合、年龄校准依次顶一下
  add(B7.secondEnd7, "pop");
  add(B7.ageEnd7, "pop");

  return cues;
}
