/**
 * Security utilities for CSRF protection and token management
 */

// Get CSRF token from cookie
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Get CSRF token from meta tag or cookie
function getCSRFToken() {
    let token = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
    if (!token) {
        token = getCookie('csrf_token');
    }
    return token;
}

// Add CSRF token to fetch requests
function secureFetch(url, options = {}) {
    const token = getCSRFToken();
    
    const headers = options.headers || {};
    if (token) {
        headers['X-CSRFToken'] = token;
    }
    
    return fetch(url, { ...options, headers });
}

// Alert dismiss functionality
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.alert-close').forEach(closeBtn => {
        closeBtn.addEventListener('click', function() {
            const alert = this.closest('.alert');
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        });
    });
});

// Auto-hide success alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.alert-success').forEach(alert => {
        setTimeout(() => {
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 300);
        }, 5000);
    });
});
