from flask import Flask, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
import os

# Initialize SQLAlchemy
db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    
    # Configure the application
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///../receipts.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
    
    # Initialize extensions
    db.init_app(app)
    
    # Root route to redirect to API
    @app.route('/')
    def index():
        return redirect('/api')
    
    # Register blueprints
    from app.routes.receipt_routes import receipt_bp
    app.register_blueprint(receipt_bp)
    
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    
    return app