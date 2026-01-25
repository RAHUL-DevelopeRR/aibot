/**
 * =========================================
 * SECURE EXAM MODULE - FIXED STATE MACHINE
 * =========================================
 * 
 * COMPLETE REWRITE for proper lifecycle:
 * - Tab isolation (exam runs in separate tab)
 * - No retry required for normal flow
 * - Security checks only after MCQs rendered
 * - Score always shown (even on termination)
 * - 10-second score display guaranteed
 * - Clean redirect to home
 * 
 * STATE MACHINE:
 * EXAM_LOADING → GENERATING_MCQS → MCQS_READY → EXAM_IN_PROGRESS
 * EXAM_IN_PROGRESS → EXAM_SUBMITTED → SHOWING_SCORE → WRITING_MARKS → REDIRECTING_HOME
 * SESSION_TERMINATED (from any active state) → SHOWING_SCORE → WRITING_MARKS → REDIRECTING_HOME
 * =========================================
 */

// =========================================
// STRICT STATE MACHINE
// =========================================
const EXAM_STATE = {
    EXAM_LOADING: 'EXAM_LOADING',
    GENERATING_MCQS: 'GENERATING_MCQS',
    MCQS_READY: 'MCQS_READY',
    EXAM_IN_PROGRESS: 'EXAM_IN_PROGRESS',
    EXAM_SUBMITTED: 'EXAM_SUBMITTED',
    SHOWING_SCORE: 'SHOWING_SCORE',
    SESSION_TERMINATED: 'SESSION_TERMINATED',
    WRITING_MARKS: 'WRITING_MARKS',
    REDIRECTING_HOME: 'REDIRECTING_HOME',
    ERROR: 'ERROR'
};

// =========================================
// EXAM STATE - SINGLE SOURCE OF TRUTH
// =========================================
const examState = {
    currentState: EXAM_STATE.EXAM_LOADING,
    questions: [],
    answers: {},
    score: 0,
    totalQuestions: 10,
    violationCount: 0,
    maxViolations: 3,
    sessionBlocked: false,
    isFullscreen: false,
    mcqsRendered: false,           // Track if MCQs have been rendered
    securityEnabled: false,        // Security only enabled AFTER MCQs render
    submissionLocked: false,
    marksSaved: false,
    marksWriteAttempted: false
};

// =========================================
// CONFIGURATION
// =========================================
const CONFIG = {
    SCORE_DISPLAY_TIME_MS: 10000,   // Exactly 10 seconds
    GENERATION_TIMEOUT_MS: 60000,   // 60 seconds for MCQ generation
    get HOME_URL() { return window.EXAM_CONFIG?.homeUrl || '/student/dashboard'; },
    get GENERATE_URL() { return window.EXAM_CONFIG?.generateUrl || '/viva/api/generate'; },
    get SAVE_MARKS_URL() { return window.EXAM_CONFIG?.saveMarksUrl || '/viva/api/save-marks'; },
    get VIOLATION_URL() { return window.EXAM_CONFIG?.violationUrl || '/viva/api/violation'; }
};

// =========================================
// DOM ELEMENTS CACHE
// =========================================
let elements = {};

function initElements() {
    elements = {
        loadingSection: document.getElementById('loading-section'),
        resultsSection: document.getElementById('results-section'),
        questionsContainer: document.getElementById('questions-container'),
        scoreValue: document.getElementById('score-value'),
        totalQuestions: document.getElementById('total-questions'),
        submitAllBtn: document.getElementById('submit-all-btn'),
        toast: document.getElementById('toast')
    };
    log('DOM elements initialized');
}

// =========================================
// LOGGING
// =========================================
function log(message, data = null) {
    const timestamp = new Date().toISOString().substr(11, 12);
    const state = examState.currentState;
    const prefix = `[Exam ${timestamp}] [${state}]`;
    if (data !== null) {
        console.log(prefix, message, data);
    } else {
        console.log(prefix, message);
    }
}

function logError(message, error = null) {
    const timestamp = new Date().toISOString().substr(11, 12);
    const prefix = `[Exam ERROR ${timestamp}]`;
    if (error) {
        console.error(prefix, message, error);
    } else {
        console.error(prefix, message);
    }
}

// =========================================
// STATE MACHINE - STRICT TRANSITIONS
// =========================================
function setState(newState) {
    const oldState = examState.currentState;

    // Validate transition
    if (!isValidTransition(oldState, newState)) {
        logError(`Invalid state transition: ${oldState} → ${newState}`);
        return false;
    }

    examState.currentState = newState;
    log(`STATE: ${oldState} → ${newState}`);
    handleStateChange(newState, oldState);
    return true;
}

