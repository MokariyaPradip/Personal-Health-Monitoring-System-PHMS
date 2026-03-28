let deleteMedicationId = null;
let deleteMedicationTriggerButton = null;

function confirmDeleteMedication(medicationId, triggerButton) {
    deleteMedicationId = medicationId;
    deleteMedicationTriggerButton = triggerButton;
    document.getElementById('confirmDeleteMedicationModal').style.display = 'block';
}

function closeConfirmDeleteMedicationModal() {
    document.getElementById('confirmDeleteMedicationModal').style.display = 'none';
    deleteMedicationId = null;
    deleteMedicationTriggerButton = null;
}

function executeDeleteMedication() {
    if (!deleteMedicationId) {
        showToast('Error: No medication selected', 'error');
        return;
    }

    const medicationId = deleteMedicationId;
    const triggerBtn = deleteMedicationTriggerButton;

    closeConfirmDeleteMedicationModal();
    deleteMedication(medicationId, triggerBtn);
}

function deleteMedication(medicationId, triggerButton) {
    const request = () => fetch(`/delete-medication/${medicationId}`, {
        method: 'DELETE',
        headers: {
            'X-CSRFToken': window.getCsrfToken()
        }
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                showToast('Medication deleted successfully');
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Refreshing medications...');
                }
                location.reload();
            } else {
                showToast(data.message || 'Failed to delete medication', 'error');
            }
        });

    const requestPromise = triggerButton && window.PHMSLoading
        ? window.PHMSLoading.withLoading({ button: triggerButton, buttonText: 'Deleting...' }, request)
        : request();

    requestPromise.catch(() => showToast('Error deleting medication. Please try again.', 'error'));
}

function openMedicationModal() {
    document.getElementById('medicationModal').style.display = 'block';
}

function closeMedicationModal() {
    document.getElementById('medicationModal').style.display = 'none';
    document.getElementById('medicationForm').reset();
}

function addMedication(event) {
    const medicineName = document.getElementById('medicine_name').value;
    const dosage = document.getElementById('dosage').value;
    const frequency = document.getElementById('frequency').value;
    const startDate = document.getElementById('start_date').value;
    const endDate = document.getElementById('end_date').value;
    const isCritical = document.getElementById('is_critical').checked;

    if (!medicineName || !dosage || !frequency || !startDate || !endDate) {
        showToast('Please fill in all fields', 'error');
        return;
    }

    const submitBtn = event ? event.target : null;
    if (submitBtn) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(submitBtn, 'Adding Medication...');
        } else {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Adding Medication...';
        }
    }

    fetch('/add-medication', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.getCsrfToken()
        },
        body: JSON.stringify({
            medicine_name: medicineName,
            dosage: dosage,
            frequency: frequency,
            start_date: startDate,
            end_date: endDate,
            is_critical: isCritical
        })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.message && data.message.toLowerCase().includes('added')) {
                showToast('Medication added successfully');
                closeMedicationModal();
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Refreshing medications...');
                }
                location.reload();
            } else {
                showToast(data.message || 'Failed to add medication', 'error');
                if (submitBtn) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(submitBtn);
                    } else {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Add Medication';
                    }
                }
            }
        })
        .catch(() => {
            showToast('Something went wrong. Please try again.', 'error');
            if (submitBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(submitBtn);
                } else {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Add Medication';
                }
            }
        });
}

function openMedicineModal() {
    document.getElementById('medicineModal').style.display = 'block';
}

function closeMedicineModal() {
    document.getElementById('medicineModal').style.display = 'none';
    document.getElementById('medicineForm').reset();
}

function addMedicine(event) {
    const name = document.getElementById('new_medicine_name').value;
    const type = document.getElementById('new_medicine_type').value;
    const purpose = document.getElementById('new_medicine_purpose').value;
    const remark = document.getElementById('new_medicine_remark').value;

    if (!name || !purpose) {
        showToast('Please fill required fields', 'error');
        return;
    }

    const submitBtn = event ? event.target : null;
    if (submitBtn) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(submitBtn, 'Adding Medicine...');
        } else {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Adding Medicine...';
        }
    }

    fetch('/add-medicine', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.getCsrfToken()
        },
        body: JSON.stringify({
            medicine_name: name,
            medicine_type: type,
            purpose: purpose,
            remark: remark
        })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                showToast('Medicine added successfully');
                closeMedicineModal();
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Refreshing medicines...');
                }
                location.reload();
            } else {
                showToast(data.message, 'error');
                if (submitBtn) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(submitBtn);
                    } else {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Add Medicine';
                    }
                }
            }
        })
        .catch(() => {
            showToast('Something went wrong. Please try again.', 'error');
            if (submitBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(submitBtn);
                } else {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Add Medicine';
                }
            }
        });
}

window.onclick = function (event) {
    const medicationModal = document.getElementById('medicationModal');
    const medicineModal = document.getElementById('medicineModal');
    const confirmDeleteModal = document.getElementById('confirmDeleteMedicationModal');

    if (event.target === medicationModal) {
        closeMedicationModal();
    }
    if (event.target === medicineModal) {
        closeMedicineModal();
    }
    if (event.target === confirmDeleteModal) {
        closeConfirmDeleteMedicationModal();
    }
};

document.addEventListener('DOMContentLoaded', function () {
    const today = new Date().toISOString().split('T')[0];

    const startDateInput = document.getElementById('start_date');
    const endDateInput = document.getElementById('end_date');

    if (startDateInput) {
        startDateInput.setAttribute('min', today);
    }
    if (endDateInput) {
        endDateInput.setAttribute('min', today);
    }

    const addMedicationBtn = document.getElementById('addMedicationBtn');
    if (addMedicationBtn) {
        addMedicationBtn.addEventListener('click', openMedicationModal);
    }

    document.addEventListener('click', function (event) {
        const actionEl = event.target.closest('[data-action]');
        if (!actionEl) {
            return;
        }

        const action = actionEl.getAttribute('data-action');
        if (action === 'confirm-delete-medication') {
            const medicationId = Number(actionEl.getAttribute('data-medication-id'));
            if (medicationId) {
                confirmDeleteMedication(medicationId, actionEl);
            }
            return;
        }

        if (action === 'close-confirm-delete-medication-modal') {
            closeConfirmDeleteMedicationModal();
            return;
        }

        if (action === 'execute-delete-medication') {
            executeDeleteMedication();
            return;
        }

        if (action === 'close-medication-modal') {
            closeMedicationModal();
            return;
        }

        if (action === 'submit-medication') {
            addMedication(event);
            return;
        }

        if (action === 'open-medicine-modal') {
            openMedicineModal();
            return;
        }

        if (action === 'close-medicine-modal') {
            closeMedicineModal();
            return;
        }

        if (action === 'submit-medicine') {
            addMedicine(event);
        }
    });
});
