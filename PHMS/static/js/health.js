let deleteEntryId = null;
let deleteTriggerButton = null;
let pendingDeleteState = null;
let bannerDismissTimer = null;
let bannerCountdownTimer = null;
let activeModalElement = null;
let activeModalReturnFocus = null;

const HEALTH_REFRESH_SELECTORS = [
    '#healthStatsGrid',
    '#smartwatchHealthBanner',
    '#lastEntrySection',
    '#healthInsightsSection',
    '#healthHistorySection'
];

function confirmDelete(entryId, triggerButton) {
    deleteEntryId = entryId;
    deleteTriggerButton = triggerButton;
    openAccessibleModal('confirmDeleteModal', '[data-action="execute-delete-entry"]', triggerButton);
}

function closeConfirmModal() {
    closeAccessibleModal('confirmDeleteModal');
    deleteEntryId = null;
    deleteTriggerButton = null;
}

function openModal() {
    openAccessibleModal('healthModal', '#heart_rate', document.getElementById('addHealthEntryBtn'));
}

function closeModal() {
    closeAccessibleModal('healthModal');
    document.getElementById('healthForm').reset();
    clearHealthFormErrors();
}

function getFocusableElements(container) {
    if (!container) {
        return [];
    }

    return Array.from(container.querySelectorAll([
        'button:not([disabled])',
        '[href]',
        'input:not([disabled])',
        'select:not([disabled])',
        'textarea:not([disabled])',
        '[tabindex]:not([tabindex="-1"])'
    ].join(','))).filter((element) => !element.hasAttribute('disabled') && element.offsetParent !== null);
}

function focusFirstElement(container, preferredSelector) {
    const preferredElement = preferredSelector ? container.querySelector(preferredSelector) : null;
    const focusableElements = getFocusableElements(container);
    const target = preferredElement || focusableElements[0] || container;
    if (target && typeof target.focus === 'function') {
        target.focus();
    }
}

function handleModalKeydown(event) {
    if (!activeModalElement) {
        return;
    }

    if (event.key === 'Escape') {
        event.preventDefault();
        if (activeModalElement.id === 'healthModal') {
            closeModal();
        } else if (activeModalElement.id === 'confirmDeleteModal') {
            closeConfirmModal();
        }
        return;
    }

    if (event.key !== 'Tab') {
        return;
    }

    const focusableElements = getFocusableElements(activeModalElement);
    if (focusableElements.length === 0) {
        event.preventDefault();
        activeModalElement.focus();
        return;
    }

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];
    const currentIndex = focusableElements.indexOf(document.activeElement);

    if (event.shiftKey && (document.activeElement === firstElement || currentIndex === -1)) {
        event.preventDefault();
        lastElement.focus();
        return;
    }

    if (!event.shiftKey && document.activeElement === lastElement) {
        event.preventDefault();
        firstElement.focus();
    }
}

function openAccessibleModal(modalId, preferredFocusSelector, returnFocusElement) {
    const modal = document.getElementById(modalId);
    if (!modal) {
        return;
    }

    if (activeModalElement) {
        closeAccessibleModal(activeModalElement.id);
    }

    activeModalReturnFocus = returnFocusElement || document.activeElement;
    activeModalElement = modal;
    modal.setAttribute('aria-hidden', 'false');
    modal.style.display = 'block';
    modal.removeEventListener('keydown', handleModalKeydown);
    modal.addEventListener('keydown', handleModalKeydown);
    document.body.classList.add('modal-open');

    window.setTimeout(() => {
        focusFirstElement(modal, preferredFocusSelector);
    }, 0);
}

function closeAccessibleModal(modalId) {
    const modal = document.getElementById(modalId);
    if (!modal) {
        return;
    }

    modal.setAttribute('aria-hidden', 'true');
    modal.style.display = 'none';
    modal.removeEventListener('keydown', handleModalKeydown);

    if (activeModalElement === modal) {
        activeModalElement = null;
        document.body.classList.remove('modal-open');
    }

    const returnFocusTarget = activeModalReturnFocus;
    activeModalReturnFocus = null;
    if (returnFocusTarget && typeof returnFocusTarget.focus === 'function') {
        window.setTimeout(() => returnFocusTarget.focus(), 0);
    }
}