function isValidTransition(from, to) {
    const validTransitions = {
        [EXAM_STATE.EXAM_LOADING]: [EXAM_STATE.GENERATING_MCQS, EXAM_STATE.ERROR],
        [EXAM_STATE.GENERATING_MCQS]: [EXAM_STATE.MCQS_READY, EXAM_STATE.ERROR],
        [EXAM_STATE.MCQS_READY]: [EXAM_STATE.EXAM_IN_PROGRESS],
        [EXAM_STATE.EXAM_IN_PROGRESS]: [EXAM_STATE.EXAM_SUBMITTED, EXAM_STATE.SESSION_TERMINATED],
        [EXAM_STATE.EXAM_SUBMITTED]: [EXAM_STATE.SHOWING_SCORE],
        [EXAM_STATE.SESSION_TERMINATED]: [EXAM_STATE.SHOWING_SCORE],
        [EXAM_STATE.SHOWING_SCORE]: [EXAM_STATE.WRITING_MARKS],
        [EXAM_STATE.WRITING_MARKS]: [EXAM_STATE.REDIRECTING_HOME],
        [EXAM_STATE.REDIRECTING_HOME]: [],
        [EXAM_STATE.ERROR]: [EXAM_STATE.GENERATING_MCQS, EXAM_STATE.REDIRECTING_HOME]
    };

    return validTransitions[from]?.includes(to) ?? false;
}

function handleStateChange(newState, oldState) {
    switch (newState) {
        case EXAM_STATE.GENERATING_MCQS:
            showLoader('Generating questions...');
            startMCQGeneration();
            break;

        case EXAM_STATE.MCQS_READY:
            hideLoader();
            renderQuestions();
            // Enable security ONLY after MCQs are rendered
            examState.mcqsRendered = true;
            examState.securityEnabled = true;
            log('Security checks now ENABLED');
            setState(EXAM_STATE.EXAM_IN_PROGRESS);
            break;

        case EXAM_STATE.EXAM_IN_PROGRESS:
            log('Exam in progress - student can answer');
            break;

        case EXAM_STATE.EXAM_SUBMITTED:
            log('Processing submission...');
            processSubmission();
            break;

        case EXAM_STATE.SESSION_TERMINATED:
            log('Session terminated - setting score to 0');
            examState.score = 0;
            examState.sessionBlocked = true;
            examState.submissionLocked = true;
            // Immediately show score (which is 0)
            setState(EXAM_STATE.SHOWING_SCORE);
            break;

        case EXAM_STATE.SHOWING_SCORE:
            showScoreScreen();
            // Start 10-second countdown, then write marks
            setTimeout(() => {
                setState(EXAM_STATE.WRITING_MARKS);
            }, CONFIG.SCORE_DISPLAY_TIME_MS);
            break;

        case EXAM_STATE.WRITING_MARKS:
            writeMarksToGoogleSheets();
            break;

        case EXAM_STATE.REDIRECTING_HOME:
            performFinalRedirect();
            break;

        case EXAM_STATE.ERROR:
            hideLoader();
            showErrorModal('Failed to generate questions. Please try again.');
            break;
    }
}

// =========================================
// LOADER CONTROL
// =========================================
const loaderMessages = [
    "Preparing your exam...",
    "Connecting to AI...",
    "Generating MCQs...",
    "Processing questions...",
    "Almost ready..."
];
let loaderInterval = null;
let loaderMsgIndex = 0;

function showLoader(message) {
    if (elements.loadingSection) {
        elements.loadingSection.classList.remove('hidden');
        elements.loadingSection.style.display = 'block';
        updateLoaderText(message || loaderMessages[0]);
    }
    if (elements.resultsSection) {
        elements.resultsSection.classList.add('hidden');
        elements.resultsSection.style.display = 'none';
    }

    // Cycle through messages every 3 seconds
    stopLoaderAnimation();
    loaderMsgIndex = 0;
    loaderInterval = setInterval(() => {
        loaderMsgIndex = (loaderMsgIndex + 1) % loaderMessages.length;
        updateLoaderText(loaderMessages[loaderMsgIndex]);
    }, 3000);
}

function updateLoaderText(text) {
    const textEl = elements.loadingSection?.querySelector('.experiments-loading span');
    if (textEl) textEl.textContent = text;
}

function stopLoaderAnimation() {
    if (loaderInterval) {
        clearInterval(loaderInterval);
        loaderInterval = null;
    }
}

function hideLoader() {
    stopLoaderAnimation();
    if (elements.loadingSection) {
        elements.loadingSection.classList.add('hidden');
        elements.loadingSection.style.display = 'none';
    }
}

