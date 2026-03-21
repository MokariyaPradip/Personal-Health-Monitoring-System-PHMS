(function () {
    const page = document.getElementById('smartwatchPage');
    if (!page) {
        return;
    }

    const provider = page.dataset.provider || 'google_fit';

    const connectBtn = document.getElementById('connectBtn');
    const syncBtn = document.getElementById('syncBtn');
    const disconnectBtn = document.getElementById('disconnectBtn');
    const refreshBtn = document.getElementById('refreshStatusBtn');

    const statusPill = document.getElementById('connectionStatusPill');
    const lastSyncedAtEl = document.getElementById('lastSyncedAt');
    const lastAttemptAtEl = document.getElementById('lastAttemptAt');
    const incrementalCursorEl = document.getElementById('incrementalCursor');
    const incrementalSinceEl = document.getElementById('incrementalSince');
    const errorsContainer = document.getElementById('errorsContainer');
    const statusRegion = document.getElementById('statusRegion');

    function fmt(value, fallback) {
        if (!value) {
            return fallback || 'N/A';
        }

        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return value;
        }

        return date.toLocaleString();
    }

    function setConnectedUi(isConnected) {
        if (statusPill) {
            statusPill.textContent = isConnected ? 'Connected' : 'Disconnected';
            statusPill.classList.toggle('connected', isConnected);
            statusPill.classList.toggle('disconnected', !isConnected);
        }

        if (connectBtn) {
            connectBtn.style.display = isConnected ? 'none' : 'inline-block';
        }

        if (syncBtn) {
            syncBtn.disabled = !isConnected;
        }

        if (disconnectBtn) {
            disconnectBtn.disabled = !isConnected;
        }
    }

    function renderErrors(accountError, syncError) {
        const messages = [];
        if (accountError) {
            messages.push({ source: 'Account', message: accountError });
        }
        if (syncError) {
            messages.push({ source: 'Sync', message: syncError });
        }

        if (!errorsContainer) {
            return;
        }

        if (!messages.length) {
            errorsContainer.innerHTML = '<p class="no-errors">No sync errors recorded recently.</p>';
            return;
        }

        const html = messages.map((item) => (
            `<li><span class="error-source">${item.source}</span><span class="error-message">${item.message}</span></li>`
        )).join('');

        errorsContainer.innerHTML = `<ul class="error-list">${html}</ul>`;
    }

    function applyStatusPayload(data) {
        if (!data || !data.success) {
            setConnectedUi(false);
            if (lastSyncedAtEl) {
                lastSyncedAtEl.textContent = 'Never synced';
            }
            if (lastAttemptAtEl) {
                lastAttemptAtEl.textContent = 'No attempts yet';
            }
            if (incrementalCursorEl) {
                incrementalCursorEl.textContent = 'N/A';
            }
            if (incrementalSinceEl) {
                incrementalSinceEl.textContent = 'N/A';
            }
            renderErrors(null, null);
            return;
        }

        const account = data.account || {};
        const syncState = data.sync_state || {};
        const isConnected = account.connection_status === 'connected';

        setConnectedUi(isConnected);

        if (lastSyncedAtEl) {
            lastSyncedAtEl.textContent = fmt(account.last_synced_at, 'Never synced');
        }
        if (lastAttemptAtEl) {
            lastAttemptAtEl.textContent = fmt(syncState.last_synced_at, 'No attempts yet');
        }
        if (incrementalCursorEl) {
            incrementalCursorEl.textContent = syncState.incremental_cursor || 'N/A';
        }
        if (incrementalSinceEl) {
            incrementalSinceEl.textContent = fmt(syncState.incremental_since, 'N/A');
        }

        renderErrors(account.last_error, syncState.last_error);
    }

    function fetchStatus(silent) {
        const doFetch = () => fetch(`/smartwatch/status/${provider}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': window.getCsrfToken()
            }
        })
            .then((res) => res.json())
            .then((data) => {
                applyStatusPayload(data);
                return data;
            })
            .catch(() => {
                if (!silent) {
                    showToast('Unable to refresh smartwatch status', 'error');
                }
            });

        if (!silent && window.PHMSLoading && statusRegion) {
            return window.PHMSLoading.withLoading({ region: statusRegion, regionText: 'Refreshing status...' }, doFetch);
        }

        return doFetch();
    }

    function connectSmartwatch() {
        if (!connectBtn) {
            return;
        }

        const request = () => fetch(`/smartwatch/authorize/${provider}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': window.getCsrfToken()
            }
        })
            .then((res) => res.json())
            .then((data) => {
                if (!data.success || !data.authorization_url) {
                    throw new Error(data.message || 'Unable to start provider authorization');
                }

                window.location.href = data.authorization_url;
            })
            .catch((err) => {
                showToast(err.message || 'Unable to connect smartwatch provider', 'error');
            });

        if (window.PHMSLoading) {
            window.PHMSLoading.withLoading({ button: connectBtn, buttonText: 'Redirecting...' }, request);
            return;
        }

        request();
    }

    function disconnectSmartwatch() {
        if (!disconnectBtn) {
            return;
        }

        showConfirmModal('Disconnect this smartwatch provider?', function () {
            const request = () => fetch(`/smartwatch/disconnect/${provider}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': window.getCsrfToken()
                },
                body: JSON.stringify({})
            })
                .then((res) => res.json())
                .then((data) => {
                    if (!data.success) {
                        throw new Error(data.message || 'Disconnect failed');
                    }

                    showToast('Smartwatch account disconnected');
                    fetchStatus(true);
                })
                .catch((err) => {
                    showToast(err.message || 'Failed to disconnect account', 'error');
                });

            if (window.PHMSLoading) {
                window.PHMSLoading.withLoading({ button: disconnectBtn, buttonText: 'Disconnecting...' }, request);
                return;
            }

            request();
        });
    }

    function syncNow() {
        if (!syncBtn) {
            return;
        }

        const request = () => fetch(`/smartwatch/sync-now/${provider}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.getCsrfToken()
            },
            body: JSON.stringify({})
        })
            .then((res) => res.json())
            .then((data) => {
                if (!data.success) {
                    throw new Error(data.message || 'Sync failed');
                }

                const result = data.sync_result || {};
                showToast(
                    `Sync complete: ${result.ingested_count || 0} ingested, ${result.deduplicated_count || 0} duplicate skipped`,
                    'success'
                );

                fetchStatus(true);
            })
            .catch((err) => {
                showToast(err.message || 'Sync failed. Please try again.', 'error');
            });

        if (window.PHMSLoading) {
            window.PHMSLoading.withLoading({ button: syncBtn, buttonText: 'Syncing...' }, request);
            return;
        }

        request();
    }

    function showCallbackToastFromQuery() {
        const params = new URLSearchParams(window.location.search);
        const status = params.get('status');
        const message = params.get('message');

        if (status && message) {
            showToast(message, status === 'success' ? 'success' : 'error');
            params.delete('status');
            params.delete('message');
            const qs = params.toString();
            const nextUrl = qs ? `${window.location.pathname}?${qs}` : window.location.pathname;
            window.history.replaceState({}, document.title, nextUrl);
        }
    }

    if (connectBtn) {
        connectBtn.addEventListener('click', connectSmartwatch);
    }
    if (disconnectBtn) {
        disconnectBtn.addEventListener('click', disconnectSmartwatch);
    }
    if (syncBtn) {
        syncBtn.addEventListener('click', syncNow);
    }
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function () {
            fetchStatus(false);
        });
    }

    showCallbackToastFromQuery();
    fetchStatus(true);
})();
