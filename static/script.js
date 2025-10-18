// Nova AI - Enhanced JavaScript with All Features

// State
let currentUser = null;
let currentConversationId = null;
let isRecording = false;
let recognition = null;

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
    setupEventListeners();
    setupSpeechRecognition();
    initializeMarked();
});

// ============================================================
// AUTHENTICATION
// ============================================================

async function checkAuthStatus() {
    try {
        const response = await fetch('/auth/status');
        const data = await response.json();
        
        if (data.authenticated) {
            currentUser = data.user;
            hideAuthModal();
            showApp();
            loadConversations();
            applyUserSettings(data.user);
        } else {
            showAuthModal();
        }
    } catch (error) {
        console.error('Auth check failed:', error);
        showAuthModal();
    }
}

function showAuthModal() {
    document.getElementById('auth-modal').classList.remove('hidden');
}

function hideAuthModal() {
    document.getElementById('auth-modal').classList.add('hidden');
}

function showApp() {
    document.getElementById('username-display').textContent = currentUser.username;
    document.getElementById('user-avatar').textContent = currentUser.username[0].toUpperCase();
}

// Login
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;
    const errorDiv = document.getElementById('login-error');
    
    try {
        const response = await fetch('/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data.user;
            hideAuthModal();
            showApp();
            loadConversations();
            applyUserSettings(data.user);
        } else {
            errorDiv.textContent = data.error;
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = 'Login failed. Please try again.';
        errorDiv.style.display = 'block';
    }
});

// Signup
document.getElementById('signup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const username = document.getElementById('signup-username').value;
    const email = document.getElementById('signup-email').value;
    const password = document.getElementById('signup-password').value;
    const errorDiv = document.getElementById('signup-error');
    
    try {
        const response = await fetch('/auth/signup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            currentUser = data.user;
            hideAuthModal();
            showApp();
            loadConversations();
            applyUserSettings(data.user);
        } else {
            errorDiv.textContent = data.error;
            errorDiv.style.display = 'block';
        }
    } catch (error) {
        errorDiv.textContent = 'Signup failed. Please try again.';
        errorDiv.style.display = 'block';
    }
});

// Toggle auth forms
document.getElementById('show-signup').addEventListener('click', () => {
    document.getElementById('login-form').style.display = 'none';
    document.getElementById('signup-form').style.display = 'flex';
    document.getElementById('login-error').style.display = 'none';
});

document.getElementById('show-login').addEventListener('click', () => {
    document.getElementById('signup-form').style.display = 'none';
    document.getElementById('login-form').style.display = 'flex';
    document.getElementById('signup-error').style.display = 'none';
});

// Logout
document.getElementById('logout-btn').addEventListener('click', async () => {
    try {
        await fetch('/auth/logout', { method: 'POST' });
        currentUser = null;
        currentConversationId = null;
        clearMessages();
        showAuthModal();
    } catch (error) {
        console.error('Logout failed:', error);
    }
});

// ============================================================
// USER SETTINGS
// ============================================================

function applyUserSettings(user) {
    // Apply theme
    setTheme(user.theme);
}

// Theme switching
function setTheme(theme) {
    const body = document.body;
    body.className = theme === 'dark' ? 'dark-mode' : 'light-mode';
    
    // Update active button
    document.querySelectorAll('[data-theme]').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.theme === theme);
    });
}

document.querySelectorAll('[data-theme]').forEach(btn => {
    btn.addEventListener('click', async () => {
        const theme = btn.dataset.theme;
        setTheme(theme);
        
        if (currentUser) {
            try {
                await fetch('/api/settings/theme', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ theme })
                });
            } catch (error) {
                console.error('Failed to save theme:', error);
            }
        }
    });
});

// ============================================================
// CONVERSATIONS
// ============================================================

