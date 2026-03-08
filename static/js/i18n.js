/**
 * GLaDOS i18n — Frontend Internationalization Module
 * Supports dot-notation keys, {variable} interpolation, arrays, and DOM auto-translation.
 */
const I18n = (function() {
    let _translations = {};
    let _lang = 'pl';
    const _supportedLangs = ['pl', 'en'];

    function init(translations, lang) {
        _translations = translations || {};
        _lang = _supportedLangs.includes(lang) ? lang : 'pl';
    }

    /**
     * Translate a key using dot notation.
     * Usage: t('chat.placeholder') or t('backend.cpu.high', {pct: 90})
     */
    function t(key, params) {
        let value = _translations;
        const parts = key.split('.');
        for (const part of parts) {
            if (value && typeof value === 'object' && part in value) {
                value = value[part];
            } else {
                return key; // fallback: return the key itself
            }
        }
        if (typeof value === 'string' && params) {
            return value.replace(/\{(\w+)\}/g, (_, k) => (k in params ? params[k] : `{${k}}`));
        }
        return (typeof value === 'string') ? value : key;
    }

    /**
     * Get a list (array) translation.
     */
    function tList(key) {
        let value = _translations;
        const parts = key.split('.');
        for (const part of parts) {
            if (value && typeof value === 'object' && part in value) {
                value = value[part];
            } else {
                return [];
            }
        }
        return Array.isArray(value) ? value : [];
    }

    /**
     * Get raw nested object (for things like cores, emotions maps).
     */
    function tObj(key) {
        let value = _translations;
        const parts = key.split('.');
        for (const part of parts) {
            if (value && typeof value === 'object' && part in value) {
                value = value[part];
            } else {
                return null;
            }
        }
        return (typeof value === 'object' && !Array.isArray(value)) ? value : null;
    }

    /**
     * Update all DOM elements with data-i18n attribute.
     * <span data-i18n="nav.dashboard">Dashboard</span>
     * Also supports data-i18n-placeholder for input placeholders.
     */
    function updateDOM() {
        document.querySelectorAll('[data-i18n]').forEach(el => {
            const key = el.getAttribute('data-i18n');
            const translated = t(key);
            if (translated !== key) {
                el.textContent = translated;
            }
        });
        document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            const translated = t(key);
            if (translated !== key) {
                el.placeholder = translated;
            }
        });
        document.querySelectorAll('[data-i18n-title]').forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            const translated = t(key);
            if (translated !== key) {
                el.title = translated;
            }
        });
    }

    /**
     * Switch language — calls API, sets cookie, reloads page.
     */
    function setLang(lang) {
        if (!_supportedLangs.includes(lang)) return;
        fetch(`/api/i18n/set/${lang}`, {
            method: 'POST',
            headers: {'X-API-Key': window._apiKey || ''}
        }).then(() => {
            location.reload();
        }).catch(() => {
            location.reload();
        });
    }

    function getLang() {
        return _lang;
    }

    function getSupportedLangs() {
        return _supportedLangs;
    }

    return { init, t, tList, tObj, updateDOM, setLang, getLang, getSupportedLangs };
})();
