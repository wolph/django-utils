// Inline JSON validation and dependency-free syntax highlighting for
// django-utils2's JSONWidget.
// CSP-safe: no inline handlers, no eval, attached via addEventListener.
//
// Highlighting works by overlaying a <pre> on top of the <textarea>
// (pointer-events: none) and painting a token-colored copy of the value
// into it, while the textarea's own text is transparent (see
// json_widget.css). The real textarea never goes away, so focus, caret,
// selection, undo, paste and form submission all stay native, and with
// JavaScript disabled the widget degrades to a plain textarea.
(function () {
    'use strict';

    // Lexes rather than parses: mid-edit content is invalid JSON most of
    // the time and the colors must keep working while the user types.
    // Groups: 1 = string (unterminated tolerated), 2 = number,
    // 3 = true/false/null.
    var TOKEN_RE =
        /("(?:\\.|[^"\\\n])*"?)|(-?\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b)|\b(true|false|null)\b/g;

    function span(className, text) {
        var node = document.createElement('span');
        node.className = className;
        node.textContent = text;
        return node;
    }

    function render(code, value) {
        var fragment = document.createDocumentFragment();
        var last = 0;
        var match;
        TOKEN_RE.lastIndex = 0;
        while ((match = TOKEN_RE.exec(value)) !== null) {
            if (match.index > last) {
                fragment.appendChild(
                    document.createTextNode(value.slice(last, match.index))
                );
            }
            var className;
            if (match[1] !== undefined) {
                // A string directly followed by `:` is an object key.
                className = /^[ \t\r\n]*:/.test(
                    value.slice(TOKEN_RE.lastIndex)
                )
                    ? 'django-utils-json-key'
                    : 'django-utils-json-string';
            } else if (match[2] !== undefined) {
                className = 'django-utils-json-number';
            } else {
                className = 'django-utils-json-literal';
            }
            fragment.appendChild(span(className, match[0]));
            last = TOKEN_RE.lastIndex;
        }
        if (last < value.length) {
            fragment.appendChild(document.createTextNode(value.slice(last)));
        }
        // A trailing newline produces a visible empty line in a textarea
        // but not in a <pre>; pad one so line counts and scroll heights
        // stay in sync.
        fragment.appendChild(document.createTextNode('\n'));
        code.textContent = '';
        code.appendChild(fragment);
    }

    // Wraps the textarea in a positioning container and mounts the
    // overlay; returns the overlay's <pre> and <code>.
    function mountOverlay(textarea) {
        var wrapper = document.createElement('div');
        wrapper.className = 'django-utils-json-widget';
        textarea.parentNode.insertBefore(wrapper, textarea);
        var pre = document.createElement('pre');
        pre.className = 'django-utils-json-highlight';
        pre.setAttribute('aria-hidden', 'true');
        var code = document.createElement('code');
        pre.appendChild(code);
        wrapper.appendChild(textarea);
        wrapper.appendChild(pre);
        return {pre: pre, code: code};
    }

    function messageFor(textarea) {
        var id = textarea.id + '-json-error';
        var node = document.getElementById(id);
        if (!node) {
            node = document.createElement('p');
            node.id = id;
            node.className = 'django-utils-json-error';
            node.hidden = true;
            // The textarea lives inside the overlay wrapper; the error
            // belongs below the widget as a whole, not inside it.
            var anchor =
                textarea.closest('.django-utils-json-widget') || textarea;
            anchor.parentNode.insertBefore(node, anchor.nextSibling);
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

    function activate(textarea) {
        // See dropdown_filter.js's `activate()` for why this guard
        // exists: `Media` deduplicates the script tag on a change form,
        // but nothing stops a page (or an inline-added form row) from
        // running init() more than once over the same textarea.
        if (textarea.dataset.duJsonActivated) {
            return;
        }
        textarea.dataset.duJsonActivated = '1';
        var overlay = mountOverlay(textarea);

        function update() {
            render(overlay.code, textarea.value);
            validate(textarea);
        }

        textarea.addEventListener('input', update);
        textarea.addEventListener('scroll', function () {
            overlay.pre.scrollTop = textarea.scrollTop;
            overlay.pre.scrollLeft = textarea.scrollLeft;
        });
        update();
    }

    function init() {
        var fields = document.querySelectorAll('textarea[data-json-widget]');
        Array.prototype.forEach.call(fields, activate);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
