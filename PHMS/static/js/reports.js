(function () {
    function parseDataAttribute(el, attrName, fallback) {
        if (!el) {
            return fallback;
        }

        const raw = el.getAttribute(attrName);
        if (!raw) {
            return fallback;
        }

        try {
            return JSON.parse(raw);
        } catch (_err) {
            return fallback;
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
    }

    function renderCharts(container) {
        if (typeof Chart === 'undefined') {
            return;
        }

        const hasReportData = container.getAttribute('data-has-report-data') === '1';
        if (!hasReportData) {
            return;
        }

        const riskIndicators = parseDataAttribute(container, 'data-risk-indicators', {});
        const trendAnalysis = parseDataAttribute(container, 'data-trend-analysis', {});
        const medicationAdherence = parseDataAttribute(container, 'data-medication-adherence', {});

        const riskCounts = { normal: 0, warning: 0, critical: 0 };
        Object.values(riskIndicators || {}).forEach((item) => {
            const status = (item && item.status ? item.status : '').toLowerCase();
            if (status in riskCounts) {
                riskCounts[status] += 1;
            }
        });

        const taken = Number(medicationAdherence.total_taken_doses || 0);
        const total = Number(medicationAdherence.total_scheduled_doses || 0);
        const missed = Math.max(total - taken, 0);

        const trendLabels = [];
        const trendValues = [];
        Object.entries(trendAnalysis || {}).forEach(([metric, stats]) => {
            trendLabels.push(metric.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()));
            const v = stats && stats.pct_change !== null ? Number(stats.pct_change) : 0;
            trendValues.push(Number.isFinite(v) ? v : 0);
        });

        const riskCtx = document.getElementById('riskPieChart');
        if (riskCtx) {
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
        if (adherenceCtx) {
            new Chart(adherenceCtx, {
                type: 'pie',
                data: {
                    labels: ['Taken', 'Missed'],
                    datasets: [{
                        data: [taken, missed],
                        backgroundColor: ['#3498db', '#e74c3c'],
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
        if (trendCtx) {
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
    }

    document.addEventListener('DOMContentLoaded', function () {
        const container = document.querySelector('.reports-container');
        if (!container) {
            return;
        }

        renderCharts(container);

        const today = new Date().toISOString().split('T')[0];
        const endInput = document.getElementById('end_date');
        const startInput = document.getElementById('start_date');

        if (endInput) {
            endInput.setAttribute('max', today);
        }

        if (startInput) {
            startInput.addEventListener('change', function () {
                if (endInput && this.value) {
                    endInput.setAttribute('min', this.value);
                }
            });
        }

        const printReportBtn = document.getElementById('printReportBtn');
        if (printReportBtn) {
            printReportBtn.addEventListener('click', function () {
                window.print();
            });
        }

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
