/* Prezentacja z lektorem — włącza się parametrem ?demo=1, potem trwa między
 * stronami (stan w sessionStorage). Niczego nie zapisuje w aplikacji: tylko
 * nawigacja, podświetlenie, napisy i dźwięk. Bez ?demo=1 i bez trwającej
 * prezentacji skrypt kończy się w pierwszych liniach.
 * Scenariusz: demo_script.json, nagrania: audio/manifest.json
 * (tools/generate_voiceover.py). */
(function () {
  "use strict";

  var KEY = "miniwms-demo";
  var PAUSE_MS = 500;
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

  state = state || { active: false, index: 0, playing: false, muted: false, volume: 1, visited: {} };

  var css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = base + "demo.css";
  document.head.appendChild(css);

  var steps = [];
  var manifest = {};
  var audio = null;          // bieżące nagranie — zawsze najwyżej jedno
  var preloaded = {};        // id → Audio (kolejny krok)
  var timer = null;
  var spotEl = null;
  var ui = {};

  function fetchJSON(path) {
    return fetch(base + path, { cache: "no-cache" }).then(function (r) {
      return r.ok ? r.json() : {};
    }).catch(function () { return {}; });
  }

  Promise.all([fetchJSON("demo_script.json"), fetchJSON("audio/manifest.json")]).then(function (res) {
    steps = (res[0] && res[0].steps) || [];
    manifest = res[1] || {};
    if (!steps.length) return;
    buildUI();
    if (state.active) showStep(state.index, true);
    else showStart();
  });

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
    ui.mute = button("🔊", "Wycisz", toggleMute);
    ui.volume = el("input", "demo-volume");
    ui.volume.type = "range";
    ui.volume.min = "0"; ui.volume.max = "1"; ui.volume.step = "0.05";
    ui.volume.value = String(state.volume);
    ui.volume.setAttribute("aria-label", "Głośność");
    ui.volume.addEventListener("input", function () {
      state.volume = Number(ui.volume.value);
      if (audio) audio.volume = state.volume;
      save();
    });
    ui.count = el("span", "demo-count");
    var close = button("✕", "Zakończ prezentację", stop);
    [ui.prev, ui.play, ui.next, ui.mute, ui.volume, ui.count].forEach(function (c) { controls.appendChild(c); });
    controls.appendChild(el("span", "demo-spacer"));
    controls.appendChild(close);

    bar.appendChild(ui.progress);
    bar.appendChild(ui.caption);
    bar.appendChild(controls);
    document.body.appendChild(bar);
    document.body.classList.add("demo-on");
    ui.bar = bar;
    renderMute();
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
    overlay.appendChild(el("p", "demo-start-hint", "Około trzech minut, z lektorem. Włącz dźwięk."));
    document.body.appendChild(overlay);
    startBtn.focus();
  }

  function renderPlay() { ui.play.textContent = state.playing ? "⏸" : "▶"; }
  function renderMute() { ui.mute.textContent = state.muted ? "🔇" : "🔊"; }
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
    haltAudio();
    state.index = i;
    save();
    showStep(i, false);
  }

  function showStep(i, resumed) {
    var step = steps[i];
    var target = step.url || state.visited[i];
    if (target && !samePath(target)) {
      save();
      location.href = target;
      return;
    }
    state.visited[i] = location.pathname;
    save();
    ui.caption.textContent = step.text;
    renderProgress(0);
    spotlight(find(step.selector));
    if (location.pathname.indexOf("/login") === 0) {
      state.playing = false;
      ui.caption.textContent = "Zaloguj się — po zalogowaniu kliknij ▶, prezentacja wróci w tym miejscu.";
    }
    renderPlay();
    if (state.playing) play(step, resumed);
  }

  // --- Dźwięk ---------------------------------------------------------------

  function clipUrl(step) {
    return manifest[step.id] ? base + "audio/" + manifest[step.id] : null;
  }

  function haltAudio() {
    clearTimeout(timer);
    timer = null;
    if (audio) {
      audio.onended = audio.onerror = audio.ontimeupdate = null;
      audio.pause();
      audio = null;
    }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }

  function play(step, resumed) {
    haltAudio();
    var src = clipUrl(step);
    if (!src) { speak(step, "brak nagrania w manifest.json"); return; }
    audio = preloaded[step.id] || new Audio(src);
    delete preloaded[step.id];
    audio.volume = state.volume;
    audio.muted = state.muted;
    audio.ontimeupdate = function () {
      if (audio && audio.duration) renderProgress(audio.currentTime / audio.duration);
    };
    audio.onended = function () { finished(step); };
    audio.onerror = function () { speak(step, "nie udało się wczytać " + src); };
    var p = audio.play();
    if (p && p.catch) p.catch(function (err) { blocked(err, resumed); });
    preloadNext();
  }

  function speak(step, reason) {
    console.warn("[demo] " + step.id + ": " + reason + " — czytam przez speechSynthesis.");
    haltAudio();
    if (!window.speechSynthesis) { timer = setTimeout(function () { finished(step); }, 4000); return; }
    var u = new SpeechSynthesisUtterance(step.text);
    u.lang = "pl-PL";
    u.volume = state.muted ? 0 : state.volume;
    u.onend = function () { finished(step); };
    u.onerror = function (e) {
      if (e.error === "not-allowed") blocked(e, true);
    };
    window.speechSynthesis.speak(u);
  }

  // Przeglądarka nie pozwoliła odtworzyć dźwięku bez kliknięcia (np. po
  // przejściu na nową stronę) — czekamy na ▶.
  function blocked(err, resumed) {
    if (err && err.name && err.name !== "NotAllowedError" && err.error !== "not-allowed") return;
    state.playing = false;
    save();
    renderPlay();
    if (resumed) ui.caption.textContent = steps[state.index].text + "  (kliknij ▶, aby kontynuować)";
  }

  function preloadNext() {
    var next = steps[state.index + 1];
    var src = next && clipUrl(next);
    if (src && !preloaded[next.id]) {
      var a = new Audio();
      a.preload = "auto";
      a.src = src;
      preloaded[next.id] = a;
    }
  }

  function finished(step) {
    renderProgress(1);
    timer = setTimeout(function () {
      if (!state.playing) return;
      var last = state.index >= steps.length - 1;
      if (step.action === "click") {
        var link = find(step.selector);
        if (link) {
          state.index += 1;
          save();
          link.click();
          return;
        }
      }
      if (last) {
        state.playing = false;
        save();
        renderPlay();
        ui.caption.textContent = "Koniec prezentacji. Dziękujemy!";
        spotlight(null);
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
    if (!state.playing) {
      clearTimeout(timer);
      if (audio) audio.pause();
      if (window.speechSynthesis) window.speechSynthesis.cancel();
      return;
    }
    ui.caption.textContent = steps[state.index].text;
    if (audio && !audio.ended) {
      var p = audio.play();
      if (p && p.catch) p.catch(function (err) { blocked(err, false); });
    } else {
      play(steps[state.index], false);
    }
  }

  function toggleMute() {
    state.muted = !state.muted;
    if (audio) audio.muted = state.muted;
    save();
    renderMute();
  }

  function stop() {
    haltAudio();
    spotlight(null);
    try { sessionStorage.removeItem(KEY); } catch (e) { /* tryb prywatny */ }
    state = { active: false };
    if (ui.bar) ui.bar.remove();
    document.body.classList.remove("demo-on");
  }
})();
