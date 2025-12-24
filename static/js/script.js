class ChatManager {
    constructor() {
        this.chats = JSON.parse(localStorage.getItem('medicalChats')) || {};
        this.currentChatId = null;
        this.currentMessages = [];
        this.initializeElements();
        this.bindEvents();
        this.showWelcomeMessage();
        this.updateChatHistory();
    }

    initializeElements() {
        this.queryForm = document.getElementById('queryForm');
        this.queryInput = document.getElementById('queryInput');
        this.submitBtn = document.getElementById('submitBtn');
        this.messagesContainer = document.getElementById('messagesContainer');
        this.chatHistory = document.getElementById('chatHistory');
        this.newChatBtn = document.getElementById('newChatBtn');
        this.clearChatBtn = document.getElementById('clearChatBtn');
        this.sidebarToggle = document.getElementById('sidebarToggle');
        this.sidebar = document.getElementById('sidebar');
    }

    bindEvents() {
        this.queryForm.addEventListener('submit', (e) => this.handleSubmit(e));
        this.newChatBtn.addEventListener('click', () => this.createNewChat());
        this.clearChatBtn.addEventListener('click', () => this.clearCurrentChat());
        this.sidebarToggle.addEventListener('click', () => this.toggleSidebar());
        
        // Example query clicks
        document.addEventListener('click', (e) => {
            if (e.target.closest('.example-query')) {
                const query = e.target.closest('.example-query').dataset.query;
                this.queryInput.value = query;
                this.handleSubmit(e);
            }
        });

        // Chat history clicks
        this.chatHistory.addEventListener('click', (e) => {
            const historyItem = e.target.closest('.history-item');
            if (historyItem) {
                this.switchChat(historyItem.dataset.chatId);
            }
        });

        // Close sidebar on mobile when clicking outside
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 && 
                !this.sidebar.contains(e.target) && 
                !this.sidebarToggle.contains(e.target)) {
                this.sidebar.classList.remove('open');
            }
        });
    }

    async handleSubmit(e) {
        e.preventDefault();
        const query = this.queryInput.value.trim();
        
        if (!query) return;

        this.hideWelcomeMessage();
        this.addMessage('user', query);
        this.queryInput.value = '';
        this.setLoading(true);

        try {
            const response = await fetch('/query', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query })
            });
            
            const data = await response.json();
            this.setLoading(false);

            if (data.error) {
                this.addMessage('assistant', data.error, 'error');
            } else if (data.warning) {
                this.addMessage('assistant', data.warning + ' Try a different disease name or consult a healthcare professional.', 'warning');
            } else {
                this.addMessage('assistant', data.response);
            }

            this.saveCurrentChat();
            this.updateChatHistory();
        } catch (error) {
            this.setLoading(false);
            this.addMessage('assistant', 'Error: Unable to process query. Please try again.', 'error');
        }
    }

    addMessage(sender, content, type = '') {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${sender} ${type}`;
        
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        messageDiv.innerHTML = `
            <div class="message-avatar">
                <i class="fas ${sender === 'user' ? 'fa-user' : 'fa-user-md'}"></i>
            </div>
            <div class="message-content">
                <div class="message-bubble">${this.formatMessage(content)}</div>
                <div class="message-time">${time}</div>
            </div>
        `;

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();

        // Add to current messages array
        this.currentMessages.push({ sender, content, type, time });
    }

    formatMessage(content) {
        return content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
    }

    setLoading(loading) {
        if (loading) {
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'message assistant loading-message';
            loadingDiv.innerHTML = `
                <div class="message-avatar">
                    <i class="fas fa-user-md"></i>
                </div>
                <div class="message-content">
                    <div class="message-bubble">
                        <div class="loading">
                            <span>Thinking</span>
                            <div class="loading-dots">
                                <div class="loading-dot"></div>
                                <div class="loading-dot"></div>
                                <div class="loading-dot"></div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            this.messagesContainer.appendChild(loadingDiv);
            this.scrollToBottom();
            this.submitBtn.disabled = true;
        } else {
            const loadingMessage = this.messagesContainer.querySelector('.loading-message');
            if (loadingMessage) {
                loadingMessage.remove();
            }
            this.submitBtn.disabled = false;
        }
    }

    hideWelcomeMessage() {
        const welcomeMessage = this.messagesContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.style.display = 'none';
        }
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    createNewChat() {
        // Save current messages to history if any exist
        if (this.currentMessages.length > 0) {
            const chatId = 'chat_' + Date.now();
            const firstUserMessage = this.currentMessages.find(msg => msg.sender === 'user');
            const title = firstUserMessage ? firstUserMessage.content.substring(0, 50) + '...' : 'Previous Chat';
            
            this.chats[chatId] = {
                messages: [...this.currentMessages],
                title: title,
                lastUpdated: new Date().toISOString()
            };
            this.saveChats();
        }
        
        // Reset current chat
        this.currentChatId = null;
        this.currentMessages = [];
        this.clearMessages();
        this.showWelcomeMessage();
        this.updateChatHistory();
    }

    clearCurrentChat() {
        this.currentMessages = [];
        this.currentChatId = null;
        this.clearMessages();
        this.showWelcomeMessage();
    }

    clearMessages() {
        this.messagesContainer.innerHTML = '';
    }

    showWelcomeMessage() {
        this.messagesContainer.innerHTML = `
            <div class="welcome-message">
                <div class="welcome-icon">
                    <i class="fas fa-user-md"></i>
                </div>
                <h2>Welcome to Medical RAG Assistant</h2>
                <p>Ask about disease symptoms, precautions, or related conditions</p>
                <div class="example-queries">
                    <div class="example-query" data-query="What are the symptoms of pneumonia?">
                        <i class="fas fa-question-circle"></i>
                        What are the symptoms of pneumonia?
                    </div>
                    <div class="example-query" data-query="How can I prevent Malaria?">
                        <i class="fas fa-heart"></i>
                        How can I prevent Malaria?
                    </div>
                    <div class="example-query" data-query="Tell me about fungal infections">
                        <i class="fas fa-microscope"></i>
                        Tell me about fungal infections
                    </div>
                </div>
            </div>
        `;
    }

    switchChat(chatId) {
        // Save current messages if any
        if (this.currentMessages.length > 0) {
            const newChatId = 'chat_' + Date.now();
            const firstUserMessage = this.currentMessages.find(msg => msg.sender === 'user');
            const title = firstUserMessage ? firstUserMessage.content.substring(0, 50) + '...' : 'Previous Chat';
            
            this.chats[newChatId] = {
                messages: [...this.currentMessages],
                title: title,
                lastUpdated: new Date().toISOString()
            };
            this.saveChats();
        }

        // Load selected chat
        this.currentChatId = chatId;
        this.currentMessages = [];
        this.loadSelectedChat(chatId);
        this.updateActiveChat();
        
        // Close sidebar on mobile
        if (window.innerWidth <= 768) {
            this.sidebar.classList.remove('open');
        }
    }

    loadSelectedChat(chatId) {
        this.clearMessages();
        
        if (this.chats[chatId] && this.chats[chatId].messages.length > 0) {
            this.chats[chatId].messages.forEach(msg => {
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${msg.sender} ${msg.type || ''}`;
                
                messageDiv.innerHTML = `
                    <div class="message-avatar">
                        <i class="fas ${msg.sender === 'user' ? 'fa-user' : 'fa-user-md'}"></i>
                    </div>
                    <div class="message-content">
                        <div class="message-bubble">${this.formatMessage(msg.content)}</div>
                        <div class="message-time">${msg.time}</div>
                    </div>
                `;
                
                this.messagesContainer.appendChild(messageDiv);
            });
            this.scrollToBottom();
        }
    }

    saveCurrentChat() {
        // This method is no longer needed as we handle saving in createNewChat and switchChat
    }

    loadCurrentChat() {
        // This method is no longer needed as we use currentMessages array
    }

    saveChats() {
        localStorage.setItem('medicalChats', JSON.stringify(this.chats));
    }

    updateChatHistory() {
        // Get all saved chats sorted by most recent
        const chatEntries = Object.entries(this.chats)
            .filter(([id, chat]) => chat.messages.length > 0)
            .sort(([,a], [,b]) => new Date(b.lastUpdated || 0) - new Date(a.lastUpdated || 0));

        // Clear and populate history
        this.chatHistory.innerHTML = '';

        chatEntries.forEach(([chatId, chat]) => {
            const historyItem = document.createElement('div');
            historyItem.className = `history-item ${chatId === this.currentChatId ? 'active' : ''}`;
            historyItem.dataset.chatId = chatId;
            
            const title = chat.title || 'Previous Chat';
            
            historyItem.innerHTML = `
                <i class="fas fa-comment"></i>
                <span>${title}</span>
            `;
            
            this.chatHistory.appendChild(historyItem);
        });
    }

    updateActiveChat() {
        document.querySelectorAll('.history-item').forEach(item => {
            item.classList.toggle('active', item.dataset.chatId === this.currentChatId);
        });
    }

    toggleSidebar() {
        this.sidebar.classList.toggle('open');
    }
}

// Initialize the chat manager when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new ChatManager();
});