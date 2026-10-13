/* Prezentacja z napisami — włącza się parametrem ?demo=1, potem trwa między
 * stronami (stan w sessionStorage). Niczego nie zapisuje w aplikacji: tylko
 * nawigacja, podświetlenie i napisy. Bez ?demo=1 i bez trwającej prezentacji
 * skrypt kończy się w pierwszych liniach.
 * Scenariusz: demo_script.json. Krok trwa tyle, ile czytanie napisu
 * (stepMs); start i koniec kroku idą jako zdarzenia demo:step / demo:end
 * (tools/record_video.py liczy z nich rozdziały i napisy filmu). */
(function () {
  "use strict";

  var KEY = "miniwms-demo";
  var PAUSE_MS = 500;
  var MS_PER_CHAR = 65;   // ok. 15 znaków na sekundę — spokojne tempo czytania
  var MIN_STEP_MS = 4000;
  var TICK_MS = 100;
  var base = (document.currentScript && document.currentScript.dataset.base) || "/static/demo/";

  function load() {
    try { return JSON.parse(sessionStorage.getItem(KEY)) || null; } catch (e) { return null; }
  }
  function save() {
    try { sessionStorage.setItem(KEY, JSON.stringify(state)); } catch (e) { /* tryb prywatny */ }
  }

  var wantsDemo = new URLSearchParams(location.search).get("demo") === "1";
  var state = load();
  if (!wantsDemo && !(state && state.active)) return;

  state = state || { active: false, index: 0, playing: false, visited: {} };

  var css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = base + "demo.css";
  document.head.appendChild(css);

  var steps = [];
  var ticker = null;   // odliczanie bieżącego kroku
  var timer = null;    // pauza przed następnym krokiem
  var elapsed = 0;     // ms bieżącego kroku (zostaje przy pauzie)
  var spotEl = null;
  var ui = {};

  fetch(base + "demo_script.json", { cache: "no-cache" })
    .then(function (r) { return r.ok ? r.json() : {}; })
    .catch(function () { return {}; })
    .then(function (script) {
      steps = (script && script.steps) || [];
      if (!steps.length) return;
      buildUI();
      if (state.active) showStep(state.index);
      else showStart();
    });

  function stepMs(step) {
    return Math.max(MIN_STEP_MS, step.text.length * MS_PER_CHAR);
  }

  function emit(name, detail) {
    document.dispatchEvent(new CustomEvent(name, { detail: detail }));
  }

  // --- UI -----------------------------------------------------------------

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text) e.textContent = text;
    return e;
  }

  function button(label, title, onClick) {
    var b = el("button", "demo-btn", label);
    b.type = "button";
    b.title = title;
    b.setAttribute("aria-label", title);
    b.addEventListener("click", onClick);
    return b;
  }

  function buildUI() {
    var bar = el("div", "demo-bar");
    bar.setAttribute("role", "region");
    bar.setAttribute("aria-label", "Prezentacja");
    ui.caption = el("p", "demo-caption");
    ui.caption.setAttribute("aria-live", "polite");
    ui.progress = el("div", "demo-progress");
    ui.fill = el("div", "demo-progress-fill");
    ui.progress.appendChild(ui.fill);

    var controls = el("div", "demo-controls");
    ui.prev = button("⏮", "Poprzedni krok", function () { go(state.index - 1); });
    ui.play = button("▶", "Start / pauza", togglePlay);
    ui.next = button("⏭", "Następny krok", function () { go(state.index + 1); });
    ui.count = el("span", "demo-count");
    var close = button("✕", "Zakończ prezentację", stop);
    [ui.prev, ui.play, ui.next, ui.count].forEach(function (c) { controls.appendChild(c); });
    controls.appendChild(el("span", "demo-spacer"));
    controls.appendChild(close);

    bar.appendChild(ui.progress);
    bar.appendChild(ui.caption);
    bar.appendChild(controls);
    document.body.appendChild(bar);
    document.body.classList.add("demo-on");
    ui.bar = bar;
  }

  function showStart() {
    ui.bar.hidden = true;
    var overlay = el("div", "demo-start");
    var startBtn = el("button", "demo-start-btn", "▶ Rozpocznij prezentację");
    startBtn.type = "button";
    startBtn.addEventListener("click", function () {
      overlay.remove();
      ui.bar.hidden = false;
      state.active = true;
      state.playing = true;
      state.visited = {};
      go(0);
    });
    overlay.appendChild(startBtn);
    overlay.appendChild(el("p", "demo-start-hint", "Około trzech minut, z napisami. Możesz zatrzymać w każdej chwili."));
    document.body.appendChild(overlay);
    startBtn.focus();
  }

  function renderPlay() { ui.play.textContent = state.playing ? "⏸" : "▶"; }
  function renderProgress(fraction) {
    var pct = ((state.index + (fraction || 0)) / steps.length) * 100;
    ui.fill.style.width = Math.min(100, pct) + "%";
    ui.count.textContent = (state.index + 1) + " / " + steps.length;
    ui.prev.disabled = state.index === 0;
    ui.next.disabled = state.index >= steps.length - 1;
  }

  // --- Kroki ----------------------------------------------------------------

  function samePath(url) {
    return new URL(url, location.href).pathname === location.pathname;
  }

  function find(selector) {
    var list = Array.isArray(selector) ? selector : [selector];
    for (var i = 0; i < list.length; i++) {
      try {
        var found = list[i] && document.querySelector(list[i]);
        if (found) return found;
      } catch (e) { /* selektor nieobsługiwany w tej przeglądarce */ }
    }
    return null;
  }

  function spotlight(target) {
    if (spotEl) spotEl.classList.remove("demo-spot");
    spotEl = target;
    if (!target) return;
    target.classList.add("demo-spot");
    target.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function go(i) {
    if (i < 0 || i >= steps.length) return;
    halt();
    state.index = i;
    save();
    showStep(i);
  }

  function showStep(i) {
    var step = steps[i];
    var target = step.url || state.visited[i];
    if (target && !samePath(target)) {
      save();
      location.href = target;
      return;
    }
    state.visited[i] = location.pathname;
    save();
    elapsed = 0;
    ui.caption.textContent = step.text;
    renderProgress(0);
    spotlight(find(step.selector));
    if (location.pathname.indexOf("/login") === 0) {
      state.playing = false;
      ui.caption.textContent = "Zaloguj się — po zalogowaniu kliknij ▶, prezentacja wróci w tym miejscu.";
    }
    renderPlay();
    if (state.playing) run(step);
  }

  // --- Czas kroku -----------------------------------------------------------

  function halt() {
    clearInterval(ticker);
    clearTimeout(timer);
    ticker = timer = null;
  }

  function run(step) {
    halt();
    if (elapsed === 0) emit("demo:step", { id: step.id, index: state.index });
    var total = stepMs(step);
    ticker = setInterval(function () {
      elapsed += TICK_MS;
      renderProgress(Math.min(1, elapsed / total));
      if (elapsed >= total) finished(step);
    }, TICK_MS);
  }

  function finished(step) {
    halt();
    renderProgress(1);
    timer = setTimeout(function () {
      if (!state.playing) return;
      if (step.action === "click") {
        var link = find(step.selector);
        if (link) {
          state.index += 1;
          save();
          link.click();
          return;
        }
      }
      if (state.index >= steps.length - 1) {
        state.playing = false;
        save();
        renderPlay();
        ui.caption.textContent = "Koniec prezentacji. Dziękujemy!";
        spotlight(null);
        emit("demo:end", {});
        return;
      }
      go(state.index + 1);
    }, PAUSE_MS);
  }

  // --- Sterowanie -------------------------------------------------------------

  function togglePlay() {
    state.playing = !state.playing;
    save();
    renderPlay();
    if (!state.playing) { halt(); return; }
    var step = steps[state.index];
    ui.caption.textContent = step.text;
    if (elapsed >= stepMs(step)) finished(step);
    else run(step);
  }

  function stop() {
    halt();
    spotlight(null);
    try { sessionStorage.removeItem(KEY); } catch (e) { /* tryb prywatny */ }
    state = { active: false };
    if (ui.bar) ui.bar.remove();
    document.body.classList.remove("demo-on");
  }
})();
