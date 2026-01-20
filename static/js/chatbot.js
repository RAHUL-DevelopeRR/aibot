/**
 * Floating Chatbot Widget
 * Can be embedded in any page
 */

class ChatbotWidget {
    constructor() {
        this.isOpen = false;
        this.conversationHistory = [];
        this.csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || '';
        this.init();
    }

    init() {
        this.createWidget();
        this.bindEvents();
    }

    createWidget() {
        // Create floating button
        const floatingBtn = document.createElement('div');
        floatingBtn.id = 'chatbot-floating-btn';
        floatingBtn.innerHTML = '<i class="fas fa-robot"></i>';
        floatingBtn.title = 'AI Study Assistant';
        document.body.appendChild(floatingBtn);

        // Create chat window
        const chatWindow = document.createElement('div');
        chatWindow.id = 'chatbot-window';
        chatWindow.innerHTML = `
            <div class="chatbot-header">
                <div class="chatbot-title">
                    <i class="fas fa-robot"></i>
                    <span>AI Assistant</span>
                </div>
                <button class="chatbot-close" id="chatbot-close">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            <div class="chatbot-messages" id="chatbot-messages">
                <div class="message bot-message">
                    <div class="message-content">
                        Hi! 👋 I'm your AI Study Assistant. Ask me anything about your lab experiments!
                    </div>
                </div>
            </div>
            <div class="chatbot-input-area">
                <input type="text" id="chatbot-input" placeholder="Ask a question..." autocomplete="off">
                <button id="chatbot-send"><i class="fas fa-paper-plane"></i></button>
            </div>
        `;
        document.body.appendChild(chatWindow);

        // Add styles
        this.addStyles();
    }

    addStyles() {
        const styles = document.createElement('style');
        styles.textContent = `
            #chatbot-floating-btn {
                position: fixed;
                bottom: 24px;
                right: 24px;
                width: 60px;
                height: 60px;
                border-radius: 50%;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 24px;
                cursor: pointer;
                box-shadow: 0 4px 20px rgba(102, 126, 234, 0.4);
                transition: transform 0.3s, box-shadow 0.3s;
                z-index: 9999;
            }
            #chatbot-floating-btn:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 25px rgba(102, 126, 234, 0.5);
            }
            #chatbot-floating-btn.hidden { display: none; }

            #chatbot-window {
                position: fixed;
                bottom: 100px;
                right: 24px;
                width: 380px;
                height: 500px;
                background: white;
                border-radius: 16px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                display: none;
                flex-direction: column;
                z-index: 9998;
                overflow: hidden;
            }
            #chatbot-window.open { display: flex; }

            #chatbot-window .chatbot-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 14px 16px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            #chatbot-window .chatbot-title {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 600;
            }
            #chatbot-window .chatbot-close {
                background: rgba(255,255,255,0.2);
                border: none;
                color: white;
                width: 28px;
                height: 28px;
                border-radius: 50%;
                cursor: pointer;
                transition: background 0.2s;
            }
            #chatbot-window .chatbot-close:hover {
                background: rgba(255,255,255,0.3);
            }

            #chatbot-window .chatbot-messages {
                flex: 1;
                overflow-y: auto;
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }

            #chatbot-window .message {
                max-width: 85%;
                animation: chatFadeIn 0.3s ease;
            }
            @keyframes chatFadeIn {
                from { opacity: 0; transform: translateY(8px); }
                to { opacity: 1; transform: translateY(0); }
            }

            #chatbot-window .bot-message {
                align-self: flex-start;
            }
            #chatbot-window .user-message {
                align-self: flex-end;
            }

            #chatbot-window .message-content {
                padding: 10px 14px;
                border-radius: 14px;
                line-height: 1.4;
                font-size: 14px;
            }
            #chatbot-window .bot-message .message-content {
                background: #f3f4f6;
                border-bottom-left-radius: 4px;
            }
            #chatbot-window .user-message .message-content {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border-bottom-right-radius: 4px;
            }

            #chatbot-window .chatbot-input-area {
                display: flex;
                gap: 8px;
                padding: 12px 16px;
                border-top: 1px solid #e5e7eb;
            }
            #chatbot-window #chatbot-input {
                flex: 1;
                padding: 10px 14px;
                border: 2px solid #e5e7eb;
                border-radius: 20px;
                outline: none;
                font-size: 14px;
            }
            #chatbot-window #chatbot-input:focus {
                border-color: #667eea;
            }
            #chatbot-window #chatbot-send {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                border: none;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                cursor: pointer;
                transition: transform 0.2s;
            }
            #chatbot-window #chatbot-send:hover {
                transform: scale(1.05);
            }
            #chatbot-window #chatbot-send:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }

            #chatbot-window .typing-dots {
                display: flex;
                gap: 4px;
                padding: 10px 14px;
                background: #f3f4f6;
                border-radius: 14px;
                width: fit-content;
            }
            #chatbot-window .typing-dots span {
                width: 6px;
                height: 6px;
                background: #9ca3af;
                border-radius: 50%;
                animation: dotPulse 1.4s infinite;
            }
            #chatbot-window .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
            #chatbot-window .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
            @keyframes dotPulse {
                0%, 60%, 100% { transform: translateY(0); }
                30% { transform: translateY(-3px); }
            }

            @media (max-width: 480px) {
                #chatbot-window {
                    width: calc(100% - 20px);
                    right: 10px;
                    bottom: 90px;
                    height: 60vh;
                }
            }
        `;
        document.head.appendChild(styles);
    }

