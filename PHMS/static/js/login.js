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

function login(event) {
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const loginBtn = event ? event.target : null;

    if (loginBtn) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(loginBtn, 'Signing in...');
        } else {
            loginBtn.disabled = true;
            loginBtn.textContent = 'Signing in...';
        }
    }

    fetch('/login', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            email: emailInput ? emailInput.value : '',
            password: passwordInput ? passwordInput.value : ''
        })
    })
        .then((res) => res.json())
        .then((data) => {
            if (data.success) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Loading dashboard...');
                }
                window.location = '/dashboard';
            } else {
                showPageToast(data.message, true);
                if (loginBtn) {
                    if (window.PHMSLoading) {
                        window.PHMSLoading.clearButtonLoading(loginBtn);
                    } else {
                        loginBtn.disabled = false;
                        loginBtn.textContent = 'Login';
                    }
                }
            }
        })
        .catch(() => {
            showPageToast('Login failed. Please try again.', true);
            if (loginBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(loginBtn);
                } else {
                    loginBtn.disabled = false;
                    loginBtn.textContent = 'Login';
                }
            }
        });
}

document.addEventListener('DOMContentLoaded', function () {
    const loginBtn = document.getElementById('loginBtn');
    if (loginBtn) {
        loginBtn.addEventListener('click', login);
    }
});
