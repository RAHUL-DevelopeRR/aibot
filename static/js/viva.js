/**
 * Viva interface interactions and AJAX handling
 */

// Global variables
let currentQuestionId = null;
const answerCache = {};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Set first question as active
    const firstQuestionBtn = document.querySelector('.question-btn');
    if (firstQuestionBtn) {
        const questionId = firstQuestionBtn.getAttribute('onclick').match(/\d+/);
        navigateQuestion(parseInt(questionId));
    }
    
    // Load answers from cache
    loadAnswersFromPage();
});

function navigateQuestion(questionId) {
    // Hide all questions
    document.querySelectorAll('.question-card').forEach(card => {
        card.style.display = 'none';
    });
    
    // Show selected question
    document.getElementById('question-' + questionId).style.display = 'block';
    
    // Update active button
    document.querySelectorAll('.question-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    
    document.querySelector(`button[onclick="navigateQuestion(${questionId})"]`).classList.add('active');
    
    currentQuestionId = questionId;
}

function saveAnswer(questionId) {
    const answerText = document.getElementById('answer-' + questionId).value;
    
    // Store in cache
    answerCache[questionId] = answerText;
    
    const vivaId = window.location.pathname.split('/').pop();
    const token = getCookie('csrf_token');
    
    fetch(`/api/viva/${vivaId}/submit-answer`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': token
        },
        body: JSON.stringify({
            question_number: questionId,
            answer_text: answerText
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Update status icon
            const statusElement = document.getElementById('status-' + questionId);
            if (statusElement) {
                statusElement.innerHTML = '<i class="fas fa-check"></i>';
            }
            
            updateProgress();
            showNotification('Answer saved successfully!', 'success');
        } else {
            showNotification(data.message || 'Error saving answer', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error saving answer', 'danger');
    });
}

function updateProgress() {
    const vivaId = window.location.pathname.split('/').pop();
    
    fetch(`/api/viva/${vivaId}/progress`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const progress = data.progress_percentage;
                const progressFill = document.getElementById('progressFill');
                const progressText = document.getElementById('progressText');
                
                if (progressFill && progressText) {
                    progressFill.style.width = progress + '%';
                    progressText.innerText = Math.round(progress) + '% Complete';
                }
            }
        })
        .catch(error => console.error('Error updating progress:', error));
}

function submitViva() {
    const confirmed = confirm('Are you sure you want to submit this viva? This action cannot be undone.');
    
    if (!confirmed) {
        return;
    }
    
    const vivaId = window.location.pathname.split('/').pop();
    const token = getCookie('csrf_token');
    
    fetch(`/api/viva/${vivaId}/submit`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': token
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showNotification('Viva submitted successfully!', 'success');
            setTimeout(() => {
                window.location.href = '/student/dashboard';
            }, 2000);
        } else {
            showNotification(data.message || 'Error submitting viva', 'danger');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Error submitting viva', 'danger');
    });
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type}`;
    notification.innerHTML = `
        ${message}
        <button class="alert-close">&times;</button>
    `;
    
    // Insert at top of main content
    const mainContent = document.querySelector('.main-content');
    if (mainContent) {
        mainContent.insertBefore(notification, mainContent.firstChild);
    }
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
    
    // Close button functionality
    notification.querySelector('.alert-close').addEventListener('click', function() {
        notification.style.opacity = '0';
        setTimeout(() => notification.remove(), 300);
    });
}

function loadAnswersFromPage() {
    const textareas = document.querySelectorAll('.answer-textarea');
    textareas.forEach(textarea => {
        const id = textarea.id.replace('answer-', '');
        answerCache[id] = textarea.value;
    });
}

// Auto-save answers every 30 seconds
setInterval(() => {
    if (currentQuestionId && answerCache[currentQuestionId]) {
        saveAnswer(currentQuestionId);
    }
}, 30000);

// Prevent accidental page closing
window.addEventListener('beforeunload', function(e) {
    // Only warn if there are unsaved changes
    const hasChanges = Object.keys(answerCache).some(id => {
        const textarea = document.getElementById('answer-' + id);
        return textarea && textarea.value !== '';
    });
    
    if (hasChanges) {
        e.preventDefault();
        e.returnValue = '';
        return '';
    }
});