// =========================================
// MCQ GENERATION - AUTO-START, NO RETRY NEEDED
// =========================================
async function startMCQGeneration() {
    log('Starting MCQ generation automatically...');

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), CONFIG.GENERATION_TIMEOUT_MS);

        const response = await fetch(CONFIG.GENERATE_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            signal: controller.signal,
            body: JSON.stringify({
                experiment_id: window.EXAM_CONFIG.experimentId,
                topic: window.EXAM_CONFIG.experimentTopic,
                student_session: window.EXAM_CONFIG.studentSession
            })
        });

        clearTimeout(timeoutId);

        const payload = await response.json().catch(() => ({}));

        if (!response.ok || payload.status !== 'success') {
            throw new Error(payload?.message || 'Failed to generate MCQs');
        }

        const questions = payload.data?.questions || [];
        if (questions.length === 0) {
            throw new Error('No questions received from server');
        }

        // Validate questions
        const validQuestions = questions.filter(q =>
            q.question && q.options && Object.keys(q.options).length === 4 && q.correct_answer
        );

        if (validQuestions.length === 0) {
            throw new Error('All questions were invalid');
        }

        // Assign IDs
        validQuestions.forEach((q, i) => q.id = q.id || (i + 1));

        examState.questions = validQuestions;
        examState.totalQuestions = validQuestions.length;
        examState.answers = {};

        log(`MCQs generated successfully: ${validQuestions.length} questions`);
        showToast(`${validQuestions.length} questions loaded!`, 'success');

        setState(EXAM_STATE.MCQS_READY);

    } catch (error) {
        logError('MCQ generation failed:', error);
        setState(EXAM_STATE.ERROR);
    }
}

