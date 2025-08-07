# tradeup_app/models.py
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime
import uuid

@dataclass
class User:
    user_id: str
    name: str
    email: str
    created_at: datetime = field(default_factory=datetime.now)
    trade_count: int = 0
    success_rate: float = 0.0
    followers: List[str] = field(default_factory=list)
    following: List[str] = field(default_factory=list)

@dataclass
class Item:
    name: str
    category: str
    estimated_value: float
    description: str
    images: List[str] = field(default_factory=list)
    item_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    condition: str = "good"  # poor, fair, good, excellent
    brand: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)

@dataclass
class Trade:
    user_id: str
    from_item: Item
    to_item: Item
    timestamp: datetime = field(default_factory=datetime.now)
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "completed"  # pending, completed, failed
    trade_partner: Optional[str] = None

@dataclass
class TradeOpportunity:
    listing_id: str
    item: Item
    marketplace: str
    contact_info: str
    score: float
    distance: float = 0.0

# tradeup_app/database.py
import sqlite3
import json
from typing import List, Optional
from .models import User, Item, Trade

class Database:
    def __init__(self, db_path: str = "tradeup.db"):
        self.db_path = db_path
        self.setup_database()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def setup_database(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    created_at TEXT,
                    trade_count INTEGER DEFAULT 0,
                    success_rate REAL DEFAULT 0.0,
                    followers TEXT DEFAULT '[]',
                    following TEXT DEFAULT '[]'
                )
            ''')
            
            # Items table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    item_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    name TEXT NOT NULL,
                    category TEXT NOT NULL,
                    estimated_value REAL NOT NULL,
                    description TEXT,
                    images TEXT DEFAULT '[]',
                    condition TEXT DEFAULT 'good',
                    brand TEXT,
                    created_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Trades table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    trade_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    from_item_id TEXT NOT NULL,
                    to_item_id TEXT NOT NULL,
                    timestamp TEXT,
                    status TEXT DEFAULT 'completed',
                    trade_partner TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (from_item_id) REFERENCES items (item_id),
                    FOREIGN KEY (to_item_id) REFERENCES items (item_id)
                )
            ''')
            
            # Social feed table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS social_posts (
                    post_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    trade_id TEXT,
                    content TEXT NOT NULL,
                    timestamp TEXT,
                    likes INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (trade_id) REFERENCES trades (trade_id)
                )
            ''')
            
            conn.commit()
    
    def save_user(self, user: User) -> bool:
        """Save user to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users 
                    (user_id, name, email, created_at, trade_count, success_rate, followers, following)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user.user_id, user.name, user.email, 
                    user.created_at.isoformat(), user.trade_count, user.success_rate,
                    json.dumps(user.followers), json.dumps(user.following)
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving user: {e}")
            return False
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
                row = cursor.fetchone()
                
                if row:
                    return User(
                        user_id=row[0], name=row[1], email=row[2],
                        created_at=datetime.fromisoformat(row[3]),
                        trade_count=row[4], success_rate=row[5],
                        followers=json.loads(row[6]),
                        following=json.loads(row[7])
                    )
                return None
        except Exception as e:
            print(f"Error getting user: {e}")
            return None
    
    def save_item(self, item: Item, user_id: str) -> bool:
        """Save item to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO items 
                    (item_id, user_id, name, category, estimated_value, description, 
                     images, condition, brand, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item.item_id, user_id, item.name, item.category,
                    item.estimated_value, item.description,
                    json.dumps(item.images), item.condition, item.brand,
                    item.created_at.isoformat()
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving item: {e}")
            return False
    
    def get_user_items(self, user_id: str) -> List[Item]:
        """Get all items for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM items WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
                rows = cursor.fetchall()
                
                items = []
                for row in rows:
                    items.append(Item(
                        item_id=row[0], name=row[2], category=row[3],
                        estimated_value=row[4], description=row[5],
                        images=json.loads(row[6]), condition=row[7],
                        brand=row[8], created_at=datetime.fromisoformat(row[9])
                    ))
                return items
        except Exception as e:
            print(f"Error getting user items: {e}")
            return []
    
    def save_trade(self, trade: Trade) -> bool:
        """Save trade to database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO trades 
                    (trade_id, user_id, from_item_id, to_item_id, timestamp, status, trade_partner)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    trade.trade_id, trade.user_id, trade.from_item.item_id,
                    trade.to_item.item_id, trade.timestamp.isoformat(),
                    trade.status, trade.trade_partner
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error saving trade: {e}")
            return False
    
    def get_user_trades(self, user_id: str) -> List[Trade]:
        """Get all trades for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT t.*, 
                           fi.name as from_name, fi.category as from_category, 
                           fi.estimated_value as from_value, fi.description as from_desc,
                           ti.name as to_name, ti.category as to_category,
                           ti.estimated_value as to_value, ti.description as to_desc
                    FROM trades t
                    JOIN items fi ON t.from_item_id = fi.item_id
                    JOIN items ti ON t.to_item_id = ti.item_id
                    WHERE t.user_id = ?
                    ORDER BY t.timestamp DESC
                ''', (user_id,))
                rows = cursor.fetchall()
                
                trades = []
                for row in rows:
                    from_item = Item(
                        name=row[7], category=row[8], estimated_value=row[9],
                        description=row[10], item_id=row[2]
                    )
                    to_item = Item(
                        name=row[11], category=row[12], estimated_value=row[13],
                        description=row[14], item_id=row[3]
                    )
                    trades.append(Trade(
                        trade_id=row[0], user_id=row[1],
                        from_item=from_item, to_item=to_item,
                        timestamp=datetime.fromisoformat(row[4]),
                        status=row[5], trade_partner=row[6]
                    ))
                return trades
        except Exception as e:
            print(f"Error getting user trades: {e}")
            return []

