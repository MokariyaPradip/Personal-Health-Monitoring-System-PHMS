function getCsrfToken() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
}

function showPageToast(message, isError) {
    const t = document.createElement('div');
    t.className = 'phms-page-toast';
    t.textContent = message;
    t.style.background = isError ? '#ef4444' : '#10b981';
    document.body.appendChild(t);
    setTimeout(() => {
        t.style.opacity = '0';
        setTimeout(() => t.remove(), 300);
    }, 3500);
}

function requestReset(event) {
    const emailInput = document.getElementById('email');
    const email = emailInput ? emailInput.value.trim() : '';

    if (!email) {
        showPageToast('Please enter your email.', true);
        return;
    }

    const button = event ? event.currentTarget : null;
    if (button) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(button, 'Sending OTP...');
        } else {
            button.disabled = true;
            button.textContent = 'Sending OTP...';
        }
    }

    fetch('/forgot-password', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ email: email })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                showPageToast(data.message || 'OTP has been sent to your email. Redirecting...', false);
                sessionStorage.setItem('reset_email', email);
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Redirecting...');
                }
                window.location.href = '/reset-password';
            } else {
                showPageToast(data.message || 'Failed to send OTP.', true);
                if (button) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(button);
                    } else {
                        button.disabled = false;
                        button.textContent = 'Send Password Reset OTP';
                    }
                }
            }
        })
        .catch(() => {
            showPageToast('Failed to request reset. Please try again.', true);
            if (button) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(button);
                } else {
                    button.disabled = false;
                    button.textContent = 'Send Password Reset OTP';
                }
            }
        });
}

document.addEventListener('DOMContentLoaded', function () {
    const requestResetBtn = document.getElementById('requestResetBtn');
    if (requestResetBtn) {
        requestResetBtn.addEventListener('click', requestReset);
    }
});
