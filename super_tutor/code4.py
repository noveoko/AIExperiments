import json
import sqlite3
import time
import random
import os
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import requests

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
OLLAMA_API = "http://localhost:11434/api/generate"
MODEL = "llama3"
TOPICS_FILE = "topics.json"
DB_FILE = "tutor.db"
LOG_FILE = "tutor.log"
STATS_FILE = "usage_stats.json"

# ----------------------------------------------------------------------
# Custom Exceptions
# ----------------------------------------------------------------------
class TutorException(Exception):
    """Base exception for all tutor-related errors."""
    pass

class DatabaseError(TutorException):
    """Raised when database operations fail."""
    pass

class LLMError(TutorException):
    """Raised when LLM API calls fail."""
    pass

class ContentError(TutorException):
    """Raised when content loading or validation fails."""
    pass

class SessionError(TutorException):
    """Raised when session management fails."""
    pass

# ----------------------------------------------------------------------
# Logging Setup
# ----------------------------------------------------------------------
def setup_logging():
    """
    Configure comprehensive logging system with multiple handlers.
    
    Creates three log streams:
    1. File handler - All logs (DEBUG and above)
    2. Console handler - Important logs (INFO and above)
    3. Error file handler - Only errors (ERROR and above)
    """
    # Create logs directory if it doesn't exist
    os.makedirs('logs', exist_ok=True)
    
    # Create logger
    logger = logging.getLogger('MathTutorPro')
    logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate handlers if function called multiple times
    if logger.handlers:
        logger.handlers.clear()
    
    # File handler - detailed logs
    file_handler = logging.FileHandler(
        f'logs/{LOG_FILE}',
        mode='a',
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)-8s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # Console handler - user-facing logs
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(levelname)s: %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    
    # Error file handler - critical errors only
    error_handler = logging.FileHandler(
        f'logs/errors_{datetime.now().strftime("%Y%m%d")}.log',
        mode='a',
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    logger.addHandler(error_handler)
    
    return logger

logger = setup_logging()

# ----------------------------------------------------------------------
# Usage Statistics Tracking
# ----------------------------------------------------------------------
@dataclass
class SessionStats:
    """Track statistics for a single tutoring session."""
    session_id: str
    student_id: int
    student_name: str
    start_time: str
    end_time: Optional[str] = None
    duration_minutes: float = 0.0
    topics_attempted: List[str] = None
    total_problems: int = 0
    correct_answers: int = 0
    incorrect_answers: int = 0
    hints_requested: int = 0
    llm_calls: int = 0
    llm_errors: int = 0
    llm_total_response_time: float = 0.0
    breaks_taken: int = 0
    states_visited: List[str] = None
    average_response_time: float = 0.0
    
    def __post_init__(self):
        """Initialize mutable default values."""
        if self.topics_attempted is None:
            self.topics_attempted = []
        if self.states_visited is None:
            self.states_visited = []
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

class UsageStatsTracker:
    """
    Track and persist usage statistics for improving user experience.
    
    This class manages both real-time session statistics and 
    cumulative usage data stored in JSON format.
    """
    
    def __init__(self, stats_file: str = STATS_FILE):
        self.stats_file = stats_file
        self.cumulative_stats = self._load_cumulative_stats()
        logger.info(f"UsageStatsTracker initialized with file: {stats_file}")
    
    def _load_cumulative_stats(self) -> Dict:
        """Load existing cumulative statistics from file."""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    stats = json.load(f)
                    logger.debug(f"Loaded cumulative stats: {len(stats.get('sessions', []))} sessions")
                    return stats
            else:
                logger.info("No existing stats file, creating new one")
                return {
                    'sessions': [],
                    'totals': {
                        'total_sessions': 0,
                        'total_students': 0,
                        'total_problems_attempted': 0,
                        'total_llm_calls': 0,
                        'total_errors': 0,
                        'average_session_duration': 0.0,
                        'average_accuracy': 0.0
                    },
                    'last_updated': datetime.now().isoformat()
                }
        except Exception as e:
            logger.error(f"Error loading cumulative stats: {e}", exc_info=True)
            raise ContentError(f"Failed to load usage statistics: {e}")
    
    def save_session_stats(self, session_stats: SessionStats):
        """
        Save session statistics and update cumulative totals.
        
        Steps:
        1. Add session to sessions list
        2. Recalculate cumulative totals
        3. Write to file with atomic operation
        4. Log summary
        """
        try:
            logger.info(f"Saving session stats for session {session_stats.session_id}")
            
            # Add session to list
            self.cumulative_stats['sessions'].append(session_stats.to_dict())
            
            # Update totals
            self._recalculate_totals()
            
            # Write to file atomically (write to temp, then rename)
            temp_file = f"{self.stats_file}.tmp"
            with open(temp_file, 'w') as f:
                json.dump(self.cumulative_stats, f, indent=2)
            os.replace(temp_file, self.stats_file)
            
            logger.info(f"Session stats saved successfully. Duration: {session_stats.duration_minutes:.2f} min, "
                       f"Problems: {session_stats.total_problems}, "
                       f"Accuracy: {self._calculate_accuracy(session_stats):.1f}%")
            
        except Exception as e:
            logger.error(f"Error saving session stats: {e}", exc_info=True)
            raise SessionError(f"Failed to save session statistics: {e}")
    
    def _recalculate_totals(self):
        """Recalculate cumulative statistics from all sessions."""
        sessions = self.cumulative_stats['sessions']
        
        if not sessions:
            return
        
        totals = {
            'total_sessions': len(sessions),
            'total_students': len(set(s['student_id'] for s in sessions)),
            'total_problems_attempted': sum(s['total_problems'] for s in sessions),
            'total_llm_calls': sum(s['llm_calls'] for s in sessions),
            'total_errors': sum(s['llm_errors'] for s in sessions),
            'average_session_duration': sum(s['duration_minutes'] for s in sessions) / len(sessions),
            'average_accuracy': sum(
                (s['correct_answers'] / s['total_problems'] * 100) 
                if s['total_problems'] > 0 else 0 
                for s in sessions
            ) / len(sessions)
        }
        
        self.cumulative_stats['totals'] = totals
        self.cumulative_stats['last_updated'] = datetime.now().isoformat()
        
        logger.debug(f"Recalculated totals: {totals}")
    
    def _calculate_accuracy(self, session_stats: SessionStats) -> float:
        """Calculate accuracy percentage for a session."""
        if session_stats.total_problems == 0:
            return 0.0
        return (session_stats.correct_answers / session_stats.total_problems) * 100
    
    def get_stats_summary(self) -> Dict:
        """Get human-readable summary of usage statistics."""
        totals = self.cumulative_stats['totals']
        return {
            'Total Sessions': totals['total_sessions'],
            'Unique Students': totals['total_students'],
            'Problems Attempted': totals['total_problems_attempted'],
            'Average Session Duration (min)': f"{totals['average_session_duration']:.2f}",
            'Average Accuracy': f"{totals['average_accuracy']:.1f}%",
            'LLM Calls': totals['total_llm_calls'],
            'LLM Errors': totals['total_errors']
        }
    
    def export_stats(self, format: str = 'json') -> str:
        """Export statistics in specified format (json or csv)."""
        if format == 'json':
            return json.dumps(self.cumulative_stats, indent=2)
        elif format == 'csv':
            # Simple CSV export of sessions
            import csv
            import io
            output = io.StringIO()
            if self.cumulative_stats['sessions']:
                writer = csv.DictWriter(output, fieldnames=self.cumulative_stats['sessions'][0].keys())
                writer.writeheader()
                writer.writerows(self.cumulative_stats['sessions'])
            return output.getvalue()
        else:
            raise ValueError(f"Unsupported format: {format}")

# ----------------------------------------------------------------------
# Content loading with error handling
# ----------------------------------------------------------------------
def load_topics() -> Dict:
    """
    Load topic data from JSON file with validation.
    
    Steps:
    1. Check if file exists
    2. Load and parse JSON
    3. Validate structure
    4. Create default if missing
    5. Log result
    
    Returns:
        Dict containing topic data
        
    Raises:
        ContentError: If file is corrupted or invalid
    """
    logger.debug("Loading topics from file")
    
    default_topics = {
        "solving_linear_equations": {
            "name": "Solving Linear Equations",
            "prerequisites": ["basic_arithmetic", "variables"],
            "explanations": {
                "visual": "Imagine a balance scale. To keep it balanced, whatever you do to one side you must do to the other.",
                "procedural": "Apply inverse operations to isolate the variable. Add/subtract first, then multiply/divide.",
                "analogy": "If you have a mystery number x and you know that 2x + 3 = 7, think of undoing the operations in reverse order."
            },
            "problems": [
                {"text": "Solve for x: x + 5 = 12", "answer": 7, "difficulty": 1},
                {"text": "Solve for x: 3x = 15", "answer": 5, "difficulty": 1},
                {"text": "Solve for x: 2x + 4 = 10", "answer": 3, "difficulty": 2},
                {"text": "Solve for x: 5x - 7 = 18", "answer": 5, "difficulty": 2}
            ],
            "misconceptions": [
                "Student subtracts incorrectly",
                "Student forgets to apply operation to both sides",
                "Student multiplies instead of divides"
            ]
        }
    }
    
    try:
        if os.path.exists(TOPICS_FILE):
            with open(TOPICS_FILE, 'r') as f:
                topics = json.load(f)
                
            # Validate structure
            if not isinstance(topics, dict):
                raise ContentError("Topics file must contain a dictionary")
            
            for topic_id, topic_data in topics.items():
                required_keys = ['name', 'problems']
                for key in required_keys:
                    if key not in topic_data:
                        raise ContentError(f"Topic '{topic_id}' missing required key: {key}")
            
            logger.info(f"Successfully loaded {len(topics)} topics from {TOPICS_FILE}")
            return topics
        else:
            logger.warning(f"Topics file not found, creating default: {TOPICS_FILE}")
            with open(TOPICS_FILE, 'w') as f:
                json.dump(default_topics, f, indent=2)
            logger.info("Created default topics file")
            return default_topics
            
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error in topics file: {e}", exc_info=True)
        raise ContentError(f"Topics file is corrupted: {e}")
    except Exception as e:
        logger.error(f"Unexpected error loading topics: {e}", exc_info=True)
        raise ContentError(f"Failed to load topics: {e}")

# ----------------------------------------------------------------------
# Database setup with error handling
# ----------------------------------------------------------------------
def init_db():
    """
    Initialize database with proper error handling and logging.
    
    Creates all required tables with proper schema.
    Uses transactions to ensure atomicity.
    """
    logger.info("Initializing database")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Enable foreign keys
        c.execute('PRAGMA foreign_keys = ON')
        
        logger.debug("Creating students table")
        c.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP
            )
        ''')
        
        logger.debug("Creating topics table")
        c.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                topic_id TEXT PRIMARY KEY,
                topic_name TEXT,
                content TEXT   -- JSON dump of explanations, problems, etc.
            )
        ''')
        
        logger.debug("Creating student_topics table")
        c.execute('''
            CREATE TABLE IF NOT EXISTS student_topics (
                student_id INTEGER,
                topic_id TEXT,
                mastery_level INTEGER DEFAULT 0,
                status TEXT DEFAULT 'learning',
                ease_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 0,
                next_review_date DATE,
                last_reviewed_date DATE,
                consecutive_correct INTEGER DEFAULT 0,
                total_attempts INTEGER DEFAULT 0,
                misconceptions TEXT,
                PRIMARY KEY (student_id, topic_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
            )
        ''')
        
        logger.debug("Creating session_history table")
        c.execute('''
            CREATE TABLE IF NOT EXISTS session_history (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                topic_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                interaction_log TEXT,
                duration_minutes INTEGER,
                performance_score REAL,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
            )
        ''')
        
        conn.commit()
        logger.info("Database initialized successfully")
        
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {e}", exc_info=True)
        raise DatabaseError(f"Failed to initialize database: {e}")
    finally:
        if conn:
            conn.close()

