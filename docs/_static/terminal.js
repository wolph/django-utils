// Typewriter effect for elements marked data-terminal. The content is
// real text in the DOM (accessible and rendered as-is without JS);
// the script only animates its appearance. Honors reduced motion.
(function () {
    'use strict';
    function animate(block) {
        if (block.dataset.terminalDone) {
            return;
        }
        block.dataset.terminalDone = '1';
        var full = block.textContent;
        block.textContent = '';
        block.classList.add('terminal-animating');
        var i = 0;
        function tick() {
            var step = 2 + Math.floor(Math.random() * 3);
            i = Math.min(i + step, full.length);
            block.textContent = full.slice(0, i);
            if (i < full.length) {
                window.setTimeout(tick, 16);
            } else {
                block.classList.remove('terminal-animating');
            }
        }
        tick();
    }
    document.addEventListener('DOMContentLoaded', function () {
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            return;
        }
        var blocks = document.querySelectorAll('[data-terminal]');
        var observer = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                if (entry.isIntersecting) {
                    animate(entry.target);
                    observer.unobserve(entry.target);
                }
            });
        });
        blocks.forEach(function (block) {
            observer.observe(block);
        });
    });
})();
