let deleteMedicationId = null;
let deleteMedicationTriggerButton = null;

function getAllowedMedicationFrequencies() {
    return Array.isArray(window.ALLOWED_MEDICATION_FREQUENCIES)
        ? window.ALLOWED_MEDICATION_FREQUENCIES.map((frequency) => Number(frequency))
        : [1, 2, 3, 4, 6, 8, 12, 24, 48, 72, 96, 120, 240];
}

function isAllowedMedicationFrequency(value) {
    const frequency = Number(value);
    return Number.isInteger(frequency) && getAllowedMedicationFrequencies().includes(frequency);
}

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
                // Remove card from DOM
                removeMedicationCardFromDOM(medicationId);
                // Update overview counters
                decrementOverviewCountsAfterDelete(medicationId, data.medication || null);
            } else {
                showToast(data.message || 'Failed to delete medication', 'error');
            }
        });

    const requestPromise = triggerButton && window.PHMSLoading
        ? window.PHMSLoading.withLoading({ button: triggerButton, buttonText: 'Deleting...' }, request)
        : request();

    requestPromise.catch(() => showToast('Error deleting medication. Please try again.', 'error'));
}


function findMedicationCard(medicationId) {
    return document.querySelector(`.medication-card button.edit-btn[data-medication-id="${medicationId}"]`)?.closest('.medication-card');
}

function removeMedicationCardFromDOM(medicationId) {
    const card = findMedicationCard(medicationId);
    if (card && card.parentNode) {
        card.parentNode.removeChild(card);
    }

    // If list becomes empty, show no-data message
    const list = document.querySelector('.medications-list');
    if (!list || list.children.length === 0) {
        const section = document.querySelector('.medications-section');
        if (section) {
            const noData = document.createElement('div');
            noData.className = 'no-data-message';
            noData.innerHTML = '<p>📋 No medications assigned yet.</p><p class="subtitle">Click "Add Medication" to start tracking your medications.</p>';
            const existingList = document.querySelector('.medications-list');
            if (existingList) existingList.remove();
            section.appendChild(noData);
        }
    }

    // Keyboard toggle support for details buttons (Enter / Space)
    document.addEventListener('keydown', function (ev) {
        const active = document.activeElement;
        if (!active) return;
        if (!(active.matches && active.matches('button[data-action="toggle-medication-details"]'))) return;
        if (ev.key === 'Enter' || ev.key === ' ') {
            ev.preventDefault();
            toggleMedicationDetailsByButton(active);
        }
    });
    // Update header count
    const headerCountEl = document.getElementById('medications-header-count');
    if (headerCountEl) {
        const v = Number(headerCountEl.textContent || 0);
        headerCountEl.textContent = Math.max(0, v - 1);
    }
}

function formatDisplayDate(isoDate) {
    if (!isoDate) return 'N/A';
    const d = new Date(isoDate + 'T00:00:00');
    if (Number.isNaN(d.getTime())) return isoDate;
    const opts = { day: '2-digit', month: 'short', year: 'numeric' };
    return d.toLocaleDateString(undefined, opts);
}

function isEndingSoon(endDateStr) {
    if (!endDateStr) return false;
    const end = new Date(endDateStr + 'T00:00:00');
    const today = new Date();
    today.setHours(0,0,0,0);
    const diff = (end - today) / (1000 * 60 * 60 * 24);
    return diff >= 0 && diff <= 7;
}

