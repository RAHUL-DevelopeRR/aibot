/**
 * Enhanced Anti-cheat module for viva interface
 * 
 * Security Features:
 * - Force fullscreen mode on entry
 * - Auto-submit viva if fullscreen exits
 * - Detect tab switches and window blur
 * - Block right-click, copy, paste, cut
 * - Block keyboard shortcuts (F12, Escape, Tab, Ctrl, Alt)
 * - Immediately reports violations to server (0 marks)
 */

(function() {
    'use strict';
    
    let vivaSessionId = null;
    let isVivaActive = false;
    let violationReported = false;
    let fullscreenEntered = false;
    
    /**
     * Initialize anti-cheat for a viva session
     * @param {number} sessionId - The viva session ID
     */
    function init(sessionId) {
        vivaSessionId = sessionId;
        isVivaActive = true;
        violationReported = false;
        fullscreenEntered = false;
        
        // Bind all event listeners
        bindFullscreenChange();
        bindVisibilityChange();
        bindWindowBlur();
        bindCopyPaste();
        bindContextMenu();
        bindKeyboardShortcuts();
        bindBeforeUnload();
        bindTextSelection();
        
        console.log('Enhanced Anti-cheat initialized for session:', sessionId);
        
        // Request fullscreen after a brief delay
        setTimeout(() => {
            requestFullscreen();
        }, 500);
    }
    
    /**
     * Request fullscreen mode
     */
    function requestFullscreen() {
        const elem = document.documentElement;
        
        if (elem.requestFullscreen) {
            elem.requestFullscreen().then(() => {
                fullscreenEntered = true;
                console.log('Fullscreen entered');
            }).catch(err => {
                console.warn('Fullscreen request failed:', err);
                showFullscreenWarning();
            });
        } else if (elem.webkitRequestFullscreen) { // Safari
            elem.webkitRequestFullscreen();
            fullscreenEntered = true;
        } else if (elem.msRequestFullscreen) { // IE11
            elem.msRequestFullscreen();
            fullscreenEntered = true;
        } else {
            showFullscreenWarning();
        }
    }
    
    /**
     * Show fullscreen warning if API not supported
     */
    function showFullscreenWarning() {
        const banner = document.querySelector('.warning-banner');
        if (banner) {
            banner.innerHTML = `
                <i class="fas fa-exclamation-triangle"></i>
                <strong>Warning:</strong> Your browser doesn't support fullscreen mode. 
                Please use Chrome or Firefox for secure viva. Any tab switch will result in <strong>0 marks</strong>.
            `;
            banner.style.background = '#f8d7da';
            banner.style.borderColor = '#f5c6cb';
            banner.style.color = '#721c24';
        }
    }
    
    /**
     * Bind fullscreen change event - auto-submit if exited
     */
    function bindFullscreenChange() {
        document.addEventListener('fullscreenchange', handleFullscreenChange);
        document.addEventListener('webkitfullscreenchange', handleFullscreenChange);
        document.addEventListener('mozfullscreenchange', handleFullscreenChange);
        document.addEventListener('MSFullscreenChange', handleFullscreenChange);
    }
    
    function handleFullscreenChange() {
        const isFullscreen = !!(
            document.fullscreenElement ||
            document.webkitFullscreenElement ||
            document.mozFullScreenElement ||
            document.msFullscreenElement
        );
        
        if (!isFullscreen && isVivaActive && fullscreenEntered) {
            // Fullscreen was exited - this is a violation
            reportViolation('Fullscreen mode exited - Viva terminated');
        }
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
        isVivaActive = false;
        
        const token = getCookie('csrf_token');
        
        fetch(`/api/viva/${vivaSessionId}/violation`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token
            },
            body: JSON.stringify({ reason: reason })
        })
        .then(response => {
            // Check if response is JSON before parsing
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return response.json();
            }
            // If not JSON, return a default object
            return { success: true, fallback: true };
        })
        .then(data => {
            showViolationAlert(reason);
            // Redirect to marks page after showing alert
            setTimeout(() => {
                window.location.href = `/student/viva/marks/${vivaSessionId}`;
            }, 3000);
        })
        .catch(error => {
            console.error('Error reporting violation:', error);
            // Still show alert even if API fails
            showViolationAlert(reason);
            setTimeout(() => {
                window.location.href = `/student/viva/marks/${vivaSessionId}`;
            }, 3000);
        });
    }
    
    /**
     * Show violation alert to user
     */
    function showViolationAlert(reason) {
        // Exit fullscreen first if still in it
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
        }
        
        // Create overlay
        const overlay = document.createElement('div');
        overlay.id = 'violation-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(135deg, #dc3545 0%, #c82333 100%);
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
            <i class="fas fa-exclamation-triangle" style="font-size: 80px; margin-bottom: 20px; animation: pulse 1s infinite;"></i>
            <h1 style="font-size: 36px; margin-bottom: 15px; font-weight: 700;">VIOLATION DETECTED!</h1>
            <p style="font-size: 20px; margin-bottom: 10px; max-width: 500px;">${reason}</p>
            <div style="background: rgba(0,0,0,0.3); padding: 20px 40px; border-radius: 10px; margin-top: 20px;">
                <p style="font-size: 24px; font-weight: 600; margin: 0;">Your Score: <span style="font-size: 32px;">0 / 10</span></p>
            </div>
            <p style="font-size: 14px; margin-top: 30px; opacity: 0.8;">Redirecting to results page in 3 seconds...</p>
            <style>
                @keyframes pulse {
                    0%, 100% { transform: scale(1); }
                    50% { transform: scale(1.1); }
                }
            </style>
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
     * Detect window blur (losing focus) - with debounce to prevent false positives
     */
    let blurTimeout = null;
    function bindWindowBlur() {
        window.addEventListener('blur', function() {
            if (isVivaActive && !violationReported) {
                // Add a small delay to prevent false positives from browser UI interactions
                blurTimeout = setTimeout(() => {
                    if (!document.hasFocus() && isVivaActive && !violationReported) {
                        reportViolation('Window focus lost - You switched to another window');
                    }
                }, 500);
            }
        });
        
        window.addEventListener('focus', function() {
            // Clear pending violation if user returns quickly
            if (blurTimeout) {
                clearTimeout(blurTimeout);
                blurTimeout = null;
            }
        });
    }
    
    /**
     * Prevent and detect copy/paste/cut
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
                showWarningToast('Right-click is disabled during viva');
                return false;
            }
        });
    }
    
    /**
     * Prevent text selection
     */
    function bindTextSelection() {
        document.addEventListener('selectstart', function(e) {
            if (isVivaActive) {
                // Allow selection in MCQ options for clicking
                if (e.target.closest('.mcq-option') || e.target.closest('input')) {
                    return true;
                }
                e.preventDefault();
                return false;
            }
        });
    }
    
    /**
     * Prevent keyboard shortcuts - ENHANCED
     */
    function bindKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            if (!isVivaActive) return;
            
            // Block Escape key
            if (e.key === 'Escape') {
                e.preventDefault();
                showWarningToast('Escape key is disabled during viva');
                return false;
            }
            
            // Block Tab key (prevents tabbing out)
            if (e.key === 'Tab' && !e.target.closest('.mcq-options')) {
                e.preventDefault();
                showWarningToast('Tab navigation is disabled during viva');
                return false;
            }
            
            // Block F12 (DevTools)
            if (e.key === 'F12') {
                e.preventDefault();
                reportViolation('Developer tools access attempt (F12)');
                return false;
            }
            
            // Block all Ctrl combinations except radio buttons
            if (e.ctrlKey) {
                e.preventDefault();
                
                // Report for dangerous shortcuts
                if (e.key === 'c' || e.key === 'v' || e.key === 'x') {
                    reportViolation(`Clipboard shortcut detected (Ctrl+${e.key.toUpperCase()})`);
                } else if (e.shiftKey && e.key === 'I') {
                    reportViolation('Developer tools access attempt (Ctrl+Shift+I)');
                } else if (e.key === 'u') {
                    // View source - just block
                    showWarningToast('Viewing source is disabled');
                } else if (e.key === 'p') {
                    showWarningToast('Printing is disabled during viva');
                } else if (e.key === 's') {
                    showWarningToast('Saving is disabled during viva');
                }
                return false;
            }
            
            // Block all Alt combinations
            if (e.altKey) {
                e.preventDefault();
                if (e.key === 'Tab') {
                    reportViolation('Alt+Tab detected - Window switching attempted');
                } else if (e.key === 'F4') {
                    showWarningToast('Closing window is not allowed during viva');
                }
                return false;
            }
            
            // Block other function keys
            if (['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7', 'F8', 'F9', 'F10', 'F11'].includes(e.key)) {
                e.preventDefault();
                if (e.key === 'F5') {
                    showWarningToast('Refresh is disabled during viva');
                } else if (e.key === 'F11') {
                    // F11 toggles fullscreen - allow but warn
                    showWarningToast('Use the viva interface, do not toggle fullscreen');
                }
                return false;
            }
        });
    }
    
    /**
     * Show a temporary warning toast
     */
    function showWarningToast(message) {
        // Remove existing toast
        const existing = document.getElementById('warning-toast');
        if (existing) existing.remove();
        
        const toast = document.createElement('div');
        toast.id = 'warning-toast';
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%);
            color: #212529;
            padding: 12px 24px;
            border-radius: 8px;
            font-weight: 600;
            font-size: 14px;
            z-index: 99998;
            box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            animation: slideUp 0.3s ease-out;
        `;
        toast.innerHTML = `<i class="fas fa-exclamation-circle" style="margin-right: 8px;"></i>${message}`;
        
        // Add animation style
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideUp {
                from { opacity: 0; transform: translateX(-50%) translateY(20px); }
                to { opacity: 1; transform: translateX(-50%) translateY(0); }
            }
        `;
        document.head.appendChild(style);
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.remove();
        }, 2500);
    }
    
    /**
     * Warn before page unload - only show confirmation, don't report violation
     * Violation will be handled by visibility change or session timeout
     */
    function bindBeforeUnload() {
        window.addEventListener('beforeunload', function(e) {
            if (isVivaActive && !violationReported) {
                // Only show confirmation dialog - don't report violation here
                // This prevents issues with page refresh during normal operation
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
        violationReported = true; // Prevent further violations
        
        // Exit fullscreen
        if (document.fullscreenElement) {
            document.exitFullscreen().catch(() => {});
        }
        
        console.log('Anti-cheat disabled - viva submitted');
    }
    
    /**
     * Get cookie value by name (or from meta tag for csrf_token)
     */
    function getCookie(name) {
        // First try to get from meta tag (for csrf_token)
        if (name === 'csrf_token') {
            const meta = document.querySelector('meta[name="csrf-token"]');
            if (meta) return meta.getAttribute('content');
        }
        // Fallback to cookie
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
        reportViolation: reportViolation,
        requestFullscreen: requestFullscreen
    };
})();
