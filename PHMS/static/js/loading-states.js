(function () {
    const OVERLAY_ID = 'phmsGlobalLoadingOverlay';
    let overlayRefCount = 0;

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function ensureOverlay() {
        let overlay = document.getElementById(OVERLAY_ID);
        if (overlay) {
            return overlay;
        }

        overlay = document.createElement('div');
        overlay.id = OVERLAY_ID;
        overlay.className = 'phms-loading-overlay';
        overlay.innerHTML =
            '<div class="phms-loading-panel" role="status" aria-live="polite">' +
            '<span class="phms-spinner" aria-hidden="true"></span>' +
            '<p class="phms-loading-text" data-loading-text>Loading...</p>' +
            '</div>';
        document.body.appendChild(overlay);
        return overlay;
    }

    function showOverlay(message) {
        const overlay = ensureOverlay();
        const text = overlay.querySelector('[data-loading-text]');
        if (text) {
            text.textContent = message || 'Loading...';
        }

        overlayRefCount += 1;
        overlay.classList.add('phms-visible');
        document.body.classList.add('phms-loading-active');
    }

    function hideOverlay() {
        overlayRefCount = Math.max(0, overlayRefCount - 1);
        if (overlayRefCount > 0) {
            return;
        }

        const overlay = document.getElementById(OVERLAY_ID);
        if (overlay) {
            overlay.classList.remove('phms-visible');
        }
        document.body.classList.remove('phms-loading-active');
    }

    function setButtonLoading(button, loadingText) {
        if (!button || button.dataset.phmsLoading === '1') {
            return;
        }

        button.dataset.phmsLoading = '1';
        button.dataset.phmsOriginalHtml = button.innerHTML;
        button.dataset.phmsWasDisabled = button.disabled ? '1' : '0';

        if ('disabled' in button) {
            button.disabled = true;
        }

        button.classList.add('phms-btn-loading');
        const message = escapeHtml(loadingText || button.dataset.loadingText || 'Please wait...');
        button.innerHTML =
            '<span class="phms-btn-content">' +
            '<span class="phms-btn-spinner" aria-hidden="true"></span>' +
            '<span>' + message + '</span>' +
            '</span>';
    }

    function clearButtonLoading(button) {
        if (!button || button.dataset.phmsLoading !== '1') {
            return;
        }

        if (button.dataset.phmsOriginalHtml !== undefined) {
            button.innerHTML = button.dataset.phmsOriginalHtml;
        }

        const wasDisabled = button.dataset.phmsWasDisabled === '1';
        if ('disabled' in button) {
            button.disabled = wasDisabled;
        }

        button.classList.remove('phms-btn-loading');
        delete button.dataset.phmsLoading;
        delete button.dataset.phmsOriginalHtml;
        delete button.dataset.phmsWasDisabled;
    }

    function setRegionLoading(region, isLoading, message) {
        if (!region) {
            return;
        }

        const existingLoader = region.querySelector('[data-phms-region-loader="1"]');
        if (isLoading) {
            region.classList.add('phms-region-loading');
            if (!existingLoader) {
                const loader = document.createElement('div');
                loader.dataset.phmsRegionLoader = '1';
                loader.className = 'phms-inline-loader';
                loader.innerHTML =
                    '<span class="phms-spinner" aria-hidden="true"></span>' +
                    '<span>' + escapeHtml(message || 'Loading...') + '</span>';
                region.appendChild(loader);
            } else {
                const text = existingLoader.querySelector('span:last-child');
                if (text) {
                    text.textContent = message || 'Loading...';
                }
            }
            return;
        }

        region.classList.remove('phms-region-loading');
        if (existingLoader) {
            existingLoader.remove();
        }
    }

    function withLoading(options, requestFactory) {
        const opts = options || {};
        const button = opts.button || null;
        const region = opts.region || null;

        if (button) {
            setButtonLoading(button, opts.buttonText);
        }
        if (region) {
            setRegionLoading(region, true, opts.regionText);
        }
        if (opts.overlay) {
            showOverlay(opts.overlayText || 'Loading...');
        }

        return Promise.resolve()
            .then(requestFactory)
            .finally(() => {
                if (button) {
                    clearButtonLoading(button);
                }
                if (region) {
                    setRegionLoading(region, false);
                }
                if (opts.overlay) {
                    hideOverlay();
                }
            });
    }

    function bindAutoLoading() {
        document.querySelectorAll('form[data-loading-form]').forEach((form) => {
            form.addEventListener('submit', function (event) {
                if (event.defaultPrevented) {
                    return;
                }

                const submitter = event.submitter || form.querySelector('button[type="submit"], input[type="submit"]');
                if (submitter) {
                    setButtonLoading(submitter, submitter.dataset.loadingText || form.dataset.loadingButtonText || 'Please wait...');
                }

                showOverlay(form.dataset.loadingMessage || 'Loading...');
            });
            form.dataset.loadingBound = '1';
        });

        document.querySelectorAll('a[data-loading-link]').forEach((link) => {
            if (link.dataset.loadingBound === '1') {
                return;
            }

            link.addEventListener('click', function (event) {
                if (event.defaultPrevented) {
                    return;
                }
                if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
                    return;
                }

                const href = link.getAttribute('href') || '';
                if (!href || href.startsWith('#') || href.startsWith('javascript:')) {
                    return;
                }

                showOverlay(link.dataset.loadingMessage || 'Loading...');

                // Fallback for links that trigger downloads without navigation.
                const timeoutMs = Number(link.dataset.loadingTimeout || 12000);
                window.setTimeout(() => {
                    if (document.visibilityState === 'visible') {
                        hideOverlay();
                    }
                }, Number.isFinite(timeoutMs) ? timeoutMs : 12000);
            });
            link.dataset.loadingBound = '1';
        });
    }

    window.PHMSLoading = {
        showOverlay,
        hideOverlay,
        setButtonLoading,
        clearButtonLoading,
        setRegionLoading,
        withLoading
    };

    document.addEventListener('DOMContentLoaded', bindAutoLoading);
})();