function buildMedicationCardElement(med) {
    const card = document.createElement('div');
    card.className = 'medication-card';

    const statusBadge = med.current_status === 'ACTIVE' ? '<span class="status-badge active">🟢 Active</span>' : (med.current_status === 'FUTURE' ? '<span class="status-badge future">📅 Future</span>' : '<span class="status-badge expired">⏱️ Expired</span>');
    const criticalBadge = med.is_critical ? '<span class="status-badge critical" title="Critical Medication - Immediate email alerts sent if dose is missed">⚠️ CRITICAL</span>' : '';

    const startDisplay = formatDisplayDate(med.start_date);
    const endDisplay = formatDisplayDate(med.end_date);
    let duration = 'N/A';
    if (med.start_date && med.end_date) {
        try {
            const s = new Date(med.start_date + 'T00:00:00');
            const e = new Date(med.end_date + 'T00:00:00');
            const days = Math.round((e - s) / (1000 * 60 * 60 * 24)) + 1;
            duration = `${days} day(s)`;
        } catch (err) {
            duration = 'N/A';
        }
    }

    card.innerHTML = `
        <div class="med-card-header">
            <div class="med-card-title-row">
                <h3 class="med-title">${escapeHtml(med.medicine_name || '')}</h3>
                <div class="med-card-actions">
                    <button class="edit-btn" type="button" title="Edit medication" aria-label="Edit medication ${escapeHtml(med.medicine_name || '')}" data-action="open-edit-medication-modal"
                        data-medication-id="${med.medication_id}"
                        data-medicine-name="${escapeHtml(med.medicine_name || '')}"
                        data-dosage="${escapeHtml(med.dosage || '')}"
                        data-frequency="${med.frequency}"
                        data-start-date="${med.start_date || ''}"
                        data-end-date="${med.end_date || ''}"
                        data-is-critical="${med.is_critical}"
                        data-current-status="${med.current_status}"><span aria-hidden="true">✏️</span><span class="sr-only">Edit medication</span></button>
                    <button class="delete-btn" type="button" title="Delete medication" aria-label="Delete medication ${escapeHtml(med.medicine_name || '')}" data-action="confirm-delete-medication" data-medication-id="${med.medication_id}"><span aria-hidden="true">🗑️</span><span class="sr-only">Delete medication</span></button>
                </div>
            </div>

            <div class="med-card-badges">
                ${statusBadge}
                ${criticalBadge}
            </div>
        </div>

        <div class="med-card-body">
            <div class="med-card-purpose">
                <span class="detail-label">Purpose</span>
                <span class="detail-value">${escapeHtml(med.medicine_purpose || 'N/A')}</span>
            </div>

            <div class="med-card-stats" aria-label="Medication summary">
                <div class="med-stat">
                    <span class="stat-label">Dosage</span>
                    <span class="stat-value">${escapeHtml(med.dosage || '')}</span>
                </div>
                <div class="med-stat">
                    <span class="stat-label">Frequency</span>
                    <span class="stat-value">${med.frequency}x / day</span>
                </div>
            </div>

            <div class="med-card-summary-footer">
                <button class="toggle-btn" type="button" data-action="toggle-medication-details" aria-expanded="false" aria-controls="med-details-${med.medication_id}">Details</button>
            </div>

            <div id="med-details-${med.medication_id}" class="med-details-collapsible" hidden>
                <div class="med-card-footer">
                    <div class="med-date-item">
                        <span class="detail-label">Start</span>
                        <span class="detail-value">${startDisplay}</span>
                    </div>
                    <div class="med-date-item">
                        <span class="detail-label">End</span>
                        <span class="detail-value">${endDisplay}</span>
                    </div>
                    <div class="med-note">${escapeHtml(med.medicine_remark || 'N/A')}</div>
                </div>
            </div>
        </div>
    `;

    return card;
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function incrementOverviewCountsAfterAdd(med) {
    const headerCountEl = document.getElementById('medications-header-count');
    if (headerCountEl) headerCountEl.textContent = Number(headerCountEl.textContent || 0) + 1;

    const totalEl = document.getElementById('overview-total');
    if (totalEl) totalEl.textContent = Number(totalEl.textContent || 0) + 1;

    if (med.current_status === 'ACTIVE') {
        const el = document.getElementById('overview-active'); if (el) el.textContent = Number(el.textContent || 0) + 1;
    }
    if (med.is_critical) {
        const el = document.getElementById('overview-critical'); if (el) el.textContent = Number(el.textContent || 0) + 1;
    }
    if (isEndingSoon(med.end_date)) {
        const el = document.getElementById('overview-ending-soon'); if (el) el.textContent = Number(el.textContent || 0) + 1;
    }
}

function decrementOverviewCountsAfterDelete(medicationId, med) {
    // med may be null; best-effort decrement based on data attributes in DOM
    const headerCountEl = document.getElementById('medications-header-count');
    if (headerCountEl) headerCountEl.textContent = Math.max(0, Number(headerCountEl.textContent || 0) - 1);

    const totalEl = document.getElementById('overview-total');
    if (totalEl) totalEl.textContent = Math.max(0, Number(totalEl.textContent || 0) - 1);

    // Try to infer active/critical/ending from removed DOM if med not provided
    let infer = med;
    if (!infer) {
        const card = findMedicationCard(medicationId);
        if (card) {
            infer = {
                current_status: card.querySelector('.status-badge')?.textContent?.includes('Active') ? 'ACTIVE' : (card.querySelector('.status-badge')?.textContent?.includes('Future') ? 'FUTURE' : 'EXPIRED'),
                is_critical: !!card.querySelector('.status-badge.critical'),
                end_date: card.querySelector('[data-end-date]')?.getAttribute('data-end-date') || null,
            };
        }
    }

    if (infer) {
        if (infer.current_status === 'ACTIVE') { const el = document.getElementById('overview-active'); if (el) el.textContent = Math.max(0, Number(el.textContent || 0) - 1); }
        if (infer.is_critical) { const el = document.getElementById('overview-critical'); if (el) el.textContent = Math.max(0, Number(el.textContent || 0) - 1); }
        if (isEndingSoon(infer.end_date)) { const el = document.getElementById('overview-ending-soon'); if (el) el.textContent = Math.max(0, Number(el.textContent || 0) - 1); }
    }
}

function replaceMedicationCardInDOM(med) {
    const existing = findMedicationCard(med.medication_id);
    const newCard = buildMedicationCardElement(med);
    if (existing && existing.parentNode) {
        existing.parentNode.replaceChild(newCard, existing);
    } else {
        // Append into list
        let list = document.querySelector('.medications-list');
        if (!list) {
            const section = document.querySelector('.medications-section');
            if (section) {
                list = document.createElement('div');
                list.className = 'medications-list';
                // Remove any no-data messages
                const noData = section.querySelector('.no-data-message');
                if (noData) noData.remove();
                section.appendChild(list);
            }
        }
        if (list) list.appendChild(newCard);
    }

    // Update overview counts conservatively by recomputing totals if available
}

function toggleMedicationDetailsByButton(btn) {
    const targetId = btn.getAttribute('aria-controls');
    if (!targetId) return;
    const details = document.getElementById(targetId);
    if (!details) return;
    const expanded = btn.getAttribute('aria-expanded') === 'true';

    if (expanded) {
        // collapse
        details.style.maxHeight = details.scrollHeight + 'px';
        details.offsetHeight; // force reflow
        details.style.transition = 'max-height 220ms ease, opacity 180ms ease';
        details.style.maxHeight = '0';
        details.style.opacity = '0';
        btn.setAttribute('aria-expanded', 'false');
        try { btn.textContent = 'Details'; } catch (e) {}
        window.setTimeout(() => {
            details.hidden = true;
            details.style.maxHeight = '';
            details.style.opacity = '';
            details.style.transition = '';
        }, 240);
    } else {
        // expand
        details.hidden = false;
        details.style.maxHeight = '0';
        details.style.opacity = '0';
        details.offsetHeight; // force reflow
        details.style.transition = 'max-height 300ms ease, opacity 220ms ease';
        details.style.maxHeight = details.scrollHeight + 'px';
        details.style.opacity = '1';
        btn.setAttribute('aria-expanded', 'true');
        try { btn.textContent = 'Details'; } catch (e) {}
        window.setTimeout(() => {
            details.style.maxHeight = '';
            details.style.opacity = '';
            details.style.transition = '';
        }, 320);
    }
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

    if (!isAllowedMedicationFrequency(frequency)) {
        showToast('Please choose a supported frequency from the list', 'error');
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
            if (data && data.success) {
                showToast(data.message || 'Medication added successfully');
                closeMedicationModal();
                // Insert new medication card into DOM
                if (data.medication) {
                    replaceMedicationCardInDOM(data.medication);
                    incrementOverviewCountsAfterAdd(data.medication);
                }
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

function openEditMedicationModal(medicationId, medicineName, dosage, frequency, startDate, endDate, isCritical, currentStatus) {
    document.getElementById('edit_medication_id').value = medicationId;
    document.getElementById('edit_current_status').value = currentStatus || 'ACTIVE';
    document.getElementById('edit_medicine_name').value = medicineName;
    document.getElementById('edit_dosage').value = dosage;
    document.getElementById('edit_frequency').value = frequency;
    document.getElementById('edit_start_date').value = startDate;
    document.getElementById('edit_end_date').value = endDate;
    document.getElementById('edit_is_critical').checked = isCritical === 'true' || isCritical === true;
    
    // Display status information and restrictions
    updateStatusRestrictions(currentStatus);
    
    document.getElementById('editMedicationModal').style.display = 'block';
}

function updateStatusRestrictions(status) {
    const statusInfo = document.getElementById('editStatusInfo');
    const statusLabel = document.getElementById('editStatusLabel');
    const restrictionsDiv = document.getElementById('editRestrictions');
    const medicineName = document.getElementById('edit_medicine_name');
    const dosage = document.getElementById('edit_dosage');
    const frequency = document.getElementById('edit_frequency');
    const startDate = document.getElementById('edit_start_date');
    
    statusInfo.style.display = 'block';
    
    const statusStyles = {
        'ACTIVE': { label: '🟢 Active', color: '#4CAF50', restrictions: [] },
        'FUTURE': { label: '📅 Future', color: '#2196F3', restrictions: [] },
        'EXPIRED': { label: '⏱️ Expired', color: '#FF9800', restrictions: [] }
    };
    
    const config = statusStyles[status] || statusStyles['ACTIVE'];
    statusLabel.textContent = config.label;
    statusLabel.style.color = config.color;
    statusInfo.style.borderLeftColor = config.color;
    
    // Build restrictions list based on status and update per-field notes and visual states
    let restrictionsHTML = '';

    // Helper to reset field visuals/notes
    function resetField(fieldEl, noteEl) {
        if (!fieldEl) return;
        fieldEl.disabled = false;
        fieldEl.classList.remove('locked-field');
        fieldEl.removeAttribute('aria-disabled');
        fieldEl.style.opacity = '';
        if (noteEl) noteEl.textContent = '';
    }

    const noteMedicine = document.getElementById('note_edit_medicine_name');
    const noteDosage = document.getElementById('note_edit_dosage');
    const noteFrequency = document.getElementById('note_edit_frequency');
    const noteStart = document.getElementById('note_edit_start_date');
    const noteEnd = document.getElementById('note_edit_end_date');
    const noteCritical = document.getElementById('note_edit_is_critical');

    // Reset all fields first
    [medicineName, dosage, frequency, startDate, document.getElementById('edit_end_date'), document.getElementById('edit_is_critical')].forEach((el) => {
        if (el) {
            el.classList.remove('locked-field');
            el.removeAttribute('aria-disabled');
            el.style.opacity = '';
        }
    });
    [noteMedicine, noteDosage, noteFrequency, noteStart, noteEnd, noteCritical].forEach((n) => { if (n) n.textContent = ''; });

    if (status === 'EXPIRED') {
        restrictionsHTML = '<strong>⚠️ This medication has expired. Edit restrictions apply:</strong><ul style="margin: 5px 0; padding-left: 20px;">' +
            '<li><span style="color: #d32f2f;">❌ Cannot change: Medicine, Dosage, Frequency, Start Date</span></li>' +
            '<li><span style="color: #388e3c;">✅ Can change: End Date (to extend), Critical flag</span></li>' +
            '<li>Expired medications cannot have new logs created</li></ul>';

        // Disable restricted fields with clear visual 'locked' state and notes
        [[medicineName, noteMedicine, 'Cannot change: medication is expired'], [dosage, noteDosage, 'Cannot change: medication is expired'], [frequency, noteFrequency, 'Cannot change: medication is expired'], [startDate, noteStart, 'Cannot change: medication is expired']].forEach(([el, note, msg]) => {
            if (el) {
                el.disabled = true;
                el.classList.add('locked-field');
                el.setAttribute('aria-disabled', 'true');
            }
            if (note) note.textContent = msg;
        });

        if (noteEnd) noteEnd.textContent = 'Editable: extend the end date to reactivate';
        if (noteCritical) noteCritical.textContent = 'Editable: toggle critical flag';
    } else if (status === 'FUTURE') {
        restrictionsHTML = '<strong>📋 This medication starts in the future:</strong><ul style="margin: 5px 0; padding-left: 20px;">' +
            '<li><span style="color: #388e3c;">✅ Can change: All fields</span></li>' +
            '<li>No medication logs have been created yet</li>' +
            '<li>If you set start date to today, logs will be created immediately</li></ul>';

        // All fields editable — clear notes to 'Editable'
        if (noteMedicine) noteMedicine.textContent = 'Editable';
        if (noteDosage) noteDosage.textContent = 'Editable';
        if (noteFrequency) noteFrequency.textContent = 'Editable';
        if (noteStart) noteStart.textContent = 'Editable';
        if (noteEnd) noteEnd.textContent = 'Editable';
        if (noteCritical) noteCritical.textContent = 'Editable';
    } else { // ACTIVE
        restrictionsHTML = '<strong>⚠️ This medication is currently active:</strong><ul style="margin: 5px 0; padding-left: 20px;">' +
            '<li><span style="color: #d32f2f;">❌ Cannot change: Medicine, Start Date</span></li>' +
            '<li><span style="color: #388e3c;">✅ Can change: Dosage, Frequency, End Date, Critical flag</span></li>' +
            '<li>Frequency changes only affect today\'s pending doses</li>' +
            '<li>Reducing end date will delete pending logs after that date</li></ul>';

        // Disable medicine and start date; add explanatory notes
        if (medicineName) {
            medicineName.disabled = true;
            medicineName.classList.add('locked-field');
            medicineName.setAttribute('aria-disabled', 'true');
        }
        if (startDate) {
            startDate.disabled = true;
            startDate.classList.add('locked-field');
            startDate.setAttribute('aria-disabled', 'true');
        }
        if (noteMedicine) noteMedicine.textContent = 'Locked: cannot change medicine for active prescriptions';
        if (noteStart) noteStart.textContent = 'Locked: start date must remain in the past or today';

        // Editable fields
        if (dosage) { dosage.disabled = false; dosage.classList.remove('locked-field'); if (noteDosage) noteDosage.textContent = 'Editable'; }
        if (frequency) { frequency.disabled = false; frequency.classList.remove('locked-field'); if (noteFrequency) noteFrequency.textContent = 'Editable (affects upcoming doses today)'; }
        if (noteEnd) noteEnd.textContent = 'Editable';
        if (noteCritical) noteCritical.textContent = 'Editable';

        // Visual adjustments for clarity
        if (medicineName) medicineName.style.opacity = '0.6';
        if (startDate) startDate.style.opacity = '0.6';
    }

    restrictionsDiv.innerHTML = restrictionsHTML;
}

function closeEditMedicationModal() {
    document.getElementById('editMedicationModal').style.display = 'none';
    document.getElementById('editMedicationForm').reset();
}

function editMedication(event) {
    const medicationId = document.getElementById('edit_medication_id').value;
    const currentStatus = document.getElementById('edit_current_status').value;
    const medicineName = document.getElementById('edit_medicine_name').value;
    const dosage = document.getElementById('edit_dosage').value;
    const frequency = document.getElementById('edit_frequency').value;
    const startDate = document.getElementById('edit_start_date').value;
    const endDate = document.getElementById('edit_end_date').value;
    const isCritical = document.getElementById('edit_is_critical').checked;

    if (!medicationId || !medicineName || !dosage || !frequency || !startDate || !endDate) {
        showToast('Please fill in all fields', 'error');
        return;
    }

    if (!isAllowedMedicationFrequency(frequency)) {
        showToast('Please choose a supported frequency from the list', 'error');
        return;
    }

    // Validate date range
    if (new Date(endDate) < new Date(startDate)) {
        showToast('End date must be on or after start date', 'error');
        return;
    }

    // Status-specific frontend validations
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const startDateObj = new Date(startDate);
    startDateObj.setHours(0, 0, 0, 0);
    
    // For ACTIVE medications: validate start date cannot be moved to the future
    if (currentStatus === 'ACTIVE' && startDateObj > today) {
        showToast('Cannot move start date to the future for active medications. The new start date must be today or earlier.', 'error');
        return;
    }

    const submitBtn = event ? event.target : null;
    if (submitBtn) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(submitBtn, 'Updating Medication...');
        } else {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Updating Medication...';
        }
    }

    fetch(`/update-medication/${medicationId}`, {
        method: 'PUT',
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
            if (data && data.success) {
                showToast(data.message || 'Medication updated successfully');
                closeEditMedicationModal();
                if (data.medication) {
                    replaceMedicationCardInDOM(data.medication);
                }
            } else {
                showToast(data.message || 'Failed to update medication', 'error');
                if (submitBtn) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(submitBtn);
                    } else {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Update Medication';
                    }
                }
            }
        })
        .catch(() => {
            showToast('Error updating medication. Please try again.', 'error');
            if (submitBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(submitBtn);
                } else {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Update Medication';
                }
            }
        });
}

