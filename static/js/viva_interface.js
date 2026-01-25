/**
 * Viva interface MCQ handler with auto-save and fullscreen enforcement
 */

const vivaId = window.vivaId || document.currentScript?.dataset?.vivaId;
let questions = window.questions || [];
let savedAnswers = window.savedAnswers || {};
let currentQuestion = null;

function showQuestion(questionNum) {
    const question = questions.find(q => q.question_number === questionNum);
    if (!question) return;

    // Update active button
    document.querySelectorAll('.question-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-question="${questionNum}"]`).classList.add('active');

    const savedAnswer = savedAnswers[questionNum] || '';

    const container = document.getElementById('question-container');
    container.innerHTML = `
        <div class="mcq-question">
            <div class="question-text">
                <span class="q-number">Question ${questionNum}</span>
                <p>${question.question}</p>
            </div>
            <div class="mcq-options">
                ${Object.entries(question.options).map(([key, value]) => `
                    <label class="mcq-option ${savedAnswer === key ? 'selected' : ''}">
                        <input type="radio" name="answer-${questionNum}" value="${key}" 
                               ${savedAnswer === key ? 'checked' : ''}
                               onchange="saveAnswer(${questionNum}, '${key}')">
                        <span class="option-key">${key}</span>
                        <span class="option-text">${value}</span>
                    </label>
                `).join('')}
            </div>
            <div class="save-status" id="save-status-${questionNum}" style="display: none;"></div>
        </div>
    `;

    currentQuestion = questionNum;
}

async function saveAnswer(questionNum, selectedOption) {
    try {
        const response = await fetch(`/api/viva/${vivaId}/submit-answer`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrf_token')
            },
            body: JSON.stringify({
                question_number: questionNum,
                answer_text: selectedOption
            })
        });

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            if (response.status === 401) {
                showToast('Session expired. Redirecting...', 'error');
                setTimeout(() => { window.location.href = '/login'; }, 2000);
                return;
            }
            console.error('Server returned non-JSON response');
            showToast('Server error. Please try again.', 'error');
            return;
        }

        const data = await response.json();

        if (response.ok && data.success) {
            savedAnswers[questionNum] = selectedOption;

            const btn = document.querySelector(`[data-question="${questionNum}"]`);
            if (btn) {
                btn.classList.add('answered');
                const statusIcon = btn.querySelector('.q-status');
                if (statusIcon) statusIcon.innerHTML = '<i class="fas fa-check"></i>';
            }

            document.querySelectorAll(`[name="answer-${questionNum}"]`).forEach(radio => {
                radio.closest('.mcq-option').classList.remove('selected');
            });
            document.querySelector(`input[value="${selectedOption}"]`).closest('.mcq-option').classList.add('selected');

            const statusEl = document.getElementById(`save-status-${questionNum}`);
            if (statusEl) {
                statusEl.textContent = '✓ Saved';
                statusEl.className = 'save-status success';
                statusEl.style.display = 'block';
                setTimeout(() => statusEl.style.display = 'none', 2000);
            }

            updateProgress();

            // Auto-advance to next question
            if (questionNum < questions.length) {
                setTimeout(() => showQuestion(questionNum + 1), 500);
            }
        } else if (data.login_required) {
            showToast('Session expired. Redirecting...', 'error');
            setTimeout(() => { window.location.href = '/login'; }, 2000);
        } else if (data.csrf_error) {
            showToast('Security token expired. Refreshing...', 'warning');
            setTimeout(() => { window.location.reload(); }, 2000);
        } else {
            showToast(data.error || 'Error saving answer', 'error');
        }
    } catch (error) {
        console.error('Error saving answer:', error);
        showToast('Error saving answer. Please try again.', 'error');
    }
}

async function updateProgress() {
    try {
        const response = await fetch(`/api/viva/${vivaId}/progress`);
        const data = await response.json();

        if (data.success) {
            const statEl = document.getElementById('progress-stat');
            const fillEl = document.getElementById('progress-fill');
            if (statEl) statEl.textContent = `${data.answered_questions}/${data.total_questions}`;
            if (fillEl) fillEl.style.width = (data.progress_percentage || 0) + '%';
        }
    } catch (error) {
        console.error('Error updating progress:', error);
    }
}