async function loadConversations() {
    try {
        const response = await fetch('/api/conversations');
        const data = await response.json();
        
        const list = document.getElementById('conversations-list');
        list.innerHTML = '';
        
        data.conversations.forEach(conv => {
            const item = document.createElement('div');
            item.className = 'conversation-item';
            if (conv.id === currentConversationId) {
                item.classList.add('active');
            }
            
            const date = new Date(conv.updated_at);
            const dateStr = date.toLocaleDateString();
            
            item.innerHTML = `
                <div class="conversation-title">${conv.title}</div>
                <div class="conversation-date">${dateStr} • ${conv.message_count} messages</div>
            `;
            
            item.addEventListener('click', () => loadConversation(conv.id));
            list.appendChild(item);
        });
    } catch (error) {
        console.error('Failed to load conversations:', error);
    }
}

async function loadConversation(conversationId) {
    try {
        const response = await fetch(`/api/conversations/${conversationId}`);
        const data = await response.json();
        
        currentConversationId = conversationId;
        
        // Clear and load messages
        clearMessages();
        
        data.conversation.messages.forEach(msg => {
            addMessage(msg.content, msg.role);
        });
        
        // Update active state
        document.querySelectorAll('.conversation-item').forEach(item => {
            item.classList.remove('active');
        });
        event.target.closest('.conversation-item')?.classList.add('active');
        
    } catch (error) {
        console.error('Failed to load conversation:', error);
    }
}

document.getElementById('new-chat-btn').addEventListener('click', () => {
    currentConversationId = null;
    clearMessages();
    showWelcomeScreen();
    
    // Remove active state from conversations
    document.querySelectorAll('.conversation-item').forEach(item => {
        item.classList.remove('active');
    });
});

// ============================================================
// EXPORT
// ============================================================

document.getElementById('export-txt-btn').addEventListener('click', async () => {
    if (!currentConversationId) {
        alert('No conversation to export. Start chatting first!');
        return;
    }
    
    try {
        const response = await fetch(`/api/export/${currentConversationId}/txt`);
        const blob = await response.blob();
        downloadFile(blob, `nova_conversation_${currentConversationId}.txt`);
    } catch (error) {
        console.error('Export TXT failed:', error);
        alert('Failed to export conversation');
    }
});

document.getElementById('export-pdf-btn').addEventListener('click', async () => {
    if (!currentConversationId) {
        alert('No conversation to export. Start chatting first!');
        return;
    }
    
    try {
        const response = await fetch(`/api/export/${currentConversationId}/pdf`);
        const blob = await response.blob();
        downloadFile(blob, `nova_conversation_${currentConversationId}.pdf`);
    } catch (error) {
        console.error('Export PDF failed:', error);
        alert('Failed to export conversation');
    }
});

function downloadFile(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ============================================================
// VOICE INPUT
// ============================================================

function setupSpeechRecognition() {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;
        recognition.lang = 'en-US';
        
        recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            document.getElementById('message-input').value = transcript;
            stopRecording();
        };
        
        recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            stopRecording();
        };
        
        recognition.onend = () => {
            stopRecording();
        };
    }
}

document.getElementById('voice-btn').addEventListener('click', () => {
    if (!recognition) {
        alert('Speech recognition not supported in your browser');
        return;
    }
    
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
});

function startRecording() {
    isRecording = true;
    recognition.start();
    document.getElementById('voice-btn').classList.add('recording');
}

function stopRecording() {
    isRecording = false;
    if (recognition) {
        recognition.stop();
    }
    document.getElementById('voice-btn').classList.remove('recording');
}

// ============================================================
// MESSAGES & CHAT
// ============================================================

function setupEventListeners() {
    const sendBtn = document.getElementById('send-btn');
    const messageInput = document.getElementById('message-input');
    
    sendBtn.addEventListener('click', sendMessage);
    
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Auto-resize textarea
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = messageInput.scrollHeight + 'px';
    });
}

