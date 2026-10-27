/**
 * modals.js - Pine Script v6 & Modal Interaction Hub
 * Modular coordinator delegating to export_modal.js and settings_modal.js
 * Nexus Quant Terminal
 */

import {
    detectStrategyType,
    buildRiskHeaderV6,
    buildExecutionFooterV6
} from './modals/settings_modal.js';

import {
    generatePineScriptV6,
    generatePineScriptV5,
    generateAIPrompt,
    showToast,
    togglePineScriptModal,
    copyPineScript,
    copyAIPrompt,
    downloadPineScriptFile
} from './modals/export_modal.js';

export {
    detectStrategyType,
    buildRiskHeaderV6,
    buildExecutionFooterV6,
    generatePineScriptV6,
    generatePineScriptV5,
    generateAIPrompt,
    showToast,
    togglePineScriptModal,
    copyPineScript,
    copyAIPrompt,
    downloadPineScriptFile
};

// Global browser bridge compatibility
if (typeof window !== 'undefined') {
    window.BinSimModules = window.BinSimModules || {};
    window.BinSimModules.modals = {
        detectStrategyType,
        generatePineScriptV6,
        generatePineScriptV5,
        generateAIPrompt,
        showToast,
        togglePineScriptModal,
        copyPineScript,
        copyAIPrompt,
        downloadPineScriptFile
    };
    window.detectStrategyType = detectStrategyType;
    window.generatePineScriptV6 = generatePineScriptV6;
    window.generatePineScriptV5 = generatePineScriptV5;
    window.generateAIPrompt = generateAIPrompt;
    window.showToast = showToast;
    window.togglePineScriptModal = togglePineScriptModal;
    window.copyPineScript = copyPineScript;
    window.copyAIPrompt = copyAIPrompt;
    window.downloadPineScriptFile = downloadPineScriptFile;
}
