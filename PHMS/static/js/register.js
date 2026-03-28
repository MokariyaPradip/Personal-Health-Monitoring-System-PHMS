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

function register(event) {
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const ageInput = document.getElementById('age');
    const genderInput = document.getElementById('gender');
    const heightInput = document.getElementById('height');
    const weightInput = document.getElementById('weight');
    const registerBtn = event ? event.currentTarget : null;

    if (registerBtn) {
        if (window.PHMSLoading) {
            window.PHMSLoading.setButtonLoading(registerBtn, 'Creating account...');
        } else {
            registerBtn.disabled = true;
            registerBtn.textContent = 'Creating account...';
        }
    }

    fetch('/register', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            username: usernameInput ? usernameInput.value : '',
            email: emailInput ? emailInput.value : '',
            password: passwordInput ? passwordInput.value : '',
            age: ageInput ? ageInput.value : '',
            gender: genderInput ? genderInput.value : '',
            height: heightInput ? heightInput.value : '',
            weight: weightInput ? weightInput.value : ''
        })
    })
        .then((res) => res.json())
        .then((data) => {
            showPageToast(data.message, !data.success);
            if (data.success) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.showOverlay('Redirecting to login...');
                }
                window.location = '/login';
                return;
            }

            if (registerBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(registerBtn);
                } else {
                    registerBtn.disabled = false;
                    registerBtn.textContent = 'Register';
                }
            }
        })
        .catch(() => {
            showPageToast('Registration failed. Please try again.', true);
            if (registerBtn) {
                if (window.PHMSLoading) {
                    window.PHMSLoading.clearButtonLoading(registerBtn);
                } else {
                    registerBtn.disabled = false;
                    registerBtn.textContent = 'Register';
                }
            }
        });
}

document.addEventListener('DOMContentLoaded', function () {
    const registerBtn = document.getElementById('registerBtn');
    if (registerBtn) {
        registerBtn.addEventListener('click', register);
    }
});
