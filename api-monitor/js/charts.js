let responseChartInst = null;
let uptimeChartInst = null;

document.addEventListener('DOMContentLoaded', () => {
    // Shared Chart Configuration Settings
    Chart.defaults.color = '#9CA3AF'; // text-muted
    Chart.defaults.font.family = "'Inter', system-ui, -apple-system, sans-serif";

    // Response Time History Chart (Line)
    const ctxResponse = document.getElementById('responseTimeChart');
    if (ctxResponse) {
        responseChartInst = new Chart(ctxResponse, {
            type: 'line',
            data: {
                labels: [],
                datasets: []
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#e2e8f0',
                            font: { family: 'Inter', size: 12 },
                            usePointStyle: true,
                            pointStyle: 'circle',
                        },
                    },
                    tooltip: {
                        backgroundColor: '#1F2937',
                        titleColor: '#E5E7EB',
                        bodyColor: '#E5E7EB',
                        borderColor: '#374151',
                        borderWidth: 1,
                        padding: 10,
                        callbacks: {
                            label: function (context) {
                                return `${context.dataset.label}: ${context.parsed.y}ms`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'hour',
                            displayFormats: { hour: 'HH:mm' },
                        },
                        grid: {
                            color: '#1F2937', // border-color
                            drawBorder: false
                        },
                        ticks: {
                            font: { size: 11 }
                        }
                    },
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: '#1F2937', // border-color
                            drawBorder: false
                        },
                        ticks: {
                            font: { size: 11 },
                            callback: function (value) {
                                return value + 'ms';
                            }
                        }
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
            }
        });
    }

    // Uptime Percentage Chart (Area)
    const ctxUptime = document.getElementById('uptimeChart');
    if (ctxUptime) {
        // Create gradient for area fill
        const gradient = ctxUptime.getContext('2d').createLinearGradient(0, 0, 0, 300);
        gradient.addColorStop(0, 'rgba(16, 185, 129, 0.2)'); // success-color with opacity
        gradient.addColorStop(1, 'rgba(16, 185, 129, 0)');

        uptimeChartInst = new Chart(ctxUptime, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Uptime (%)',
                    data: [],
                    borderColor: '#10B981', // success-color
                    backgroundColor: gradient,
                    borderWidth: 2,
                    pointBackgroundColor: '#111827',
                    pointBorderColor: '#10B981',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    fill: true, // Area chart
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: '#1F2937',
                        titleColor: '#E5E7EB',
                        bodyColor: '#E5E7EB',
                        borderColor: '#374151',
                        borderWidth: 1,
                        padding: 10,
                        callbacks: {
                            label: function (context) {
                                return `Uptime: ${context.parsed.y}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        type: 'time',
                        time: {
                            unit: 'hour'
                        },
                        grid: {
                            color: '#1F2937',
                            drawBorder: false
                        },
                        ticks: {
                            font: { size: 11 }
                        }
                    },
                    y: {
                        grid: {
                            color: '#1F2937',
                            drawBorder: false
                        },
                        ticks: {
                            font: { size: 11 },
                            callback: function (value) {
                                return value + '%';
                            }
                        },
                        min: 90,
                        max: 100
                    }
                },
                interaction: {
                    intersect: false,
                    mode: 'index',
                },
            }
        });
    }

    // Listen for data from dashboard.js
    document.addEventListener('chartDataReady', (e) => {
        const { series } = e.detail;

        if (responseChartInst && series) {
            const colors = [
                { line: '#7C3AED', bg: 'rgba(124, 58, 237, 0.1)' },
                { line: '#06b6d4', bg: 'rgba(6,182,212,0.1)' },
                { line: '#10b981', bg: 'rgba(16,185,129,0.1)' },
                { line: '#f59e0b', bg: 'rgba(245,158,11,0.1)' },
                { line: '#ef4444', bg: 'rgba(239,68,68,0.1)' },
            ];

            const datasets = series.map((s, i) => {
                const color = colors[i % colors.length];
                return {
                    label: s.name,
                    data: s.data.map(d => ({
                        x: new Date(d.time),
                        y: d.response_time,
                    })),
                    borderColor: color.line,
                    backgroundColor: color.bg,
                    fill: false,
                    tension: 0.4,
                    borderWidth: 2,
                    pointBackgroundColor: '#111827',
                    pointBorderColor: color.line,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                };
            });

            responseChartInst.data.datasets = datasets;
            responseChartInst.update('default');
        }

        // Ideally we would get uptime series from backend too, 
        // but since it's not currently provided by `/api/dashboard/response-times` 
        // we'll leave it empty unless added later.
    });
});
