/**
 * WPS 演示 — 从 brief 对象生成幻灯片（PoC 骨架）
 * 在 wpsjs debug 环境下于 WPS 演示中执行；完整实现需按 wps-jsapi 补全形状/图表 API。
 *
 * @param {object} brief - 与 deck_brief.yaml 同结构
 * @returns {number} 幻灯片页数
 */
function buildFromBrief(brief) {
  if (typeof wps === "undefined" || !wps.WppApplication) {
    throw new Error("请在 WPS 演示加载项环境中运行");
  }
  var app = wps.WppApplication();
  var pres = app.Presentations.Add();

  var slides = brief.slides || [];
  for (var i = 0; i < slides.length; i++) {
    var spec = slides[i];
    var stype = (spec.type || "content").toLowerCase();
    var layout = 1; // ppLayoutText
    if (stype === "title" || stype === "closing") layout = 1;
    else if (stype === "section") layout = 2;
    var slide = pres.Slides.Add(pres.Slides.Count + 1, layout);
    if (slide.Shapes.HasTitle) {
      slide.Shapes.Title.TextFrame.TextRange.Text = spec.title || "";
    }
    if (stype === "content" && spec.bullets && spec.bullets.length) {
      var body = slide.Shapes.Placeholders(2);
      if (body) {
        var text = spec.bullets.join("\r");
        body.TextFrame.TextRange.Text = text;
      }
    }
    if ((stype === "title" || stype === "closing") && spec.subtitle) {
      try {
        slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = spec.subtitle;
      } catch (e) { /* layout 差异 */ }
    }
  }
  return pres.Slides.Count;
}

/**
 * @param {string} path - 绝对路径 .pptx
 */
function savePresentation(path) {
  var app = wps.WppApplication();
  var pres = app.ActivePresentation;
  if (!pres) throw new Error("无活动演示文稿");
  pres.SaveAs(path);
}

// wpsjs RPC 注册（debug 模式下由本地 HTTP 转发）
if (typeof window !== "undefined") {
  window.myteamWpsDeck = { buildFromBrief: buildFromBrief, savePresentation: savePresentation };
}