async function submitViva() {
    const answeredCount = Object.keys(savedAnswers).length;
    const totalQuestions = questions.length;

    if (answeredCount < totalQuestions) {
        if (!confirm(`You have only answered ${answeredCount} out of ${totalQuestions} questions. Unanswered questions will be marked as incorrect. Continue?`)) {
            return;
        }
    } else {
        if (!confirm('Are you sure you want to submit the viva? You cannot change answers after submission.')) {
            return;
        }
    }

    if (window.AntiCheat) {
        AntiCheat.disable();
    }

    try {
        const response = await fetch(`/api/viva/${vivaId}/submit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrf_token')
            }
        });

        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            if (response.status === 401) {
                showToast('Session expired. Redirecting...', 'error');
                setTimeout(() => { window.location.href = '/login'; }, 2000);
                return;
            }
            console.error('Server returned non-JSON response:', response.status);
            showToast('Server error. Please try again.', 'error');
            return;
        }

        const data = await response.json();

        if (response.ok && data.success) {
            showToast(`Viva submitted! You scored ${data.obtained_marks}/${data.total_marks} marks.`, 'success', 2000);
            setTimeout(() => { window.location.href = `/student/viva/marks/${vivaId}`; }, 2000);
        } else if (data.login_required) {
            showToast('Session expired. Redirecting to login...', 'error');
            setTimeout(() => { window.location.href = '/login'; }, 2000);
        } else {
            showToast(data.error || 'Error submitting viva', 'error');
        }
    } catch (error) {
        console.error('Error submitting viva:', error);
        showToast('Error submitting viva. Please try again.', 'error');
    }
}

function getCookie(name) {
    if (name === 'csrf_token') {
        const meta = document.querySelector('meta[name="csrf-token"]');
        if (meta) return meta.getAttribute('content');
    }
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

function showToast(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 25px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 999999;
        animation: slideIn 0.3s ease;
        max-width: 400px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    `;
    if (type === 'success') toast.style.background = 'linear-gradient(135deg, #28a745, #20c997)';
    else if (type === 'error') toast.style.background = 'linear-gradient(135deg, #dc3545, #c82333)';
    else if (type === 'warning') toast.style.background = 'linear-gradient(135deg, #ffc107, #e0a800)';
    else toast.style.background = 'linear-gradient(135deg, #667eea, #764ba2)';

    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

document.addEventListener('DOMContentLoaded', () => {
    const chatbotBtn = document.getElementById('chatbot-floating-btn');
    const chatbotWindow = document.getElementById('chatbot-window');
    if (chatbotBtn) chatbotBtn.style.display = 'none';
    if (chatbotWindow) chatbotWindow.style.display = 'none';

    console.log('Viva interface loaded');
});

function enterFullscreenMode() {
    const elem = document.documentElement;
    const enterFS = elem.requestFullscreen || elem.webkitRequestFullscreen || elem.msRequestFullscreen;

    function showVivaContent() {
        // CRITICAL: Hide fullscreen modal and show viva container
        document.getElementById('fullscreen-modal').classList.add('hidden');
        const vivaContainer = document.getElementById('viva-container');
        if (vivaContainer) {
            vivaContainer.classList.remove('hidden');
        }

        if (window.AntiCheat) {
            AntiCheat.init(vivaId);
        }

        if (questions.length > 0) {
            showQuestion(1);
        }
        updateProgress();
    }

    if (enterFS) {
        enterFS.call(elem).then(() => {
            showVivaContent();
        }).catch(err => {
            console.error('Fullscreen failed:', err);
            // Still show content even if fullscreen fails (for testing/development)
            showVivaContent();
            alert('Fullscreen is recommended but not required. You may proceed.');
        });
    } else {
        // Fallback for browsers without fullscreen API
        showVivaContent();
    }
}
