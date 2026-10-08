/* Skanowanie QR kamerą telefonu (bez kolektora). Wymaga jsQR (vendor). */
(function () {
  "use strict";

  function buildOverlay() {
    var ov = document.createElement("div");
    ov.className = "cam-overlay";
    ov.innerHTML =
      '<div class="cam-box">' +
      '  <video class="cam-video" playsinline muted></video>' +
      '  <div class="cam-frame"></div>' +
      '  <div class="cam-hint">Skieruj aparat na kod QR palety</div>' +
      '  <button type="button" class="cam-close">Zamknij</button>' +
      "</div>";
    document.body.appendChild(ov);
    return ov;
  }

  function openCamera(onResult) {
    if (typeof window.jsQR !== "function") {
      alert("Brak modułu odczytu QR.");
      return;
    }
    var overlay = buildOverlay();
    var video = overlay.querySelector(".cam-video");
    var canvas = document.createElement("canvas");
    var ctx = canvas.getContext("2d", { willReadFrequently: true });
    var stream = null;
    var raf = null;
    var stopped = false;

    function stop() {
      if (stopped) return;
      stopped = true;
      if (raf) cancelAnimationFrame(raf);
      if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
      overlay.remove();
    }

    overlay.querySelector(".cam-close").addEventListener("click", stop);

    function tick() {
      if (stopped) return;
      if (video.readyState === video.HAVE_ENOUGH_DATA) {
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        var img = ctx.getImageData(0, 0, canvas.width, canvas.height);
        var code = null;
        try {
          code = window.jsQR(img.data, img.width, img.height, {
            inversionAttempts: "dontInvert",
          });
        } catch (e) {
          // Pojedyncza klatka mogła być wadliwa — nie przerywaj pętli skanowania.
          code = null;
        }
        if (code && code.data) {
          if (window.Scanner) window.Scanner.beepOk();
          var value = code.data.trim();
          stop();
          onResult(value);
          return;
        }
      }
      raf = requestAnimationFrame(tick);
    }

    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: { ideal: "environment" } }, audio: false })
      .then(function (s) {
        stream = s;
        video.srcObject = s;
        video.setAttribute("playsinline", "true");
        return video.play();
      })
      .then(function () { raf = requestAnimationFrame(tick); })
      .catch(function (err) {
        stop();
        alert("Nie można uruchomić aparatu: " + err.message +
              "\n(Wymagane HTTPS i zgoda na kamerę.)");
      });
  }

  // Auto-podłączenie przycisków kamery: wypełniają sąsiednie pole i wysyłają formularz.
  function wire() {
    document.querySelectorAll(".scn-cam").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var wrap = btn.closest(".scn-scan");
        var input = wrap ? wrap.querySelector("input") : null;
        if (!input) return;
        openCamera(function (code) {
          input.value = code;
          var form = input.form;
          if (form) form.dispatchEvent(new Event("submit", { cancelable: true, bubbles: true }));
        });
      });
    });
  }

  if (window.Scanner) window.Scanner.openCamera = openCamera;
  if (document.readyState !== "loading") wire();
  else document.addEventListener("DOMContentLoaded", wire);
})();
