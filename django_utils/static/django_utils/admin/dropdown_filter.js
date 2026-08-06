// Progressive enhancement for dropdown_filter.html's CSP-safe admin
// filter. With JavaScript disabled, the template's link list is the
// entire UI and this file never runs. With it enabled, this swaps in
// the `<select>` (rendered `hidden` by the template whenever there are
// more than three choices) in place of the links, and navigates on
// `change` -- restoring the pre-CSP inline `onchange` behavior without
// any inline JS.
(function () {
    'use strict';

    function activate(select) {
        // `admin_list_filter` renders each filter spec's template
        // independently and concatenates the results onto the
        // changelist page, so on a page with more than one dropdown
        // filter (a supported, `JSONFieldFilter.create()`-encouraged
        // configuration) this file's `<script src>` tag -- emitted
        // unconditionally by dropdown_filter.html -- appears once per
        // filter. A classic script executes its top-level code once per
        // occurrence, so `init()` below runs once per filter too, each
        // time re-querying every `[data-dropdown-filter]` select on the
        // whole page. Without this marker, that would attach a `change`
        // listener to the same select N times. Guard: skip a select
        // that's already been activated.
        if (select.dataset.duDropdownActivated) {
            return;
        }
        select.dataset.duDropdownActivated = '1';

        var container = select.closest('ul');
        if (!container) {
            return;
        }
        var links = container.querySelectorAll('li > a');
        Array.prototype.forEach.call(links, function (link) {
            link.parentNode.hidden = true;
        });
        select.hidden = false;
        select.addEventListener('change', function () {
            window.location.assign(window.location.pathname + select.value);
        });
    }

    function init() {
        var selects = document.querySelectorAll('[data-dropdown-filter]');
        Array.prototype.forEach.call(selects, activate);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
