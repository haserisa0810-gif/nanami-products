/* 海外出生地入力の地図クリックUI（redeem フォーム共通）。
 *
 * - #overseas-map が無いページ（国内専用・地図非対応）では何もしない。
 * - 地図クリックで [name="birth_lat"] / [name="birth_lng"] に値を入れる。
 * - 手入力は従来通り可能。クリック後もユーザーが値を編集できる（上書きしない）。
 * - タイムゾーンは触らない（既存の手動選択のまま）。
 * - 海外モードでパネルが表示された瞬間に invalidateSize でサイズを再計算する。
 */
(function () {
  function initOverseasMap() {
    var mount = document.getElementById("overseas-map");
    if (!mount || mount.dataset.mapReady === "1") return;
    if (typeof L === "undefined") return;

    var latInput = document.querySelector('[name="birth_lat"]');
    var lngInput = document.querySelector('[name="birth_lng"]');
    if (!latInput || !lngInput) return;

    var startLat = parseFloat(latInput.value);
    var startLng = parseFloat(lngInput.value);
    var hasStart = !isNaN(startLat) && !isNaN(startLng);

    var map = L.map(mount, { worldCopyJump: true }).setView(
      hasStart ? [startLat, startLng] : [20, 0],
      hasStart ? 6 : 2
    );
    // 経度はクリック時に ±180 へ正規化するので、タイルは通常どおり横方向に
    // 繰り返してよい（noWrap にすると初期中心付近でタイルが欠けることがある）。
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 12,
      attribution: "&copy; OpenStreetMap contributors"
    }).addTo(map);

    function wrapLon(lon) {
      return ((lon + 180) % 360 + 360) % 360 - 180;
    }
    function clampLat(lat) {
      return Math.max(-90, Math.min(90, lat));
    }

    var marker = hasStart ? L.marker([startLat, startLng]).addTo(map) : null;

    function setInput(input, value) {
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.dispatchEvent(new Event("change", { bubbles: true }));
    }

    map.on("click", function (e) {
      var lat = Math.round(clampLat(e.latlng.lat) * 1e6) / 1e6;
      var lng = Math.round(wrapLon(e.latlng.lng) * 1e6) / 1e6;
      setInput(latInput, lat);
      setInput(lngInput, lng);
      if (marker) {
        marker.setLatLng(e.latlng);
      } else {
        marker = L.marker(e.latlng).addTo(map);
      }
    });

    mount.dataset.mapReady = "1";

    // 海外モード切替でパネルが表示されたとき、地図のサイズを再計算する。
    if ("IntersectionObserver" in window) {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) map.invalidateSize();
        });
      });
      io.observe(mount);
    } else {
      setTimeout(function () { map.invalidateSize(); }, 300);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initOverseasMap);
  } else {
    initOverseasMap();
  }
})();