// =========================================
// QUESTION RENDERING
// =========================================
function renderQuestions() {
    log('Rendering questions...');

    if (!elements.questionsContainer) {
        logError('Questions container not found');
        return;
    }

    // Show results section
    if (elements.resultsSection) {
        elements.resultsSection.classList.remove('hidden');
        elements.resultsSection.style.display = 'block';
    }

    // Clear and populate
    elements.questionsContainer.innerHTML = '';
    if (elements.totalQuestions) elements.totalQuestions.textContent = examState.questions.length;
    if (elements.scoreValue) elements.scoreValue.textContent = '0';

    examState.questions.forEach((q, idx) => {
        const card = createQuestionCard(q, idx);
        elements.questionsContainer.appendChild(card);
    });

    log(`Rendered ${examState.questions.length} questions`);

    // Scroll to questions
    setTimeout(() => {
        elements.resultsSection?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

function createQuestionCard(question, index) {
    const card = document.createElement('div');
    card.className = 'question-card';
    card.dataset.questionId = question.id;
    card.style.animationDelay = `${index * 0.05}s`;

    const optionsHTML = Object.entries(question.options).map(([letter, text]) => `
        <div class="option" data-answer="${letter}" tabindex="0">
            <span class="option-letter">${letter}</span>
            <span class="option-text">${text}</span>
            <span class="option-icon"><i class="fas fa-check-circle"></i></span>
        </div>
    `).join('');

    card.innerHTML = `
        <div class="question-header">
            <span class="question-number">${index + 1}</span>
            <p class="question-text">${question.question}</p>
        </div>
        <div class="options-container" data-correct="${question.correct_answer}">
            ${optionsHTML}
        </div>
        <div class="explanation hidden" id="explanation-${question.id}">
            <div class="explanation-header"><i class="fas fa-lightbulb"></i><span>Explanation</span></div>
            <p class="explanation-text">${question.explanation || 'No explanation provided.'}</p>
        </div>
    `;

    // Bind option click handlers
    card.querySelectorAll('.option').forEach(option => {
        option.addEventListener('click', () => handleOptionSelect(card, option));
        option.addEventListener('keydown', e => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                handleOptionSelect(card, option);
            }
        });
    });

    return card;
}

function handleOptionSelect(card, selectedOption) {
    if (examState.currentState !== EXAM_STATE.EXAM_IN_PROGRESS || examState.submissionLocked) {
        return;
    }

    // Deselect all options in this card
    card.querySelectorAll('.option').forEach(opt => opt.classList.remove('selected'));

    // Select clicked option
    selectedOption.classList.add('selected');

    // Record answer
    examState.answers[card.dataset.questionId] = selectedOption.dataset.answer;
    log(`Answer recorded: Q${card.dataset.questionId} = ${selectedOption.dataset.answer}`);
}

// =========================================
// SUBMISSION FLOW
// =========================================
function handleSubmitClick() {
    if (examState.currentState !== EXAM_STATE.EXAM_IN_PROGRESS) {
        log('Submit blocked - not in EXAM_IN_PROGRESS state');
        return;
    }

    const answeredCount = Object.keys(examState.answers).length;
    if (answeredCount < examState.questions.length) {
        showToast(`Please answer all questions (${answeredCount}/${examState.questions.length} answered)`, 'error');
        return;
    }

    setState(EXAM_STATE.EXAM_SUBMITTED);
}

function processSubmission() {
    log('Processing submission - calculating score...');

    // Lock exam
    examState.submissionLocked = true;
    if (elements.submitAllBtn) {
        elements.submitAllBtn.disabled = true;
        elements.submitAllBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    }

    // Calculate score
    let score = 0;
    examState.questions.forEach(question => {
        const card = document.querySelector(`[data-question-id="${question.id}"]`);
        if (!card) return;

        const correctAnswer = question.correct_answer;
        const userAnswer = examState.answers[question.id];

        if (userAnswer === correctAnswer) {
            score++;
        }

        // Show correct/incorrect indicators
        card.querySelectorAll('.option').forEach(option => {
            option.classList.add('disabled');
            const answer = option.dataset.answer;

            if (answer === correctAnswer) {
                option.classList.add('correct');
                option.querySelector('.option-icon').innerHTML = '<i class="fas fa-check-circle" style="color: #10b981;"></i>';
            } else if (answer === userAnswer && answer !== correctAnswer) {
                option.classList.add('incorrect');
                option.querySelector('.option-icon').innerHTML = '<i class="fas fa-times-circle" style="color: #ef4444;"></i>';
            }
        });

        // Show explanation
        const explanation = card.querySelector('.explanation');
        if (explanation) explanation.classList.remove('hidden');
    });

    examState.score = score;
    log(`Score calculated: ${score}/${examState.totalQuestions}`);

    // Transition to showing score
    setState(EXAM_STATE.SHOWING_SCORE);
}

// =========================================
// SCORE SCREEN - GUARANTEED 10 SECONDS
// =========================================
function showScoreScreen() {
    log('Showing score screen for 10 seconds...');

    // Hide questions
    if (elements.resultsSection) {
        elements.resultsSection.classList.add('hidden');
    }
    hideLoader();

    // Create or show score screen
    let scoreScreen = document.getElementById('score-screen');
    if (!scoreScreen) {
        scoreScreen = createScoreScreen();
        document.querySelector('.container').appendChild(scoreScreen);
    }

    // Update score display
    const isTerminated = examState.sessionBlocked;
    const title = isTerminated ? 'Session Terminated' : 'Exam Completed!';
    const subtitle = isTerminated
        ? 'Your session was terminated due to security violations.'
        : 'Your results have been recorded.';
    const iconClass = isTerminated ? 'error' : 'success';
    const iconHTML = isTerminated
        ? '<i class="fas fa-ban"></i>'
        : '<i class="fas fa-check-circle"></i>';

    scoreScreen.querySelector('.score-title').textContent = title;
    scoreScreen.querySelector('.score-subtitle').textContent = subtitle;
    scoreScreen.querySelector('.score-icon').className = `score-icon ${iconClass}`;
    scoreScreen.querySelector('.score-icon').innerHTML = iconHTML;
    scoreScreen.querySelector('.score-value').textContent = examState.score;
    scoreScreen.querySelector('.score-total').textContent = examState.totalQuestions;

    const percentage = Math.round((examState.score / examState.totalQuestions) * 100);
    const percentageEl = scoreScreen.querySelector('.score-percentage');
    percentageEl.textContent = `${percentage}%`;

    // Color based on score
    if (isTerminated) {
        percentageEl.style.color = '#ef4444';
    } else if (percentage >= 80) {
        percentageEl.style.color = '#10b981';
    } else if (percentage >= 50) {
        percentageEl.style.color = '#f59e0b';
    } else {
        percentageEl.style.color = '#ef4444';
    }

    scoreScreen.classList.remove('hidden');
    scoreScreen.style.display = 'block';

    // Start countdown
    startScoreCountdown();
}

function createScoreScreen() {
    const screen = document.createElement('div');
    screen.id = 'score-screen';
    screen.className = 'score-screen';
    screen.innerHTML = `
        <div class="score-card glass-card">
            <div class="score-header">
                <div class="score-icon success">
                    <i class="fas fa-check-circle"></i>
                </div>
                <h2 class="score-title">Exam Completed!</h2>
                <p class="score-subtitle">Your results have been recorded.</p>
            </div>
            
            <div class="score-display">
                <div class="score-numbers">
                    <span class="score-value">0</span>
                    <span class="score-divider">/</span>
                    <span class="score-total">10</span>
                </div>
                <div class="score-percentage-wrap">
                    <span class="score-percentage">0%</span>
                </div>
            </div>
            
            <div class="score-info">
                <div class="info-item">
                    <i class="fas fa-flask"></i>
                    <span>${window.EXAM_CONFIG?.experimentName || 'Experiment'}</span>
                </div>
                <div class="info-item">
                    <i class="fas fa-cloud-upload-alt"></i>
                    <span>Saving to Google Sheets...</span>
                </div>
            </div>
            
            <div class="redirect-countdown">
                <i class="fas fa-home"></i>
                <span>Returning to dashboard in <strong id="countdown-seconds">10</strong> seconds...</span>
            </div>
        </div>
    `;

    // Add styles
    addScoreScreenStyles();

    return screen;
}

function addScoreScreenStyles() {
    if (document.getElementById('score-screen-styles')) return;

    const style = document.createElement('style');
    style.id = 'score-screen-styles';
    style.textContent = `
        .score-screen {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.9);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 10000;
            animation: fadeIn 0.3s ease;
        }
        .score-screen.hidden { display: none; }
        .score-card {
            background: linear-gradient(145deg, #1a1a2e 0%, #16213e 100%);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 48px;
            max-width: 500px;
            width: 90%;
            text-align: center;
            animation: slideUp 0.4s ease;
        }
        .score-header { margin-bottom: 2rem; }
        .score-icon {
            width: 100px;
            height: 100px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0 auto 1.5rem;
            font-size: 3rem;
        }
        .score-icon.success {
            background: rgba(16, 185, 129, 0.15);
            color: #10b981;
            border: 3px solid rgba(16, 185, 129, 0.4);
        }
        .score-icon.error {
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 3px solid rgba(239, 68, 68, 0.4);
        }
        .score-title {
            font-size: 2rem;
            margin-bottom: 0.5rem;
            color: white;
        }
        .score-subtitle {
            color: rgba(255, 255, 255, 0.6);
            font-size: 1rem;
        }
        .score-display {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 2rem;
            margin-bottom: 1.5rem;
        }
        .score-numbers {
            display: flex;
            align-items: baseline;
            justify-content: center;
            gap: 0.25rem;
        }
        .score-value {
            font-size: 5rem;
            font-weight: 700;
            color: #667eea;
        }
        .score-divider {
            font-size: 2.5rem;
            color: rgba(255, 255, 255, 0.3);
        }
        .score-total {
            font-size: 2.5rem;
            color: rgba(255, 255, 255, 0.6);
        }
        .score-percentage-wrap { margin-top: 0.5rem; }
        .score-percentage {
            font-size: 1.8rem;
            font-weight: 600;
        }
        .score-info { margin-bottom: 1.5rem; }
        .info-item {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            padding: 0.75rem;
            color: rgba(255, 255, 255, 0.7);
        }
        .info-item i { color: #667eea; }
        .redirect-countdown {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 0.75rem;
            padding: 1rem;
            background: rgba(102, 126, 234, 0.1);
            border-radius: 8px;
            color: rgba(255, 255, 255, 0.8);
        }
        .redirect-countdown i { color: #667eea; }
        .redirect-countdown strong {
            color: #667eea;
            font-size: 1.2rem;
        }
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        @keyframes slideUp {
            from { opacity: 0; transform: translateY(30px); }
            to { opacity: 1; transform: translateY(0); }
        }
    `;
    document.head.appendChild(style);
}

function startScoreCountdown() {
    let seconds = 10;
    const countdownEl = document.getElementById('countdown-seconds');

    const tick = () => {
        if (countdownEl) countdownEl.textContent = seconds;

        if (seconds <= 0) {
            // Countdown complete - state machine handles next step
            return;
        }
        seconds--;
        setTimeout(tick, 1000);
    };

    tick();
}

// =========================================
// GOOGLE SHEETS WRITE
// =========================================
async function writeMarksToGoogleSheets() {
    if (examState.marksWriteAttempted) {
        log('Marks write already attempted, skipping...');
        setState(EXAM_STATE.REDIRECTING_HOME);
        return;
    }

    examState.marksWriteAttempted = true;
    log(`Writing marks to Google Sheets: ${examState.score}/${examState.totalQuestions}`);

    try {
        const response = await fetch(CONFIG.SAVE_MARKS_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                experiment_name: window.EXAM_CONFIG.experimentName,
                experiment_id: window.EXAM_CONFIG.experimentId,
                answers: examState.answers,
                session_id: window.EXAM_CONFIG.studentSession,
                viva_session_id: window.EXAM_CONFIG.vivaSessionId,
                score: examState.score  // Send calculated score
            })
        });

        const payload = await response.json().catch(() => ({}));

        if (response.ok && payload.status === 'success') {
            examState.marksSaved = true;
            log('Marks saved to Google Sheets successfully');
            updateSaveStatus(true);
        } else {
            logError('Failed to save marks:', payload);
            updateSaveStatus(false);
        }

    } catch (error) {
        logError('Error saving marks:', error);
        updateSaveStatus(false);
    }

    setState(EXAM_STATE.REDIRECTING_HOME);
}

