// Inline JSON validation for django-utils2's JSONWidget.
// CSP-safe: no inline handlers, no eval, attached via addEventListener.
(function () {
    'use strict';

    function messageFor(textarea) {
        var id = textarea.id + '-json-error';
        var node = document.getElementById(id);
        if (!node) {
            node = document.createElement('p');
            node.id = id;
            node.className = 'django-utils-json-error';
            node.hidden = true;
            textarea.parentNode.insertBefore(node, textarea.nextSibling);
        }
        return node;
    }

    function validate(textarea) {
        var node = messageFor(textarea);
        var value = textarea.value.trim();
        if (value === '') {
            node.hidden = true;
            return;
        }
        try {
            JSON.parse(value);
            node.hidden = true;
        } catch (error) {
            node.textContent = error.message;
            node.hidden = false;
        }
    }

    function init() {
        var fields = document.querySelectorAll('textarea[data-json-widget]');
        Array.prototype.forEach.call(fields, function (textarea) {
            textarea.addEventListener('input', function () {
                validate(textarea);
            });
            validate(textarea);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
