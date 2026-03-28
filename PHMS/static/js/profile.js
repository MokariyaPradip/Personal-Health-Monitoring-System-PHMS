function openUpdate() {
    closeAll();
    document.getElementById('updateModal').style.display = 'block';
}

function openPassword() {
    closeAll();
    document.getElementById('passwordModal').style.display = 'block';
}

function closeAll() {
    document.getElementById('updateModal').style.display = 'none';
    document.getElementById('passwordModal').style.display = 'none';
}

function updateProfile(event) {
    const username = document.getElementById('edit_username').value;
    const gender = document.getElementById('edit_gender').value;
    const age = document.getElementById('edit_age').value;
    const height = document.getElementById('edit_height').value;
    const weight = document.getElementById('edit_weight').value;

    if (!username || !gender || !age || !height || !weight) {
        showToast('Please fill in all fields', 'error');
        return;
    }

    const submitBtn = event ? event.target : null;
    if (submitBtn) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(submitBtn, 'Updating...');
        } else {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Updating...';
        }
    }

    fetch('/update-profile', {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.getCsrfToken()
        },
        body: JSON.stringify({
            username: username,
            gender: gender,
            age: parseInt(age, 10),
            height: parseFloat(height),
            weight: parseFloat(weight)
        })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                showToast('Profile updated successfully');
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Refreshing profile...');
                }
                location.reload();
            } else {
                showToast(data.message || 'Failed to update profile', 'error');
                if (submitBtn) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(submitBtn);
                    } else {
                        submitBtn.disabled = false;
                        submitBtn.textContent = 'Update';
                    }
                }
            }
        })
        .catch(() => {
            showToast('Error updating profile. Please try again.', 'error');
            if (submitBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(submitBtn);
                } else {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Update';
                }
            }
        });
}

function resetPassword(event) {
    const currentPassword = document.getElementById('current_password').value;
    const newPassword = document.getElementById('new_password').value;
    const repeat = document.getElementById('confirm_password').value;

    if (!currentPassword || !newPassword || !repeat) {
        showToast('Please fill in all fields', 'error');
        return;
    }

    if (newPassword !== repeat) {
        showToast('Passwords do not match. Please try again.', 'error');
        return;
    }

    if (newPassword.length < 8) {
        showToast('Password must be at least 8 characters long', 'error');
        return;
    }

    const submitBtn = event ? event.target : null;
    if (submitBtn) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(submitBtn, 'Changing...');
        } else {
            submitBtn.disabled = true;
            submitBtn.textContent = 'Changing...';
        }
    }

    fetch('/change-password', {
        method: 'PUT',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.getCsrfToken()
        },
        body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
            confirm_password: repeat
        })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                showToast(data.message);
                closeAll();
            } else {
                showToast(data.message || 'Failed to reset password', 'error');
            }

            if (submitBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(submitBtn);
                } else {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Change Password';
                }
            }
        })
        .catch(() => {
            showToast('Error resetting password. Please try again.', 'error');
            if (submitBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(submitBtn);
                } else {
                    submitBtn.disabled = false;
                    submitBtn.textContent = 'Change Password';
                }
            }
        });
}

function logoutUser(triggerButton) {
    if (triggerButton) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(triggerButton, 'Logging out...');
        } else {
            triggerButton.disabled = true;
            triggerButton.textContent = 'Logging out...';
        }
    }

    fetch('/logout', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': window.getCsrfToken()
        }
    })
        .then((res) => {
            if (res.ok) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Signing out...');
                }
                window.location.href = '/login';
            } else {
                showToast('Logout failed. Please try again.', 'error');
                if (triggerButton) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(triggerButton);
                    } else {
                        triggerButton.disabled = false;
                        triggerButton.textContent = '\ud83d\udeaa Logout';
                    }
                }
            }
        })
        .catch(() => {
            showToast('Error during logout. Please try again.', 'error');
            if (triggerButton) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(triggerButton);
                } else {
                    triggerButton.disabled = false;
                    triggerButton.textContent = '\ud83d\udeaa Logout';
                }
            }
        });
}

window.onclick = function (event) {
    const updateModal = document.getElementById('updateModal');
    const passwordModal = document.getElementById('passwordModal');
    if (event.target === updateModal || event.target === passwordModal) {
        closeAll();
    }
};

document.addEventListener('DOMContentLoaded', function () {
    const openUpdateBtn = document.getElementById('openUpdateBtn');
    const openPasswordBtn = document.getElementById('openPasswordBtn');
    const logoutBtn = document.getElementById('logoutBtn');

    if (openUpdateBtn) {
        openUpdateBtn.addEventListener('click', openUpdate);
    }

    if (openPasswordBtn) {
        openPasswordBtn.addEventListener('click', openPassword);
    }

    if (logoutBtn) {
        logoutBtn.addEventListener('click', function () {
            logoutUser(logoutBtn);
        });
    }

    document.addEventListener('click', function (event) {
        const actionEl = event.target.closest('[data-action]');
        if (!actionEl) {
            return;
        }

        const action = actionEl.getAttribute('data-action');
        if (action === 'close-all-profile-modals') {
            closeAll();
            return;
        }

        if (action === 'submit-profile-update') {
            updateProfile(event);
            return;
        }

        if (action === 'submit-password-change') {
            resetPassword(event);
        }
    });
});