function updateSaveStatus(success) {
    const infoItem = document.querySelector('.score-info .info-item:last-child span');
    if (infoItem) {
        infoItem.textContent = success
            ? 'Marks saved to Google Sheets ✓'
            : 'Failed to save marks (recorded locally)';
    }
}

// =========================================
// FINAL REDIRECT
// =========================================
function performFinalRedirect() {
    log('Performing final redirect...');

    // Cleanup
    cleanupSecurityListeners();

    // Exit fullscreen
    if (isInFullscreen()) {
        exitFullscreen();
    }

    // Give time for fullscreen to exit
    setTimeout(() => {
        // If this is a popup window, try to close it
        if (window.opener) {
            try {
                // Notify opener to refresh
                if (window.opener.location) {
                    window.opener.location.reload();
                }
                window.close();
                return;
            } catch (e) {
                log('Could not close window, redirecting instead');
            }
        }

        // Fallback: redirect in same tab
        window.location.href = CONFIG.HOME_URL;
    }, 500);
}

// =========================================
// SECURITY - ONLY ACTIVE AFTER MCQs RENDERED
// =========================================
function setupSecurityListeners() {
    // Fullscreen change handlers
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.addEventListener('mozfullscreenchange', handleFullscreenChange);
    document.addEventListener('MSFullscreenChange', handleFullscreenChange);

    // Visibility change (tab switch)
    document.addEventListener('visibilitychange', handleVisibilityChange);

    // Window blur (switching to another window)
    window.addEventListener('blur', handleWindowBlur);

    // Keyboard shortcuts
    document.addEventListener('keydown', handleKeyDown, true);

    // Right-click
    document.addEventListener('contextmenu', handleContextMenu, true);

    // Copy/paste
    document.addEventListener('copy', preventCopyPaste, true);
    document.addEventListener('cut', preventCopyPaste, true);
    document.addEventListener('paste', preventCopyPaste, true);

    // Before unload
    window.addEventListener('beforeunload', handleBeforeUnload);

    log('Security listeners attached');
}

