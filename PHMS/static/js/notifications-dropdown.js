(function () {
    let hideDropdownTimeout = null;

    function showNotifications() {
        if (hideDropdownTimeout) {
            clearTimeout(hideDropdownTimeout);
            hideDropdownTimeout = null;
        }

        const dropdown = document.getElementById('notificationDropdown');
        if (!dropdown) {
            return;
        }

        dropdown.style.display = 'block';
        loadNotifications();
    }

    function cancelHideDropdown() {
        if (hideDropdownTimeout) {
            clearTimeout(hideDropdownTimeout);
            hideDropdownTimeout = null;
        }
    }

    function hideNotifications() {
        hideDropdownTimeout = setTimeout(() => {
            const dropdown = document.getElementById('notificationDropdown');
            if (dropdown) {
                dropdown.style.display = 'none';
            }
        }, 300);
    }

    function loadNotifications() {
        const notificationList = document.getElementById('notificationList');
        if (window.PHMSLoading && notificationList) {
            window.PHMSLoading.setRegionLoading(notificationList, true, 'Loading notifications...');
        }

        fetch('/notifications/api?limit=15', {
            method: 'GET',
            headers: {
                'X-CSRFToken': window.getCsrfToken()
            }
        })
            .then((res) => res.json())
            .then((data) => {
                if (data.success) {
                    displayNotifications(data.notifications);
                    updateNotificationBadge(data.count);
                }
            })
            .catch((err) => {
                console.error('Error loading notifications:', err);
                if (notificationList) {
                    notificationList.innerHTML = '<div class="notification-empty">Failed to load notifications</div>';
                }
            })
            .finally(() => {
                if (window.PHMSLoading && notificationList) {
                    window.PHMSLoading.setRegionLoading(notificationList, false);
                }
            });
    }

    function displayNotifications(notifications) {
        const notificationList = document.getElementById('notificationList');
        if (!notificationList) {
            return;
        }

        if (!notifications || notifications.length === 0) {
            notificationList.innerHTML = '<div class="notification-empty">No new notifications</div>';
            return;
        }

        let html = '';
        notifications.forEach((notification) => {
            const categoryClass = `category-${notification.category || 'general'}`;
            const normalizedSeverity = normalizeSeverityValue(notification.severity);
            const severityClass = `severity-${normalizedSeverity.toLowerCase()}`;
            const categoryEmoji = getCategoryEmoji(notification.category);
            const severityLabel = getSeverityLabel(notification.severity);
            const rawTitle = String(notification.title == null ? '' : notification.title);
            const rawMessage = String(notification.message == null ? '' : notification.message);
            const shortMessage = rawMessage.slice(0, 80);
            const rawCreatedAt = String(notification.created_at == null ? '' : notification.created_at);

            html += `
                    <div class="notification-item ${categoryClass} ${severityClass}" data-alert-id="${notification.alert_id}">
                        <div class="notification-icon">${categoryEmoji}</div>
                        <div class="notification-content">
                            <div class="notification-title">${escapeHtml(rawTitle)}</div>
                            <div class="notification-message">${escapeHtml(shortMessage)}${rawMessage.length > 80 ? '...' : ''}</div>
                            <div class="notification-meta">
                                <span class="notification-severity ${severityClass}">${severityLabel}</span>
                                <span class="notification-time">${escapeHtml(rawCreatedAt)}</span>
                            </div>
                        </div>
                        <button class="notification-close" data-alert-id="${notification.alert_id}" title="Dismiss">\u2715</button>
                    </div>
                `;
        });

        notificationList.innerHTML = html;
    }

    function handleNotificationClick(alertId, element) {
        markAsRead(alertId, function () {
            element.classList.add('read');
            loadNotifications();
        });
    }

    function deleteNotification(event, alertId) {
        event.stopPropagation();
        const notificationItem = event.target.closest('.notification-item');
        if (notificationItem) {
            notificationItem.remove();
        }
        markAsRead(alertId, () => loadNotifications());
    }

    document.addEventListener('DOMContentLoaded', function () {
        const notificationContainer = document.querySelector('.notification-container');
        const notificationDropdown = document.getElementById('notificationDropdown');
        const notificationList = document.getElementById('notificationList');
        const dropdownMarkAllRead = document.getElementById('dropdownMarkAllRead');

        if (notificationContainer) {
            notificationContainer.addEventListener('mouseenter', showNotifications);
            notificationContainer.addEventListener('mouseleave', hideNotifications);
        }

        if (notificationDropdown) {
            notificationDropdown.addEventListener('mouseenter', cancelHideDropdown);
            notificationDropdown.addEventListener('mouseleave', hideNotifications);
        }

        if (dropdownMarkAllRead) {
            dropdownMarkAllRead.addEventListener('click', function () {
                markAllAsRead(() => loadNotifications(), dropdownMarkAllRead);
            });
        }

        if (notificationList) {
            notificationList.addEventListener('click', function (event) {
                const closeBtn = event.target.closest('.notification-close');
                if (closeBtn) {
                    const alertId = Number(closeBtn.getAttribute('data-alert-id'));
                    if (alertId) {
                        deleteNotification(event, alertId);
                    }
                    return;
                }

                const notificationItem = event.target.closest('.notification-item');
                if (notificationItem) {
                    const alertId = Number(notificationItem.getAttribute('data-alert-id'));
                    if (alertId) {
                        handleNotificationClick(alertId, notificationItem);
                    }
                }
            });
        }

        startNotificationPolling(120000);
    });

    window.addEventListener('click', function (event) {
        const dropdown = document.getElementById('notificationDropdown');
        if (!dropdown) {
            return;
        }

        if (!event.target.closest('.notification-container')) {
            dropdown.style.display = 'none';
        }
    });
})();
