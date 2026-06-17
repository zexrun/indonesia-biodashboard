/**
 * chat_drag.js
 * Makes the AI chat panel draggable by its header.
 * Works with Dash's async rendering — retries until the element exists.
 */

(function () {
    "use strict";

    var container   = null;
    var isDragging  = false;
    var offsetX     = 0;
    var offsetY     = 0;
    var initialized = false;
    var dragMoved   = false;   // true jika mouse bergerak saat drag (bukan klik biasa)

    /* ── Convert CSS bottom/center → explicit top/left so JS can move it ── */
    function snapToAbsolute() {
        var rect = container.getBoundingClientRect();
        container.style.left      = rect.left + "px";
        container.style.top       = rect.top  + "px";
        container.style.bottom    = "auto";
        container.style.transform = "none";
    }

    /* ── Mouse down on header/toggle: begin drag ── */
    function onMouseDown(e) {
        if (e.target && e.target.classList.contains("chat-close-btn")) return;

        isDragging = true;
        dragMoved  = false;
        var rect = container.getBoundingClientRect();
        offsetX = e.clientX - rect.left;
        offsetY = e.clientY - rect.top;

        container.style.cursor     = "grabbing";
        container.style.userSelect = "none";
        e.preventDefault();
    }

    /* ── Mouse move: reposition container ── */
    function onMouseMove(e) {
        if (!isDragging) return;
        dragMoved = true;

        var x = e.clientX - offsetX;
        var y = e.clientY - offsetY;

        var maxX = window.innerWidth  - container.offsetWidth;
        var maxY = window.innerHeight - container.offsetHeight;
        x = Math.max(0, Math.min(x, maxX));
        y = Math.max(0, Math.min(y, maxY));

        container.style.left = x + "px";
        container.style.top  = y + "px";
    }

    /* ── Mouse up: end drag; batalkan klik Dash jika ada pergerakan ── */
    function onMouseUp(e) {
        if (!isDragging) return;
        isDragging             = false;
        container.style.cursor = "";
        container.style.userSelect = "";

        // Jika mouse bergerak (drag), batalkan klik pada toggle button agar panel tidak terbuka
        if (dragMoved) {
            e.stopPropagation();
            var toggleBtn = container.querySelector(".chat-toggle-btn");
            if (toggleBtn) {
                toggleBtn.addEventListener("click", function absorbClick(ev) {
                    ev.stopPropagation();
                    toggleBtn.removeEventListener("click", absorbClick, true);
                }, true);
            }
        }
        dragMoved = false;
    }

    /* ── Attach listeners to the panel header and toggle button ── */
    function initDrag() {
        if (initialized) return;
        container = document.getElementById("ai-chat-container");
        if (!container) return;

        var header      = container.querySelector(".chat-header");
        var toggleBtn   = container.querySelector(".chat-toggle-btn");
        if (!header || !toggleBtn) return;

        // Convert to absolute position so JS can move freely
        snapToAbsolute();

        // Drag handle = header (saat panel terbuka) + toggle button (saat panel tertutup)
        header.addEventListener("mousedown", onMouseDown);
        toggleBtn.addEventListener("mousedown", onMouseDown);
        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup",   onMouseUp);

        // Re-snap if window resizes and panel goes off-screen
        window.addEventListener("resize", function () {
            if (!container) return;
            var rect = container.getBoundingClientRect();
            var x = Math.max(0, Math.min(rect.left, window.innerWidth  - container.offsetWidth));
            var y = Math.max(0, Math.min(rect.top,  window.innerHeight - container.offsetHeight));
            container.style.left = x + "px";
            container.style.top  = y + "px";
        });

        initialized = true;
    }

    /* ── Retry init until Dash renders the element ── */
    var attempts  = 0;
    var maxTries  = 40;       // 40 × 300ms = 12 s max wait
    var interval  = setInterval(function () {
        attempts++;
        initDrag();
        if (initialized || attempts >= maxTries) {
            clearInterval(interval);
        }
    }, 300);

})();