# tradeup_app/ai.py
import random
import re
from typing import List, Dict, Tuple
from .models import Item, TradeOpportunity

class TradeAI:
    # Category-based value multipliers for better trade suggestions
    CATEGORY_MULTIPLIERS = {
        'electronics': 1.2,
        'jewelry': 1.4,
        'collectibles': 1.3,
        'tools': 1.1,
        'books': 0.9,
        'clothing': 0.8,
        'home_decor': 0.9,
        'sports': 1.0,
        'music': 1.1,
        'art': 1.3
    }
    
    # Brand value multipliers
    BRAND_MULTIPLIERS = {
        'apple': 1.5, 'samsung': 1.3, 'sony': 1.2,
        'nike': 1.3, 'adidas': 1.2, 'rolex': 2.0,
        'tiffany': 1.8, 'coach': 1.4, 'gucci': 1.6
    }
    
    def estimate_item_value(self, item: Item) -> float:
        """
        Estimate item value using AI-like logic based on:
        - Category, brand, condition, and description keywords
        """
        base_value = item.estimated_value
        
        # Apply category multiplier
        category_mult = self.CATEGORY_MULTIPLIERS.get(item.category.lower(), 1.0)
        
        # Apply brand multiplier if brand exists
        brand_mult = 1.0
        if item.brand:
            brand_mult = self.BRAND_MULTIPLIERS.get(item.brand.lower(), 1.1)
        
        # Condition multiplier
        condition_multipliers = {
            'poor': 0.5, 'fair': 0.7, 'good': 1.0, 'excellent': 1.3
        }
        condition_mult = condition_multipliers.get(item.condition.lower(), 1.0)
        
        # Description keyword analysis
        description_mult = self._analyze_description(item.description)
        
        # Calculate final estimated value
        estimated_value = base_value * category_mult * brand_mult * condition_mult * description_mult
        
        return round(estimated_value, 2)
    
    def _analyze_description(self, description: str) -> float:
        """Analyze description for value-affecting keywords"""
        if not description:
            return 1.0
        
        description_lower = description.lower()
        multiplier = 1.0
        
        # Positive keywords
        positive_keywords = ['rare', 'vintage', 'limited', 'mint', 'perfect', 'new', 'original', 'authentic']
        negative_keywords = ['damaged', 'broken', 'worn', 'scratched', 'missing', 'cracked']
        
        for keyword in positive_keywords:
            if keyword in description_lower:
                multiplier *= 1.1
        
        for keyword in negative_keywords:
            if keyword in description_lower:
                multiplier *= 0.9
        
        return min(multiplier, 1.5)  # Cap at 50% increase
    
    def generate_trade_suggestions(self, item: Item) -> List[Dict]:
        """
        Generate 3 smart trade suggestions based on value progression algorithm
        """
        current_value = self.estimate_item_value(item)
        
        # Determine value increase percentage based on current value
        if current_value < 10:
            increase_range = (0.5, 1.0)  # 50-100% increase
        elif current_value < 100:
            increase_range = (0.3, 0.5)  # 30-50% increase
        elif current_value < 1000:
            increase_range = (0.2, 0.3)  # 20-30% increase
        elif current_value < 5000:
            increase_range = (0.1, 0.15)  # 10-15% increase
        else:
            increase_range = (0.05, 0.1)  # 5-10% increase
        
        suggestions = []
        categories = ['electronics', 'jewelry', 'collectibles', 'tools', 'books', 'clothing', 'home_decor', 'sports', 'music', 'art']
        
        # Generate 3 suggestions with different value increases
        for i in range(3):
            increase_factor = random.uniform(increase_range[0], increase_range[1])
            target_value = current_value * (1 + increase_factor)
            
            # Choose a different category (avoid identical categories per spec)
            available_categories = [cat for cat in categories if cat != item.category]
            target_category = random.choice(available_categories)
            
            # Generate realistic item name for the category
            item_name = self._generate_item_name(target_category, target_value)
            
            suggestions.append({
                'name': item_name,
                'category': target_category,
                'estimated_value': round(target_value, 2),
                'value_increase': round((target_value - current_value), 2),
                'percentage_increase': round(increase_factor * 100, 1),
                'trade_score': self._calculate_trade_score(item, target_category, target_value)
            })
        
        return sorted(suggestions, key=lambda x: x['trade_score'], reverse=True)
    
    def _generate_item_name(self, category: str, value: float) -> str:
        """Generate realistic item names based on category and value"""
        item_templates = {
            'electronics': {
                'low': ['Digital Camera', 'Bluetooth Speaker', 'Phone Case', 'USB Hub'],
                'mid': ['Tablet', 'Smart Watch', 'Wireless Headphones', 'Gaming Mouse'],
                'high': ['Laptop', 'DSLR Camera', 'Gaming Console', 'Smart TV']
            },
            'jewelry': {
                'low': ['Silver Ring', 'Bracelet', 'Pendant Necklace', 'Earrings'],
                'mid': ['Gold Chain', 'Diamond Earrings', 'Pearl Necklace', 'Watch'],
                'high': ['Diamond Ring', 'Gold Bracelet', 'Luxury Watch', 'Emerald Necklace']
            },
            'collectibles': {
                'low': ['Vintage Pin', 'Trading Card', 'Comic Book', 'Action Figure'],
                'mid': ['Signed Baseball', 'Vintage Toy', 'Rare Book', 'Antique Coin'],
                'high': ['Rare Painting', 'Vintage Guitar', 'Signed Jersey', 'Antique Furniture']
            }
        }
        
        # Default template for categories not defined
        default_items = ['Item', 'Gadget', 'Accessory', 'Tool']
        
        # Determine value tier
        if value < 50:
            tier = 'low'
        elif value < 500:
            tier = 'mid'
        else:
            tier = 'high'
        
        category_items = item_templates.get(category, {'low': default_items, 'mid': default_items, 'high': default_items})
        items_in_tier = category_items.get(tier, category_items.get('mid', default_items))
        
        return random.choice(items_in_tier)
    
    def _calculate_trade_score(self, from_item: Item, to_category: str, to_value: float) -> float:
        """Calculate likelihood score for successful trade (0-100)"""
        base_score = 70
        
        # Category compatibility (some categories trade better with others)
        category_compatibility = {
            'electronics': ['electronics', 'collectibles', 'tools'],
            'jewelry': ['jewelry', 'collectibles', 'art'],
            'collectibles': ['collectibles', 'art', 'jewelry']
        }
        
        if to_category in category_compatibility.get(from_item.category, []):
            base_score += 10
        
        # Value increase factor (smaller increases score higher)
        value_increase_ratio = (to_value - from_item.estimated_value) / from_item.estimated_value
        if value_increase_ratio < 0.2:
            base_score += 15
        elif value_increase_ratio < 0.5:
            base_score += 10
        elif value_increase_ratio > 1.0:
            base_score -= 20
        
        # Brand factor
        if from_item.brand:
            base_score += 10
        
        return min(max(base_score + random.randint(-10, 10), 10), 95)
    
    def score_trade_opportunity(self, from_item: Item, to_item: Item) -> float:
        """Score a specific trade opportunity"""
        return self._calculate_trade_score(from_item, to_item.category, to_item.estimated_value)
    
    def optimize_trade_path(self, start_item: Item, goal_value: float) -> List[Dict]:
        """Generate optimal trading path from start item to goal value"""
        path = []
        current_item = start_item
        current_value = self.estimate_item_value(current_item)
        
        step = 1
        while current_value < goal_value and step <= 20:  # Max 20 steps to prevent infinite loops
            suggestions = self.generate_trade_suggestions(current_item)
            best_suggestion = suggestions[0]  # Take the highest scored suggestion
            
            path.append({
                'step': step,
                'from': current_item.name,
                'to': best_suggestion['name'],
                'value_from': current_value,
                'value_to': best_suggestion['estimated_value'],
                'category': best_suggestion['category']
            })
            
            # Create new item for next iteration
            current_item = Item(
                name=best_suggestion['name'],
                category=best_suggestion['category'],
                estimated_value=best_suggestion['estimated_value'],
                description=f"Step {step} item in trade path"
            )
            current_value = best_suggestion['estimated_value']
            step += 1
        
        return path

