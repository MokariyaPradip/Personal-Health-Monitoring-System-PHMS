// Helper functions for scheduled time validation
function isScheduledTimeArrived(logDate, scheduledTime) {
    const now = new Date();
    // Use local date instead of UTC
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const currentDate = `${year}-${month}-${day}`;
    const currentTime = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

    // Compare dates
    if (logDate > currentDate) {
        return false; // Future date
    }

    // Same date, compare times
    if (logDate === currentDate) {
        const arrived = currentTime >= scheduledTime;
        return arrived;
    }

    return true; // Past date
}

function isWithinGracePeriod(logDate, scheduledTime, gracePeriodMinutes) {
    const now = new Date();
    // Use local date instead of UTC
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const day = String(now.getDate()).padStart(2, '0');
    const currentDate = `${year}-${month}-${day}`;
    
    // If it's a future date, not within grace period
    if (logDate > currentDate) {
        return false;
    }
    
    // Create datetime objects for comparison
    const scheduledDateTime = new Date(`${logDate}T${scheduledTime}`);
    const gracePeriodEnd = new Date(scheduledDateTime.getTime() + gracePeriodMinutes * 60000); // Add minutes in milliseconds
    // Current time must be >= scheduled time AND <= grace period end
    const withinPeriod = now >= scheduledDateTime && now <= gracePeriodEnd;
    return withinPeriod;
}

function updateMedicationButtonStatus(logId, logDate, scheduledTime, gracePeriodMinutes) {
    const logCard = document.querySelector(`.medication-log-card.pending[data-log-id="${logId}"]`);
    if (!logCard) {
        return;
    }

    const takenBtn = logCard.querySelector('.btn-log-action.taken');
    const missedBtn = logCard.querySelector('.btn-log-action.missed');
    if (!takenBtn || !missedBtn) {
        return;
    }
    
    const hasArrived = isScheduledTimeArrived(logDate, scheduledTime);
    const withinGracePeriod = isWithinGracePeriod(logDate, scheduledTime, gracePeriodMinutes);
    // "Mark as Taken" button: Enabled only during grace period (scheduled time to scheduled time + grace period)
    if (withinGracePeriod) {
        takenBtn.disabled = false;
        takenBtn.style.opacity = '1';
        takenBtn.style.cursor = 'pointer';
        takenBtn.style.pointerEvents = 'auto';
        takenBtn.title = 'Mark as taken';
    } else if (!hasArrived) {
        // Before scheduled time
        takenBtn.disabled = true;
        takenBtn.style.opacity = '0.5';
        takenBtn.style.cursor = 'not-allowed';
        takenBtn.style.pointerEvents = 'none';
        takenBtn.title = 'Medication time not yet arrived';
    } else {
        // After grace period
        takenBtn.disabled = true;
        takenBtn.style.opacity = '0.5';
        takenBtn.style.cursor = 'not-allowed';
        takenBtn.style.pointerEvents = 'none';
        takenBtn.title = 'Grace period has elapsed';
    }
    
    // "Mark as Missed" button: Enabled only during grace period (allows user to acknowledge they'll miss it)
    if (withinGracePeriod) {
        missedBtn.disabled = false;
        missedBtn.style.opacity = '1';
        missedBtn.style.cursor = 'pointer';
        missedBtn.style.pointerEvents = 'auto';
        missedBtn.title = 'Mark as missed';
    } else if (!hasArrived) {
        // Before scheduled time
        missedBtn.disabled = true;
        missedBtn.style.opacity = '0.5';
        missedBtn.style.cursor = 'not-allowed';
        missedBtn.style.pointerEvents = 'none';
        missedBtn.title = 'Cannot mark as missed before scheduled time';
    } else {
        // After grace period (auto-marked as missed by backend)
        missedBtn.disabled = true;
        missedBtn.style.opacity = '0.5';
        missedBtn.style.cursor = 'not-allowed';
        missedBtn.style.pointerEvents = 'none';
        missedBtn.title = 'Grace period elapsed - already marked as missed';
    }
}

// Global interval ID to prevent duplicate intervals
let medicationCheckInterval = null;

