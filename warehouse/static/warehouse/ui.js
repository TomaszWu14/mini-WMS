/* US-011: zachowania podpinane po atrybutach data-* zamiast on*= (CSP bez 'unsafe-inline').
 *   data-confirm="Pytanie?"  na <form>   — potwierdzenie przed wysłaniem
 *   data-autosubmit          na <select> — wysyła formularz po zmianie
 *   data-nav-toggle          na <button> — otwiera/zamyka menu boczne
 *   data-history-back        na <a>      — „Anuluj” wraca do poprzedniej strony (href = zapas)
 */
(function () {
  "use strict";

  function wire() {
    document.querySelectorAll("form[data-confirm]").forEach(function (form) {
      form.addEventListener("submit", function (e) {
        if (!window.confirm(form.getAttribute("data-confirm"))) e.preventDefault();
      });
    });
    document.querySelectorAll("[data-autosubmit]").forEach(function (el) {
      el.addEventListener("change", function () {
        if (el.form) el.form.submit();
      });
    });
    document.querySelectorAll("a[data-history-back]").forEach(function (link) {
      link.addEventListener("click", function (e) {
        if (window.history.length > 1) {
          e.preventDefault();
          window.history.back();
        }
      });
    });
    document.querySelectorAll("[data-nav-toggle]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        document.body.classList.toggle("nav-open");
      });
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", wire);
  else wire();
})();