# tradeup_app/marketplaces.py
import random
from typing import List, Dict
from .models import Item, TradeOpportunity

class MarketplaceConnector:
    """
    Simulates connections to various marketplaces (Facebook, Craigslist, etc.)
    In a real implementation, this would connect to actual marketplace APIs
    """
    
    def __init__(self):
        # Simulated marketplace data
        self.mock_listings = self._generate_mock_listings()
    
    def _generate_mock_listings(self) -> List[Dict]:
        """Generate realistic mock marketplace listings"""
        listings = []
        
        # Sample items across different categories and values
        sample_items = [
            {'name': 'iPhone 12', 'category': 'electronics', 'value': 350, 'marketplace': 'Facebook Marketplace'},
            {'name': 'Vintage Guitar', 'category': 'music', 'value': 450, 'marketplace': 'Craigslist'},
            {'name': 'Diamond Earrings', 'category': 'jewelry', 'value': 200, 'marketplace': 'OfferUp'},
            {'name': 'MacBook Pro', 'category': 'electronics', 'value': 800, 'marketplace': 'Facebook Marketplace'},
            {'name': 'Collectible Watch', 'category': 'collectibles', 'value': 120, 'marketplace': 'eBay'},
            {'name': 'Power Drill Set', 'category': 'tools', 'value': 85, 'marketplace': 'Craigslist'},
            {'name': 'Designer Handbag', 'category': 'clothing', 'value': 180, 'marketplace': 'Facebook Marketplace'},
            {'name': 'Gaming Console', 'category': 'electronics', 'value': 300, 'marketplace': 'OfferUp'},
            {'name': 'Antique Vase', 'category': 'collectibles', 'value': 95, 'marketplace': 'Craigslist'},
            {'name': 'Professional Camera', 'category': 'electronics', 'value': 650, 'marketplace': 'Facebook Marketplace'}
        ]
        
        for i, item_data in enumerate(sample_items):
            listings.append({
                'listing_id': f"listing_{i+1}",
                'item': Item(
                    name=item_data['name'],
                    category=item_data['category'],
                    estimated_value=item_data['value'],
                    description=f"Great condition {item_data['name'].lower()}, ready for trade!",
                    condition='good'
                ),
                'marketplace': item_data['marketplace'],
                'contact_info': f"trader{i+1}@example.com",
                'distance': random.uniform(1, 25),  # Distance in miles
                'posted_date': '2024-01-15'
            })
        
        return listings
    
    def fetch_marketplace_listings(self, target_item: Dict) -> List[TradeOpportunity]:
        """
        Fetch listings from all connected marketplaces
        In real implementation, this would call actual marketplace APIs
        """
        opportunities = []
        
        # Filter listings by category (avoid same category per spec)
        filtered_listings = [
            listing for listing in self.mock_listings 
            if listing['item'].category != target_item.get('category', '')
        ]
        
        for listing in filtered_listings:
            # Calculate trade score
            score = self._calculate_listing_score(target_item, listing)
            
            opportunity = TradeOpportunity(
                listing_id=listing['listing_id'],
                item=listing['item'],
                marketplace=listing['marketplace'],
                contact_info=listing['contact_info'],
                score=score,
                distance=listing['distance']
            )
            
            opportunities.append(opportunity)
        
        return opportunities
    
    def filter_listings_by_value(self, listings: List[TradeOpportunity], 
                                min_value: float, max_value: float) -> List[TradeOpportunity]:
        """Filter listings within value range"""
        return [
            listing for listing in listings 
            if min_value <= listing.item.estimated_value <= max_value
        ]
    
    def rank_listings_by_tradeability(self, listings: List[TradeOpportunity]) -> List[TradeOpportunity]:
        """Rank listings by likelihood of successful trade"""
        return sorted(listings, key=lambda x: x.score, reverse=True)
    
    def _calculate_listing_score(self, target_item: Dict, listing: Dict) -> float:
        """Calculate how likely a listing is to result in successful trade"""
        base_score = 60
        
        # Value comparison
        target_value = target_item.get('estimated_value', 0)
        listing_value = listing['item'].estimated_value
        
        if target_value > 0:
            value_ratio = listing_value / target_value
            if 1.05 <= value_ratio <= 1.5:  # 5-50% increase is ideal
                base_score += 20
            elif 1.0 <= value_ratio <= 1.05:  # Small increase
                base_score += 10
            elif value_ratio > 2.0:  # Too good to be true
                base_score -= 30
        
        # Distance factor (closer is better)
        distance_penalty = min(listing['distance'] * 2, 20)
        base_score -= distance_penalty
        
        # Marketplace reliability factor
        marketplace_scores = {
            'Facebook Marketplace': 5,
            'Craigslist': 0,
            'OfferUp': 3,
            'eBay': 8
        }
        base_score += marketplace_scores.get(listing['marketplace'], 0)
        
        # Random factor to simulate real-world variability
        base_score += random.randint(-10, 10)
        
        return max(min(base_score, 95), 10)  # Clamp between 10-95

