/**
 * Anti-cheat module for viva interface
 * Detects tab switches, window blur, copy/paste, and other violations
 * Immediately reports violations to server which finalizes marks as 0
 */

(function() {
    'use strict';
    
    let vivaSessionId = null;
    let isVivaActive = false;
    let violationReported = false;
    
    /**
     * Initialize anti-cheat for a viva session
     * @param {number} sessionId - The viva session ID
     */
    function init(sessionId) {
        vivaSessionId = sessionId;
        isVivaActive = true;
        violationReported = false;
        
        // Bind all event listeners
        bindVisibilityChange();
        bindWindowBlur();
        bindCopyPaste();
        bindContextMenu();
        bindKeyboardShortcuts();
        bindBeforeUnload();
        
        console.log('Anti-cheat initialized for session:', sessionId);
    }
    
    /**
     * Report violation to server - finalizes viva with 0 marks
     * @param {string} reason - Reason for violation
     */
    function reportViolation(reason) {
        if (violationReported || !isVivaActive || !vivaSessionId) {
            return;
        }
        
        violationReported = true;
        
        const token = getCookie('csrf_token');
        
        fetch(`/api/viva/${vivaSessionId}/violation`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token
            },
            body: JSON.stringify({ reason: reason })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showViolationAlert(reason);
                // Redirect to marks page after showing alert
                setTimeout(() => {
                    window.location.href = `/student/viva/marks/${vivaSessionId}`;
                }, 3000);
            }
        })
        .catch(error => {
            console.error('Error reporting violation:', error);
            // Still show alert even if API fails
            showViolationAlert(reason);
        });
    }
    
    /**
     * Show violation alert to user
     */
    function showViolationAlert(reason) {
        // Create overlay
        const overlay = document.createElement('div');
        overlay.id = 'violation-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(220, 53, 69, 0.95);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            z-index: 99999;
            color: white;
            text-align: center;
            padding: 20px;
        `;
        
        overlay.innerHTML = `
            <i class="fas fa-exclamation-triangle" style="font-size: 80px; margin-bottom: 20px;"></i>
            <h1 style="font-size: 32px; margin-bottom: 10px;">Violation Detected!</h1>
            <p style="font-size: 18px; margin-bottom: 20px;">${reason}</p>
            <p style="font-size: 16px;">Your viva has been terminated with <strong>0 marks</strong>.</p>
            <p style="font-size: 14px; margin-top: 20px;">Redirecting to results page...</p>
        `;
        
        document.body.appendChild(overlay);
    }
    
    /**
     * Detect tab/page visibility changes
     */
    function bindVisibilityChange() {
        document.addEventListener('visibilitychange', function() {
            if (document.hidden && isVivaActive) {
                reportViolation('Tab switch detected - You left the viva page');
            }
        });
    }
    
    /**
     * Detect window blur (losing focus)
     */
    function bindWindowBlur() {
        window.addEventListener('blur', function() {
            if (isVivaActive) {
                reportViolation('Window blur detected - You switched to another window');
            }
        });
    }
    
    /**
     * Prevent and detect copy/paste
     */
    function bindCopyPaste() {
        document.addEventListener('copy', function(e) {
            if (isVivaActive) {
                e.preventDefault();
                reportViolation('Copy attempt detected');
            }
        });
        
        document.addEventListener('cut', function(e) {
            if (isVivaActive) {
                e.preventDefault();
                reportViolation('Cut attempt detected');
            }
        });
        
        document.addEventListener('paste', function(e) {
            if (isVivaActive) {
                e.preventDefault();
                reportViolation('Paste attempt detected');
            }
        });
    }
    
    /**
     * Prevent right-click context menu
     */
    function bindContextMenu() {
        document.addEventListener('contextmenu', function(e) {
            if (isVivaActive) {
                e.preventDefault();
                return false;
            }
        });
    }
    
    /**
     * Prevent common keyboard shortcuts
     */
    function bindKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            if (!isVivaActive) return;
            
            // Prevent Ctrl+C, Ctrl+V, Ctrl+X
            if (e.ctrlKey && (e.key === 'c' || e.key === 'v' || e.key === 'x')) {
                e.preventDefault();
                return false;
            }
            
            // Prevent Ctrl+Shift+I (DevTools)
            if (e.ctrlKey && e.shiftKey && e.key === 'I') {
                e.preventDefault();
                reportViolation('Developer tools access attempt');
                return false;
            }
            
            // Prevent F12 (DevTools)
            if (e.key === 'F12') {
                e.preventDefault();
                reportViolation('Developer tools access attempt');
                return false;
            }
            
            // Prevent Ctrl+U (View Source)
            if (e.ctrlKey && e.key === 'u') {
                e.preventDefault();
                return false;
            }
            
            // Prevent Alt+Tab warning (can't actually prevent, but detect)
            if (e.altKey && e.key === 'Tab') {
                e.preventDefault();
                return false;
            }
        });
    }
    
    /**
     * Warn before page unload
     */
    function bindBeforeUnload() {
        window.addEventListener('beforeunload', function(e) {
            if (isVivaActive && !violationReported) {
                // Report violation for attempting to leave
                reportViolation('Attempted to leave/refresh the viva page');
                
                // Show confirmation dialog
                e.preventDefault();
                e.returnValue = 'Leaving this page will terminate your viva with 0 marks. Are you sure?';
                return e.returnValue;
            }
        });
    }
    
    /**
     * Disable anti-cheat (called when viva is legitimately submitted)
     */
    function disable() {
        isVivaActive = false;
        console.log('Anti-cheat disabled');
    }
    
    /**
     * Get cookie value by name
     */
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
    
    // Expose public API
    window.AntiCheat = {
        init: init,
        disable: disable,
        reportViolation: reportViolation
    };
})();