def populate_topics():
    """Insert topics from JSON into the topics table with error handling."""
    logger.info("Populating topics table")
    
    try:
        topics = load_topics()
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        for topic_id, data in topics.items():
            try:
                c.execute('''
                    INSERT OR IGNORE INTO topics (topic_id, topic_name, content)
                    VALUES (?, ?, ?)
                ''', (topic_id, data['name'], json.dumps(data)))
                logger.debug(f"Inserted/updated topic: {topic_id}")
            except sqlite3.Error as e:
                logger.warning(f"Error inserting topic {topic_id}: {e}")
        
        conn.commit()
        logger.info(f"Successfully populated {len(topics)} topics")
        
    except Exception as e:
        logger.error(f"Error populating topics: {e}", exc_info=True)
        raise DatabaseError(f"Failed to populate topics: {e}")
    finally:
        if conn:
            conn.close()

def get_student_id(name: str) -> int:
    """
    Get or create a student by name with error handling.
    
    Args:
        name: Student's name
        
    Returns:
        int: Student ID
        
    Raises:
        DatabaseError: If database operation fails
    """
    logger.debug(f"Getting student ID for: {name}")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('SELECT student_id FROM students WHERE name = ?', (name,))
        row = c.fetchone()
        
        if row:
            sid = row[0]
            logger.info(f"Found existing student: {name} (ID: {sid})")
        else:
            c.execute('INSERT INTO students (name, last_active) VALUES (?, ?)',
                      (name, datetime.now()))
            sid = c.lastrowid
            logger.info(f"Created new student: {name} (ID: {sid})")
        
        conn.commit()
        return sid
        
    except sqlite3.Error as e:
        logger.error(f"Database error getting student ID: {e}", exc_info=True)
        raise DatabaseError(f"Failed to get/create student: {e}")
    finally:
        if conn:
            conn.close()

def update_last_active(sid: int):
    """Update student's last active timestamp with error handling."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('UPDATE students SET last_active = ? WHERE student_id = ?',
                  (datetime.now(), sid))
        conn.commit()
        logger.debug(f"Updated last_active for student ID: {sid}")
    except sqlite3.Error as e:
        logger.warning(f"Error updating last_active: {e}")
    finally:
        if conn:
            conn.close()