function cleanupSecurityListeners() {
    document.removeEventListener('fullscreenchange', handleFullscreenChange);
    document.removeEventListener('webkitfullscreenchange', handleFullscreenChange);
    document.removeEventListener('mozfullscreenchange', handleFullscreenChange);
    document.removeEventListener('MSFullscreenChange', handleFullscreenChange);
    document.removeEventListener('visibilitychange', handleVisibilityChange);
    window.removeEventListener('blur', handleWindowBlur);
    document.removeEventListener('keydown', handleKeyDown, true);
    document.removeEventListener('contextmenu', handleContextMenu, true);
    document.removeEventListener('copy', preventCopyPaste, true);
    document.removeEventListener('cut', preventCopyPaste, true);
    document.removeEventListener('paste', preventCopyPaste, true);
    window.removeEventListener('beforeunload', handleBeforeUnload);
    log('Security listeners removed');
}

function isSecurityActive() {
    // Security is ONLY active when:
    // 1. MCQs have been rendered
    // 2. Exam is in progress
    // 3. Session is not already blocked
    return examState.securityEnabled &&
        examState.currentState === EXAM_STATE.EXAM_IN_PROGRESS &&
        !examState.sessionBlocked;
}

function handleVisibilityChange() {
    if (!isSecurityActive()) return;

    if (document.hidden) {
        recordViolation('Tab switch detected');
    }
}

function handleWindowBlur() {
    if (!isSecurityActive()) return;
    recordViolation('Window switch detected');
}

function handleFullscreenChange() {
    const wasFullscreen = examState.isFullscreen;
    examState.isFullscreen = isInFullscreen();

    log(`Fullscreen: ${wasFullscreen} → ${examState.isFullscreen}`);

    if (examState.isFullscreen && examState.currentState === EXAM_STATE.EXAM_LOADING) {
        // Entering fullscreen, start generating MCQs
        hideFullscreenPrompt();
        setState(EXAM_STATE.GENERATING_MCQS);
    } else if (!examState.isFullscreen && wasFullscreen && isSecurityActive()) {
        // Exited fullscreen during exam
        recordViolation('Fullscreen mode exited');
    }
}

