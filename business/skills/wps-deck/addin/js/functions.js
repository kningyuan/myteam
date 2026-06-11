/**
 * myteam WPS 演示加载项 — 供 WpsInvoke.InvokeAsHttp 调用的全局函数
 * 文档: https://open.wps.cn/documents/app-integration-dev/wps365/client/wpsoffice/
 */

function GetImage(control) {
  return "images/1.svg";
}

/**
 * 打开 pptx，套用设计主题（若可用），保存。
 * @param {object|string} param { inputPath, outputPath, themeIndex? }
 */
function beautifyDeck(param) {
  var p = param;
  if (typeof param === "string") {
    try { p = JSON.parse(param); } catch (e) { p = {}; }
  }
  if (p && p.param) p = p.param;

  var inputPath = p.inputPath || p.input;
  var outputPath = p.outputPath || p.output || inputPath;
  if (!inputPath) {
    return JSON.stringify({ ok: false, error: "missing inputPath" });
  }

  var app = wps.WppApplication();
  var pres = null;
  try {
    pres = app.Presentations.Open(inputPath, false, false, false);
  } catch (e) {
    return JSON.stringify({ ok: false, error: "Open failed: " + e.message });
  }

  try {
    var themeIndex = p.themeIndex != null ? p.themeIndex : 1;
    if (pres.Designs && pres.Designs.Count >= themeIndex) {
      try {
        pres.ApplyTemplate(pres.Designs.Item(themeIndex).Name);
      } catch (e1) {
        try { pres.ApplyTheme(pres.Designs.Item(themeIndex).Name); } catch (e2) { /* API 差异 */ }
      }
    }
    for (var i = 1; i <= pres.Slides.Count; i++) {
      var slide = pres.Slides.Item(i);
      try {
        if (slide.Shapes.HasTitle && slide.Shapes.Title) {
          slide.Shapes.Title.TextFrame.TextRange.Font.Name = "微软雅黑";
        }
      } catch (e3) { /* ignore */ }
    }
    pres.SaveAs(outputPath);
    var n = pres.Slides.Count;
    pres.Close();
    return JSON.stringify({ ok: true, slides: n, outputPath: outputPath, via: "wps-jsapi" });
  } catch (e) {
    try { pres.Close(); } catch (e4) { /* ignore */ }
    return JSON.stringify({ ok: false, error: e.message });
  }
}

/**
 * 从 brief 新建演示（WPS 原生排版）
 */
function buildFromBrief(param) {
  var p = typeof param === "string" ? JSON.parse(param) : param;
  if (p && p.param) p = p.param;
  var brief = p.brief || p;
  var outputPath = p.outputPath;
  if (!outputPath) {
    return JSON.stringify({ ok: false, error: "missing outputPath" });
  }

  var app = wps.WppApplication();
  var pres = app.Presentations.Add();
  var slides = brief.slides || [];

  for (var i = 0; i < slides.length; i++) {
    var spec = slides[i];
    var stype = (spec.type || "content").toLowerCase();
    var layout = 2;
    if (stype === "title" || stype === "closing") layout = 1;
    else if (stype === "section") layout = 3;
    var slide = pres.Slides.Add(pres.Slides.Count + 1, layout);
    if (slide.Shapes.HasTitle) {
      slide.Shapes.Title.TextFrame.TextRange.Text = spec.title || "";
    }
    if (stype === "content" && spec.bullets && spec.bullets.length) {
      try {
        slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = spec.bullets.join("\r");
      } catch (e) { /* layout */ }
    }
    if ((stype === "title" || stype === "closing") && spec.subtitle) {
      try {
        slide.Shapes.Placeholders(2).TextFrame.TextRange.Text = spec.subtitle;
      } catch (e) { /* layout */ }
    }
  }
  pres.SaveAs(outputPath);
  var n = pres.Slides.Count;
  pres.Close();
  return JSON.stringify({ ok: true, slides: n, outputPath: outputPath, via: "wps-jsapi" });
}