    bindEvents() {
        const floatingBtn = document.getElementById('chatbot-floating-btn');
        const closeBtn = document.getElementById('chatbot-close');
        const input = document.getElementById('chatbot-input');
        const sendBtn = document.getElementById('chatbot-send');

        floatingBtn.addEventListener('click', () => this.toggle());
        closeBtn.addEventListener('click', () => this.close());
        sendBtn.addEventListener('click', () => this.sendMessage());
        input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendMessage();
        });
    }

    toggle() {
        this.isOpen = !this.isOpen;
        const window = document.getElementById('chatbot-window');
        const btn = document.getElementById('chatbot-floating-btn');
        
        if (this.isOpen) {
            window.classList.add('open');
            btn.classList.add('hidden');
            document.getElementById('chatbot-input').focus();
        } else {
            window.classList.remove('open');
            btn.classList.remove('hidden');
        }
    }

    close() {
        this.isOpen = false;
        document.getElementById('chatbot-window').classList.remove('open');
        document.getElementById('chatbot-floating-btn').classList.remove('hidden');
    }

    addMessage(content, isUser = false) {
        const messagesDiv = document.getElementById('chatbot-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${isUser ? 'user-message' : 'bot-message'}`;
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = this.formatMessage(content);
        
        messageDiv.appendChild(contentDiv);
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    formatMessage(text) {
        return text
            .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre style="background:#1f2937;color:#e5e7eb;padding:8px;border-radius:6px;overflow-x:auto;font-size:12px;margin:6px 0;"><code>$2</code></pre>')
            .replace(/`([^`]+)`/g, '<code style="background:rgba(0,0,0,0.1);padding:1px 4px;border-radius:3px;font-size:12px;">$1</code>')
            .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
            .replace(/\n/g, '<br>');
    }

    showTyping() {
        const messagesDiv = document.getElementById('chatbot-messages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'message bot-message';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = '<div class="typing-dots"><span></span><span></span><span></span></div>';
        messagesDiv.appendChild(typingDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    hideTyping() {
        const typing = document.getElementById('typing-indicator');
        if (typing) typing.remove();
    }

    async sendMessage() {
        const input = document.getElementById('chatbot-input');
        const sendBtn = document.getElementById('chatbot-send');
        const message = input.value.trim();
        
        if (!message) return;

        // Add user message
        this.addMessage(message, true);
        this.conversationHistory.push({ role: 'user', content: message });

        // Clear and disable input
        input.value = '';
        input.disabled = true;
        sendBtn.disabled = true;

        // Show typing
        this.showTyping();

        try {
            const response = await fetch('/chatbot/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    messages: this.conversationHistory
                })
            });

            const data = await response.json();
            this.hideTyping();

            if (data.success) {
                this.addMessage(data.response);
                this.conversationHistory.push({ role: 'assistant', content: data.response });
            } else {
                this.addMessage('Sorry, I encountered an error. Please try again.');
            }
        } catch (error) {
            this.hideTyping();
            this.addMessage('Network error. Please check your connection.');
        }

        // Re-enable input
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
    }
}

// Initialize chatbot when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatbotWidget = new ChatbotWidget();
});