function initializeScheduledTimeValidation() {
    // Clear any existing interval first
    if (medicationCheckInterval) {
        clearInterval(medicationCheckInterval);
        medicationCheckInterval = null;
    }
    
    // Function to update all pending medication buttons
    function updateAllMedicationButtons() {
        const pendingCards = document.querySelectorAll('.medication-log-card.pending');
        if (pendingCards.length === 0) {
            return;
        }
        
        pendingCards.forEach(card => {
            const logId = card.getAttribute('data-log-id');
            const logDate = card.getAttribute('data-log-date');
            const scheduledTime = card.getAttribute('data-scheduled-time');
            const gracePeriod = parseInt(card.getAttribute('data-grace-period')) || 30; // Default 30 minutes if not set

            if (logId && logDate && scheduledTime) {
                updateMedicationButtonStatus(logId, logDate, scheduledTime, gracePeriod);
            } else {
            }
        });
    }
    // Initial update - run immediately
    updateAllMedicationButtons();

    // Update every 5 seconds to reflect real-time changes
    medicationCheckInterval = setInterval(updateAllMedicationButtons, 5000);
}

function filterByCategory(category) {
    // Update active tab
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-category="${category}"]`).classList.add('active');

    // Show/hide containers
    document.querySelectorAll('.notifications-container').forEach(container => {
        container.classList.add('hidden');
    });

    if (category === 'all') {
        document.getElementById('all-container').classList.remove('hidden');
    } else if (category === 'health') {
        document.getElementById('health-container').classList.remove('hidden');
    } else if (category === 'medication') {
        document.getElementById('medication-container').classList.remove('hidden');
    } else if (category === 'medication-logs') {
        document.getElementById('medication-logs-container').classList.remove('hidden');
        
        // Re-initialize validation when medication-logs tab is shown
        // Use setTimeout to ensure DOM has fully updated after unhiding
        setTimeout(() => {
            initializeScheduledTimeValidation();
        }, 50);
    }
}

function markMedicationTaken(logId, sourceButton) {
    // Get the log card to access scheduled time and grace period info
    const logCard = document.querySelector(`.medication-log-card.pending[data-log-id="${logId}"]`);
    if (!logCard) {
        showToast('Unable to find medication log', 'error');
        return;
    }

    const logDate = logCard.getAttribute('data-log-date');
    const scheduledTime = logCard.getAttribute('data-scheduled-time');
    const gracePeriod = parseInt(logCard.getAttribute('data-grace-period')) || 30;
    
    // Check if within grace period
    if (!isWithinGracePeriod(logDate, scheduledTime, gracePeriod)) {
        const hasArrived = isScheduledTimeArrived(logDate, scheduledTime);
        if (!hasArrived) {
            showToast('Medication time has not yet arrived', 'error');
        } else {
            showToast('Grace period has elapsed. This medication will be automatically marked as missed.', 'error');
        }
        return;
    }
    const request = () => fetch(`/medication-log/${logId}/taken`, {
        method: 'PUT',
        headers: {
            'X-CSRFToken': window.getCsrfToken(),
            'Content-Type': 'application/json'
        }
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast('Medication marked as taken!');
                // Reload page to update the log
                setTimeout(() => location.reload(), 1000);
            } else {
                showToast(data.message || 'Failed to update medication', 'error');
            }
        });

    const requestPromise = sourceButton && window.PHMSLoading
        ? window.PHMSLoading.withLoading({ button: sourceButton, buttonText: 'Updating...' }, request)
        : request();

    requestPromise.catch(err => {
            showToast('Failed to update medication', 'error');
        });
}

function markMedicationMissed(logId, sourceButton) {
    // Get the log card to access scheduled time and grace period info
    const logCard = document.querySelector(`.medication-log-card.pending[data-log-id="${logId}"]`);
    if (!logCard) {
        showToast('Unable to find medication log', 'error');
        return;
    }

    const logDate = logCard.getAttribute('data-log-date');
    const scheduledTime = logCard.getAttribute('data-scheduled-time');
    const gracePeriod = parseInt(logCard.getAttribute('data-grace-period')) || 30;
    
    // Check if within grace period
    if (!isWithinGracePeriod(logDate, scheduledTime, gracePeriod)) {
        const hasArrived = isScheduledTimeArrived(logDate, scheduledTime);
        if (!hasArrived) {
            showToast('Cannot mark as missed before scheduled time', 'error');
        } else {
            showToast('Grace period has elapsed. Medication is automatically marked as missed.', 'warning');
        }
        return;
    }
    
    const request = () => fetch(`/medication-log/${logId}/missed`, {
        method: 'PUT',
        headers: {
            'X-CSRFToken': window.getCsrfToken(),
            'Content-Type': 'application/json'
        }
    })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                showToast('Medication marked as missed', 'warning');
                // Reload page to update the log
                setTimeout(() => location.reload(), 1000);
            } else {
                showToast(data.message || 'Failed to update medication', 'error');
            }
        });

    const requestPromise = sourceButton && window.PHMSLoading
        ? window.PHMSLoading.withLoading({ button: sourceButton, buttonText: 'Updating...' }, request)
        : request();

    requestPromise.catch(err => {
            showToast('Failed to update medication', 'error');
        });
}

// ===== NOTIFICATIONS PAGE SPECIFIC FUNCTIONS =====
// These functions use the shared markAsRead() from notifications-common.js

function markAsReadOnPage(alertId, sourceButton) {
    // Use shared markAsRead function with callback to update badges
    markAsRead(alertId, function () {
        updateBadgeCounts();
    }, sourceButton);
}


// Note: markAllAsRead() is now provided by notifications-common.js
// It handles both dropdown and page contexts automatically

function updateBadgeCounts() {
    // Count unread notifications only in their respective containers to avoid duplicates
    const allUnread = document.querySelectorAll('#all-container .notification-card.unread').length;
    const healthUnread = document.querySelectorAll('#health-container .notification-card.unread').length;
    const medicationUnread = document.querySelectorAll('#medication-container .notification-card.unread').length;

    // Update or create badges
    updateOrCreateBadge('[data-category="all"]', allUnread);
    updateOrCreateBadge('[data-category="health"]', healthUnread);
    updateOrCreateBadge('[data-category="medication"]', medicationUnread);

    // Update header stats - both total and unread counts
    const allTotal = document.querySelectorAll('#all-container .notification-card').length;
    const totalStat = document.querySelector('.stat-badge:not(.unread) strong');
    const unreadStat = document.querySelector('.stat-badge.unread strong');

    if (totalStat) {
        totalStat.textContent = allTotal;
    }

    if (unreadStat) {
        unreadStat.textContent = allUnread;
    }

    // Update/hide mark all button
    const markAllBtn = document.querySelector('.header-actions .btn-secondary');
    if (markAllBtn) {
        if (allUnread === 0) {
            markAllBtn.style.display = 'none';
        } else {
            markAllBtn.style.display = '';
        }
    }
}

function updateOrCreateBadge(tabSelector, count) {
    const tabBtn = document.querySelector(tabSelector);
    if (!tabBtn) return;

    let badge = tabBtn.querySelector('.tab-badge');

    if (count > 0) {
        if (badge) {
            // Update existing badge
            badge.textContent = count;
        } else {
            // Create new badge
            badge = document.createElement('span');
            badge.className = 'tab-badge';
            badge.textContent = count;
            tabBtn.appendChild(badge);
        }
    } else {
        // Remove badge if count is 0
        if (badge) {
            badge.remove();
        }
    }
}

// Note: showToast() is now provided by notifications-common.js

// Attach event listeners when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Mark all as read button
    const markAllBtn = document.getElementById('mark-all-btn');
    if (markAllBtn) {
        markAllBtn.addEventListener('click', function () {
            markAllAsRead(null, markAllBtn);
        });
    }

    // Category tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const category = btn.getAttribute('data-category');
            filterByCategory(category);
        });
    });

    // Mark as read buttons (using event delegation for all alert cards)
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-icon')) {
            const card = e.target.closest('.notification-card');
            if (card) {
                const alertId = card.getAttribute('data-alert-id');
                if (alertId) {
                    markAsReadOnPage(alertId, e.target);
                }
            }
        }
    });

    // Medication log action buttons (taken)
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-log-action') && e.target.classList.contains('taken')) {
            const logId = e.target.getAttribute('data-log-id');
            if (logId) {
                markMedicationTaken(parseInt(logId, 10), e.target);
            }
        }
    });

    // Medication log action buttons (missed)
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('btn-log-action') && e.target.classList.contains('missed')) {
            const logId = e.target.getAttribute('data-log-id');
            if (logId) {
                markMedicationMissed(parseInt(logId, 10), e.target);
            }
        }
    });

    // Initialize scheduled time validation
    initializeScheduledTimeValidation();
});
