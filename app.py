"""
Nova AI Flask Application - Enhanced Version
=============================================
Features:
- User Authentication (Login/Signup)
- Chat History Database
- Export Conversations (PDF/TXT)
- Multi-language Support
- Dark Mode
- Voice Input
- Typing Indicators
- Code Syntax Highlighting
"""

import os
import logging
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from threading import Lock
import json
import secrets

from flask import Flask, render_template, request, jsonify, abort, session, send_file, make_response
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import HTTPException
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import io

from chatbot_logic import NovaAssistant

# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

class Config:
    """Application configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    ENV = os.environ.get('FLASK_ENV', 'development')
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///nova_ai.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Session
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = not DEBUG
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # API Settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    JSON_SORT_KEYS = False
    
    # Rate Limiting
    RATE_LIMIT_ENABLED = True
    RATE_LIMIT_REQUESTS = 30
    RATE_LIMIT_WINDOW = 60
    
    # CORS Settings
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*').split(',')
    
    # Logging
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'logs/nova_ai.log')


# ============================================================
# APPLICATION INITIALIZATION
# ============================================================

app = Flask(__name__)
app.config.from_object(Config)

# Database
db = SQLAlchemy(app)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# CORS
CORS(app, resources={r"/api/*": {"origins": Config.CORS_ORIGINS}}, supports_credentials=True)

# ============================================================
# DATABASE MODELS
# ============================================================

class User(UserMixin, db.Model):
    """User model for authentication."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    theme = db.Column(db.String(10), default='light')  # light or dark
    language = db.Column(db.String(5), default='en')  # en, es, fr, etc.
    
    # Relationships
    conversations = db.relationship('Conversation', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Conversation(db.Model):
    """Conversation model for storing chat history."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), default='New Conversation')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    messages = db.relationship('Message', backref='conversation', lazy=True, cascade='all, delete-orphan')


class Message(db.Model):
    """Message model for individual chat messages."""
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversation.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


# ============================================================
# LOGGING CONFIGURATION
# ============================================================

def setup_logging():
    """Configure application logging."""
    log_dir = os.path.dirname(Config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    logging.basicConfig(
        level=getattr(logging, Config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(Config.LOG_FILE),
            logging.StreamHandler()
        ]
    )
    app.logger.setLevel(getattr(logging, Config.LOG_LEVEL))

setup_logging()
logger = logging.getLogger(__name__)


# ============================================================
# LOGIN MANAGER
# ============================================================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================================
# RATE LIMITER
# ============================================================

class RateLimiter:
    """Simple in-memory rate limiter."""
    def __init__(self):
        self.requests = defaultdict(list)
        self.lock = Lock()
    
    def is_allowed(self, key, max_requests, window):
        if not Config.RATE_LIMIT_ENABLED:
            return True, 0
        
        with self.lock:
            now = datetime.now()
            cutoff = now - timedelta(seconds=window)
            self.requests[key] = [t for t in self.requests[key] if t > cutoff]
            
            if len(self.requests[key]) >= max_requests:
                oldest = min(self.requests[key])
                retry_after = int((oldest + timedelta(seconds=window) - now).total_seconds())
                return False, max(retry_after, 1)
            
            self.requests[key].append(now)
            return True, 0

rate_limiter = RateLimiter()


def rate_limit(max_requests=30, window=60):
    """Rate limiting decorator."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            client_ip = request.remote_addr
            allowed, retry_after = rate_limiter.is_allowed(client_ip, max_requests, window)
            
            if not allowed:
                return jsonify({
                    'error': 'Rate Limit Exceeded',
                    'status': 'error',
                    'retry_after': retry_after
                }), 429
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


# ============================================================
# MIDDLEWARE
# ============================================================

@app.before_request
def log_request_info():
    """Log incoming request details."""
    logger.info(f"Request: {request.method} {request.path} from {request.remote_addr}")


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


# ============================================================
# TRANSLATION DICTIONARY
# ============================================================

TRANSLATIONS = {
    'en': {
        'welcome': 'Welcome to Nova AI',
        'greeting': "Hi! I'm Nova 🤖 — your intelligent assistant. How can I help today?",
        'typing': 'Nova is typing...'
    },
    'es': {
        'welcome': 'Bienvenido a Nova AI',
        'greeting': "¡Hola! Soy Nova 🤖 — tu asistente inteligente. ¿Cómo puedo ayudarte hoy?",
        'typing': 'Nova está escribiendo...'
    },
    'fr': {
        'welcome': 'Bienvenue à Nova AI',
        'greeting': "Salut! Je suis Nova 🤖 — votre assistant intelligent. Comment puis-je vous aider aujourd'hui?",
        'typing': 'Nova est en train d\'écrire...'
    },
    'de': {
        'welcome': 'Willkommen bei Nova AI',
        'greeting': "Hallo! Ich bin Nova 🤖 — Ihr intelligenter Assistent. Wie kann ich Ihnen heute helfen?",
        'typing': 'Nova tippt...'
    }
}


# ============================================================
# ROUTES - AUTHENTICATION
# ============================================================

@app.route('/auth/signup', methods=['POST'])
def signup():
    """User registration endpoint."""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        # Validation
        if not username or not email or not password:
            return jsonify({'error': 'All fields are required', 'status': 'error'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters', 'status': 'error'}), 400
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists', 'status': 'error'}), 400
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists', 'status': 'error'}), 400
        
        # Create user
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        login_user(user, remember=True)
        
        logger.info(f"New user registered: {username}")
        return jsonify({
            'message': 'Registration successful',
            'status': 'success',
            'user': {'username': user.username, 'theme': user.theme, 'language': user.language}
        }), 201
        
    except Exception as e:
        logger.error(f"Signup error: {e}")
        db.session.rollback()
        return jsonify({'error': 'Registration failed', 'status': 'error'}), 500


@app.route('/auth/login', methods=['POST'])
def login():
    """User login endpoint."""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user, remember=True)
            logger.info(f"User logged in: {username}")
            return jsonify({
                'message': 'Login successful',
                'status': 'success',
                'user': {'username': user.username, 'theme': user.theme, 'language': user.language}
            }), 200
        else:
            return jsonify({'error': 'Invalid credentials', 'status': 'error'}), 401
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed', 'status': 'error'}), 500


@app.route('/auth/logout', methods=['POST'])
@login_required
def logout():
    """User logout endpoint."""
    username = current_user.username
    logout_user()
    logger.info(f"User logged out: {username}")
    return jsonify({'message': 'Logout successful', 'status': 'success'}), 200


@app.route('/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status."""
    if current_user.is_authenticated:
        return jsonify({
            'authenticated': True,
            'user': {
                'username': current_user.username,
                'theme': current_user.theme,
                'language': current_user.language
            }
        }), 200
    else:
        return jsonify({'authenticated': False}), 200


# ============================================================
# ROUTES - USER SETTINGS
# ============================================================

@app.route('/api/settings/theme', methods=['POST'])
@login_required
def update_theme():
    """Update user theme preference."""
    try:
        data = request.get_json()
        theme = data.get('theme', 'light')
        
        if theme not in ['light', 'dark']:
            return jsonify({'error': 'Invalid theme', 'status': 'error'}), 400
        
        current_user.theme = theme
        db.session.commit()
        
        return jsonify({'message': 'Theme updated', 'status': 'success', 'theme': theme}), 200
    except Exception as e:
        logger.error(f"Theme update error: {e}")
        return jsonify({'error': 'Failed to update theme', 'status': 'error'}), 500


@app.route('/api/settings/language', methods=['POST'])
@login_required
def update_language():
    """Update user language preference."""
    try:
        data = request.get_json()
        language = data.get('language', 'en')
        
        if language not in TRANSLATIONS:
            return jsonify({'error': 'Unsupported language', 'status': 'error'}), 400
        
        current_user.language = language
        db.session.commit()
        
        return jsonify({
            'message': 'Language updated',
            'status': 'success',
            'language': language,
            'translations': TRANSLATIONS[language]
        }), 200
    except Exception as e:
        logger.error(f"Language update error: {e}")
        return jsonify({'error': 'Failed to update language', 'status': 'error'}), 500


# ============================================================
# ROUTES - CHAT
# ============================================================

@app.route('/')
def home():
    """Render the main chat interface."""
    try:
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering home page: {e}", exc_info=True)
        abort(500)


@app.route('/api/ask', methods=['POST'])
@rate_limit(max_requests=30, window=60)
def ask():
    """Process chat message and return AI response."""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        conversation_id = data.get('conversation_id')
        
        if not user_message:
            return jsonify({'reply': "Please enter a valid message.", 'status': 'error'}), 400
        
        if len(user_message) > 5000:
            return jsonify({'reply': "Message too long. Please limit to 5000 characters.", 'status': 'error'}), 400
        
        # Initialize or get assistant
        if 'nova_assistant' not in session:
            session['nova_assistant'] = True
        
        # Get AI response
        assistant = NovaAssistant()
        response = assistant.ask(user_message, use_context=False)
        
        # Save to database if user is logged in
        if current_user.is_authenticated:
            try:
                # Get or create conversation
                if conversation_id:
                    conversation = Conversation.query.get(conversation_id)
                else:
                    conversation = Conversation(
                        user_id=current_user.id,
                        title=user_message[:50] + ('...' if len(user_message) > 50 else '')
                    )
                    db.session.add(conversation)
                    db.session.flush()
                
                # Save messages
                user_msg = Message(conversation_id=conversation.id, role='user', content=user_message)
                assistant_msg = Message(conversation_id=conversation.id, role='assistant', content=response)
                db.session.add(user_msg)
                db.session.add(assistant_msg)
                
                conversation.updated_at = datetime.utcnow()
                db.session.commit()
                
                conversation_id = conversation.id
            except Exception as e:
                logger.error(f"Database error: {e}")
                db.session.rollback()
        
        logger.info(f"Successfully generated response")
        
        return jsonify({
            'reply': response,
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'conversation_id': conversation_id
        }), 200
        
    except Exception as e:
        logger.error(f"Error in /api/ask: {e}", exc_info=True)
        return jsonify({
            'reply': "⚠️ Sorry, something went wrong. Please try again.",
            'status': 'error',
            'timestamp': datetime.now().isoformat()
        }), 500


# ============================================================
# ROUTES - CONVERSATION HISTORY
# ============================================================

@app.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get user's conversation history."""
    try:
        conversations = Conversation.query.filter_by(user_id=current_user.id)\
            .order_by(Conversation.updated_at.desc()).all()
        
        return jsonify({
            'conversations': [{
                'id': conv.id,
                'title': conv.title,
                'created_at': conv.created_at.isoformat(),
                'updated_at': conv.updated_at.isoformat(),
                'message_count': len(conv.messages)
            } for conv in conversations],
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}")
        return jsonify({'error': 'Failed to fetch conversations', 'status': 'error'}), 500


@app.route('/api/conversations/<int:conversation_id>', methods=['GET'])
@login_required
def get_conversation(conversation_id):
    """Get specific conversation with messages."""
    try:
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=current_user.id
        ).first_or_404()
        
        return jsonify({
            'conversation': {
                'id': conversation.id,
                'title': conversation.title,
                'messages': [{
                    'role': msg.role,
                    'content': msg.content,
                    'timestamp': msg.timestamp.isoformat()
                } for msg in conversation.messages]
            },
            'status': 'success'
        }), 200
    except Exception as e:
        logger.error(f"Error fetching conversation: {e}")
        return jsonify({'error': 'Conversation not found', 'status': 'error'}), 404


@app.route('/api/conversations/<int:conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation(conversation_id):
    """Delete a conversation."""
    try:
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=current_user.id
        ).first_or_404()
        
        db.session.delete(conversation)
        db.session.commit()
        
        return jsonify({'message': 'Conversation deleted', 'status': 'success'}), 200
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}")
        db.session.rollback()
        return jsonify({'error': 'Failed to delete conversation', 'status': 'error'}), 500


# ============================================================
# ROUTES - EXPORT
# ============================================================

@app.route('/api/export/<int:conversation_id>/txt', methods=['GET'])
@login_required
def export_txt(conversation_id):
    """Export conversation as TXT file."""
    try:
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Generate TXT content
        txt_content = f"Nova AI Conversation Export\n"
        txt_content += f"Title: {conversation.title}\n"
        txt_content += f"Date: {conversation.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        txt_content += f"{'='*60}\n\n"
        
        for msg in conversation.messages:
            role = "You" if msg.role == "user" else "Nova"
            txt_content += f"{role} ({msg.timestamp.strftime('%H:%M:%S')}):\n"
            txt_content += f"{msg.content}\n\n"
        
        # Create response
        output = io.BytesIO()
        output.write(txt_content.encode('utf-8'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/plain',
            as_attachment=True,
            download_name=f'nova_conversation_{conversation_id}.txt'
        )
    except Exception as e:
        logger.error(f"Export TXT error: {e}")
        return jsonify({'error': 'Export failed', 'status': 'error'}), 500


@app.route('/api/export/<int:conversation_id>/pdf', methods=['GET'])
@login_required
def export_pdf(conversation_id):
    """Export conversation as PDF file."""
    try:
        conversation = Conversation.query.filter_by(
            id=conversation_id,
            user_id=current_user.id
        ).first_or_404()
        
        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title = Paragraph(f"<b>Nova AI Conversation</b>", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Metadata
        meta = Paragraph(f"<b>Title:</b> {conversation.title}<br/><b>Date:</b> {conversation.created_at.strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
        story.append(meta)
        story.append(Spacer(1, 20))
        
        # Messages
        for msg in conversation.messages:
            role = "You" if msg.role == "user" else "Nova"
            timestamp = msg.timestamp.strftime('%H:%M:%S')
            
            msg_header = Paragraph(f"<b>{role}</b> ({timestamp})", styles['Heading2'])
            story.append(msg_header)
            
            msg_content = Paragraph(msg.content, styles['Normal'])
            story.append(msg_content)
            story.append(Spacer(1, 12))
        
        doc.build(story)
        buffer.seek(0)
        
        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'nova_conversation_{conversation_id}.pdf'
        )
    except Exception as e:
        logger.error(f"Export PDF error: {e}")
        return jsonify({'error': 'Export failed', 'status': 'error'}), 500


# ============================================================
# ROUTES - API ENDPOINTS
# ============================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '3.0',
        'features': ['auth', 'chat_history', 'export', 'dark_mode', 'i18n', 'voice', 'typing', 'syntax']
    }), 200


@app.route('/api/translations/<lang>', methods=['GET'])
def get_translations(lang):
    """Get translations for a specific language."""
    if lang in TRANSLATIONS:
        return jsonify({'translations': TRANSLATIONS[lang], 'status': 'success'}), 200
    else:
        return jsonify({'error': 'Language not supported', 'status': 'error'}), 404


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not Found', 'status': 'error'}), 404


@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}", exc_info=True)
    return jsonify({'error': 'Internal Server Error', 'status': 'error'}), 500


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():
    """Initialize the database."""
    with app.app_context():
        db.create_all()
        logger.info("Database initialized successfully")


# ============================================================
# APPLICATION ENTRY POINT
# ============================================================

if __name__ == '__main__':
    # Initialize database
    init_db()
    
    logger.info("Starting Nova AI Flask Application (Enhanced Version)")
    
    app.run(
        host=os.environ.get('FLASK_HOST', '0.0.0.0'),
        port=int(os.environ.get('FLASK_PORT', 5000)),
        debug=app.config['DEBUG'],
        threaded=True
    )