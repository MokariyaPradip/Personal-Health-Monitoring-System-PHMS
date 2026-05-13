/**
 * Shared Notification Utilities
 * Common functions used across base.html and notifications.js
 */

// ===== CSRF TOKEN =====
window.getCsrfToken = function () {
    const el = document.querySelector('meta[name="csrf-token"]');
    if (el && el.getAttribute('content')) {
        return el.getAttribute('content');
    }
    // Fallback: try cookie named csrf_token
    const match = document.cookie.match(new RegExp('(^| )' + 'csrf_token' + '=([^;]+)'));
    return match ? decodeURIComponent(match[2]) : '';
};

// ===== TOAST NOTIFICATIONS =====
function showToast(message, type = 'success') {
    // Simple toast notification with support for success, error, info, and warning types
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    // Color mapping for different toast types
    const colors = {
        'success': '#10b981',  // Green
        'error': '#ef4444',    // Red
        'info': '#3b82f6',     // Blue
        'warning': '#f59e0b'   // Orange
    };
    
    toast.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        padding: 12px 24px;
        background: ${colors[type] || colors.success};
        color: white;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        animation: slideIn 0.3s ease;
    `;
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ===== CONFIRM MODAL =====
function showConfirmModal(message, onConfirm) {
    const overlay = document.createElement('div');
    overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);display:flex;align-items:center;justify-content:center;z-index:10001;';
    const box = document.createElement('div');
    box.style.cssText = 'background:#fff;border-radius:12px;padding:28px 32px;max-width:360px;width:90%;box-shadow:0 8px 32px rgba(0,0,0,0.18);text-align:center;';
    box.innerHTML = `
        <p style="margin:0 0 24px;font-size:15px;color:#374151;line-height:1.5;">${message}</p>
        <button id="phms-modal-cancel" style="margin-right:10px;padding:9px 22px;border:1px solid #d1d5db;border-radius:7px;background:#fff;color:#374151;font-size:14px;cursor:pointer;">Cancel</button>
        <button id="phms-modal-confirm" style="padding:9px 22px;border:none;border-radius:7px;background:#3b82f6;color:#fff;font-size:14px;font-weight:500;cursor:pointer;">Confirm</button>
    `;
    overlay.appendChild(box);
    document.body.appendChild(overlay);
    box.querySelector('#phms-modal-cancel').addEventListener('click', () => overlay.remove());
    box.querySelector('#phms-modal-confirm').addEventListener('click', () => { overlay.remove(); onConfirm(); });
    overlay.addEventListener('click', e => { if (e.target === overlay) overlay.remove(); });
}

// ===== NOTIFICATION BADGE =====
function updateNotificationBadge(count) {
    const badge = document.getElementById('notificationBadge');
    if (badge) {
        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = 'block';
        } else {
            badge.style.display = 'none';
        }
    }
}

// ===== MARK AS READ =====
function markAsRead(alertId, callback, sourceButton) {
    const request = () => fetch(`/notifications/${alertId}/read`, {
        method: 'PUT',
        headers: {
            'X-CSRFToken': window.getCsrfToken(),
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Update UI for all cards with this alert ID
            const cards = document.querySelectorAll(`[data-alert-id="${alertId}"]`);
            cards.forEach(card => {
                card.classList.remove('unread');
                const actionBtn = card.querySelector('.btn-icon');
                if (actionBtn) {
                    actionBtn.outerHTML = '<span class="read-indicator" title="Read">✓</span>';
                }
            });
            
            // Update badge counts if function exists
            if (typeof updateBadgeCounts === 'function') {
                updateBadgeCounts();
            }
            
            // Show success message
            showToast('Notification marked as read');
            
            // Execute callback if provided
            if (callback) {
                callback(data);
            }
        }
    });

    const requestPromise = sourceButton && window.PHMSLoading
        ? window.PHMSLoading.withLoading({ button: sourceButton, buttonText: 'Marking...' }, request)
        : request();

    requestPromise.catch(() => {
        showToast('Failed to mark notification as read', 'error');
    });
}

// ===== MARK ALL AS READ =====
function markAllAsRead(callback, sourceButton) {
    // Check if we're on the notifications page or in the dropdown
    const isNotificationsPage = document.getElementById('all-container') !== null;

    const proceed = () => {
        const request = () => fetch('/notifications/mark-all-read', {
            method: 'PUT',
            headers: {
                'X-CSRFToken': window.getCsrfToken(),
                'Content-Type': 'application/json'
            }
        })
        .then(res => {
            if (!res.ok) {
                throw new Error('Network response was not ok');
            }
            return res.json();
        })
        .then(data => {
            if (data.success) {
                // Check if there were any notifications to mark
                if (data.updated_count === 0) {
                    showToast('No unread notifications to mark', 'info');
                    return;
                }

                // If on notifications page, reload to show updated state
                if (isNotificationsPage) {
                    showToast(data.message || `${data.updated_count} notification${data.updated_count !== 1 ? 's' : ''} marked as read`, 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    // In dropdown, just update the UI
                    showToast(data.message || 'All notifications marked as read', 'success');

                    // Execute callback if provided (for reloading dropdown)
                    if (callback) {
                        callback(data);
                    }
                }
            } else {
                showToast(data.message || 'Failed to mark notifications as read', 'error');
            }
        });

        const requestPromise = sourceButton && window.PHMSLoading
            ? window.PHMSLoading.withLoading({ button: sourceButton, buttonText: 'Marking...' }, request)
            : request();

        requestPromise.catch(() => {
            showToast('Failed to mark all notifications as read', 'error');
        });
    };

    if (isNotificationsPage) {
        showConfirmModal('Mark all notifications as read?', proceed);
    } else {
        proceed();
    }
}

// ===== HELPER FUNCTIONS =====
function getCategoryEmoji(category) {
    const emojiMap = {
        'health': '🏥',
        'medication': '💊',
        'appointment': '📅',
        'alert': '⚠️',
        'general': 'ℹ️'
    };
    return emojiMap[category] || emojiMap['general'];
}

function normalizeSeverityValue(severity) {
    const normalized = String(severity || '').trim().toLowerCase();
    const severityMap = {
        'high': 'High',
        'medium': 'Medium',
        'low': 'Low',
        'critical': 'Critical'
    };
    return severityMap[normalized] || 'Medium';
}

function getSeverityLabel(severity) {
    return normalizeSeverityValue(severity);
}

function escapeHtml(text) {
    const safeText = String(text == null ? '' : text);
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return safeText.replace(/[&<>"']/g, m => map[m]);
}

// ===== NOTIFICATION COUNT POLLING =====
let notificationPollingInterval = null;

function startNotificationPolling(intervalMs = 120000) {
    // Initial load
    fetchNotificationCount();
    
    // Stop any existing polling
    if (notificationPollingInterval) {
        clearInterval(notificationPollingInterval);
    }
    
    // Start new polling
    notificationPollingInterval = setInterval(() => {
        fetchNotificationCount();
    }, intervalMs);
}

function stopNotificationPolling() {
    if (notificationPollingInterval) {
        clearInterval(notificationPollingInterval);
        notificationPollingInterval = null;
    }
}

function fetchNotificationCount() {
    fetch('/notifications/count', {
        method: 'GET',
        headers: {
            'X-CSRFToken': window.getCsrfToken()
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            updateNotificationBadge(data.count);
        }
    })
    .catch(err => console.error('Error fetching notification count:', err));
}

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    stopNotificationPolling();
});
