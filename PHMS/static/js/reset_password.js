let currentStep = 'otp';
let userEmail = '';

function getCsrfToken() {
    const el = document.querySelector('meta[name="csrf-token"]');
    return el ? el.getAttribute('content') : '';
}

function showStep(step) {
    currentStep = step;

    document.querySelectorAll('.form-section').forEach((el) => el.classList.remove('active'));

    const stepSection = document.getElementById(`${step}-section`);
    if (stepSection) {
        stepSection.classList.add('active');
    }

    const steps = ['otp', 'password', 'complete'];
    const currentIdx = steps.indexOf(step);

    document.querySelectorAll('.step').forEach((el, idx) => {
        el.classList.remove('active', 'completed');
        if (idx < currentIdx) {
            el.classList.add('completed');
        } else if (idx === currentIdx) {
            el.classList.add('active');
        }
    });
}

function clearMessages() {
    const errorEl = document.querySelector('.error-message');
    const successEl = document.querySelector('.success-message');

    if (errorEl) {
        errorEl.classList.remove('show');
        errorEl.textContent = '';
    }

    if (successEl) {
        successEl.classList.remove('show');
        successEl.textContent = '';
    }
}

function showError(message) {
    clearMessages();
    const errorEl = document.querySelector('.error-message');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.classList.add('show');
    }
    window.scrollTo(0, 0);
}

function showSuccess(message) {
    clearMessages();
    const successEl = document.querySelector('.success-message');
    if (successEl) {
        successEl.textContent = message;
        successEl.classList.add('show');
    }
    window.scrollTo(0, 0);
}

function verifyOTP(event) {
    const otpInput = document.getElementById('otp');
    const otp = otpInput ? otpInput.value.trim() : '';

    if (!otp) {
        showError('Please enter the OTP.');
        return;
    }

    if (otp.length !== 6 || !/^\d+$/.test(otp)) {
        showError('OTP must be 6 digits.');
        return;
    }

    const button = event ? event.currentTarget : null;
    if (button) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(button, 'Verifying...');
        } else {
            button.disabled = true;
            button.textContent = 'Verifying...';
        }
    }

    fetch('/reset-password', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            email: userEmail,
            otp: otp
        })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                showSuccess(data.message);
                setTimeout(() => {
                    showStep('password');
                    if (button) {
                        if (window.PHMSLoading) {
                            window.PHMSLoading.clearButtonLoading(button);
                        } else {
                            button.disabled = false;
                            button.textContent = 'Verify OTP';
                        }
                    }
                }, 1500);
            } else {
                showError(data.message || 'OTP verification failed.');
                if (button) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(button);
                    } else {
                        button.disabled = false;
                        button.textContent = 'Verify OTP';
                    }
                }
            }
        })
        .catch((error) => {
            console.error('Error:', error);
            showError('Failed to verify OTP. Please try again.');
            if (button) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(button);
                } else {
                    button.disabled = false;
                    button.textContent = 'Verify OTP';
                }
            }
        });
}

function resetPassword(event) {
    const passwordInput = document.getElementById('password');
    const confirmInput = document.getElementById('confirm_password');
    const otpInput = document.getElementById('otp');

    const password = passwordInput ? passwordInput.value : '';
    const confirmPassword = confirmInput ? confirmInput.value : '';
    const otp = otpInput ? otpInput.value.trim() : '';

    if (!password || !confirmPassword) {
        showError('Please enter both password fields.');
        return;
    }

    if (password !== confirmPassword) {
        showError('Passwords do not match.');
        return;
    }

    if (password.length < 8) {
        showError('Password must be at least 8 characters long.');
        return;
    }

    const button = event ? event.currentTarget : null;
    if (button) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(button, 'Resetting Password...');
        } else {
            button.disabled = true;
            button.textContent = 'Resetting Password...';
        }
    }

    fetch('/reset-password', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            email: userEmail,
            otp: otp,
            password: password,
            confirm_password: confirmPassword
        })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                showSuccess(data.message);
                sessionStorage.removeItem('reset_email');
                setTimeout(() => {
                    showStep('complete');
                    if (button) {
                        if (window.PHMSLoading) {
                            window.PHMSLoading.clearButtonLoading(button);
                        } else {
                            button.disabled = false;
                            button.textContent = 'Reset Password';
                        }
                    }
                }, 1500);
            } else {
                showError(data.message || 'Password reset failed.');
                if (button) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(button);
                    } else {
                        button.disabled = false;
                        button.textContent = 'Reset Password';
                    }
                }
            }
        })
        .catch((error) => {
            console.error('Error:', error);
            showError('Failed to reset password. Please try again.');
            if (button) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(button);
                } else {
                    button.disabled = false;
                    button.textContent = 'Reset Password';
                }
            }
        });
}

function goBack() {
    if (currentStep === 'password') {
        showStep('otp');
        const otpInput = document.getElementById('otp');
        if (otpInput) {
            otpInput.focus();
        }
    }
}

function resendOTP(triggerLink) {
    if (triggerLink) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(triggerLink, 'Resending...');
        } else {
            triggerLink.style.pointerEvents = 'none';
            triggerLink.style.opacity = '0.6';
            triggerLink.textContent = 'Resending...';
        }
    }

    fetch('/forgot-password', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({ email: userEmail })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                showSuccess('New OTP has been sent to your email.');
                const otpInput = document.getElementById('otp');
                if (otpInput) {
                    otpInput.value = '';
                    otpInput.focus();
                }
            } else {
                showError(data.message || 'Failed to resend OTP.');
            }

            if (triggerLink) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(triggerLink);
                } else {
                    triggerLink.style.pointerEvents = '';
                    triggerLink.style.opacity = '';
                    triggerLink.textContent = 'Resend';
                }
            }
        })
        .catch((error) => {
            console.error('Error:', error);
            showError('Failed to resend OTP. Please try again.');

            if (triggerLink) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(triggerLink);
                } else {
                    triggerLink.style.pointerEvents = '';
                    triggerLink.style.opacity = '';
                    triggerLink.textContent = 'Resend';
                }
            }
        });
}

document.addEventListener('DOMContentLoaded', function () {
    userEmail = sessionStorage.getItem('reset_email');

    if (!userEmail) {
        window.location.href = '/forgot-password';
        return;
    }

    const emailDisplay = document.getElementById('email-display');
    if (emailDisplay) {
        emailDisplay.textContent = userEmail;
    }

    showStep('otp');

    const verifyOtpBtn = document.getElementById('verifyOtpBtn');
    const resetPasswordBtn = document.getElementById('resetPasswordBtn');
    const backToOtpBtn = document.getElementById('backToOtpBtn');

    if (verifyOtpBtn) {
        verifyOtpBtn.addEventListener('click', verifyOTP);
    }

    if (resetPasswordBtn) {
        resetPasswordBtn.addEventListener('click', resetPassword);
    }

    if (backToOtpBtn) {
        backToOtpBtn.addEventListener('click', goBack);
    }

    document.addEventListener('click', function (event) {
        const resendLink = event.target.closest('[data-action="resend-otp"]');
        if (!resendLink) {
            return;
        }

        event.preventDefault();
        resendOTP(resendLink);
    });
});
