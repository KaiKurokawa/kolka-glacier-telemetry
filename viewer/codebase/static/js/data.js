(function () {
  "use strict";

  // =====================================================================
  // Константы
  // =====================================================================
  const REFRESH_MS   = 10 * 60 * 1000;
  const WEEK_DAYS    = 7;
  const WEEK_LIMIT   = 1000;     // свёрнутое окно: неделя, явный лимит
  const YEAR_DAYS    = 365;
  const YEAR_LIMIT   = 99999;    // развёрнутое окно: год, явный большой лимит
  const YEAR_TTL_MS  = 10 * 60 * 1000;
  const TRAFFIC_STUB_VALUE = 1;
  const WIDE_START   = "2000-01-01";
  const WIDE_END     = "2099-12-31";
  const PLOT_KEYS = ["temperature","humidity","pressure","wind",
                     "wind_direction","precipitation","snow","battery"];

  const PLOT_META = {
    temperature:    { field:"air_temperature_average_at_2m", unit:"°C", dec:1, label:"Температура, °C",
      columns:[["air_temperature_average_at_2m","Средняя, °C",1],
               ["air_temperature_minimum_at_2m","Минимум, °C",1],
               ["air_temperature_maximum_at_2m","Максимум, °C",1]] },
    humidity:       { field:"relative_humidity_average_at_2m", unit:"%", dec:0, label:"Влажность, %",
      columns:[["relative_humidity_average_at_2m","Средняя, %",0]] },
    pressure:       { field:"atmospheric_pressure_average_at_station", unit:"гПа", dec:1, label:"Давление, гПа",
      columns:[["atmospheric_pressure_average_at_station","На станции, гПа",1],
               ["atmospheric_pressure_average_at_mean_sea_level","К ур. моря, гПа",1]] },
    wind:           { field:"wind_speed_average_at_10m", unit:"м/с", dec:1, label:"Ветер, м/с",
      columns:[["wind_speed_average_at_10m","Средняя, м/с",1],
               ["wind_speed_maximum_at_10m","Максимум, м/с",1],
               ["wind_direction_average_at_10m","Направление, °",0]] },
    wind_direction: { field:"wind_direction_average_at_10m", unit:"°", dec:0, label:"Направление, °",
      columns:[["wind_direction_average_at_10m","Направление, °",0],
               ["wind_speed_average_at_10m","Скорость, м/с",1]] },
    precipitation:  { field:"precipitation_sum", unit:"мм", dec:1, label:"Осадки, мм", isBar:true,
      columns:[["precipitation_sum","Сумма, мм",1],
               ["precipitation_accumulated","Накопл., мм",1],
               ["precipitation_intensity_average_at_2m","Интенс., мм/ч",2]] },
    snow:           { field:"snow_depth_average", unit:"см", dec:1, label:"Снег, см",
      columns:[["snow_depth_instantaneous","Мгновенная, см",1],
               ["snow_depth_average","Средняя, см",1],
               ["snow_depth_minimum","Минимум, см",1],
               ["snow_depth_maximum","Максимум, см",1]] },
    battery:        { field:"battery_instantaneous_voltage", unit:"V", dec:1, label:"Батарея, V",
      columns:[["battery_instantaneous_voltage","Напряжение, V",1]] },
  };

  const TRAFFIC_COLORS = { 1:"#16a34a", 2:"#65a30d", 3:"#ca8a04", 4:"#ea580c", 5:"#dc2626" };
  const TRAFFIC_LABELS = { 1:"Норма", 2:"Внимание", 3:"Предупреждение", 4:"Тревога", 5:"Опасность" };
  const ALERT_MESSAGES = { 4: "Предупреждение", 5: "Опасность" };

  // =====================================================================
  // Утилиты
  // =====================================================================
  const $ = (id) => document.getElementById(id);
  const esc = (v) => String(v == null ? "" : v)
      .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
  const fmt = (v, d) => (v == null ? "—" : Number(v).toFixed(d == null ? 1 : d));
  const fmtTime = (iso) => {
    const d = new Date(iso);
    return isNaN(d) ? String(iso || "") : d.toLocaleString("ru-RU");
  };
  function toMs(v) {
    if (v == null) return NaN;
    if (typeof v === "number") return isFinite(v) ? v : NaN;
    const n = Number(v);
    if (isFinite(n) && String(v).trim() !== "") return n;
    let s = String(v).trim();
    if (s.indexOf(" ") === 10 && s.indexOf("T") === -1) s = s.replace(" ", "T");
    if (/^\d{4}-\d{2}-\d{2}$/.test(s)) s = s + "T00:00:00";
    let t = Date.parse(s);
    if (!isFinite(t)) t = Date.parse(v);
    return isFinite(t) ? t : NaN;
  }
  function localIsoDay(d) {
    return d.getFullYear() + "-" + String(d.getMonth()+1).padStart(2,"0") + "-" +
           String(d.getDate()).padStart(2,"0");
  }
  function dayShift(isoDay, delta) {
    const p = isoDay.split("-");
    return localIsoDay(new Date(+p[0], +p[1]-1, +p[2] + delta));
  }

  // =====================================================================
  // Состояние
  // =====================================================================
  let weekData  = [];
  let weekPlots = {};
  let yearCache = null;
  let loadingYear = false;
  let modalKey = null;
  let connected = false;

  // =====================================================================
  // Сеть
  // =====================================================================
  // БЛОК: единый источник и для недели, и для модалки. limit передаётся ЯВНО:
  // неделя -> WEEK_LIMIT (1000), модалка -> YEAR_LIMIT (99999).
  function fetchBlock(endDay, days, limit) {
    const q = new URLSearchParams();
    q.set("end_date", endDay);
    q.set("days", String(days));
    q.set("limit", String(limit));
    q.set("three_hour_intervals", "false");
    return fetch("/api/telemetry/block?" + q.toString(), { headers: { "Accept": "application/json" } })
      .then((res) => { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); })
      .then((payload) => {
        console.info("[data] block days=" + days + " limit=" + limit + " -> записей: " +
                     ((payload && payload.data) ? payload.data.length : 0));
        return payload;
      });
  }

  // ЗОНД последней даты. limit=1 — намеренно: источник сортирует по убыванию,
  // одна запись = самая свежая. ЭТОТ ЗАПРОС НЕ РИСУЕТ МОДАЛКУ (модалка ходит
  // в fetchBlock). Зонд нужен только при старте недели / авто-опросе.
  function fetchLatestProbe() {
    const q = new URLSearchParams();
    q.set("start_date", WIDE_START);
    q.set("end_date", WIDE_END);
    q.set("three_hour_intervals", "false");
    q.set("limit", "1");
    q.set("offset", "0");
    return fetch("/api/telemetry?" + q.toString(), { headers: { "Accept": "application/json" } })
      .then((res) => { if (!res.ok) throw new Error("HTTP " + res.status); return res.json(); });
  }

  function latestDayOf(rows) {
    let ms = -Infinity;
    (rows || []).forEach((r) => { const t = toMs(r.observation_timestamp); if (t > ms) ms = t; });
    return isFinite(ms) ? localIsoDay(new Date(ms)) : null;
  }
  function latestDayFromWeek() {
    if (!weekData.length) return null;
    return localIsoDay(new Date(toMs(weekData[weekData.length - 1].observation_timestamp)));
  }

  // =====================================================================
  // Заглушки по блокам
  // =====================================================================
  function setFrameEmpty(key, empty) {
    const fr = $("frame_" + key);
    if (fr) fr.classList.toggle("empty", empty);
  }
  function setBadge(off, text) {
    const badge = $("status-badge");
    const label = $("updated-badge");
    if (badge) badge.classList.toggle("off", off);
    if (label) label.textContent = text;
  }

  function setTrafficLight(value) {
    const banner = $("alert-banner"), alertText = $("alert-text"), alertLevel = $("alert-level");
    const lights = document.querySelectorAll("#traffic-light .t-light");

    lights.forEach((el) => {
      el.classList.remove("on");
      el.style.background = ""; el.style.boxShadow = ""; el.style.borderColor = "";
    });

    if (value == null) {
      if (banner) banner.classList.remove("visible","level-4","level-5");
      return;
    }

    const v = Math.max(1, Math.min(5, Math.round(Number(value) || 0)));

    lights.forEach((el) => {
      const lvl = Number(el.getAttribute("data-level"));
      if (lvl <= v) {
        el.classList.add("on");
        el.style.background = TRAFFIC_COLORS[lvl];
        el.style.boxShadow = "0 0 18px " + TRAFFIC_COLORS[lvl] + "66";
        el.style.borderColor = TRAFFIC_COLORS[lvl];
      }
    });

    if (banner) {
      banner.classList.remove("visible","level-4","level-5");
      if (v >= 4 && ALERT_MESSAGES[v]) {
        if (alertText) alertText.textContent = ALERT_MESSAGES[v];
        if (alertLevel) alertLevel.textContent = TRAFFIC_LABELS[v];
        banner.classList.add("visible", "level-" + v);
      }
    }
  }


    function loadPhotos() {
    // До ответа сервера и до загрузки картинок — во всех рамках «Нет данных»
    document.querySelectorAll(".photo-frame[data-slot]").forEach((fr) => {
      fr.innerHTML = "<span>Нет данных</span>";
      fr.style.cursor = "default";
      fr.onclick = null;
    });

    fetch("/api/v1/photos/latest_per_camera", { headers: { "Accept": "application/json" } })
      .then((r) => {
        if (!r.ok) { console.warn("[photos] HTTP " + r.status); return []; }
        return r.json().catch(() => []);
      })
      .then((items) => {
        const arr = Array.isArray(items) ? items : [];
        const byCamera = new Map();
        arr.forEach((it, idx) => {
          const slot = Number(it && it.camera_id) || (idx + 1);
          byCamera.set(slot, it);
        });
        document.querySelectorAll(".photo-frame[data-slot]").forEach((fr) => {
          const slot = Number(fr.getAttribute("data-slot"));
          const it = byCamera.get(slot);
          if (!it || !it.url) {
            fr.innerHTML = "<span>Нет данных</span>";
            fr.style.cursor = "default";
            fr.onclick = null;
            return;
          }
          // caption НЕ используем нигде в отображении (в нём служебный текст сервера).
          const label = it.observation_date ? ("Камера " + slot + " · " + it.observation_date)
                                            : ("Камера " + slot);
          // img создаётся скрытым: пока не загрузился — в рамке остаётся span «Нет данных».
          const img = new Image();
          img.alt = "";                       // пустой alt = браузер не рисует текст
          img.style.cssText = "width:100%;height:100%;object-fit:cover;border-radius:12px;display:none";
          img.onload = () => {
            fr.innerHTML = "";
            img.style.display = "block";
            fr.appendChild(img);
            fr.style.cursor = "pointer";
            fr.onclick = () => openPhotoModal(it.url, label, slot);
          };
          img.onerror = () => {
            fr.innerHTML = "<span>Нет данных</span>";
            fr.style.cursor = "default";
            fr.onclick = null;
          };
          img.src = it.url;
        });
      })
      .catch((e) => {
        console.warn("[photos] exception:", e);
        document.querySelectorAll(".photo-frame[data-slot]").forEach((fr) => {
          if (!fr.querySelector("img")) {
            fr.innerHTML = "<span>Нет данных</span>";
            fr.style.cursor = "default";
            fr.onclick = null;
          }
        });
      });
  }

    // Открывает ту же модалку, что и графики, но с увеличенным фото

    // Увеличенное фото в той же модалке, что и графики.
  function openPhotoModal(src, label, slot) {
    const mdl = $("chart-modal");
    const mp  = $("modal-plot");
    const wt  = $("modal-table");
    const mt  = $("modal-title");
    if (!mdl || !mp) return;

    modalKey = "__photo__" + slot;
    if (mt) mt.textContent = label || ("Камера " + slot);
    mp.innerHTML = '<img src="' + esc(src) + '" alt="" ' +
                   'style="width:100%;max-height:75vh;object-fit:contain;' +
                   'border-radius:8px;display:block;margin:0 auto">';
    if (wt) wt.innerHTML = "";
    setModalFrameEmpty(false);

    mdl.classList.add("open");
    mdl.setAttribute("aria-hidden", "false");
  }

  function loadIndicator() {
    fetch("/api/v1/indicator/", { headers: { "Accept": "application/json" } })
      .then((r) => {
        if (!r.ok) { console.warn("[indicator] HTTP " + r.status); return null; }
        return r.json().catch(() => { console.warn("[indicator] тело ответа не JSON"); return null; });
      })
      .then((p) => {
        // Допускаем и плоский {level}, и обёртку {data:{level}} на случай расхождения.
        const obj = (p && p.level != null) ? p
                  : (p && p.data && p.data.level != null ? p.data : null);
        if (!obj) console.warn("[indicator] в ответе нет поля level:", p);
        setTrafficLight(obj && obj.level != null ? obj.level : null);
      })
      .catch((e) => { console.warn("[indicator] exception:", e); setTrafficLight(null); });
  }

  function renderPlaceholders() {
    connected = false;
    setBadge(true, "Нет подключения");
    renderKPI(null);
    PLOT_KEYS.forEach((key) => {
      setFrameEmpty(key, true);
      const el = $("plot_" + key);
      if (el && typeof Plotly !== "undefined") { try { Plotly.purge(el); } catch (e) {} }
    });
  }

  // =====================================================================
  // Рендер шапки, KPI, мини-графиков (неделя)
  // =====================================================================
  function renderHead() {
    const t = $("station-title");
    const latest = weekData.length ? weekData[weekData.length - 1] : null;
    setBadge(false, "Последние данные: " + (latest ? fmtTime(latest.observation_timestamp) : "—"));
  }
  function kpiCard(cls, ic, title, value, unit, sub) {
    return '<div class="kpi">' +
        '<div class="top"><span class="icon ' + cls + '">' + ic + '</span>' + esc(title) + '</div>' +
        '<div class="value">' + esc(value) + (unit ? '<small>' + esc(unit) + '</small>' : '') + '</div>' +
        '<div class="sub" title="' + esc(sub) + '">' + esc(sub) + '</div></div>';
  }
  function renderKPI(l) {
    const g = $("kpi-grid");
    if (!g) return;
    if (!l) {
      const stub = (cls, ic, title, unit) => kpiCard(cls, ic, title, "—", unit, "нет данных");
      g.innerHTML = [
        stub("blue","°C","Темп.","°C"),
        stub("yellow","м/с","Ветер","м/с"),
        stub("violet","гПа","Давл.","гПа"),
        stub("orange","%","Влажн.","%"),
        stub("green","мм","Осадки","мм"),
        stub("cyan","см","Снег","см"),
        stub("red","В","Батарея","В"),
      ].join("");
      return;
    }
    g.innerHTML = [
      kpiCard("blue","°C","Темп.", fmt(l.air_temperature_average_at_2m), "°C",
          "мин " + fmt(l.air_temperature_minimum_at_2m) + " / макс " + fmt(l.air_temperature_maximum_at_2m)),
      kpiCard("yellow","м/с","Ветер", fmt(l.wind_speed_average_at_10m), "м/с",
          "порывы " + fmt(l.wind_speed_maximum_at_10m) + " · " + fmt(l.wind_direction_average_at_10m,0) + "°"),
      kpiCard("violet","гПа","Давл.", fmt(l.atmospheric_pressure_average_at_station), "гПа",
          "м.м. " + fmt(l.atmospheric_pressure_average_at_mean_sea_level)),
      kpiCard("orange","%","Влажн.", fmt(l.relative_humidity_average_at_2m,0), "%", "на выс. 2 м"),
      kpiCard("green","мм","Осадки", fmt(l.precipitation_sum), "мм",
          "накопл. " + fmt(l.precipitation_accumulated)),
      kpiCard("cyan","см","Снег", fmt(l.snow_depth_average), "см",
          "мин " + fmt(l.snow_depth_minimum) + " / макс " + fmt(l.snow_depth_maximum)),
      kpiCard("red","V","Батарея", fmt(l.battery_instantaneous_voltage), "V", "мгновенно"),
    ].join("");
  }
  function renderMini(keepView) {
    if (typeof Plotly === "undefined") return;
    PLOT_KEYS.forEach((key) => {
      const el = $("plot_" + key);
      const fig = weekPlots[key];
      if (!el) return;
      if (!fig || !fig.data) { setFrameEmpty(key, true); return; }
      setFrameEmpty(key, false);
      const cur = (keepView && el.layout && el.layout.xaxis && el.layout.xaxis.range)
          ? el.layout.xaxis.range.slice() : null;
      const lay = Object.assign({}, fig.layout, {
        height: el.clientHeight || 240,
        hovermode: false,
        uirevision: key,
      });
      if (cur) lay.xaxis = Object.assign({}, fig.layout.xaxis || {}, { range: cur, autorange: false });
      Plotly.react(el, fig.data, lay);
    });
  }
  function renderWeek() {
    const has = weekData.length > 0;
    connected = has;
    if (has) {
      renderHead();
      renderKPI(weekData[weekData.length - 1]);
      renderMini(false);
    } else {
      renderPlaceholders();
    }
  }

  // =====================================================================
  // Модалка: годовой график + годовая таблица (YEAR_LIMIT записей)
  // =====================================================================
  function buildModalTable(key) {
    const wrap = $("modal-table");
    if (!wrap) return;
    const meta = PLOT_META[key];
    if (!yearCache || !yearCache.data.length || !meta) {
      wrap.innerHTML = '<div class="loading">Нет данных</div>';
      return;
    }
    const rows = yearCache.data.slice().reverse();
    let head = "<tr><th>Время</th>" +
        meta.columns.map((c) => "<th>" + esc(c[1]) + "</th>").join("") + "</tr>";
    let body = "";
    for (const r of rows) {
      body += "<tr><td>" + esc(fmtTime(r.observation_timestamp)) + "</td>" +
          meta.columns.map((c) => "<td>" + esc(fmt(r[c[0]], c[2])) + "</td>").join("") + "</tr>";
    }
    wrap.innerHTML = "<table><thead>" + head + "</thead><tbody>" + body + "</tbody></table>";
  }
  function setModalFrameEmpty(empty) {
    const fr = $("modal-frame");
    if (fr) fr.classList.toggle("empty", empty);
  }
  function renderModalChart(key) {
    const mp = $("modal-plot");
    if (!mp || !yearCache) { setModalFrameEmpty(true); buildModalTable(key); return; }
    const fig = yearCache.plots[key];
    if (!fig || !fig.data) { setModalFrameEmpty(true); buildModalTable(key); return; }
    setModalFrameEmpty(false);
    const meta = PLOT_META[key] || {};
    const bigLayout = Object.assign({}, fig.layout, {
      height: Math.max(520, Math.round(window.innerHeight * 0.62)),
      margin: { l: 60, r: 28, t: 28, b: 48 },
      font: Object.assign({}, fig.layout.font, { size: 14 }),
      hovermode: fig.layout.polar ? "closest" : "x unified",
      uirevision: "modal-" + key,
    });
    Plotly.react(mp, fig.data, bigLayout);
    if (!meta.isBar && !fig.layout.polar) {
      try { Plotly.restyle(mp, { "line.shape": "spline" }, [0]); } catch (e) {}
    }
    Plotly.Plots.resize(mp);
    buildModalTable(key);
  }
  function openModal(key) {
    const mdl = $("chart-modal");
    if (!mdl || typeof Plotly === "undefined") return;
    modalKey = key;
    const mt = $("modal-title");
    if (mt) mt.textContent = (PLOT_META[key] || {}).label || key;
    mdl.classList.add("open");
    mdl.setAttribute("aria-hidden", "false");

    const fresh = yearCache && (Date.now() - yearCache.at) < YEAR_TTL_MS;
    if (fresh) { renderModalChart(key); return; }

    const wt = $("modal-table");
    if (wt) wt.innerHTML = '<div class="loading">Загрузка данных за год…</div>';
    setModalFrameEmpty(true);
    ensureYear().then(() => {
      if (modalKey === key) renderModalChart(key);
    }).catch((err) => {
      console.error("[data] Ошибка открытия модалки:", err);
      setModalFrameEmpty(true);
      if (wt) wt.innerHTML = '<div class="loading">Ошибка загрузки</div>';
    });
  }

  // Модалка НЕ делает зонд: latestDay берётся из уже загруженной недели.
  // В Network при клике по графику будет ОДИН запрос block?days=365&limit=99999.
  function ensureYear() {
    if (loadingYear) return Promise.resolve();
    loadingYear = true;

    const latestDay = latestDayFromWeek();
    const chain = latestDay
      ? Promise.resolve(latestDay)
      : fetchLatestProbe().then((probe) => {
          const d = latestDayOf(probe.data);
          if (!d) throw new Error("нет данных на сервере");
          return d;
        });

    return chain
      .then((day) => fetchBlock(day, YEAR_DAYS, YEAR_LIMIT))
      .then((payload) => {
        loadingYear = false;
        if (payload.error) throw new Error(payload.error);
        const rows = (payload.data || []).slice();
        rows.sort((a, b) => (a.observation_timestamp < b.observation_timestamp ? -1 : 1));
        yearCache = { at: Date.now(), data: rows, plots: payload.plots || {} };
        console.info("[data] yearCache (год, limit=" + YEAR_LIMIT + "), записей: " + rows.length);
      })
      .catch((e) => {
        loadingYear = false;
        console.warn("[data] год не загружен:", e.message || e);
        throw e;
      });
  }

  function closeModal() {
    const mdl = $("chart-modal"); if (!mdl) return;
    mdl.classList.remove("open");
    mdl.setAttribute("aria-hidden","true");
    const mp = $("modal-plot");
    if (mp) {
      try { if (mp.data && mp.data.length) Plotly.purge(mp); } catch (e) {}
      mp.innerHTML = "";   // важно для фото: убирает <img>, чтобы не мешать графику
    }
    const wt = $("modal-table"); if (wt) wt.innerHTML = "";
    setModalFrameEmpty(false);
    modalKey = null;
  }

  // =====================================================================
  // Привязки кликов
  // =====================================================================
  function bindExpandByClick(el, key) {
    if (!el || el._expandBound) return;
    el._expandBound = true;
    let sx = 0, sy = 0, st = 0, moved = false;
    el.addEventListener("pointerdown", (e) => { sx=e.clientX; sy=e.clientY; st=Date.now(); moved=false; });
    el.addEventListener("pointermove", (e) => {
      if (!st) return;
      if (Math.abs(e.clientX-sx) > 6 || Math.abs(e.clientY-sy) > 6) moved = true;
    });
    el.addEventListener("pointerup", () => {
      if (!st) return;
      const dt = Date.now() - st; st = 0;
      if (!moved && dt < 400) openModal(key);
    });
    el.addEventListener("pointercancel", () => { st = 0; });
  }
  function bindModalControls() {
    PLOT_KEYS.forEach((key) => bindExpandByClick($("plot_" + key), key));
    document.querySelectorAll("[data-expand]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        openModal(btn.getAttribute("data-expand"));
      });
    });
    const mdl = $("chart-modal");
    if (mdl) mdl.addEventListener("click", (e) => {
      if (e.target.hasAttribute("data-close")) closeModal();
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && mdl && mdl.classList.contains("open")) closeModal();
    });
    window.addEventListener("resize", () => {
      if (mdl && mdl.classList.contains("open")) {
        try { Plotly.Plots.resize($("modal-plot")); } catch (e) {}
      }
    });
  }

  // =====================================================================
  // Неделя: старт и авто-опрос (WEEK_LIMIT записей)
  // =====================================================================
  function loadWeek(keepView) {
    return fetchLatestProbe()
      .then((probe) => {
        const latestDay = latestDayOf(probe.data);
        if (!latestDay) { weekData = []; weekPlots = {}; renderWeek(); return; }
        return fetchBlock(latestDay, WEEK_DAYS, WEEK_LIMIT).then((payload) => {
          if (payload.error) throw new Error(payload.error);
          const rows = payload.data || [];
          rows.sort((a, b) => (a.observation_timestamp < b.observation_timestamp ? -1 : 1));
          weekData = rows;
          weekPlots = payload.plots || {};
          if (keepView && weekData.length) {
            connected = true;
            renderHead();
            renderKPI(weekData[weekData.length - 1]);
            renderMini(true);
          } else {
            renderWeek();
          }
        });
      })
      .catch((e) => {
        console.warn("[data] неделя не загружена:", e.message || e);
        if (!weekData.length) renderPlaceholders();
        else setBadge(true, "Нет подключения (показаны последние данные)");
      });
  }

  function init() {
    bindModalControls();
    renderPlaceholders();
    loadWeek(false);
    loadPhotos();
    loadIndicator();
    setInterval(() => { loadWeek(true); loadPhotos(); loadIndicator(); }, REFRESH_MS);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();