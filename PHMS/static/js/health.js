let deleteEntryId = null;
let deleteTriggerButton = null;

function confirmDelete(entryId, triggerButton) {
    deleteEntryId = entryId;
    deleteTriggerButton = triggerButton;
    document.getElementById('confirmDeleteModal').style.display = 'block';
}

function closeConfirmModal() {
    document.getElementById('confirmDeleteModal').style.display = 'none';
    deleteEntryId = null;
    deleteTriggerButton = null;
}

function executeDelete() {
    if (!deleteEntryId) {
        showToast('Error: No entry selected', 'error');
        return;
    }

    const entryId = deleteEntryId;
    const triggerBtn = deleteTriggerButton;

    closeConfirmModal();
    deleteHealth(entryId, triggerBtn);
}

function deleteHealth(entryId, triggerButton) {
    const request = () => fetch(`/delete-health/${entryId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': window.getCsrfToken()
        }
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                showToast('Health record deleted successfully');
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Refreshing health history...');
                }
                location.reload();
            } else {
                showToast(data.message || 'Failed to delete entry', 'error');
            }
        });

    const requestPromise = triggerButton && window.PHMSLoading
        ? window.PHMSLoading.withLoading({ button: triggerButton, buttonText: 'Deleting...' }, request)
        : request();

    requestPromise.catch(() => showToast('Failed to delete entry', 'error'));
}

function openModal() {
    document.getElementById('healthModal').style.display = 'block';
}

function closeModal() {
    document.getElementById('healthModal').style.display = 'none';
    document.getElementById('healthForm').reset();
}

function addHealth(event) {
    const heartRate = document.getElementById('heart_rate').value;
    const temperature = document.getElementById('temperature').value;
    const steps = document.getElementById('steps').value;
    const sleep = document.getElementById('sleep_hours').value;
    const bp = document.getElementById('blood_pressure').value;
    const sugar = document.getElementById('sugar').value;

    if (!heartRate && !temperature && !steps && !sleep && !bp && !sugar) {
        showToast('Please enter at least one health detail', 'error');
        return;
    }

    if (heartRate && (heartRate < 30 || heartRate > 220)) {
        showToast('Heart rate must be between 30 and 220 bpm', 'error');
        return;
    }

    if (temperature && (temperature < 35 || temperature > 42)) {
        showToast('Temperature must be between 35\u00B0C and 42\u00B0C', 'error');
        return;
    }

    if (steps && (steps < 0 || steps > 60000)) {
        showToast('Steps must be between 0 and 60,000', 'error');
        return;
    }

    if (sleep && (sleep < 0 || sleep > 24)) {
        showToast('Sleep hours must be between 0 and 24', 'error');
        return;
    }

    if (sugar && (sugar < 40 || sugar > 600)) {
        showToast('Blood sugar must be between 40 and 600 mg/dL', 'error');
        return;
    }

    if (bp && (bp < 40 || bp > 250)) {
        showToast('Blood pressure must be between 40 and 250 mmHg', 'error');
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
        heart_rate: heartRate || null,
        temperature: temperature || null,
        steps: steps || null,
        sleep_hours: sleep || null,
        blood_pressure: bp || null,
        sugar: sugar || null
    };

    fetch('/add-health', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.getCsrfToken()
        },
        body: JSON.stringify(formData)
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.message && data.message.toLowerCase().includes('added')) {
                showToast('Health entry saved successfully!');
                closeModal();
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Refreshing health history...');
                }
                location.reload();
            } else {
                showToast(data.message || 'Failed to save health entry', 'error');
                if (submitBtn) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(submitBtn);
                    } else {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Submit';
                    }
                }
            }
        })
        .catch(() => {
            showToast('Something went wrong. Please try again', 'error');
            if (submitBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(submitBtn);
                } else {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Submit';
                }
            }
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
    const sourceFilter = document.getElementById('history-source-filter');

    if (addHealthEntryBtn) {
        addHealthEntryBtn.addEventListener('click', openModal);
    }

    if (sourceFilter) {
        sourceFilter.addEventListener('change', function () {
            if (this.form) {
                this.form.submit();
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

        if (action === 'close-health-modal') {
            closeModal();
            return;
        }

        if (action === 'submit-health-entry') {
            addHealth(event);
        }
    });
});
