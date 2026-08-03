// Activates select2 on the CSP-safe dropdown filter's <select>, when
// the admin's select2 assets (jQuery + select2, loaded via
// `Select2Mixin.Media`) are present on the page. `dropdown_filter.js`
// has already unhidden the select and wired its plain `change`
// navigation by the time this runs; select2 replaces the widget in
// place without touching the underlying <select>'s value or `change`
// behavior. If select2 isn't available, this silently does nothing and
// the plain (unhidden) `<select>` from `dropdown_filter.js` is used.
(function () {
    'use strict';

    function init() {
        if (!window.django || !django.jQuery || !django.jQuery.fn.select2) {
            return;
        }
        var selects = document.querySelectorAll('[data-select2-filter]');
        Array.prototype.forEach.call(selects, function (select) {
            django.jQuery(select).select2();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