# tradeup_app/social.py
from typing import List, Dict, Optional
from datetime import datetime
import uuid
from .models import User, Trade

class SocialNetwork:
    """Handle social features: following, feed, nominations"""
    
    def __init__(self, database):
        self.db = database
    
    def post_trade_story(self, user_id: str, trade: Trade, message: str = "") -> bool:
        """Post a trade story to social feed"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Generate engaging trade story message
                if not message:
                    value_increase = trade.to_item.estimated_value - trade.from_item.estimated_value
                    percentage_increase = (value_increase / trade.from_item.estimated_value) * 100
                    
                    message = f"🔄 Just traded my {trade.from_item.name} for a {trade.to_item.name}! " \
                             f"Increased value by ${value_increase:.2f} ({percentage_increase:.1f}%) 📈 " \
                             f"#{trade.to_item.category} #TradeUp"
                
                post_id = str(uuid.uuid4())
                cursor.execute('''
                    INSERT INTO social_posts (post_id, user_id, trade_id, content, timestamp, likes)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (post_id, user_id, trade.trade_id, message, datetime.now().isoformat(), 0))
                
                conn.commit()
                return True
        except Exception as e:
            print(f"Error posting trade story: {e}")
            return False
    
    def follow_user(self, follower_id: str, followee_id: str) -> bool:
        """Follow another user"""
        try:
            follower = self.db.get_user(follower_id)
            followee = self.db.get_user(followee_id)
            
            if not follower or not followee:
                return False
            
            # Add to follower's following list
            if followee_id not in follower.following:
                follower.following.append(followee_id)
                self.db.save_user(follower)
            
            # Add to followee's followers list
            if follower_id not in followee.followers:
                followee.followers.append(follower_id)
                self.db.save_user(followee)
            
            return True
        except Exception as e:
            print(f"Error following user: {e}")
            return False
    
    def unfollow_user(self, follower_id: str, followee_id: str) -> bool:
        """Unfollow a user"""
        try:
            follower = self.db.get_user(follower_id)
            followee = self.db.get_user(followee_id)
            
            if not follower or not followee:
                return False
            
            # Remove from follower's following list
            if followee_id in follower.following:
                follower.following.remove(followee_id)
                self.db.save_user(follower)
            
            # Remove from followee's followers list
            if follower_id in followee.followers:
                followee.followers.remove(follower_id)
                self.db.save_user(followee)
            
            return True
        except Exception as e:
            print(f"Error unfollowing user: {e}")
            return False
    
    def get_user_feed(self, user_id: str, limit: int = 20) -> List[Dict]:
        """Get social feed for user (posts from people they follow)"""
        try:
            user = self.db.get_user(user_id)
            if not user:
                return []
            
            # Include user's own posts and posts from people they follow
            feed_user_ids = [user_id] + user.following
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                placeholders = ','.join('?' * len(feed_user_ids))
                cursor.execute(f'''
                    SELECT p.post_id, p.user_id, p.trade_id, p.content, p.timestamp, p.likes,
                           u.name as user_name
                    FROM social_posts p
                    JOIN users u ON p.user_id = u.user_id
                    WHERE p.user_id IN ({placeholders})
                    ORDER BY p.timestamp DESC
                    LIMIT ?
                ''', feed_user_ids + [limit])
                
                rows = cursor.fetchall()
                
                feed_posts = []
                for row in rows:
                    feed_posts.append({
                        'post_id': row[0],
                        'user_id': row[1],
                        'user_name': row[6],
                        'trade_id': row[2],
                        'content': row[3],
                        'timestamp': row[4],
                        'likes': row[5],
                        'time_ago': self._get_time_ago(datetime.fromisoformat(row[4]))
                    })
                
                return feed_posts
        except Exception as e:
            print(f"Error getting user feed: {e}")
            return []
    
    def _get_time_ago(self, post_time: datetime) -> str:
        """Get human-readable time difference"""
        now = datetime.now()
        diff = now - post_time
        
        if diff.days > 0:
            return f"{diff.days} days ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hours ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minutes ago"
        else:
            return "Just now"
    
    def like_post(self, post_id: str) -> bool:
        """Like a social media post"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('UPDATE social_posts SET likes = likes + 1 WHERE post_id = ?', (post_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            print(f"Error liking post: {e}")
            return False
    
    def nominate_user_for_gift(self, nominator_id: str, nominee_data: Dict) -> str:
        """Nominate someone to receive a high-value gift"""
        try:
            nomination_id = str(uuid.uuid4())
            
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Create nominations table if it doesn't exist
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS nominations (
                        nomination_id TEXT PRIMARY KEY,
                        nominator_id TEXT NOT NULL,
                        nominee_name TEXT NOT NULL,
                        nominee_email TEXT,
                        nominee_story TEXT NOT NULL,
                        gift_type TEXT DEFAULT 'house',
                        status TEXT DEFAULT 'pending',
                        created_at TEXT,
                        votes INTEGER DEFAULT 0,
                        FOREIGN KEY (nominator_id) REFERENCES users (user_id)
                    )
                ''')
                
                cursor.execute('''
                    INSERT INTO nominations 
                    (nomination_id, nominator_id, nominee_name, nominee_email, nominee_story, 
                     gift_type, status, created_at, votes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    nomination_id, nominator_id, 
                    nominee_data.get('name', ''), nominee_data.get('email', ''),
                    nominee_data.get('story', ''), nominee_data.get('gift_type', 'house'),
                    'pending', datetime.now().isoformat(), 0
                ))
                
                conn.commit()
                return nomination_id
        except Exception as e:
            print(f"Error creating nomination: {e}")
            return ""
    
    def get_nominations(self, status: str = "pending") -> List[Dict]:
        """Get nominations by status"""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT n.*, u.name as nominator_name
                    FROM nominations n
                    JOIN users u ON n.nominator_id = u.user_id
                    WHERE n.status = ?
                    ORDER BY n.votes DESC, n.created_at DESC
                ''', (status,))
                
                rows = cursor.fetchall()
                nominations = []
                for row in rows:
                    nominations.append({
                        'nomination_id': row[0],
                        'nominator_id': row[1],
                        'nominator_name': row[10],
                        'nominee_name': row[2],
                        'nominee_email': row[3],
                        'nominee_story': row[4],
                        'gift_type': row[5],
                        'status': row[6],
                        'created_at': row[7],
                        'votes': row[8]
                    })
                return nominations
        except Exception as e:
            print(f"Error getting nominations: {e}")
            return []

# tradeup_app/utils.py
import json
import logging
from typing import Dict, Any
from datetime import datetime

class Config:
    """Application configuration"""
    def __init__(self):
        self.config = {
            'database_path': 'tradeup.db',
            'max_trade_suggestions': 3,
            'max_marketplace_results': 20,
            'social_feed_limit': 50,
            'log_level': 'INFO',
            'enable_ai_learning': True,
            'marketplace_apis': {
                'facebook': {'enabled': False, 'api_key': ''},
                'craigslist': {'enabled': False, 'api_key': ''},
                'offerup': {'enabled': False, 'api_key': ''}
            }
        }
    
    def get(self, key: str, default=None):
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any):
        self.config[key] = value

def load_config() -> Config:
    """Load application configuration"""
    return Config()

def validate_item_data(item_data: Dict) -> tuple[bool, str]:
    """Validate item data before processing"""
    required_fields = ['name', 'category', 'estimated_value', 'description']
    
    for field in required_fields:
        if field not in item_data:
            return False, f"Missing required field: {field}"
    
    if not isinstance(item_data['estimated_value'], (int, float)):
        return False, "estimated_value must be a number"
    
    if item_data['estimated_value'] <= 0:
        return False, "estimated_value must be positive"
    
    if len(item_data['name'].strip()) == 0:
        return False, "name cannot be empty"
    
    return True, ""

def log_event(event_type: str, data: Dict):
    """Log application events"""
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('tradeup_app')
    
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'event_type': event_type,
        'data': data
    }
    
    logger.info(json.dumps(log_entry))

def format_currency(amount: float) -> str:
    """Format currency for display"""
    return f"${amount:,.2f}"

def calculate_percentage_increase(old_value: float, new_value: float) -> float:
    """Calculate percentage increase between two values"""
    if old_value == 0:
        return 0
    return ((new_value - old_value) / old_value) * 100

# tradeup_app/core.py
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from .models import User, Item, Trade
from .database import Database
from .ai import TradeAI
from .marketplaces import MarketplaceConnector
from .social import SocialNetwork
from .utils import load_config, validate_item_data, log_event

class TradeUpApp:
    """Main application class - coordinates all functionality"""
    
    def __init__(self, db_path: str = "tradeup.db"):
        self.config = load_config()
        self.db = Database(db_path)
        self.ai = TradeAI()
        self.marketplace = MarketplaceConnector()
        self.social = SocialNetwork(self.db)
        
        log_event('app_initialized', {'db_path': db_path})
    
    def register_user(self, user_data: Dict) -> tuple[bool, str]:
        """Register a new user"""
        try:
            # Validate required fields
            required_fields = ['name', 'email']
            for field in required_fields:
                if field not in user_data or not user_data[field].strip():
                    return False, f"Missing required field: {field}"
            
            # Check if email already exists
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT user_id FROM users WHERE email = ?', (user_data['email'],))
                if cursor.fetchone():
                    return False, "Email already registered"
            
            # Create new user
            user = User(
                user_id=str(uuid.uuid4()),
                name=user_data['name'].strip(),
                email=user_data['email'].strip().lower()
            )
            
            success = self.db.save_user(user)
            if success:
                log_event('user_registered', {'user_id': user.user_id, 'name': user.name})
                return True, user.user_id
            else:
                return False, "Failed to save user"
                
        except Exception as e:
            log_event('user_registration_error', {'error': str(e)})
            return False, f"Registration failed: {str(e)}"
    
    def add_item(self, user_id: str, item_data: Dict) -> tuple[bool, str]:
        """Add an item for a user"""
        try:
            # Validate item data
            is_valid, error_msg = validate_item_data(item_data)
            if not is_valid:
                return False, error_msg
            
            # Create item
            item = Item(
                name=item_data['name'].strip(),
                category=item_data['category'].lower(),
                estimated_value=float(item_data['estimated_value']),
                description=item_data.get('description', '').strip(),
                images=item_data.get('images', []),
                condition=item_data.get('condition', 'good'),
                brand=item_data.get('brand', '').strip() or None
            )
            
            # Use AI to refine value estimate
            item.estimated_value = self.ai.estimate_item_value(item)
            
            success = self.db.save_item(item, user_id)
            if success:
                log_event('item_added', {
                    'user_id': user_id, 
                    'item_id': item.item_id,
                    'estimated_value': item.estimated_value
                })
                return True, item.item_id
            else:
                return False, "Failed to save item"
                
        except Exception as e:
            log_event('add_item_error', {'error': str(e)})
            return False, f"Failed to add item: {str(e)}"
    
    def suggest_next_trades(self, item: Item) -> List[Dict]:
        """
        Generate smart trade suggestions for an item
        Returns list of suggested items with trade scores
        """
        try:
            # Get AI-powered suggestions
            suggestions = self.ai.generate_trade_suggestions(item)
            
            log_event('trade_suggestions_generated', {
                'item_id': item.item_id,
                'current_value': item.estimated_value,
                'suggestions_count': len(suggestions)
            })
            
            return suggestions
            
        except Exception as e:
            log_event('suggest_trades_error', {'error': str(e)})
            return []
    
    def find_trade_opportunities(self, target_item: Dict) -> List[Dict]:
        """
        Find actual marketplace opportunities for trading
        """
        try:
            # Fetch opportunities from marketplaces
            opportunities = self.marketplace.fetch_marketplace_listings(target_item)
            
            # Filter by value range (5-50% increase)
            min_value = target_item.get('estimated_value', 0) * 1.05
            max_value = target_item.get('estimated_value', 0) * 1.5
            
            filtered_opportunities = self.marketplace.filter_listings_by_value(
                opportunities, min_value, max_value
            )
            
            # Rank by tradeability
            ranked_opportunities = self.marketplace.rank_listings_by_tradeability(
                filtered_opportunities
            )
            
            # Convert to dict format for response
            result = []
            for opp in ranked_opportunities[:10]:  # Top 10 opportunities
                result.append({
                    'listing_id': opp.listing_id,
                    'item_name': opp.item.name,
                    'category': opp.item.category,
                    'estimated_value': opp.item.estimated_value,
                    'description': opp.item.description,
                    'marketplace': opp.marketplace,
                    'contact_info': opp.contact_info,
                    'score': opp.score,
                    'distance': opp.distance
                })
            
            log_event('trade_opportunities_found', {
                'target_item': target_item.get('name', 'Unknown'),
                'opportunities_count': len(result)
            })
            
            return result
            
        except Exception as e:
            log_event('find_opportunities_error', {'error': str(e)})
            return []
    
    def generate_trade_message(self, from_item: Item, to_item_data: Dict) -> str:
        """
        Generate persuasive trade message based on best practices
        """
        try:
            # Extract key details
            from_name = from_item.name
            from_brand = from_item.brand or "quality"
            from_value = from_item.estimated_value
            
            to_name = to_item_data.get('item_name', 'your item')
            to_value = to_item_data.get('estimated_value', 0)
            
            # Calculate trade benefit
            value_difference = to_value - from_value
            
            # Generate personalized message
            message_templates = [
                f"Hi! I have a {from_brand} {from_name} (${from_value:.0f} value) that I'd love to trade for your {to_name}. "
                f"This is part of my 'Trade Up' challenge where I'm trading items without using money. "
                f"My {from_name} is in great condition and might be perfect for someone who needs {from_item.category} items. "
                f"Would you be interested in this trade?",
                
                f"Hello! I'm doing a unique trading project and wondering if you'd be interested in trading your {to_name} "
                f"for my {from_brand} {from_name}? It's valued at ${from_value:.0f} and in excellent condition. "
                f"I'm trying to trade up from small items to bigger goals - it's like the famous paperclip to house story! "
                f"Let me know if this interests you.",
                
                f"Hi there! I noticed your {to_name} listing and have an interesting proposal. "
                f"I have a {from_name} ({from_brand} brand, ${from_value:.0f} value) that I'd like to trade for it. "
                f"This is part of a fun 'Trade Up' project where I use only trading, no money. "
                f"Would you be open to this kind of trade?"
            ]
            
            # Select template based on value difference
            if value_difference > 50:
                template_index = 0  # More detailed explanation for big jumps
            elif value_difference > 10:
                template_index = 1  # Medium explanation
            else:
                template_index = 2  # Simple approach
            
            message = message_templates[template_index]
            
            log_event('trade_message_generated', {
                'from_item': from_name,
                'to_item': to_name,
                'message_length': len(message)
            })
            
            return message
            
        except Exception as e:
            log_event('generate_message_error', {'error': str(e)})
            return "Hi! I'd like to trade my item for yours. Let me know if you're interested!"
    
    def submit_trade(self, user_id: str, from_item_id: str, to_item_data: Dict, 
                    trade_partner: str = "") -> tuple[bool, str]:
        """
        Submit and record a completed trade
        """
        try:
            # Get the from_item
            user_items = self.db.get_user_items(user_id)
            from_item = next((item for item in user_items if item.item_id == from_item_id), None)
            
            if not from_item:
                return False, "Source item not found"
            
            # Create the to_item
            to_item = Item(
                name=to_item_data.get('item_name', ''),
                category=to_item_data.get('category', ''),
                estimated_value=to_item_data.get('estimated_value', 0),
                description=to_item_data.get('description', ''),
                condition=to_item_data.get('condition', 'good')
            )
            
            # Save the new item
            self.db.save_item(to_item, user_id)
            
            # Create trade record
            trade = Trade(
                user_id=user_id,
                from_item=from_item,
                to_item=to_item,
                trade_partner=trade_partner
            )
            
            # Save trade
            trade_saved = self.db.save_trade(trade)
            if not trade_saved:
                return False, "Failed to save trade record"
            
            # Update user trade count
            user = self.db.get_user(user_id)
            if user:
                user.trade_count += 1
                # Recalculate success rate (simplified - assuming all trades successful)
                user.success_rate = min(user.success_rate + 0.1, 1.0)
                self.db.save_user(user)
            
            # Post to social feed
            self.social.post_trade_story(user_id, trade)
            
            log_event('trade_completed', {
                'user_id': user_id,
                'trade_id': trade.trade_id,
                'value_increase': to_item.estimated_value - from_item.estimated_value
            })
            
            return True, trade.trade_id
            
        except Exception as e:
            log_event('submit_trade_error', {'error': str(e)})
            return False, f"Failed to submit trade: {str(e)}"
    
    def get_user_progress(self, user_id: str) -> Dict:
        """
        Get comprehensive user progress and statistics
        """
        try:
            user = self.db.get_user(user_id)
            if not user:
                return {}
            
            trades = self.db.get_user_trades(user_id)
            items = self.db.get_user_items(user_id)
            
            # Calculate progress statistics
            total_value_gained = sum(
                trade.to_item.estimated_value - trade.from_item.estimated_value 
                for trade in trades
            )
            
            current_items = sorted(items, key=lambda x: x.created_at, reverse=True)
            current_total_value = sum(item.estimated_value for item in current_items)
            
            # Calculate trade path
            if trades:
                starting_value = trades[-1].from_item.estimated_value if trades else 0
                current_highest_value = max(item.estimated_value for item in current_items) if current_items else 0
                total_multiplier = current_highest_value / starting_value if starting_value > 0 else 0
            else:
                starting_value = 0
                current_highest_value = 0
                total_multiplier = 0
            
            progress_data = {
                'user_id': user_id,
                'user_name': user.name,
                'member_since': user.created_at.strftime('%Y-%m-%d'),
                'total_trades': user.trade_count,
                'success_rate': user.success_rate * 100,
                'followers_count': len(user.followers),
                'following_count': len(user.following),
                'current_items_count': len(current_items),
                'current_total_value': current_total_value,
                'total_value_gained': total_value_gained,
                'starting_value': starting_value,
                'current_highest_value': current_highest_value,
                'value_multiplier': round(total_multiplier, 2),
                'recent_trades': [
                    {
                        'trade_id': trade.trade_id,
                        'from_item': trade.from_item.name,
                        'to_item': trade.to_item.name,
                        'value_increase': trade.to_item.estimated_value - trade.from_item.estimated_value,
                        'date': trade.timestamp.strftime('%Y-%m-%d')
                    }
                    for trade in trades[:5]  # Last 5 trades
                ],
                'current_items': [
                    {
                        'item_id': item.item_id,
                        'name': item.name,
                        'category': item.category,
                        'estimated_value': item.estimated_value,
                        'condition': item.condition
                    }
                    for item in current_items[:10]  # Top 10 current items
                ]
            }
            
            log_event('user_progress_retrieved', {
                'user_id': user_id,
                'total_trades': user.trade_count,
                'current_value': current_total_value
            })
            
            return progress_data
            
        except Exception as e:
            log_event('get_progress_error', {'error': str(e)})
            return {}
    
    def get_trade_path_optimization(self, user_id: str, goal_value: float) -> List[Dict]:
        """
        Generate optimal trade path to reach a goal value
        """
        try:
            # Get user's current highest value item
            current_items = self.db.get_user_items(user_id)
            if not current_items:
                return []
            
            highest_value_item = max(current_items, key=lambda x: x.estimated_value)
            
            # Generate optimal path
            trade_path = self.ai.optimize_trade_path(highest_value_item, goal_value)
            
            log_event('trade_path_generated', {
                'user_id': user_id,
                'starting_value': highest_value_item.estimated_value,
                'goal_value': goal_value,
                'path_length': len(trade_path)
            })
            
            return trade_path
            
        except Exception as e:
            log_event('trade_path_error', {'error': str(e)})
            return []
    
    def get_social_feed(self, user_id: str) -> List[Dict]:
        """Get social media feed for user"""
        return self.social.get_user_feed(user_id)
    
    def follow_user(self, follower_id: str, followee_id: str) -> bool:
        """Follow another user"""
        return self.social.follow_user(follower_id, followee_id)
    
    def nominate_for_gift(self, nominator_id: str, nominee_data: Dict) -> str:
        """Nominate someone for a gift"""
        return self.social.nominate_user_for_gift(nominator_id, nominee_data)

# Example usage and testing
if __name__ == "__main__":
    # Initialize the app
    app = TradeUpApp()
    
    # Register a test user
    success, user_id = app.register_user({
        'name': 'Alice Johnson',
        'email': 'alice@example.com'
    })
    
    if success:
        print(f"✅ User registered successfully: {user_id}")
        
        # Add starting item (bobby pin)
        success, item_id = app.add_item(user_id, {
            'name': 'Bobby Pin',
            'category': 'accessories',
            'estimated_value': 0.20,
            'description': 'Small gold bobby pin in good condition',
            'condition': 'good'
        })
        
        if success:
            print(f"✅ Item added successfully: {item_id}")
            
            # Get the item
            user_items = app.db.get_user_items(user_id)
            bobby_pin = user_items[0]
            
            # Get trade suggestions
            suggestions = app.suggest_next_trades(bobby_pin)
            print(f"\n📊 Trade suggestions for {bobby_pin.name} (${bobby_pin.estimated_value}):")
            
            for i, suggestion in enumerate(suggestions, 1):
                print(f"{i}. {suggestion['name']} - ${suggestion['estimated_value']} "
                      f"(+${suggestion['value_increase']}, {suggestion['percentage_increase']}% increase)")
            
            # Find marketplace opportunities
            if suggestions:
                opportunities = app.find_trade_opportunities(suggestions[0])
                print(f"\n🛒 Marketplace opportunities for {suggestions[0]['name']}:")
                
                for opp in opportunities[:3]:
                    print(f"- {opp['item_name']} on {opp['marketplace']}: "
                          f"${opp['estimated_value']} (Score: {opp['score']:.1f}/100)")
            
            # Generate trade message
            if suggestions and opportunities:
                message = app.generate_trade_message(bobby_pin, opportunities[0])
                print(f"\n💬 Generated trade message:")
                print(f'"{message}"')
            
            # Simulate a trade
            if suggestions:
                success, trade_id = app.submit_trade(user_id, bobby_pin.item_id, {
                    'item_name': suggestions[0]['name'],
                    'category': suggestions[0]['category'],
                    'estimated_value': suggestions[0]['estimated_value'],
                    'description': f"Traded up from bobby pin",
                    'condition': 'good'
                }, 'trader123@example.com')
                
                if success:
                    print(f"✅ Trade completed successfully: {trade_id}")
                    
                    # Get user progress
                    progress = app.get_user_progress(user_id)
                    print(f"\n📈 User Progress:")
                    print(f"- Total trades: {progress['total_trades']}")
                    print(f"- Value gained: ${progress['total_value_gained']:.2f}")
                    print(f"- Current highest value: ${progress['current_highest_value']:.2f}")
                    print(f"- Value multiplier: {progress['value_multiplier']}x")
                    
                    # Generate trade path to house
                    house_goal = 250000  # $250k house
                    trade_path = app.get_trade_path_optimization(user_id, house_goal)
                    
                    if trade_path:
                        print(f"\n🏠 Trade path to ${house_goal:,} house ({len(trade_path)} steps):")
                        for step in trade_path[:5]:  # Show first 5 steps
                            print(f"Step {step['step']}: {step['from']} → {step['to']} "
                                  f"(${step['value_from']:.2f} → ${step['value_to']:.2f})")
                        if len(trade_path) > 5:
                            print(f"... and {len(trade_path) - 5} more steps")
    
    print("\n🎉 Trade Up App POC Demo Complete!")
