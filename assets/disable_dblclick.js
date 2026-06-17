// Disable MapLibre double-click zoom on the map graph
(function () {
    var observer = new MutationObserver(function () {
        var el = document.getElementById("map-graph");
        if (el && !el._dblclickDisabled) {
            el.addEventListener(
                "dblclick",
                function (e) {
                    e.stopPropagation();
                    e.preventDefault();
                },
                true
            );
            el._dblclickDisabled = true;
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
})();

// Stop layer toggle clicks from bubbling up to the widget card header,
// which would trigger the collapse toggle callback unintentionally.
// Uses bubble phase so Dash still receives the click on the checklist itself.
(function () {
    document.addEventListener("click", function (e) {
        var toggle = e.target.closest(".layer-toggle-inline");
        if (!toggle) return;
        // Only stop propagation once the event has passed the toggle container —
        // Dash's React handler fires during bubble on the element itself, so
        // stopping here prevents it reaching the parent header div.
        var header = e.target.closest(".widget-card-header");
        if (header) {
            e.stopPropagation();
        }
    }, false);
})();