function handleKeyDown(e) {
    if (!isSecurityActive()) return;

    const key = e.key?.toLowerCase();
    const ctrl = e.ctrlKey;
    const shift = e.shiftKey;

    const blockedCombos = [
        ctrl && key === 'c',
        ctrl && key === 'x',
        ctrl && key === 'v',
        ctrl && key === 'a',
        ctrl && key === 'p',
        ctrl && key === 's',
        ctrl && key === 'u',
        ctrl && shift && key === 'i',
        ctrl && shift && key === 'j',
        key === 'f12',
        key === 'escape'
    ];

    if (blockedCombos.some(b => b)) {
        e.preventDefault();
        e.stopPropagation();
        showBlockedNotification('This action is disabled during the exam');
        return false;
    }
}

function handleContextMenu(e) {
    if (!isSecurityActive()) return;
    e.preventDefault();
    showBlockedNotification('Right-click is disabled');
    return false;
}

function preventCopyPaste(e) {
    if (!isSecurityActive()) return;
    e.preventDefault();
    showBlockedNotification('Copy/paste is disabled');
    return false;
}

function handleBeforeUnload(e) {
    if (examState.currentState === EXAM_STATE.EXAM_IN_PROGRESS && !examState.submissionLocked) {
        e.preventDefault();
        e.returnValue = 'Your exam is in progress. Are you sure you want to leave?';
        return e.returnValue;
    }
}

// =========================================
// VIOLATION HANDLING
// =========================================
function recordViolation(reason) {
    if (!isSecurityActive()) return;

    examState.violationCount++;
    log(`VIOLATION #${examState.violationCount}: ${reason}`);

    if (examState.violationCount >= examState.maxViolations) {
        // Terminate session
        terminateSession(reason);
    } else {
        // Show warning
        showViolationWarning(reason);
    }
}

function terminateSession(reason) {
    log('Terminating session due to violations');

    // Report to server
    reportViolationToServer(reason);

    // Transition to SESSION_TERMINATED state
    setState(EXAM_STATE.SESSION_TERMINATED);
}

async function reportViolationToServer(reason) {
    try {
        await fetch(CONFIG.VIOLATION_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            credentials: 'include',
            body: JSON.stringify({
                viva_session_id: window.EXAM_CONFIG.vivaSessionId,
                reason: reason
            })
        });
    } catch (error) {
        logError('Failed to report violation:', error);
    }
}

// =========================================
// UI HELPERS - MODALS & NOTIFICATIONS
// =========================================
function createSecurityUI() {
    // Fullscreen prompt
    const fullscreenPrompt = document.createElement('div');
    fullscreenPrompt.id = 'fullscreen-prompt';
    fullscreenPrompt.className = 'security-modal';
    fullscreenPrompt.innerHTML = `
        <div class="security-modal-overlay"></div>
        <div class="security-modal-content">
            <div class="security-icon info">
                <i class="fas fa-expand"></i>
            </div>
            <h2>Enter Fullscreen Mode</h2>
            <p>This exam requires fullscreen mode for security purposes.</p>
            <button class="security-btn primary" id="enter-fullscreen-btn">
                <i class="fas fa-expand"></i> Enter Fullscreen
            </button>
        </div>
    `;
    document.body.appendChild(fullscreenPrompt);

    // Warning modal
    const warningModal = document.createElement('div');
    warningModal.id = 'warning-modal';
    warningModal.className = 'security-modal hidden';
    warningModal.innerHTML = `
        <div class="security-modal-overlay"></div>
        <div class="security-modal-content">
            <div class="security-icon warning">
                <i class="fas fa-exclamation-triangle"></i>
            </div>
            <h2>Security Warning</h2>
            <p id="warning-message">A security violation has been detected.</p>
            <div class="violation-counter">
                <span>Violations: </span>
                <strong id="violation-count">0</strong> / <strong>${examState.maxViolations}</strong>
            </div>
            <button class="security-btn" id="continue-btn">Continue Exam</button>
        </div>
    `;
    document.body.appendChild(warningModal);

    // Error modal
    const errorModal = document.createElement('div');
    errorModal.id = 'error-modal';
    errorModal.className = 'security-modal hidden';
    errorModal.innerHTML = `
        <div class="security-modal-overlay"></div>
        <div class="security-modal-content">
            <div class="security-icon error">
                <i class="fas fa-times-circle"></i>
            </div>
            <h2>Error</h2>
            <p id="error-message">An error occurred.</p>
            <button class="security-btn primary" id="retry-btn">Retry</button>
            <button class="security-btn" id="exit-btn">Exit</button>
        </div>
    `;
    document.body.appendChild(errorModal);

    // Bind events
    document.getElementById('enter-fullscreen-btn').addEventListener('click', requestFullscreen);
    document.getElementById('continue-btn').addEventListener('click', handleContinue);
    document.getElementById('retry-btn').addEventListener('click', handleRetry);
    document.getElementById('exit-btn').addEventListener('click', handleExit);
}

