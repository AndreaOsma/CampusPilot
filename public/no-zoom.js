// GENERADO por dev/lib/design-system/native-web.mjs — no lo edites en la app.
// Sin zoom en el móvil (decisión de Andrea, 2026-10-29): Safari ignora user-scalable=no y el
// touch-action de CSS para el pellizco, así que se cortan sus gestos aquí. El scroll normal sigue igual.
(function () {
  var stop = function (e) { e.preventDefault(); };
  document.addEventListener("gesturestart", stop, { passive: false });
  document.addEventListener("gesturechange", stop, { passive: false });
  document.addEventListener("gestureend", stop, { passive: false });
  document.addEventListener("touchmove", function (e) {
    if (e.touches && e.touches.length > 1) e.preventDefault();
  }, { passive: false });
})();
