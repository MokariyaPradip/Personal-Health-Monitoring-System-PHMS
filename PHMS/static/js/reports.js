(function () {
    function announceForScreenReader(message) {
        const liveRegion = document.getElementById('reportLiveRegion');
        if (!liveRegion) {
            return;
        }
        // Clear first so repeated messages are announced reliably.
        liveRegion.textContent = '';
        window.setTimeout(() => {
            liveRegion.textContent = message;
        }, 20);
    }

    function setChartLoading(isLoading, message) {
        const loadingEl = document.getElementById('chartLoading');
        if (!loadingEl) {
            return;
        }
        if (message) {
            const textEl = loadingEl.querySelector('.chart-loading-text');
            if (textEl) {
                textEl.textContent = message;
            }
        }
        loadingEl.classList.toggle('is-active', Boolean(isLoading));
        loadingEl.setAttribute('aria-hidden', isLoading ? 'false' : 'true');
    }

    function setChartSummary(id, text) {
        const el = document.getElementById(id);
        if (!el) {
            return;
        }
        el.textContent = text;
    }

    function setDownloadLoading(isLoading, message) {
        const actions = document.querySelector('.report-actions');
        if (!actions) {
            return;
        }
        const status = actions.querySelector('.download-status');
        if (status && message) {
            const text = status.querySelector('.download-status-text');
            if (text) {
                text.textContent = message;
            }
        }
        actions.classList.toggle('is-loading', Boolean(isLoading));
        if (status) {
            status.setAttribute('aria-hidden', isLoading ? 'false' : 'true');
        }
    }

    async function fetchChartsData(container) {
        const reportType = container.getAttribute('data-report-type') || '';
        if (!reportType) {
            return null;
        }

        const params = new URLSearchParams();
        params.append('report_type', reportType);
        const feature = container.getAttribute('data-feature-filter') || 'all';
        if (feature) {
            params.append('feature', feature);
        }

        if (reportType === 'custom') {
            const startDate = container.getAttribute('data-start-date') || '';
            const endDate = container.getAttribute('data-end-date') || '';
            if (startDate) {
                params.append('start_date', startDate);
            }
            if (endDate) {
                params.append('end_date', endDate);
            }
        }

        try {
            setChartLoading(true, 'Loading charts...');
            const resp = await fetch(`/reports/charts?${params.toString()}`, { credentials: 'same-origin' });
            if (!resp.ok) {
                announceForScreenReader('Failed to load chart data.');
                setChartLoading(false, 'Unable to load charts.');
                return null;
            }
            const payload = await resp.json();
            setChartLoading(false);
            return payload;
        } catch (_err) {
            announceForScreenReader('Failed to load chart data.');
            setChartLoading(false, 'Unable to load charts.');
            return null;
        }
    }

    function setDateRange(preset) {
        const today = new Date();
        let startDate;
        const endDate = today;

        if (typeof preset === 'number') {
            startDate = new Date(today);
            startDate.setDate(today.getDate() - preset + 1);
        } else if (preset === 'month') {
            startDate = new Date(today.getFullYear(), today.getMonth(), 1);
        } else if (preset === 'year') {
            startDate = new Date(today.getFullYear(), 0, 1);
        } else {
            return;
        }

        const formatDate = (d) => d.toISOString().split('T')[0];
        const startInput = document.getElementById('start_date');
        const endInput = document.getElementById('end_date');

        if (startInput) {
            startInput.value = formatDate(startDate);
        }
        if (endInput) {
            endInput.value = formatDate(endDate);
        }

        syncDateConstraints();
    }

    function syncDateConstraints() {
        const today = new Date().toISOString().split('T')[0];
        const startInput = document.getElementById('start_date');
        const endInput = document.getElementById('end_date');

        if (startInput) {
            startInput.setAttribute('max', today);
        }
        if (endInput) {
            endInput.setAttribute('max', today);
        }

        if (startInput && endInput) {
            if (startInput.value) {
                endInput.setAttribute('min', startInput.value);
            } else {
                endInput.removeAttribute('min');
            }

            if (endInput.value) {
                startInput.setAttribute('max', endInput.value);
            }
        }

        if (endInput && endInput.value && endInput.value > today) {
            endInput.value = today;
        }

        if (startInput && startInput.value && startInput.value > today) {
            startInput.value = '';
        }

        if (startInput && endInput && startInput.value && endInput.value && startInput.value > endInput.value) {
            endInput.value = '';
        }

        if (startInput && endInput) {
            if (startInput.value) {
                endInput.setAttribute('min', startInput.value);
            } else {
                endInput.removeAttribute('min');
            }

            if (endInput.value) {
                startInput.setAttribute('max', endInput.value);
            } else {
                startInput.setAttribute('max', today);
            }
        }
    }

    function initReportDetails() {
        const details = document.querySelectorAll('.report-details');
        if (!details.length) {
            return;
        }

        const mq = window.matchMedia('(max-width: 900px)');
        const apply = () => {
            details.forEach((item) => {
                if (mq.matches) {
                    item.removeAttribute('open');
                } else {
                    item.setAttribute('open', '');
                }
            });
        };

        apply();
        if (typeof mq.addEventListener === 'function') {
            mq.addEventListener('change', apply);
        } else if (typeof mq.addListener === 'function') {
            mq.addListener(apply);
        }
    }

    function enhanceTablesForMobile() {
        const tables = document.querySelectorAll('.report-table');
        tables.forEach((table) => {
            const headers = [];
            const headerCells = table.querySelectorAll('thead th');
            
            headerCells.forEach((th) => {
                headers.push(th.textContent.trim());
            });

            if (headers.length === 0) {
                return;
            }

            const rows = table.querySelectorAll('tbody tr');
            rows.forEach((row) => {
                const cells = row.querySelectorAll('td');
                cells.forEach((cell, index) => {
                    if (index < headers.length) {
                        cell.setAttribute('data-label', headers[index]);
                    }
                });
            });
        });
    }

    function addTablePagination() {
        const defaultPageSize = 25;
        document.querySelectorAll('.report-table').forEach((table) => {
            const tbody = table.tBodies && table.tBodies[0];
            if (!tbody) return;
            const rows = Array.from(tbody.querySelectorAll('tr'));
            if (rows.length <= defaultPageSize) return;

            const tableWrap = table.closest('.table-wrap') || table.parentElement;
            let controls = tableWrap.querySelector('.table-pagination');
            if (controls) controls.remove();

            controls = document.createElement('div');
            controls.className = 'table-pagination';
            controls.setAttribute('tabindex', '0');
            controls.setAttribute('role', 'group');
            controls.setAttribute('aria-label', 'Table pagination controls');
            controls.innerHTML = `
                <div class="pagination-actions">
                    <button class="page-btn prev" type="button" aria-label="Previous page">Prev</button>
                    <span class="page-info">Page <span class="current-page">1</span> / <span class="total-pages">1</span></span>
                    <button class="page-btn next" type="button" aria-label="Next page">Next</button>
                </div>
                <div class="pagination-settings">
                    <label>Rows:</label>
                    <select class="page-size" aria-label="Rows per page">
                        <option>10</option>
                        <option selected>25</option>
                        <option>50</option>
                        <option>100</option>
                    </select>
                </div>
            `;

            tableWrap.appendChild(controls);

            const prevBtn = controls.querySelector('.prev');
            const nextBtn = controls.querySelector('.next');
            const pageSizeSelect = controls.querySelector('.page-size');

            function renderPage(pageSize, page) {
                const totalPages = Math.max(1, Math.ceil(rows.length / pageSize));
                page = Math.min(Math.max(1, page), totalPages);
                rows.forEach((r, idx) => {
                    r.style.display = (idx >= (page - 1) * pageSize && idx < page * pageSize) ? '' : 'none';
                });
                controls.querySelector('.current-page').textContent = page;
                controls.querySelector('.total-pages').textContent = totalPages;
                prevBtn.disabled = page <= 1;
                nextBtn.disabled = page >= totalPages;
                controls.dataset.currentPage = page;
                controls.dataset.pageSize = pageSize;
            }

            pageSizeSelect.addEventListener('change', function () {
                renderPage(Number(this.value), 1);
            });
            prevBtn.addEventListener('click', function () {
                const p = Number(controls.dataset.currentPage || 1);
                renderPage(Number(controls.dataset.pageSize || defaultPageSize), p - 1);
            });
            nextBtn.addEventListener('click', function () {
                const p = Number(controls.dataset.currentPage || 1);
                renderPage(Number(controls.dataset.pageSize || defaultPageSize), p + 1);
            });

            controls.addEventListener('keydown', function (event) {
                if (event.key === 'ArrowLeft' && !prevBtn.disabled) {
                    prevBtn.click();
                } else if (event.key === 'ArrowRight' && !nextBtn.disabled) {
                    nextBtn.click();
                }
            });

            // initialize
            renderPage(Number(pageSizeSelect.value), 1);
        });
    }

    // Server-side pagination for large datasets (fetches pages from /reports/records)
    function setupServerRecordsPagination() {
        const container = document.querySelector('.reports-container');
        if (!container) return false;
        const recordCount = Number(container.getAttribute('data-record-count') || 0);
        const threshold = 500; // switch to server-side when more than this many records
        if (recordCount <= threshold) return false;

        const table = document.getElementById('rawRecordsTable');
        if (!table) return false;

        const placeholder = table.parentElement.querySelector('.server-pagination-placeholder');
        if (!placeholder) return false;

        // build controls
        let controls = placeholder.querySelector('.table-pagination-server');
        if (controls) controls.remove();
        controls = document.createElement('div');
        controls.className = 'table-pagination table-pagination-server';
        controls.setAttribute('tabindex', '0');
        controls.setAttribute('role', 'group');
        controls.setAttribute('aria-label', 'Server-side table pagination controls');
        controls.innerHTML = `
            <div class="pagination-actions">
                <button class="page-btn prev" type="button" aria-label="Previous page">Prev</button>
                <span class="page-info">Page <span class="current-page">1</span> / <span class="total-pages">1</span></span>
                <button class="page-btn next" type="button" aria-label="Next page">Next</button>
            </div>
            <div class="pagination-settings">
                <label>Rows:</label>
                <select class="page-size" aria-label="Rows per page">
                    <option>25</option>
                    <option selected>50</option>
                    <option>100</option>
                </select>
            </div>
        `;
        placeholder.appendChild(controls);

        let status = placeholder.querySelector('.table-pagination-status');
        if (status) status.remove();
        status = document.createElement('div');
        status.className = 'table-pagination-status';
        status.setAttribute('role', 'status');
        status.setAttribute('aria-live', 'polite');
        status.innerHTML = `
            <span class="table-status-left">
                <span class="table-status-spinner" aria-hidden="true"></span>
                <span class="table-status-text">Loading records...</span>
            </span>
            <button class="table-retry-btn" type="button" hidden>Retry</button>
        `;
        placeholder.insertBefore(status, controls);

        const prevBtn = controls.querySelector('.prev');
        const nextBtn = controls.querySelector('.next');
        const pageSizeSelect = controls.querySelector('.page-size');
        const statusText = status.querySelector('.table-status-text');
        const retryBtn = status.querySelector('.table-retry-btn');

        function setControlsDisabled(disabled) {
            [prevBtn, nextBtn, pageSizeSelect].forEach((el) => {
                if (!el) return;
                el.disabled = disabled;
            });
        }

        function showStatus(message, isError) {
            if (statusText) {
                statusText.textContent = message;
            }
            if (retryBtn) {
                retryBtn.hidden = !isError;
            }
            status.classList.toggle('is-error', Boolean(isError));
            status.hidden = !message;
        }

        async function loadPage(page, per_page) {
            setControlsDisabled(true);
            showStatus('Loading records...', false);
            announceForScreenReader(`Loading records page ${page}`);
            const startInput = document.getElementById('start_date');
            const endInput = document.getElementById('end_date');
            const params = new URLSearchParams();
            if (startInput && startInput.value) params.append('start_date', startInput.value);
            if (endInput && endInput.value) params.append('end_date', endInput.value);
            params.append('page', String(page));
            params.append('per_page', String(per_page));

            const resp = await fetch(`/reports/records?${params.toString()}`, { credentials: 'same-origin' });
            if (!resp.ok) {
                console.error('Failed to load records', resp.statusText);
                announceForScreenReader('Failed to load records.');
                showStatus('Unable to load records. Please retry.', true);
                setControlsDisabled(false);
                return;
            }
            const payload = await resp.json();
            renderRecords(payload.items);
            const totalPages = Math.max(1, Math.ceil((payload.total || 0) / (payload.per_page || per_page)));
            controls.querySelector('.current-page').textContent = payload.page || 1;
            controls.querySelector('.total-pages').textContent = totalPages;
            prevBtn.disabled = (payload.page || 1) <= 1;
            nextBtn.disabled = (payload.page || 1) >= totalPages;
            controls.dataset.currentPage = payload.page || 1;
            controls.dataset.pageSize = payload.per_page || per_page;
            announceForScreenReader(`Loaded records page ${payload.page || 1} of ${totalPages}`);
            showStatus('', false);
            setControlsDisabled(false);
        }

        pageSizeSelect.addEventListener('change', function () { loadPage(1, Number(this.value)); });
        prevBtn.addEventListener('click', function () { const p = Number(controls.dataset.currentPage || 1); loadPage(p - 1, Number(controls.dataset.pageSize || pageSizeSelect.value)); });
        nextBtn.addEventListener('click', function () { const p = Number(controls.dataset.currentPage || 1); loadPage(p + 1, Number(controls.dataset.pageSize || pageSizeSelect.value)); });
        retryBtn.addEventListener('click', function () {
            const p = Number(controls.dataset.currentPage || 1);
            const size = Number(controls.dataset.pageSize || pageSizeSelect.value);
            loadPage(p, size);
        });

        controls.addEventListener('keydown', function (event) {
            if (event.key === 'ArrowLeft' && !prevBtn.disabled) {
                prevBtn.click();
            } else if (event.key === 'ArrowRight' && !nextBtn.disabled) {
                nextBtn.click();
            }
        });

        // initial load
        loadPage(1, Number(pageSizeSelect.value));
        return true;
    }

    function renderRecords(items) {
        const table = document.getElementById('rawRecordsTable');
        if (!table) return;
        const tbody = table.tBodies && table.tBodies[0];
        if (!tbody) return;
        tbody.innerHTML = '';
        items.forEach((it) => {
            const tr = document.createElement('tr');
            const mk = (v) => v === null || v === undefined ? '-' : v;
            tr.innerHTML = `
                <th scope="row">${mk(it.recorded_at)}</th>
                <td>${mk(it.heart_rate)}</td>
                <td>${mk(it.blood_pressure)}</td>
                <td>${mk(it.sugar)}</td>
                <td>${mk(it.temperature)}</td>
                <td>${mk(it.steps)}</td>
                <td>${mk(it.sleep_hours)}</td>
                <td>${mk(it.health_score)}</td>
                <td>${mk(it.data_source)}</td>
            `;
            tbody.appendChild(tr);
        });
        enhanceTablesForMobile();
    }

    function setupLoadingAnnouncements() {
        const form = document.querySelector('[data-loading-form]');
        if (form) {
            form.addEventListener('submit', function () {
                const message = form.getAttribute('data-loading-message') || 'Loading report.';
                announceForScreenReader(message);
            });
        }

        document.addEventListener('click', function (event) {
            const loadingLink = event.target.closest('[data-loading-link]');
            if (!loadingLink) {
                return;
            }
            const message = loadingLink.getAttribute('data-loading-message') || 'Loading.';
            announceForScreenReader(message);

            if (loadingLink.closest('.report-actions')) {
                setDownloadLoading(true, message.replace('Preparing', 'Preparing download'));
                if (window.__downloadLoadingTimer) {
                    window.clearTimeout(window.__downloadLoadingTimer);
                }
                window.__downloadLoadingTimer = window.setTimeout(function () {
                    setDownloadLoading(false);
                }, 8000);
            }
        });
    }

    async function renderCharts(container) {
        if (typeof Chart === 'undefined') {
            return;
        }

        const hasReportData = container.getAttribute('data-has-report-data') === '1';
        if (!hasReportData) {
            return;
        }

        const payload = await fetchChartsData(container);
        if (!payload) {
            return;
        }

        const riskIndicators = payload.risk_indicators || {};
        const trendAnalysis = payload.trend_analysis || {};
        const medicationAdherence = payload.medication_adherence || {};
        const mlDistribution = payload.ml_classifier_distribution || {};
        const timeseriesTrends = payload.timeseries_trends || {};

        const riskCounts = { normal: 0, warning: 0, critical: 0 };
        Object.values(riskIndicators || {}).forEach((item) => {
            const status = (item && item.status ? item.status : '').toLowerCase();
            if (status in riskCounts) {
                riskCounts[status] += 1;
            }
        });

        function toggleChartEmpty(key, isEmpty) {
            const el = document.querySelector(`[data-chart-empty="${key}"]`);
            if (!el) {
                return;
            }
            el.classList.toggle('is-visible', Boolean(isEmpty));
        }

        const riskTotal = riskCounts.normal + riskCounts.warning + riskCounts.critical;
        toggleChartEmpty('risk', riskTotal === 0);

        setChartSummary(
            'riskChartSummary',
            `Risk distribution: ${riskCounts.normal} normal, ${riskCounts.warning} warning, ${riskCounts.critical} critical.`
        );

        const taken = Number(medicationAdherence.total_taken_doses || 0);
        const total = Number(medicationAdherence.total_scheduled_doses || 0);
        const missed = Number(medicationAdherence.total_missed_doses || 0);
        const skipped = Number(medicationAdherence.total_skipped_doses || 0);
        const adherencePct = total > 0 ? Math.round((taken / total) * 100) : 0;
        const adherenceTotal = taken + missed + skipped;

        toggleChartEmpty('adherence', adherenceTotal === 0);

        setChartSummary(
            'adherenceChartSummary',
            `Medication adherence: ${taken} taken, ${missed} missed, ${skipped} skipped (${adherencePct}% adherence).`
        );

        const trendLabels = [];
        const trendValues = [];
        Object.entries(trendAnalysis || {}).forEach(([metric, stats]) => {
            trendLabels.push(metric.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
            const v = stats && stats.pct_change !== null ? Number(stats.pct_change) : 0;
            trendValues.push(Number.isFinite(v) ? v : 0);
        });

        toggleChartEmpty('trend', trendLabels.length === 0);

        if (trendLabels.length) {
            const summaryParts = trendLabels.map((label, idx) => {
                const value = trendValues[idx];
                const direction = value > 0 ? 'up' : value < 0 ? 'down' : 'flat';
                return `${label}: ${value}% ${direction}`;
            });
            setChartSummary('trendChartSummary', `Trend changes by metric: ${summaryParts.join('; ')}.`);
        } else {
            setChartSummary('trendChartSummary', 'Trend changes by metric: no data available.');
        }

        const palette = ['#3b82f6', '#16a34a', '#f59e0b', '#8b5cf6', '#ef4444', '#0ea5e9'];

        const riskCtx = document.getElementById('riskPieChart');
        if (riskCtx && riskTotal > 0) {
            new Chart(riskCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Normal', 'Warning', 'Critical'],
                    datasets: [{
                        data: [riskCounts.normal, riskCounts.warning, riskCounts.critical],
                        backgroundColor: ['#27ae60', '#f39c12', '#e74c3c'],
                        borderWidth: 1,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            });
        }

        const adherenceCtx = document.getElementById('adherencePieChart');
        if (adherenceCtx && adherenceTotal > 0) {
            new Chart(adherenceCtx, {
                type: 'pie',
                data: {
                    labels: ['Taken', 'Missed', 'Skipped'],
                    datasets: [{
                        data: [taken, missed, skipped],
                        backgroundColor: ['#3498db', '#e74c3c', '#f59e0b'],
                        borderWidth: 1,
                        borderColor: '#ffffff'
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'bottom' }
                    }
                }
            });
        }

        const trendCtx = document.getElementById('trendBarChart');
        if (trendCtx && trendLabels.length) {
            new Chart(trendCtx, {
                type: 'bar',
                data: {
                    labels: trendLabels,
                    datasets: [{
                        label: '% Change',
                        data: trendValues,
                        backgroundColor: trendValues.map((v) => (v >= 0 ? '#667eea' : '#ef4444')),
                        borderRadius: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {
                        y: {
                            ticks: {
                                callback: function (value) { return value + '%'; }
                            }
                        }
                    },
                    plugins: {
                        legend: { display: false }
                    }
                }
            });
        }

        const mlCtx = document.getElementById('mlDistributionChart');
        if (mlCtx) {
            const mlLabels = ['Low Risk', 'Medium Risk', 'High Risk'];
            const mlValues = mlLabels.map((label) => Number(mlDistribution[label] || 0));
            const mlTotal = mlValues.reduce((sum, value) => sum + value, 0);

            toggleChartEmpty('ml', mlTotal === 0);

            setChartSummary(
                'mlChartSummary',
                `ML risk prediction distribution: ${mlValues[0]} low, ${mlValues[1]} medium, ${mlValues[2]} high.`
            );

            if (mlTotal > 0) {
                new Chart(mlCtx, {
                    type: 'bar',
                    data: {
                        labels: mlLabels,
                        datasets: [{
                            label: 'Predictions',
                            data: mlValues,
                            backgroundColor: ['#22c55e', '#f59e0b', '#ef4444'],
                            borderRadius: 6
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false }
                        }
                    }
                });
            }
        }

        const timeseriesCtx = document.getElementById('timeseriesLineChart');
        if (timeseriesCtx) {
            const tsLabels = Array.isArray(timeseriesTrends.labels) ? timeseriesTrends.labels : [];
            const rawDatasets = Array.isArray(timeseriesTrends.datasets) ? timeseriesTrends.datasets : [];
            const tsDatasets = rawDatasets.map((item, idx) => {
                const color = palette[idx % palette.length];
                return {
                    label: item.label || item.metric || `Series ${idx + 1}`,
                    data: Array.isArray(item.values) ? item.values : [],
                    borderColor: color,
                    backgroundColor: color,
                    tension: 0.35,
                    spanGaps: true,
                    pointRadius: 2,
                    pointHoverRadius: 4,
                    borderWidth: 2,
                    fill: false
                };
            });

            toggleChartEmpty('timeseries', tsDatasets.length === 0);

            if (tsDatasets.length) {
                const seriesLabels = tsDatasets.map((series) => series.label).join(', ');
                const pointCount = tsLabels.length;
                setChartSummary(
                    'timeseriesChartSummary',
                    `Time-series trends with ${tsDatasets.length} series (${seriesLabels}) across ${pointCount} points.`
                );
            } else {
                setChartSummary('timeseriesChartSummary', 'Time-series trends: no data available.');
            }

            if (tsDatasets.length) {
                new Chart(timeseriesCtx, {
                    type: 'line',
                    data: {
                        labels: tsLabels,
                        datasets: tsDatasets
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: 'index',
                            intersect: false
                        },
                        scales: {
                            x: {
                                ticks: {
                                    maxTicksLimit: 8
                                }
                            }
                        },
                        plugins: {
                            legend: { position: 'bottom' }
                        }
                    }
                });
            }
        }
    }

    document.addEventListener('DOMContentLoaded', function () {
        const container = document.querySelector('.reports-container');
        if (!container) {
            return;
        }

        setupLoadingAnnouncements();
        enhanceTablesForMobile();
        // Prefer server-side pagination for large datasets; fallback to client-side
        const usedServer = setupServerRecordsPagination();
        if (!usedServer) {
            addTablePagination();
        }
        renderCharts(container);
        initReportDetails();

        const endInput = document.getElementById('end_date');
        const startInput = document.getElementById('start_date');

        syncDateConstraints();

        if (startInput) {
            startInput.addEventListener('change', function () {
                syncDateConstraints();
            });
        }

        if (endInput) {
            endInput.addEventListener('change', function () {
                syncDateConstraints();
            });
        }

        const printReportBtn = document.getElementById('printReportBtn');
        if (printReportBtn) {
            printReportBtn.addEventListener('click', function () {
                window.print();
            });
        }

        window.addEventListener('pagehide', function () {
            setDownloadLoading(false);
        });

        document.addEventListener('click', function (event) {
            const actionEl = event.target.closest('[data-action="set-date-range"]');
            if (!actionEl) {
                return;
            }

            const presetRaw = actionEl.getAttribute('data-preset');
            const numericPreset = Number(presetRaw);
            const preset = Number.isFinite(numericPreset) && presetRaw !== '' ? numericPreset : presetRaw;
            setDateRange(preset);
        });
    });

    window.setDateRange = setDateRange;
})();