window.onclick = function (event) {
    const medicationModal = document.getElementById('medicationModal');
    const editMedicationModal = document.getElementById('editMedicationModal');
    const medicineModal = document.getElementById('medicineModal');
    const confirmDeleteModal = document.getElementById('confirmDeleteMedicationModal');

    if (event.target === medicationModal) {
        closeMedicationModal();
    }
    if (event.target === editMedicationModal) {
        closeEditMedicationModal();
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
    const editStartDateInput = document.getElementById('edit_start_date');
    const editEndDateInput = document.getElementById('edit_end_date');

    if (startDateInput) {
        startDateInput.setAttribute('min', today);
    }
    if (endDateInput) {
        endDateInput.setAttribute('min', today);
    }
    if (editStartDateInput) {
        editStartDateInput.setAttribute('min', today);
    }
    if (editEndDateInput) {
        editEndDateInput.setAttribute('min', today);
    }

    const addMedicationBtn = document.getElementById('addMedicationBtn');
    if (addMedicationBtn) {
        addMedicationBtn.addEventListener('click', openMedicationModal);
    }

    // Autocomplete for medicine search
    const searchInput = document.getElementById('medicine_search_input');
    const suggestionsList = document.getElementById('medicine_suggestions');
    let suggestionTimer = null;
    if (searchInput) {
        searchInput.addEventListener('input', function (e) {
            const q = (e.target.value || '').trim();
            if (suggestionTimer) clearTimeout(suggestionTimer);
            if (!q) { suggestionsList.style.display = 'none'; suggestionsList.innerHTML = ''; return; }
            suggestionTimer = setTimeout(() => {
                fetch(`/api/medicine-suggestions?q=${encodeURIComponent(q)}`)
                    .then((r) => r.json())
                    .then((res) => {
                        const items = res.suggestions || [];
                        suggestionsList.innerHTML = '';
                        if (items.length === 0) { suggestionsList.style.display = 'none'; return; }
                        items.forEach((name) => {
                            const li = document.createElement('li');
                            li.setAttribute('role', 'option');
                            li.className = 'suggestion-item';
                            li.textContent = name;
                            li.addEventListener('click', () => {
                                searchInput.value = name;
                                suggestionsList.style.display = 'none';
                                document.getElementById('medicine_search_form').submit();
                            });
                            suggestionsList.appendChild(li);
                        });
                        suggestionsList.style.display = 'block';
                    })
                    .catch(() => { suggestionsList.style.display = 'none'; suggestionsList.innerHTML = ''; });
            }, 250);
        });

        // Close suggestions on outside click
        document.addEventListener('click', (ev) => {
            if (!ev.target.closest('#medicine_search_input') && !ev.target.closest('#medicine_suggestions')) {
                suggestionsList.style.display = 'none';
            }
        });
    }

    // Load more paging for medicines
    const loadMoreBtn = document.getElementById('loadMoreMedicines');
    if (loadMoreBtn) {
        loadMoreBtn.addEventListener('click', function () {
            const btn = this;
            let page = Number(btn.getAttribute('data-page') || 1);
            const next = page + 1;
            btn.disabled = true;
            btn.textContent = 'Loading...';
            const q = document.getElementById('medicine_search_input')?.value || '';
            fetch(`/api/medicines?q=${encodeURIComponent(q)}&page=${next}&page_size=9`)
                .then((r) => r.json())
                .then((data) => {
                    const list = document.querySelector('.medicines-list');
                    if (list && Array.isArray(data.medicines)) {
                        data.medicines.forEach((m) => {
                            const card = document.createElement('div');
                            card.className = 'medicine-card';
                            card.innerHTML = `<div class="medicine-card-header"><h3 class="medicine-name">${escapeHtml(m.medicine_name)}</h3></div>` +
                                `<div class="medicine-card-body"><div class="medicine-detail"><span class="detail-label">Medicine Type</span><span class="detail-text">${escapeHtml(m.medicine_type || 'N/A')}</span></div><div class="medicine-detail"><span class="detail-label">Purpose</span><span class="detail-text">${escapeHtml(m.purpose || 'N/A')}</span></div><div class="medicine-detail"><span class="detail-label">Remarks</span><span class="detail-text">${escapeHtml(m.remark || 'N/A')}</span></div></div>`;
                            list.appendChild(card);
                        });
                    }
                    if (data.has_more) {
                        btn.setAttribute('data-page', String(next));
                        btn.disabled = false;
                        btn.textContent = 'Load more';
                    } else {
                        btn.remove();
                    }
                })
                .catch(() => { showToast('Failed to load more medicines', 'error'); btn.disabled = false; btn.textContent = 'Load more'; });
        });
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

        if (action === 'toggle-medication-details') {
            // Toggle collapsible details for a medication card
            const btn = actionEl;
            toggleMedicationDetailsByButton(btn);
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

        if (action === 'open-edit-medication-modal') {
            const medicationId = actionEl.getAttribute('data-medication-id');
            const medicineName = actionEl.getAttribute('data-medicine-name');
            const dosage = actionEl.getAttribute('data-dosage');
            const frequency = actionEl.getAttribute('data-frequency');
            const startDate = actionEl.getAttribute('data-start-date');
            const endDate = actionEl.getAttribute('data-end-date');
            const isCritical = actionEl.getAttribute('data-is-critical');
            const currentStatus = actionEl.getAttribute('data-current-status');
            openEditMedicationModal(medicationId, medicineName, dosage, frequency, startDate, endDate, isCritical, currentStatus);
            return;
        }

        if (action === 'close-edit-medication-modal') {
            closeEditMedicationModal();
            return;
        }

        if (action === 'submit-edit-medication') {
            editMedication(event);
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