function showFullscreenPrompt() {
    const prompt = document.getElementById('fullscreen-prompt');
    if (prompt) prompt.classList.remove('hidden');
}

function hideFullscreenPrompt() {
    const prompt = document.getElementById('fullscreen-prompt');
    if (prompt) prompt.classList.add('hidden');
}

function showViolationWarning(message) {
    const modal = document.getElementById('warning-modal');
    const msgEl = document.getElementById('warning-message');
    const countEl = document.getElementById('violation-count');

    if (msgEl) msgEl.textContent = message;
    if (countEl) countEl.textContent = examState.violationCount;
    if (modal) modal.classList.remove('hidden');
}

function handleContinue() {
    document.getElementById('warning-modal')?.classList.add('hidden');
    if (!isInFullscreen()) {
        requestFullscreen();
    }
}

function showErrorModal(message) {
    const modal = document.getElementById('error-modal');
    const msgEl = document.getElementById('error-message');

    if (msgEl) msgEl.textContent = message;
    if (modal) modal.classList.remove('hidden');
}

function handleRetry() {
    document.getElementById('error-modal')?.classList.add('hidden');
    if (examState.currentState === EXAM_STATE.ERROR) {
        examState.currentState = EXAM_STATE.EXAM_LOADING; // Reset for retry
        setState(EXAM_STATE.GENERATING_MCQS);
    }
}

function handleExit() {
    window.location.href = CONFIG.HOME_URL;
}

// =========================================
// FULLSCREEN HELPERS
// =========================================
function requestFullscreen() {
    const elem = document.documentElement;
    if (elem.requestFullscreen) elem.requestFullscreen();
    else if (elem.webkitRequestFullscreen) elem.webkitRequestFullscreen();
    else if (elem.msRequestFullscreen) elem.msRequestFullscreen();
    else if (elem.mozRequestFullScreen) elem.mozRequestFullScreen();
}

function exitFullscreen() {
    if (document.exitFullscreen) document.exitFullscreen().catch(() => { });
    else if (document.webkitExitFullscreen) document.webkitExitFullscreen();
    else if (document.msExitFullscreen) document.msExitFullscreen();
    else if (document.mozCancelFullScreen) document.mozCancelFullScreen();
}

function isInFullscreen() {
    return !!(document.fullscreenElement || document.webkitFullscreenElement ||
        document.msFullscreenElement || document.mozFullScreenElement);
}

// =========================================
// TOAST NOTIFICATIONS
// =========================================
function showToast(message, type = 'info') {
    const toast = elements.toast;
    if (!toast) return;

    const icon = toast.querySelector('.toast-icon');
    const messageEl = toast.querySelector('.toast-message');

    if (messageEl) messageEl.textContent = message;
    toast.className = 'toast ' + type;

    if (icon) {
        icon.className = 'toast-icon fas ' + (
            type === 'success' ? 'fa-check-circle' :
                type === 'error' ? 'fa-exclamation-circle' : 'fa-info-circle'
        );
    }

    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 4000);
}

function showBlockedNotification(message) {
    let notification = document.getElementById('blocked-notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'blocked-notification';
        notification.className = 'blocked-notification';
        document.body.appendChild(notification);
    }

    notification.innerHTML = `<i class="fas fa-ban"></i> ${message}`;
    notification.classList.add('show');

    setTimeout(() => notification.classList.remove('show'), 2000);
}

// =========================================
// INITIALIZATION
// =========================================
document.addEventListener('DOMContentLoaded', () => {
    log('Exam module initializing...');

    // Validate config
    if (!window.EXAM_CONFIG) {
        logError('EXAM_CONFIG not found!');
        document.body.innerHTML = '<div style="text-align:center;padding:50px;color:red;"><h1>Configuration Error</h1><p>Please reload the page.</p></div>';
        return;
    }

    log('EXAM_CONFIG:', window.EXAM_CONFIG);

    // Initialize
    initElements();
    createSecurityUI();
    setupSecurityListeners();

    // Bind submit button
    if (elements.submitAllBtn) {
        elements.submitAllBtn.addEventListener('click', handleSubmitClick);
    }

    // Show fullscreen prompt
    showFullscreenPrompt();

    log('Exam module ready - waiting for fullscreen');
});
