(function () {
  "use strict";
  if (typeof Plotly === "undefined") { console.warn("[zoom] Plotly не найден"); return; }

  // Любая граница оси (число-мс ИЛИ ISO-строка) -> конечное число мс. Без NaN.
  function toMs(v) {
    if (v == null) return NaN;
    if (typeof v === "number") return isFinite(v) ? v : NaN;
    var n = Number(v);
    if (isFinite(n) && String(v).trim() !== "") return n;
    var t = Date.parse(v);
    return isFinite(t) ? t : NaN;
  }
  function pairMs(r) {
    if (!r || r.length < 2) return null;
    var a = toMs(r[0]), b = toMs(r[1]);
    if (!isFinite(a) || !isFinite(b) || b <= a) return null;
    return [a, b];
  }
  // Полный диапазон из самих данных трейсов (надёжнее внутренних полей Plotly).
  function homeOf(gd) {
    if (gd.__zoomHome) return gd.__zoomHome;
    var mn = Infinity, mx = -Infinity, tr = gd.data || [], i, j, x, t;
    for (i = 0; i < tr.length; i++) {
      x = tr[i].x; if (!x) continue;
      for (j = 0; j < x.length; j++) { t = toMs(x[j]); if (t < mn) mn = t; if (t > mx) mx = t; }
    }
    if (!isFinite(mn) || !isFinite(mx) || mx <= mn) return null;
    gd.__zoomHome = [mn, mx];
    return gd.__zoomHome;
  }
  function curOf(gd, home) {
    var r = null;
    if (gd.layout && gd.layout.xaxis) r = pairMs(gd.layout.xaxis.range);
    return r || (home ? home.slice() : null);
  }

  function attach(gd) {
    if (!gd || gd.__zoomAttached) return;
    gd.__zoomAttached = true;
    var pending = 0, raf = 0, mx = 0;

    function apply() {
      raf = 0;
      if (!pending) return;
      var home = homeOf(gd);
      if (!home) { pending = 0; return; }
      var cur = curOf(gd, home);
      if (!cur) { pending = 0; return; }
      var lo = cur[0], hi = cur[1], span = hi - lo, hspan = home[1] - home[0];
      var f = Math.exp(pending * 0.002); pending = 0;          // пачка wheel -> 1 коэффициент
      var ns = Math.min(Math.max(span * f, hspan / 50), hspan); // потолок зума ~50x
      var rect = gd.getBoundingClientRect();
      var frac = rect.width > 0 ? (mx - rect.left) / rect.width : 0.5;
      frac = Math.min(1, Math.max(0, frac));                    // якорь под курсором
      var anchor = lo + frac * span;
      var nlo = anchor - frac * ns, nhi = anchor + (1 - frac) * ns;
      if (nlo < home[0]) { nhi += home[0] - nlo; nlo = home[0]; }
      if (nhi > home[1]) { nlo -= nhi - home[1]; nhi = home[1]; }
      Plotly.relayout(gd, { "xaxis.range": [Math.max(nlo, home[0]), Math.min(nhi, home[1])] });
    }

    gd.addEventListener("wheel", function (e) {
      e.preventDefault();              // лента/страница под курсором не скроллятся
      mx = e.clientX;
      pending += e.deltaY;             // накапливаем, рисуем максимум 1 раз за кадр
      if (!raf) raf = requestAnimationFrame(apply);
    }, { passive: false });

    gd.addEventListener("dblclick", function (e) {
      var home = homeOf(gd);
      if (home) { e.preventDefault(); Plotly.relayout(gd, { "xaxis.range": [home[0], home[1]] }); }
    });
  }

  // Единственный владелец зума — наш обработчик: нативный выключаем принудительно,
  // каким бы ни был конфиг с сервера или из index.html.
  function forceConfig(cfg) {
    var out = {}, k;
    if (cfg && typeof cfg === "object") for (k in cfg) out[k] = cfg[k];
    out.responsive = true;
    out.displayModeBar = false;
    out.scrollZoom = false;
    out.doubleClick = false;
    return out;
  }

  ["react", "newPlot"].forEach(function (name) {
    var orig = Plotly[name];
    if (typeof orig !== "function" || orig.__zoomPatched) return;
    function wrapped(gd, data, layout, config) {
      if (gd && gd.__zoomHome) gd.__zoomHome = null;   // данные могли измениться
      var p = orig.call(Plotly, gd, data, layout, forceConfig(config));
      try { attach(typeof gd === "string" ? document.getElementById(gd) : gd); } catch (e) {}
      return p;
    }
    wrapped.__zoomPatched = true;
    Plotly[name] = wrapped;
  });

  // Страховка: если какой-то график отрисован до патча — починить и его.
  function fixExisting() {
    var nodes = document.querySelectorAll(".js-plotly-plot");
    for (var i = 0; i < nodes.length; i++) {
      var gd = nodes[i];
      if (!gd || !gd.data || !gd.layout) continue;
      var cfg = (gd._context && gd._context.config) ? gd._context.config : {};
      if (cfg.scrollZoom !== false || !gd.__zoomAttached) {
        Plotly.react(gd, gd.data, gd.layout, cfg);   // пройдёт через патч и прикрепит зум
      }
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { setTimeout(fixExisting, 0); });
  } else {
    setTimeout(fixExisting, 0);
  }

  console.info("[zoom] колесо = зум, двойной клик = сброс");
})();