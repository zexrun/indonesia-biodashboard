(function () {
    'use strict';

    var DEFAULT_ORDER = ['ranked', 'mollweide', 'habitat', 'ias_ujungkulon', 'ias_baluran'];
    var _draggingKey = null;

    function getCurrentOrder() {
        // Read from the layer-order store via the Dash store element
        var store = document.getElementById('layer-order');
        if (store) {
            try {
                var val = JSON.parse(store.getAttribute('data-dash-store') || '');
                if (Array.isArray(val) && val.length === 5) return val;
            } catch (e) {}
        }
        // Fallback: read from window if previously set
        return (window._layerCurrentOrder || DEFAULT_ORDER).slice();
    }

    function clearIndicators() {
        DEFAULT_ORDER.forEach(function (k) {
            var s = document.getElementById('layer-slot-' + k);
            if (s) s.classList.remove(
                'layer-slot-dragging', 'layer-slot-over-above', 'layer-slot-over-below'
            );
        });
    }

    function setup() {
        var slots = DEFAULT_ORDER.map(function (k) {
            return document.getElementById('layer-slot-' + k);
        });

        if (slots.some(function (s) { return !s; })) return false;
        if (slots[0]._dragReady) return true;

        slots.forEach(function (slot) {
            var key = slot.id.replace('layer-slot-', '');
            slot._dragReady = true;
            slot.draggable = false;

            // Only start drag when mouse is down on the drag handle
            slot.addEventListener('mousedown', function (e) {
                slot.draggable = !!e.target.closest('.layer-drag-handle');
            });

            // Safety reset if mouse released without dragging
            slot.addEventListener('mouseup', function () {
                slot.draggable = false;
            });

            slot.addEventListener('dragstart', function (e) {
                _draggingKey = key;
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', key);
                // Store current order at drag start
                window._layerCurrentOrder = getCurrentOrder().slice();
                setTimeout(function () {
                    slot.classList.add('layer-slot-dragging');
                }, 0);
            });

            slot.addEventListener('dragend', function () {
                slot.draggable = false;
                clearIndicators();
                _draggingKey = null;
            });

            slot.addEventListener('dragover', function (e) {
                if (!_draggingKey || _draggingKey === key) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                var rect = slot.getBoundingClientRect();
                var above = e.clientY < rect.top + rect.height / 2;
                slot.classList.toggle('layer-slot-over-above', above);
                slot.classList.toggle('layer-slot-over-below', !above);
            });

            slot.addEventListener('dragleave', function (e) {
                if (!slot.contains(e.relatedTarget)) {
                    slot.classList.remove('layer-slot-over-above', 'layer-slot-over-below');
                }
            });

            slot.addEventListener('drop', function (e) {
                e.preventDefault();
                var above = e.clientY < slot.getBoundingClientRect().top + slot.getBoundingClientRect().height / 2;
                slot.classList.remove('layer-slot-over-above', 'layer-slot-over-below');

                if (!_draggingKey || _draggingKey === key) return;

                var order = (window._layerCurrentOrder || DEFAULT_ORDER).slice();
                var fromIdx = order.indexOf(_draggingKey);
                order.splice(fromIdx, 1);
                var toIdx = order.indexOf(key);
                order.splice(above ? toIdx : toIdx + 1, 0, _draggingKey);

                // Write new order — picked up by dcc.Interval clientside callback
                window._layerDragOrder = order;
                window._layerCurrentOrder = order;
            });
        });

        return true;
    }

    // Poll until Dash renders the slot elements
    var poll = setInterval(function () {
        if (setup()) clearInterval(poll);
    }, 150);

})();
