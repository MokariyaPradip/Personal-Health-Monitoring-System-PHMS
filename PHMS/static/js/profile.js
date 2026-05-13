const ProfilePage = (() => {
    const selectors = {
        updateModal: '#updateModal',
        passwordModal: '#passwordModal',
        openUpdateBtn: '#openUpdateBtn',
        openPasswordBtn: '#openPasswordBtn',
        logoutBtn: '#logoutBtn',
    };

    let lastFocusedElement = null;
    let activeModal = null;

    function getCsrfTokenSafe() {
        if (typeof window.getCsrfToken === 'function') {
            return window.getCsrfToken();
        }
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta && meta.getAttribute('content')) {
            return meta.getAttribute('content');
        }
        const match = document.cookie.match(new RegExp('(^| )' + 'csrf_token' + '=([^;]+)'));
        return match ? decodeURIComponent(match[2]) : '';
    }

    function showToastSafe(message, type = 'success') {
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
            return;
        }
        // Fallback if shared notification util is not loaded.
        window.alert(message);
    }

    function loadingApi() {
        const fallback = {
            setButtonLoading(button, text) {
                if (!button) return;
                button.dataset.originalText = button.textContent;
                button.disabled = true;
                button.textContent = text;
            },
            clearButtonLoading(button) {
                if (!button) return;
                button.disabled = false;
                button.textContent = button.dataset.originalText || button.textContent;
            },
            showOverlay() {
                // no-op fallback
            },
        };
        return window.PHMSLoading || fallback;
    }

    async function parseResponseBody(response) {
        const contentType = (response.headers.get('content-type') || '').toLowerCase();
        if (contentType.includes('application/json')) {
            try {
                return await response.json();
            } catch (_err) {
                return null;
            }
        }

        try {
            const text = await response.text();
            return text ? { message: text } : null;
        } catch (_err) {
            return null;
        }
    }

    function getErrorMessage(payload, fallback) {
        if (payload && typeof payload.message === 'string' && payload.message.trim()) {
            return payload.message;
        }
        if (payload && payload.errors && typeof payload.errors === 'object') {
            const first = Object.values(payload.errors)[0];
            if (typeof first === 'string' && first.trim()) {
                return first;
            }
        }
        return fallback;
    }

    async function requestJson(url, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfTokenSafe(),
            ...(options.headers || {}),
        };

        const response = await fetch(url, { ...options, headers });
        if (!response.ok) {
            const errorPayload = await parseResponseBody(response);
            const fallback = `Request failed (${response.status}${response.statusText ? ` ${response.statusText}` : ''})`;
            const message = getErrorMessage(errorPayload, fallback);
            const error = new Error(message);
            error.data = errorPayload || { success: false, message };
            error.status = response.status;
            throw error;
        }

        const data = await parseResponseBody(response);
        if (!data || typeof data !== 'object') {
            const error = new Error('Server returned an unexpected response format');
            error.data = { success: false, message: 'Server returned an unexpected response format' };
            error.status = response.status;
            throw error;
        }

        return data;
    }

    function withButtonLoading(button, text, callback) {
        const loader = loadingApi();
        if (button) loader.setButtonLoading(button, text);
        return Promise.resolve()
            .then(callback)
            .finally(() => {
                if (button) loader.clearButtonLoading(button);
            });
    }

    function getFocusableElements(modal) {
        if (!modal) return [];
        return Array.from(modal.querySelectorAll('a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])'))
            .filter((el) => el.offsetWidth > 0 || el.offsetHeight > 0 || el === document.activeElement);
    }

    function handleKeyDown(e) {
        if (!activeModal) return;

        if (e.key === 'Escape' || e.key === 'Esc') {
            e.preventDefault();
            closeAll();
            return;
        }

        if (e.key !== 'Tab') return;
        const focusable = getFocusableElements(activeModal);
        if (focusable.length === 0) {
            e.preventDefault();
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey && document.activeElement === first) {
            e.preventDefault();
            last.focus();
            return;
        }
        if (!e.shiftKey && document.activeElement === last) {
            e.preventDefault();
            first.focus();
        }
    }

    function openModal(modalId) {
        closeAll();
        const modal = document.getElementById(modalId);
        if (!modal) return;

        lastFocusedElement = document.activeElement;
        modal.style.display = 'block';
        modal.setAttribute('aria-hidden', 'false');
        activeModal = modal;
        document.body.style.overflow = 'hidden';
        document.addEventListener('keydown', handleKeyDown);

        const focusable = getFocusableElements(modal);
        if (focusable.length) {
            focusable[0].focus();
            return;
        }

        const content = modal.querySelector('.modal-content');
        if (content) {
            content.setAttribute('tabindex', '-1');
            content.focus();
        }
    }

    function closeAll() {
        [selectors.updateModal, selectors.passwordModal].forEach((sel) => {
            const modal = document.querySelector(sel);
            if (!modal) return;
            modal.style.display = 'none';
            modal.setAttribute('aria-hidden', 'true');
        });
        activeModal = null;
        document.body.style.overflow = '';
        document.removeEventListener('keydown', handleKeyDown);
        if (lastFocusedElement && typeof lastFocusedElement.focus === 'function') {
            lastFocusedElement.focus();
        }
    }

    function clearFieldErrors() {
        ['username', 'gender', 'age', 'height', 'weight'].forEach((field) => {
            const el = document.getElementById('error_' + field);
            if (el) el.textContent = '';
        });
    }

    function clearPasswordErrors() {
        ['current_password', 'new_password', 'confirm_password'].forEach((field) => {
            const el = document.getElementById('error_' + field);
            if (el) el.textContent = '';
        });
    }

    function renderPasswordError(field, message) {
        const errEl = document.getElementById('error_' + field);
        if (errEl) errEl.textContent = message;
    }

    function renderFieldErrors(errors) {
        if (!errors || typeof errors !== 'object') return;

        Object.entries(errors).forEach(([field, message]) => {
            const errEl = document.getElementById('error_' + field);
            if (errEl) errEl.textContent = message;
        });

        const firstErrorField = Object.keys(errors)[0];
        const firstInput = document.getElementById('edit_' + firstErrorField);
        if (firstInput) firstInput.focus();
    }

    function setHtmlWithUnit(id, value, unit) {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerHTML = value !== null && value !== undefined && value !== ''
            ? `${value} <span class="unit">${unit}</span>`
            : 'N/A';
    }

    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function applyUpdatedProfile(updated) {
        if (!updated) return;

        if (updated.username) {
            setText('display_username', updated.username);
            setText('info_username', updated.username);
        }
        if (updated.gender !== undefined) {
            setText('info_gender', updated.gender || 'N/A');
        }
        if (updated.age !== undefined) {
            setText('info_age', updated.age ? `${updated.age} years` : 'N/A');
        }
        if (updated.height !== undefined) {
            setHtmlWithUnit('metric_height', updated.height, 'cm');
        }
        if (updated.weight !== undefined) {
            setHtmlWithUnit('metric_weight', updated.weight, 'kg');
        }
        if (updated.bmi !== undefined) {
            setHtmlWithUnit('metric_bmi', updated.bmi, 'kg/m²');
        }
    }

    function updateCompletionMeter(completionPercent) {
        const clamped = Math.max(0, Math.min(100, Number(completionPercent) || 0));
        const meter = document.querySelector('.completion-meter');
        const fill = document.querySelector('.completion-fill');
        const label = document.querySelector('.profile-overview-value');

        if (meter) meter.setAttribute('aria-valuenow', Math.round(clamped));
        if (fill) fill.style.width = `${clamped}%`;
        if (label) label.textContent = `${Math.round(clamped)}%`;

        const srOnly = meter ? meter.parentElement.querySelector('.sr-only') : null;
        if (srOnly) srOnly.textContent = `Profile is ${Math.round(clamped)}% complete`;
    }

    function buildProfilePayload() {
        return {
            username: document.getElementById('edit_username')?.value,
            gender: document.getElementById('edit_gender')?.value,
            age: parseInt(document.getElementById('edit_age')?.value, 10),
            height: parseFloat(document.getElementById('edit_height')?.value),
            weight: parseFloat(document.getElementById('edit_weight')?.value),
        };
    }

    function validateProfilePayload(payload) {
        return Boolean(payload.username && payload.gender && payload.age && payload.height && payload.weight);
    }

    async function updateProfile(event) {
        const payload = buildProfilePayload();
        clearFieldErrors();

        if (!validateProfilePayload(payload)) {
            showToastSafe('Please fill in all fields', 'error');
            return;
        }

        const submitBtn = event ? event.target : null;
        try {
            const data = await withButtonLoading(submitBtn, 'Updating...', () => requestJson('/update-profile', {
                method: 'PUT',
                body: JSON.stringify(payload),
            }));

            if (!data.success) {
                if (data.errors) {
                    renderFieldErrors(data.errors);
                } else {
                    showToastSafe(data.message || 'Failed to update profile', 'error');
                }
                return;
            }

            showToastSafe('Profile updated successfully');
            applyUpdatedProfile(data.updated || {});
            if (typeof data.completion === 'number') {
                updateCompletionMeter(data.completion);
            }
            closeAll();
        } catch (error) {
            if (error.data && error.data.errors) {
                renderFieldErrors(error.data.errors);
                showToastSafe(getErrorMessage(error.data, 'Validation failed'), 'error');
                return;
            }
            showToastSafe(error.message || 'Error updating profile. Please try again.', 'error');
        }
    }

    async function resetPassword(event) {
        const currentPassword = document.getElementById('current_password')?.value;
        const newPassword = document.getElementById('new_password')?.value;
        const repeat = document.getElementById('confirm_password')?.value;

        clearPasswordErrors();

        if (!currentPassword || !newPassword || !repeat) {
            if (!currentPassword) renderPasswordError('current_password', 'Current password is required');
            if (!newPassword) renderPasswordError('new_password', 'New password is required');
            if (!repeat) renderPasswordError('confirm_password', 'Please confirm your new password');
            showToastSafe('Please fill in all fields', 'error');
            return;
        }
        if (newPassword !== repeat) {
            renderPasswordError('confirm_password', 'Passwords do not match');
            showToastSafe('Passwords do not match. Please try again.', 'error');
            return;
        }
        if (newPassword.length < 8) {
            renderPasswordError('new_password', 'Password must be at least 8 characters');
            showToastSafe('Password must be at least 8 characters long', 'error');
            return;
        }

        const submitBtn = event ? event.target : null;
        try {
            const data = await withButtonLoading(submitBtn, 'Changing...', () => requestJson('/change-password', {
                method: 'PUT',
                body: JSON.stringify({
                    current_password: currentPassword,
                    new_password: newPassword,
                    confirm_password: repeat,
                }),
            }));

            if (data.success) {
                showToastSafe(data.message || 'Password changed successfully');
                closeAll();
                return;
            }
            renderPasswordError('current_password', data.message || 'Failed to reset password');
            showToastSafe(data.message || 'Failed to reset password', 'error');
        } catch (error) {
            if (error.data && error.data.errors) {
                const message = getErrorMessage(error.data, 'Failed to reset password');
                renderPasswordError('current_password', message);
                showToastSafe(message, 'error');
                return;
            }
            showToastSafe(error.message || 'Error resetting password. Please try again.', 'error');
        }
    }

    async function logoutUser(triggerButton) {
        try {
            await withButtonLoading(triggerButton, 'Logging out...', () => requestJson('/logout', {
                method: 'POST',
            }));
            loadingApi().showOverlay('Signing out...');
            window.location.href = '/login';
        } catch (error) {
            showToastSafe(error.message || 'Logout failed. Please try again.', 'error');
            if (triggerButton && !window.PHMSLoading) {
                triggerButton.textContent = '🚪 Logout';
            }
        }
    }

    function handleDocumentClick(event) {
        const actionEl = event.target.closest('[data-action]');
        if (!actionEl) return;

        const action = actionEl.getAttribute('data-action');
        if (action === 'close-all-profile-modals') {
            closeAll();
            return;
        }
        if (action === 'open-profile-update') {
            openModal('updateModal');
            return;
        }
        if (action === 'submit-profile-update') {
            updateProfile(event);
            return;
        }
        if (action === 'submit-password-change') {
            resetPassword(event);
        }
    }

    function handleBackdropClick(event) {
        const updateModal = document.querySelector(selectors.updateModal);
        const passwordModal = document.querySelector(selectors.passwordModal);
        if (event.target === updateModal || event.target === passwordModal) {
            closeAll();
        }
    }

    function init() {
        const openUpdateBtn = document.querySelector(selectors.openUpdateBtn);
        const openPasswordBtn = document.querySelector(selectors.openPasswordBtn);
        const logoutBtn = document.querySelector(selectors.logoutBtn);
        const updateForm = document.getElementById('updateForm');
        const passwordForm = document.getElementById('passwordForm');

        if (openUpdateBtn) openUpdateBtn.addEventListener('click', () => openModal('updateModal'));
        if (openPasswordBtn) openPasswordBtn.addEventListener('click', () => openModal('passwordModal'));
        if (logoutBtn) logoutBtn.addEventListener('click', () => logoutUser(logoutBtn));

        if (updateForm) {
            updateForm.addEventListener('submit', (event) => {
                event.preventDefault();
                updateProfile(event);
            });
        }

        if (passwordForm) {
            passwordForm.addEventListener('submit', (event) => {
                event.preventDefault();
                resetPassword(event);
            });
        }

        document.addEventListener('click', handleDocumentClick);
        window.addEventListener('click', handleBackdropClick);
    }

    return {
        init,
    };
})();

document.addEventListener('DOMContentLoaded', () => {
    ProfilePage.init();
});
