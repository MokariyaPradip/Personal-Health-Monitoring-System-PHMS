(function () {
    const page = document.getElementById('smartwatchPage');
    if (!page) {
        return;
    }

    let currentProvider = page.dataset.provider || 'google_fit';
    const providerSelect = document.getElementById('providerSelect');
    const providerNameEl = document.getElementById('providerName');
    const providerLabelEl = document.getElementById('providerLabel');

    const connectBtn = document.getElementById('connectBtn');
    const syncBtn = document.getElementById('syncBtn');
    const disconnectBtn = document.getElementById('disconnectBtn');
    const refreshBtn = document.getElementById('refreshStatusBtn');
    const diagnosticsBtn = document.getElementById('preSyncDiagnosticsBtn');

    const statusPill = document.getElementById('connectionStatusPill');
    const lastSyncedAtEl = document.getElementById('lastSyncedAt');
    const lastAttemptAtEl = document.getElementById('lastAttemptAt');
    const incrementalCursorEl = document.getElementById('incrementalCursor');
    const incrementalSinceEl = document.getElementById('incrementalSince');
    const errorsContainer = document.getElementById('errorsContainer');
    const statusRegion = document.getElementById('statusRegion');
    const diagnosticsSummary = document.getElementById('diagnosticsSummary');

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

        const list = document.createElement('ul');
        list.className = 'error-list';

        messages.forEach((item) => {
            const listItem = document.createElement('li');

            const sourceEl = document.createElement('span');
            sourceEl.className = 'error-source';
            sourceEl.textContent = item.source;

            const messageEl = document.createElement('span');
            messageEl.className = 'error-message';
            messageEl.textContent = String(item.message);

            listItem.appendChild(sourceEl);
            listItem.appendChild(messageEl);
            list.appendChild(listItem);
        });

        errorsContainer.replaceChildren(list);
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

    function renderDiagnosticsSummary(data) {
        if (!diagnosticsSummary) {
            return;
        }

        if (!data || !data.success || !data.diagnostics) {
            diagnosticsSummary.textContent = 'Diagnostics unavailable for this provider right now.';
            return;
        }

        const diagnostics = data.diagnostics;
        const nonZero = Array.isArray(diagnostics.non_zero_metric_families)
            ? diagnostics.non_zero_metric_families
            : [];
        const totals = diagnostics.metric_point_totals || {};

        const nonZeroText = nonZero.length ? nonZero.join(', ') : 'none';
        const totalsText = Object.keys(totals).length
            ? Object.entries(totals).map(([k, v]) => `${k}:${v}`).join(' | ')
            : 'unavailable';

        diagnosticsSummary.textContent = `Available metric families: ${nonZeroText}. Point totals: ${totalsText}.`;
    }

    function runPreSyncDiagnostics() {
        const request = () => fetch(`/smartwatch/pre-sync-diagnostics/${currentProvider}`, {
            method: 'GET',
            headers: {
                'X-CSRFToken': window.getCsrfToken()
            }
        })
            .then((res) => res.json())
            .then((data) => {
                if (!data.success) {
                    throw new Error(data.message || 'Diagnostics failed');
                }

                renderDiagnosticsSummary(data);
                showToast('Pre-sync diagnostics loaded', 'info');
            })
            .catch((err) => {
                if (diagnosticsSummary) {
                    diagnosticsSummary.textContent = err.message || 'Diagnostics failed. Please try again.';
                }
                showToast(err.message || 'Diagnostics failed. Please try again.', 'error');
            });

        if (window.PHMSLoading && diagnosticsBtn) {
            window.PHMSLoading.withLoading({ button: diagnosticsBtn, buttonText: 'Running...' }, request);
            return;
        }

        request();
    }

    function fetchStatus(silent) {
        const doFetch = () => fetch(`/smartwatch/status/${currentProvider}`, {
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

        const request = () => fetch(`/smartwatch/authorize/${currentProvider}`, {
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
            const request = () => fetch(`/smartwatch/disconnect/${currentProvider}`, {
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

        const request = () => fetch(`/smartwatch/sync-now/${currentProvider}`, {
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

    function updateProviderQueryParam(providerId) {
        const url = new URL(window.location.href);
        url.searchParams.set('provider', providerId);
        window.history.replaceState({}, document.title, url.toString());
    }

    function switchProvider(providerId) {
        if (!providerId || providerId === currentProvider) {
            return;
        }

        currentProvider = providerId;
        page.dataset.provider = providerId;

        if (providerNameEl) {
            providerNameEl.textContent = providerId;
        }
        if (providerLabelEl && providerSelect) {
            const selectedOption = providerSelect.options[providerSelect.selectedIndex];
            if (selectedOption) {
                providerLabelEl.textContent = selectedOption.text;
            }
        }

        updateProviderQueryParam(providerId);
        if (diagnosticsSummary) {
            diagnosticsSummary.textContent = 'Run pre-sync diagnostics to preview provider metric availability.';
        }
        fetchStatus(false);
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
    if (diagnosticsBtn) {
        diagnosticsBtn.addEventListener('click', function () {
            runPreSyncDiagnostics();
        });
    }
    if (providerSelect) {
        providerSelect.addEventListener('change', function () {
            switchProvider(providerSelect.value);
        });
    }

    showCallbackToastFromQuery();
    fetchStatus(true);
})();
