/**
 * navigation_controller.js - Mode Switching & Tab Navigation Controller
 * Handles switching between Smart Pilot and Advanced modes, tab switching, and chart resizing.
 * Nexus Quant Terminal
 */

export function switchTab(tabId) {
    const tabBtns = document.querySelectorAll('.tab-btn');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabBtns.forEach(btn => {
        if (btn.dataset.tab === tabId) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });

    tabPanes.forEach(pane => {
        if (pane.id === tabId) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });

    if (window.state) {
        window.state.currentTab = tabId;
    }

    // Chart resizing dispatching on tab activation
    setTimeout(() => {
        if (tabId === 'dashboard' && window.mainChart) {
            const el = document.getElementById('tv-chart');
            if (el && window.mainChart.applyOptions) {
                const targetChart = window.mainChart;
                targetChart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
            }
        } else if (tabId === 'smart-dashboard') {
            if (window.smartChart && window.smartChart.applyOptions) {
                const el = document.getElementById('smart-tv-chart');
                if (el) {
                    const targetChart = window.smartChart;
                    targetChart.applyOptions({ width: el.clientWidth, height: el.clientHeight });
                }
            }
            if (typeof window.createCorrelationHeatmap === 'function' && window.state && window.state.lastCorrelation) {
                window.createCorrelationHeatmap('smart-correlation-canvas', window.state.lastCorrelation.matrix, window.state.lastCorrelation.labels);
            }
        }
    }, 60);
}

export function initNavigation() {
    const modeSmartBtn = document.getElementById('mode-smart');
    const modeAdvancedBtn = document.getElementById('mode-advanced');

    if (modeSmartBtn) {
        modeSmartBtn.addEventListener('click', () => {
            switchTab('smart-dashboard');
        });
    }

    if (modeAdvancedBtn) {
        modeAdvancedBtn.addEventListener('click', () => {
            switchTab('dashboard');
        });
    }

    const tabButtons = document.querySelectorAll('.tabs-nav .tab-btn');
    tabButtons.forEach(btn => {
        btn.addEventListener('click', (e) => {
            const targetTab = e.currentTarget.dataset.tab;
            if (targetTab) {
                switchTab(targetTab);
            }
        });
    });
}
