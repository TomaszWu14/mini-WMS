/* Wspólne narzędzia interfejsu skanerowego. */
(function () {
  "use strict";

  // Dźwięk potwierdzenia / błędu (WebAudio, bez plików).
  let actx = null;
  function tone(freq, dur, type, gain) {
    try {
      actx = actx || new (window.AudioContext || window.webkitAudioContext)();
      if (actx.state === "suspended") actx.resume();
      const o = actx.createOscillator();
      const g = actx.createGain();
      o.type = type || "square";
      o.frequency.value = freq;
      o.connect(g);
      g.connect(actx.destination);
      // Głośniejszy brzęczyk magazynowy.
      g.gain.setValueAtTime(gain || 0.32, actx.currentTime);
      o.start();
      o.stop(actx.currentTime + dur);
    } catch (e) { /* brak audio — ignoruj */ }
  }

  window.Scanner = {
    beepOk: function () { tone(950, 0.16); if (navigator.vibrate) navigator.vibrate(80); },
    beepErr: function () {
      tone(200, 0.28, "sawtooth");
      if (navigator.vibrate) navigator.vibrate([90, 60, 90]);
    },

    // Trzymaj pole skanera w focusie (kolektor wpisuje znaki jak klawiatura).
    keepFocus: function (input) {
      if (!input) return;
      const refocus = function () { setTimeout(function () { input.focus(); }, 30); };
      input.addEventListener("blur", refocus);
      document.addEventListener("click", function (e) {
        // Nie odbieraj focusu interaktywnym elementom (przyciski/inputy).
        if (e.target.closest("button, input, a")) return;
        input.focus();
      });
      input.focus();
    },

    // Zamienia odpowiedź na obiekt JSON; błąd sieci lub nie-JSON (np. strona
    // błędu 500) jest przechwytywany i zwracany jako {ok:false}, żeby UI nigdy
    // nie został zablokowany (przycisk disabled, brak komunikatu).
    _parse: function (r) {
      return r.json().then(
        function (j) { j._status = r.status; return j; },
        function () { return { ok: false, _status: r.status, error: "Błąd serwera (" + r.status + ")." }; }
      );
    },
    _netErr: function () {
      return { ok: false, _status: 0, error: "Brak połączenia z serwerem." };
    },

    getJSON: function (url, params) {
      const qs = new URLSearchParams(params || {}).toString();
      const self = this;
      return fetch(url + (qs ? "?" + qs : ""), {
        headers: { "X-Requested-With": "XMLHttpRequest" },
      }).then(function (r) { return self._parse(r); }, self._netErr);
    },

    postForm: function (url, data) {
      const body = new URLSearchParams(data || {});
      const self = this;
      return fetch(url, {
        method: "POST",
        headers: {
          "X-CSRFToken": window.CSRF || "",
          "Content-Type": "application/x-www-form-urlencoded",
          "X-Requested-With": "XMLHttpRequest",
        },
        body: body.toString(),
      }).then(function (r) { return self._parse(r); }, self._netErr);
    },
  };
})();