function getHealthFieldDefinitions() {
    return {
        heart_rate: {
            label: 'Heart rate',
            min: 30,
            max: 220,
            step: 1,
            integer: true,
            unit: 'bpm'
        },
        temperature: {
            label: 'Temperature',
            min: 35,
            max: 42,
            step: 0.1,
            unit: '°C'
        },
        steps: {
            label: 'Steps',
            min: 0,
            max: 60000,
            step: 1,
            integer: true,
            unit: 'steps'
        },
        sleep_hours: {
            label: 'Sleep hours',
            min: 0,
            max: 24,
            step: 0.5,
            unit: 'hrs'
        },
        blood_pressure: {
            label: 'Blood pressure',
            min: 40,
            max: 250,
            step: 1,
            integer: true,
            unit: 'mmHg'
        },
        sugar: {
            label: 'Sugar',
            min: 40,
            max: 600,
            step: 1,
            integer: true,
            unit: 'mg/dL'
        }
    };
}

function getHealthFieldElements() {
    return Object.keys(getHealthFieldDefinitions()).reduce((elements, fieldName) => {
        elements[fieldName] = document.getElementById(fieldName);
        return elements;
    }, {});
}

function getHealthFieldErrorElement(fieldName) {
    return document.getElementById(`${fieldName}_error`);
}

function clearHealthFieldError(fieldName) {
    const input = document.getElementById(fieldName);
    const errorEl = getHealthFieldErrorElement(fieldName);
    if (input) {
        input.classList.remove('is-invalid');
        if (input.value) {
            input.classList.add('is-valid');
        } else {
            input.classList.remove('is-valid');
        }
        input.setCustomValidity('');
    }
    if (errorEl) {
        errorEl.textContent = '';
    }
}

function showHealthFieldError(fieldName, message) {
    const input = document.getElementById(fieldName);
    const errorEl = getHealthFieldErrorElement(fieldName);
    if (input) {
        input.classList.add('is-invalid');
        input.classList.remove('is-valid');
        input.setCustomValidity(message);
    }
    if (errorEl) {
        errorEl.textContent = message;
    }
}

function clearHealthFormErrors() {
    Object.keys(getHealthFieldDefinitions()).forEach((fieldName) => {
        clearHealthFieldError(fieldName);
    });
}

function parseHealthFieldValue(fieldName, rawValue) {
    if (rawValue === '' || rawValue === null || rawValue === undefined) {
        return null;
    }

    const numericValue = Number(rawValue);
    if (Number.isNaN(numericValue)) {
        return rawValue;
    }

    return numericValue;
}

function validateSingleHealthField(fieldName, rawValue) {
    const definition = getHealthFieldDefinitions()[fieldName];
    if (!definition) {
        return true;
    }

    const value = rawValue === '' ? null : Number(rawValue);
    if (value === null) {
        clearHealthFieldError(fieldName);
        return true;
    }

    if (!Number.isFinite(value)) {
        showHealthFieldError(fieldName, `${definition.label} must be a valid number`);
        return false;
    }

    if (definition.integer && !Number.isInteger(value)) {
        showHealthFieldError(fieldName, `${definition.label} must be a whole number`);
        return false;
    }

    if (value < definition.min || value > definition.max) {
        const unitSuffix = definition.unit ? ` ${definition.unit}` : '';
        showHealthFieldError(fieldName, `${definition.label} must be between ${definition.min} and ${definition.max}${unitSuffix}`);
        return false;
    }

    if (definition.step && definition.step !== 1) {
        const decimals = String(definition.step).includes('.') ? String(definition.step).split('.')[1].length : 0;
        const rounded = Number(value.toFixed(decimals));
        if (rounded !== value) {
            showHealthFieldError(fieldName, `${definition.label} must use increments of ${definition.step}`);
            return false;
        }
    }

    clearHealthFieldError(fieldName);
    return true;
}

