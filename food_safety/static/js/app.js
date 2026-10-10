(function () {
  function initIcons() {
    if (window.lucide && typeof window.lucide.createIcons === "function") {
      window.lucide.createIcons();
    }
  }

  function initSidebar() {
    var toggle = document.getElementById("menuToggle");
    var backdrop = document.getElementById("sidebarBackdrop");
    function close() {
      document.body.classList.remove("sidebar-open");
    }
    function open() {
      document.body.classList.toggle("sidebar-open");
    }
    if (toggle) toggle.addEventListener("click", open);
    if (backdrop) backdrop.addEventListener("click", close);
  }

  function initGeoConsent() {
    document.querySelectorAll("[data-geo-consent]").forEach(function (consent) {
      var form = consent.closest("form");
      if (!form || !navigator.geolocation) return;
      var lat = form.querySelector("[name=latitude]");
      var lng = form.querySelector("[name=longitude]");
      if (!lat || !lng) return;
      consent.addEventListener("change", function () {
        if (consent.checked) {
          navigator.geolocation.getCurrentPosition(function (pos) {
            lat.value = pos.coords.latitude;
            lng.value = pos.coords.longitude;
          });
        } else {
          lat.value = "";
          lng.value = "";
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initIcons();
    initSidebar();
    initGeoConsent();
  });
})();
