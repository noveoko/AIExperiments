# app/__init__.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS
from flask_socketio import SocketIO
from celery import Celery

db = SQLAlchemy()
socketio = SocketIO()
celery = Celery()

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///marketplace_monitor.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
    app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'
    
    db.init_app(app)
    socketio.init_app(app, cors_allowed_origins="*")
    
    celery.conf.update(app.config)
    
    with app.app_context():
        from .routes import main_bp
        app.register_blueprint(main_bp)
        db.create_all()
        
    return app

# app/models.py
from . import db
from datetime import datetime

class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    condition = db.Column(db.String(50))
    location = db.Column(db.String(100))
    distance = db.Column(db.Float)
    description = db.Column(db.Text)
    listing_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    estimated_value = db.Column(db.Float)
    potential_profit = db.Column(db.Float)
    
class PriceHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    condition = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    sold = db.Column(db.Boolean, default=False)

# app/routes.py
from flask import Blueprint, jsonify, request
from .models import db, Listing, PriceHistory
from .tasks import check_new_listings
from . import socketio

main_bp = Blueprint('main', __name__)

@main_bp.route('/api/listings', methods=['GET'])
def get_listings():
    category = request.args.get('category')
    min_profit = request.args.get('min_profit', type=float)
    
    query = Listing.query
    
    if category:
        query = query.filter_by(category=category)
    if min_profit:
        query = query.filter(Listing.potential_profit >= min_profit)
        
    listings = query.order_by(Listing.potential_profit.desc()).all()
    
    return jsonify([{
        'id': l.id,
        'title': l.title,
        'category': l.category,
        'price': l.price,
        'condition': l.condition,
        'location': l.location,
        'distance': l.distance,
        'potential_profit': l.potential_profit,
        'listing_url': l.listing_url
    } for l in listings])

# app/tasks.py
from . import celery, socketio
from .models import db, Listing, PriceHistory
from datetime import datetime, timedelta
import numpy as np

@celery.task
def check_new_listings():
    """
    Periodic task to check for new listings and analyze their potential
    """
    # Mock implementation - replace with actual marketplace API calls
    new_listings = get_marketplace_listings()
    
    for listing in new_listings:
        potential_profit = analyze_profit_potential(listing)
        
        if potential_profit > 100:  # Minimum profit threshold
            new_listing = Listing(
                title=listing['title'],
                category=listing['category'],
                price=listing['price'],
                condition=listing['condition'],
                location=listing['location'],
                distance=listing['distance'],
                potential_profit=potential_profit
            )
            db.session.add(new_listing)
            
            # Notify connected clients via WebSocket
            socketio.emit('new_listing', {
                'title': listing['title'],
                'price': listing['price'],
                'potential_profit': potential_profit
            })
    
    db.session.commit()

def analyze_profit_potential(listing):
    """
    Analyze listing's profit potential based on historical data
    """
    # Get historical prices for similar items
    history = PriceHistory.query.filter_by(
        category=listing['category'],
        condition=listing['condition']
    ).filter(
        PriceHistory.date >= datetime.now() - timedelta(days=90)
    ).with_entities(PriceHistory.price).all()
    
    if not history:
        return 0
    
    prices = [h.price for h in history]
    avg_price = np.mean(prices)
    
    # Calculate potential profit
    potential_profit = avg_price - listing['price']
    
    return max(0, potential_profit)

def get_marketplace_listings():
    """
    Mock function to get marketplace listings
    Replace with actual API integration
    """
    # Mock data for testing
    return []