async function sendMessage() {
    const input = document.getElementById('message-input');
    const message = input.value.trim();
    
    if (!message) return;
    
    // Hide welcome screen
    hideWelcomeScreen();
    
    // Add user message
    addMessage(message, 'user');
    input.value = '';
    input.style.height = 'auto';
    
    // Show typing indicator
    showTypingIndicator();
    
    // Disable send button
    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;
    
    try {
        const response = await fetch('/api/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                message,
                conversation_id: currentConversationId
            })
        });
        
        const data = await response.json();
        
        // Update conversation ID
        if (data.conversation_id) {
            currentConversationId = data.conversation_id;
        }
        
        // Hide typing indicator
        hideTypingIndicator();
        
        // Add assistant message
        addMessage(data.reply, 'assistant');
        
        // Reload conversations list
        if (currentUser) {
            loadConversations();
        }
        
    } catch (error) {
        console.error('Send message failed:', error);
        hideTypingIndicator();
        addMessage('⚠️ Sorry, something went wrong. Please try again.', 'assistant');
    } finally {
        sendBtn.disabled = false;
    }
}

function addMessage(content, role) {
    const container = document.getElementById('messages-container');
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const avatar = document.createElement('div');
    avatar.className = 'message-avatar';
    avatar.textContent = role === 'user' ? currentUser?.username[0].toUpperCase() || 'U' : '🤖';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Process content with Markdown and code highlighting
    if (role === 'assistant') {
        contentDiv.innerHTML = marked.parse(content);
        
        // Apply syntax highlighting to code blocks
        contentDiv.querySelectorAll('pre code').forEach((block) => {
            hljs.highlightElement(block);
        });
    } else {
        contentDiv.textContent = content;
    }
    
    messageDiv.appendChild(avatar);
    messageDiv.appendChild(contentDiv);
    
    container.appendChild(messageDiv);
    scrollToBottom();
}

function showTypingIndicator() {
    document.getElementById('typing-indicator').classList.add('show');
    scrollToBottom();
}

function hideTypingIndicator() {
    document.getElementById('typing-indicator').classList.remove('show');
}

function clearMessages() {
    const container = document.getElementById('messages-container');
    const messages = container.querySelectorAll('.message, .welcome-screen');
    messages.forEach(msg => {
        if (!msg.id || msg.id !== 'typing-indicator') {
            msg.remove();
        }
    });
}

function showWelcomeScreen() {
    const container = document.getElementById('messages-container');
    const welcomeScreen = `
        <div class="welcome-screen" id="welcome-screen">
            <div class="welcome-icon">🤖</div>
            <h2 class="welcome-title">Welcome to Nova AI</h2>
            <p class="welcome-subtitle">Your intelligent assistant powered by advanced AI</p>
            
            <div class="welcome-features">
                <div class="feature-card">
                    <div class="feature-icon">💬</div>
                    <div class="feature-title">Natural Conversations</div>
                    <div class="feature-desc">Chat naturally with context-aware responses</div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">💾</div>
                    <div class="feature-title">Save History</div>
                    <div class="feature-desc">All conversations automatically saved</div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🎨</div>
                    <div class="feature-title">Dark Mode</div>
                    <div class="feature-desc">Easy on your eyes, day or night</div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">🎤</div>
                    <div class="feature-title">Voice Input</div>
                    <div class="feature-desc">Speak your questions naturally</div>
                </div>
                <div class="feature-card">
                    <div class="feature-icon">💻</div>
                    <div class="feature-title">Code Highlighting</div>
                    <div class="feature-desc">Beautiful syntax highlighting for code</div>
                </div>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('afterbegin', welcomeScreen);
}

function hideWelcomeScreen() {
    const welcomeScreen = document.getElementById('welcome-screen');
    if (welcomeScreen) {
        welcomeScreen.remove();
    }
}

function scrollToBottom() {
    const container = document.getElementById('messages-container');
    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
    }, 100);
}

// ============================================================
// MARKDOWN CONFIGURATION
// ============================================================

function initializeMarked() {
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            highlight: function(code, lang) {
                if (lang && hljs.getLanguage(lang)) {
                    try {
                        return hljs.highlight(code, { language: lang }).value;
                    } catch (err) {}
                }
                return hljs.highlightAuto(code).value;
            },
            breaks: true,
            gfm: true
        });
    }
}