function validateHealthForm() {
    const fields = getHealthFieldElements();
    const enteredValues = Object.entries(fields).map(([, input]) => (input ? input.value.trim() : ''));

    clearHealthFormErrors();

    if (!enteredValues.some((value) => value !== '')) {
        const message = 'Please enter at least one health detail';
        showToast(message, 'error');
        return { valid: false, message };
    }

    let firstInvalidField = null;
    Object.entries(fields).forEach(([fieldName, input]) => {
        if (!input) {
            return;
        }
        const isValid = validateSingleHealthField(fieldName, input.value.trim());
        if (!isValid && !firstInvalidField) {
            firstInvalidField = input;
        }
    });

    if (firstInvalidField) {
        firstInvalidField.focus();
        return { valid: false, message: 'Please fix the highlighted fields.' };
    }

    return { valid: true, message: '' };
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function clearHealthActionBannerTimers() {
    if (bannerDismissTimer) {
        window.clearTimeout(bannerDismissTimer);
        bannerDismissTimer = null;
    }
    if (bannerCountdownTimer) {
        window.clearInterval(bannerCountdownTimer);
        bannerCountdownTimer = null;
    }
}

function hideHealthActionBanner() {
    const banner = document.getElementById('healthActionBanner');
    if (!banner) {
        return;
    }
    clearHealthActionBannerTimers();
    banner.hidden = true;
    banner.innerHTML = '';
    banner.removeAttribute('style');
}

function showHealthActionBanner({ title, message, tone = 'success', actionLabel, actionAction, actionEntryId, countdownSeconds, autoHideMs }) {
    const banner = document.getElementById('healthActionBanner');
    if (!banner) {
        return null;
    }

    clearHealthActionBannerTimers();

    const toneStyles = {
        success: 'background:#eaf8f0;color:#0b7d4a;border-color:#b9e3ca;',
        warning: 'background:#fff4db;color:#8a5a00;border-color:#f0d28a;',
        error: 'background:#fdecea;color:#8a1f17;border-color:#f3b3ab;'
    };
    const isErrorTone = tone === 'error';

    banner.hidden = false;
    banner.setAttribute('role', isErrorTone ? 'alert' : 'status');
    banner.setAttribute('aria-live', isErrorTone ? 'assertive' : 'polite');
    banner.setAttribute('aria-atomic', 'true');
    banner.style.cssText = [
        'position:fixed',
        'right:20px',
        'bottom:20px',
        'z-index:10000',
        'display:flex',
        'align-items:center',
        'justify-content:space-between',
        'gap:1rem',
        'padding:0.9rem 1rem',
        'margin:0',
        'border:1px solid transparent',
        'border-radius:12px',
        'box-shadow:0 2px 8px rgba(0,0,0,0.08)',
        'flex-wrap:wrap',
        'width:min(420px, calc(100vw - 40px))',
        'box-sizing:border-box'
    ].join(';') + ';' + (toneStyles[tone] || toneStyles.success);

    banner.innerHTML = '';

    const copy = document.createElement('div');
    copy.style.display = 'flex';
    copy.style.flexDirection = 'column';
    copy.style.gap = '0.25rem';

    const titleEl = document.createElement('strong');
    titleEl.textContent = title;

    const messageEl = document.createElement('span');
    messageEl.innerHTML = escapeHtml(message);

    copy.appendChild(titleEl);
    copy.appendChild(messageEl);

    const actions = document.createElement('div');
    actions.style.display = 'inline-flex';
    actions.style.alignItems = 'center';
    actions.style.gap = '0.65rem';
    actions.style.flexWrap = 'wrap';

    let countdownEl = null;
    if (typeof countdownSeconds === 'number') {
        countdownEl = document.createElement('span');
        countdownEl.id = 'healthActionCountdown';
        countdownEl.style.fontSize = '0.85rem';
        countdownEl.style.fontWeight = '700';
        countdownEl.textContent = `${countdownSeconds}s`;
        actions.appendChild(countdownEl);

        let remaining = countdownSeconds;
        bannerCountdownTimer = window.setInterval(() => {
            remaining -= 1;
            if (!countdownEl) {
                return;
            }
            if (remaining > 0) {
                countdownEl.textContent = `${remaining}s`;
                return;
            }

            countdownEl.textContent = '0s';
            window.clearInterval(bannerCountdownTimer);
            bannerCountdownTimer = null;
        }, 1000);
    }

    if (actionLabel && actionAction) {
        const actionButton = document.createElement('button');
        actionButton.type = 'button';
        actionButton.className = 'btn-pagination';
        actionButton.dataset.action = actionAction;
        if (actionEntryId !== undefined && actionEntryId !== null) {
            actionButton.dataset.entryId = String(actionEntryId);
        }
        actionButton.textContent = actionLabel;
        actions.appendChild(actionButton);
    }

    banner.appendChild(copy);
    banner.appendChild(actions);

    if (autoHideMs) {
        bannerDismissTimer = window.setTimeout(() => {
            hideHealthActionBanner();
        }, autoHideMs);
    }

    return banner;
}

function getHealthPageUrl() {
    return `${window.location.pathname}${window.location.search}`;
}

function replaceSectionFromDocument(selector, sourceDocument) {
    const currentElement = document.querySelector(selector);
    const replacementElement = sourceDocument.querySelector(selector);

    if (!currentElement || !replacementElement) {
        return;
    }

    currentElement.replaceWith(replacementElement);
}

async function refreshHealthPageSections() {
    const scrollPosition = window.scrollY;
    const response = await fetch(getHealthPageUrl(), { credentials: 'same-origin' });
    if (!response.ok) {
        throw new Error('Failed to refresh health page');
    }

    const html = await response.text();
    const sourceDocument = new DOMParser().parseFromString(html, 'text/html');

    HEALTH_REFRESH_SELECTORS.forEach((selector) => {
        replaceSectionFromDocument(selector, sourceDocument);
    });

    window.scrollTo({ top: scrollPosition, behavior: 'auto' });
}

async function requestDeleteHealth(entryId) {
    const response = await fetch(`/delete-health/${entryId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': window.getCsrfToken()
        }
    });

    const data = await response.json().catch(() => ({}));
    return { response, data };
}

function restorePendingDeleteState() {
    if (!pendingDeleteState) {
        return;
    }

    const { entryCard } = pendingDeleteState;
    if (entryCard) {
        entryCard.hidden = false;
        entryCard.removeAttribute('data-pending-delete');
    }
    pendingDeleteState = null;
}

function undoPendingDelete() {
    if (!pendingDeleteState) {
        showToast('No pending delete to undo', 'error');
        return;
    }

    window.clearTimeout(pendingDeleteState.finalizeTimerId);
    clearHealthActionBannerTimers();
    restorePendingDeleteState();
    showHealthActionBanner({
        title: 'Delete undone',
        message: 'The health record is back in the list.',
        tone: 'success',
        autoHideMs: 2500
    });
}

async function finalizePendingDelete() {
    if (!pendingDeleteState) {
        return;
    }

    const { entryId, entryCard, triggerButton } = pendingDeleteState;
    pendingDeleteState = null;

    showHealthActionBanner({
        title: 'Deleting health record',
        message: 'Removing the entry now.',
        tone: 'warning'
    });

    try {
        const { response, data } = await requestDeleteHealth(entryId);
        if (!response.ok || !data.success) {
            if (entryCard) {
                entryCard.hidden = false;
                entryCard.removeAttribute('data-pending-delete');
            }
            showToast(data.message || 'Failed to delete entry', 'error');
            showHealthActionBanner({
                title: 'Delete failed',
                message: data.message || 'The health record could not be deleted.',
                tone: 'error',
                autoHideMs: 3500
            });
            return;
        }

        showHealthActionBanner({
            title: 'Health record deleted',
            message: 'The list has been refreshed without reloading the page.',
            tone: 'success',
            autoHideMs: 3000
        });
        await refreshHealthPageSections();
    } catch (error) {
        if (entryCard) {
            entryCard.hidden = false;
            entryCard.removeAttribute('data-pending-delete');
        }
        showToast('Failed to delete entry', 'error');
        showHealthActionBanner({
            title: 'Delete failed',
            message: 'Something went wrong while deleting the record.',
            tone: 'error',
            autoHideMs: 3500
        });
    } finally {
        if (triggerButton) {
            triggerButton.disabled = false;
        }
    }
}

function beginPendingDelete(entryId, triggerButton) {
    if (pendingDeleteState) {
        showToast('A delete is already pending. Undo it first.', 'error');
        return;
    }

    const entryCard = triggerButton.closest('.entry-card');
    if (!entryCard) {
        showToast('Unable to locate the selected entry', 'error');
        return;
    }

    entryCard.hidden = true;
    entryCard.dataset.pendingDelete = 'true';

    pendingDeleteState = {
        entryId,
        entryCard,
        triggerButton,
        finalizeTimerId: null
    };

    showHealthActionBanner({
        title: 'Delete queued',
        message: 'Undo within 5 seconds if you changed your mind.',
        tone: 'warning',
        actionLabel: 'Undo',
        actionAction: 'undo-pending-delete',
        actionEntryId: entryId,
        countdownSeconds: 5
    });

    pendingDeleteState.finalizeTimerId = window.setTimeout(() => {
        finalizePendingDelete();
    }, 5000);
}

function executeDelete() {
    if (!deleteEntryId) {
        showToast('Error: No entry selected', 'error');
        return;
    }

    const entryId = deleteEntryId;
    const triggerBtn = deleteTriggerButton;

    closeConfirmModal();

    if (triggerBtn) {
        triggerBtn.disabled = true;
    }

    beginPendingDelete(entryId, triggerBtn);
}

function readHealthFormPayload() {
    const heartRate = document.getElementById('heart_rate').value;
    const temperature = document.getElementById('temperature').value;
    const steps = document.getElementById('steps').value;
    const sleep = document.getElementById('sleep_hours').value;
    const bp = document.getElementById('blood_pressure').value;
    const sugar = document.getElementById('sugar').value;

    return {
        heartRate,
        temperature,
        steps,
        sleep,
        bp,
        sugar
    };
}

function validateHealthPayload(payload) {
    const values = Object.values(payload || {});
    if (!values.some((value) => value !== '' && value !== null && value !== undefined)) {
        return 'Please enter at least one health detail';
    }

    return null;
}

async function addHealth(event) {
    const healthForm = document.getElementById('healthForm');
    const validity = validateHealthForm();
    if (!validity.valid) {
        return;
    }

    if (healthForm && !healthForm.checkValidity()) {
        healthForm.reportValidity();
        return;
    }

    const payload = readHealthFormPayload();
    const validationError = validateHealthPayload(payload);
    if (validationError) {
        showToast(validationError, 'error');
        return;
    }

    const submitBtn = event ? event.target : null;
    if (submitBtn) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(submitBtn, 'Submitting...');
        } else {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Submitting...';
        }
    }

    const formData = {
        heart_rate: payload.heartRate || null,
        temperature: payload.temperature || null,
        steps: payload.steps || null,
        sleep_hours: payload.sleep || null,
        blood_pressure: payload.bp || null,
        sugar: payload.sugar || null
    };

    try {
        const response = await fetch('/add-health', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': window.getCsrfToken()
            },
            body: JSON.stringify(formData)
        });

        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.success) {
            const message = data.message || 'Failed to save health entry';
            showToast(message, 'error');
            if (data.errors) {
                showHealthActionBanner({
                    title: 'Save failed',
                    message: message,
                    tone: 'error',
                    autoHideMs: 3500
                });
            }
            return;
        }

        closeModal();
        showHealthActionBanner({
            title: 'Health entry saved',
            message: 'Your dashboard was updated without a full page reload.',
            tone: 'success',
            autoHideMs: 3000
        });

        await refreshHealthPageSections();
    } catch (error) {
        showToast('Something went wrong. Please try again', 'error');
        showHealthActionBanner({
            title: 'Save failed',
            message: 'The health entry could not be saved.',
            tone: 'error',
            autoHideMs: 3500
        });
    } finally {
        if (submitBtn) {
            if (window.PHMSLoading) {
                window.PHMSLoading.clearButtonLoading(submitBtn);
            } else {
                submitBtn.disabled = false;
                submitBtn.textContent = 'Submit';
            }
        }
    }
}

function attachHealthFormValidation() {
    const fields = getHealthFieldElements();
    Object.entries(fields).forEach(([fieldName, input]) => {
        if (!input) {
            return;
        }

        input.addEventListener('input', function () {
            validateSingleHealthField(fieldName, this.value.trim());
        });

        input.addEventListener('blur', function () {
            validateSingleHealthField(fieldName, this.value.trim());
        });
    });
}

window.onclick = function (event) {
    const healthModal = document.getElementById('healthModal');
    const confirmModal = document.getElementById('confirmDeleteModal');

    if (event.target === healthModal) {
        closeModal();
    } else if (event.target === confirmModal) {
        closeConfirmModal();
    }
};

document.addEventListener('DOMContentLoaded', function () {
    const addHealthEntryBtn = document.getElementById('addHealthEntryBtn');

    if (addHealthEntryBtn) {
        addHealthEntryBtn.addEventListener('click', openModal);
    }

    attachHealthFormValidation();

    const filterForm = document.querySelector('.health-filter-form');
    if (filterForm) {
        filterForm.addEventListener('submit', function (event) {
            const submitter = event.submitter;
            const isApplySubmit = submitter && submitter.classList.contains('health-filter-apply');
            const isExportSubmit = submitter && submitter.classList.contains('health-filter-export');
            if (!submitter || (!isApplySubmit && !isExportSubmit)) {
                event.preventDefault();
            }
        });
    }

    document.addEventListener('click', function (event) {
        const actionEl = event.target.closest('[data-action]');
        if (!actionEl) {
            return;
        }

        const action = actionEl.getAttribute('data-action');
        if (action === 'confirm-delete-entry') {
            const entryId = Number(actionEl.getAttribute('data-entry-id'));
            if (entryId) {
                confirmDelete(entryId, actionEl);
            }
            return;
        }

        if (action === 'close-confirm-modal') {
            closeConfirmModal();
            return;
        }

        if (action === 'execute-delete-entry') {
            executeDelete();
            return;
        }

        if (action === 'undo-pending-delete') {
            undoPendingDelete();
            return;
        }

        if (action === 'close-health-modal') {
            closeModal();
            return;
        }

        if (action === 'submit-health-entry') {
            addHealth(event);
        }
    });
});
