(function () {
    if (typeof window.Chart !== 'undefined') {
        return;
    }

    function FallbackChart(canvasOrId) {
        const canvas = typeof canvasOrId === 'string'
            ? document.getElementById(canvasOrId)
            : canvasOrId;

        if (!canvas || typeof canvas.getContext !== 'function') {
            return;
        }

        const ctx = canvas.getContext('2d');
        if (!ctx) {
            return;
        }

        const width = canvas.width || canvas.clientWidth || 360;
        const height = canvas.height || canvas.clientHeight || 220;

        canvas.width = width;
        canvas.height = height;

        ctx.clearRect(0, 0, width, height);
        ctx.fillStyle = '#f8fafc';
        ctx.fillRect(0, 0, width, height);
        ctx.strokeStyle = '#d1d5db';
        ctx.strokeRect(0.5, 0.5, width - 1, height - 1);

        ctx.fillStyle = '#64748b';
        ctx.font = '14px Arial, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Chart library unavailable offline', width / 2, height / 2 - 6);
        ctx.fillText('Connect to the internet for full chart rendering.', width / 2, height / 2 + 16);
    }

    window.Chart = FallbackChart;
})();
