#!/usr/bin/env python3
"""
Mathematics Tutor Pro – LLM‑powered adaptive tutor using Ollama.

Enhanced version with:
  - Robust logging system
  - Custom exception handling
  - Usage statistics tracking
  - Performance monitoring
  - Error recovery mechanisms

This is a proof‑of‑concept implementing:
  - Free‑text conversational interaction
  - Content stored in JSON (algebra topics)
  - SM‑2 spaced repetition algorithm
  - SQLite persistence for student models
  - Finite state machine with LLM‑enhanced branching
  - Fatigue detection and break suggestions

Requirements:
  - Python 3.8+
  - Ollama installed and running (https://ollama.com)
  - A model pulled, e.g. `ollama pull llama3`
  - Python packages: requests (or `ollama` library)

Run:
  python tutor_pro_enhanced.py
"""

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
import sys
import requests  # for calling Ollama's API

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
OLLAMA_API = "http://localhost:11434/api/generate"
MODEL = "llama3"          # change to any model you have pulled
TOPICS_FILE = "topics.json"
DB_FILE = "tutor.db"
LOG_FILE = "tutor_pro.log"
STATS_FILE = "usage_stats.log"

# ----------------------------------------------------------------------
# Custom Exceptions
# ----------------------------------------------------------------------
class TutorException(Exception):
    """Base exception for all tutor-related errors."""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.now()

class LLMConnectionError(TutorException):
    """Raised when unable to connect to Ollama API."""
    pass

class LLMResponseError(TutorException):
    """Raised when LLM returns invalid or unexpected response."""
    pass

class DatabaseError(TutorException):
    """Raised for database-related errors."""
    pass

class ContentLoadError(TutorException):
    """Raised when unable to load or parse content files."""
    pass

class InvalidStateError(TutorException):
    """Raised when FSM enters an invalid state."""
    pass

class StudentDataError(TutorException):
    """Raised for issues with student data."""
    pass

# ----------------------------------------------------------------------
# Logging Setup
# ----------------------------------------------------------------------
class LogLevel(Enum):
    """Enumeration for log levels."""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR
    CRITICAL = logging.CRITICAL

def setup_logging(log_file: str = LOG_FILE, console_level: str = "INFO", 
                  file_level: str = "DEBUG") -> logging.Logger:
    """
    Set up comprehensive logging system.
    
    This creates two handlers:
    1. File handler: Captures all logs at DEBUG level (detailed information)
    2. Console handler: Shows INFO and above (keeps console clean)
    
    Args:
        log_file: Path to the log file
        console_level: Logging level for console output
        file_level: Logging level for file output
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger('TutorPro')
    logger.setLevel(logging.DEBUG)  # Capture everything
    
    # Remove existing handlers to avoid duplicates
    logger.handlers = []
    
    # Create formatters
    # Detailed format for file logs
    file_formatter = logging.Formatter(
        '%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    # Simpler format for console
    console_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%H:%M:%S'
    )
    
    # File handler - logs everything
    try:
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setLevel(getattr(logging, file_level))
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create log file handler: {e}")
    
    # Console handler - logs INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level))
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger

# Initialize global logger
logger = setup_logging()

# ----------------------------------------------------------------------
# Usage Statistics Tracking
# ----------------------------------------------------------------------
@dataclass
class UsageStats:
    """Data class for tracking usage statistics."""
    timestamp: str
    student_id: int
    student_name: str
    event_type: str  # session_start, session_end, problem_attempt, state_transition, etc.
    topic_id: Optional[str] = None
    duration_seconds: Optional[float] = None
    grade: Optional[int] = None
    response_time_seconds: Optional[float] = None
    state_from: Optional[str] = None
    state_to: Optional[str] = None
    error_occurred: bool = False
    error_type: Optional[str] = None
    additional_data: Optional[Dict[str, Any]] = None

class StatsTracker:
    """
    Tracks and logs usage statistics for analytics and improvement.
    
    This class records all significant events during tutoring sessions,
    allowing for later analysis of:
    - Student engagement patterns
    - Problem difficulty calibration
    - Error rates and types
    - Session duration and timing
    - System performance
    """
    
    def __init__(self, stats_file: str = STATS_FILE):
        """
        Initialize the statistics tracker.
        
        Args:
            stats_file: Path to the statistics log file (JSON Lines format)
        """
        self.stats_file = stats_file
        self.session_stats = []
        logger.info(f"StatsTracker initialized with file: {stats_file}")
    
    def log_event(self, event: UsageStats):
        """
        Log a usage event.
        
        Args:
            event: UsageStats object containing event details
        """
        try:
            # Add to in-memory session stats
            self.session_stats.append(event)
            
            # Write to file (JSON Lines format for easy parsing)
            with open(self.stats_file, 'a', encoding='utf-8') as f:
                json.dump(asdict(event), f)
                f.write('\n')
                
            logger.debug(f"Logged stats event: {event.event_type}")
        except Exception as e:
            logger.error(f"Failed to log stats event: {e}", exc_info=True)
    
    def log_session_start(self, student_id: int, student_name: str):
        """Log the start of a tutoring session."""
        event = UsageStats(
            timestamp=datetime.now().isoformat(),
            student_id=student_id,
            student_name=student_name,
            event_type="session_start"
        )
        self.log_event(event)
    
    def log_session_end(self, student_id: int, student_name: str, duration_seconds: float):
        """Log the end of a tutoring session."""
        event = UsageStats(
            timestamp=datetime.now().isoformat(),
            student_id=student_id,
            student_name=student_name,
            event_type="session_end",
            duration_seconds=duration_seconds
        )
        self.log_event(event)
    
    def log_problem_attempt(self, student_id: int, student_name: str, topic_id: str,
                           grade: int, response_time_seconds: float, 
                           additional_data: Optional[Dict] = None):
        """Log a problem attempt."""
        event = UsageStats(
            timestamp=datetime.now().isoformat(),
            student_id=student_id,
            student_name=student_name,
            event_type="problem_attempt",
            topic_id=topic_id,
            grade=grade,
            response_time_seconds=response_time_seconds,
            additional_data=additional_data
        )
        self.log_event(event)
    
    def log_state_transition(self, student_id: int, student_name: str,
                            state_from: str, state_to: str, topic_id: Optional[str] = None):
        """Log a state machine transition."""
        event = UsageStats(
            timestamp=datetime.now().isoformat(),
            student_id=student_id,
            student_name=student_name,
            event_type="state_transition",
            state_from=state_from,
            state_to=state_to,
            topic_id=topic_id
        )
        self.log_event(event)
    
    def log_error(self, student_id: int, student_name: str, error_type: str,
                  additional_data: Optional[Dict] = None):
        """Log an error occurrence."""
        event = UsageStats(
            timestamp=datetime.now().isoformat(),
            student_id=student_id,
            student_name=student_name,
            event_type="error",
            error_occurred=True,
            error_type=error_type,
            additional_data=additional_data
        )
        self.log_event(event)
    
    def get_session_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the current session statistics.
        
        Returns:
            Dictionary containing aggregated session statistics
        """
        if not self.session_stats:
            return {}
        
        summary = {
            "total_events": len(self.session_stats),
            "problem_attempts": sum(1 for s in self.session_stats if s.event_type == "problem_attempt"),
            "errors": sum(1 for s in self.session_stats if s.error_occurred),
            "state_transitions": sum(1 for s in self.session_stats if s.event_type == "state_transition"),
            "average_response_time": None,
            "average_grade": None
        }
        
        # Calculate averages
        response_times = [s.response_time_seconds for s in self.session_stats 
                         if s.response_time_seconds is not None]
        if response_times:
            summary["average_response_time"] = sum(response_times) / len(response_times)
        
        grades = [s.grade for s in self.session_stats if s.grade is not None]
        if grades:
            summary["average_grade"] = sum(grades) / len(grades)
        
        return summary

# Initialize global stats tracker
stats_tracker = StatsTracker()

# ----------------------------------------------------------------------
# Content loading with error handling
# ----------------------------------------------------------------------
def load_topics() -> Dict:
    """
    Load topic data from JSON file with error handling.
    
    This function attempts to load the topics configuration from a JSON file.
    If the file doesn't exist, it creates a default configuration.
    If the file is corrupted, it raises a ContentLoadError.
    
    Returns:
        Dictionary containing topic configurations
        
    Raises:
        ContentLoadError: If the file exists but cannot be parsed
    """
    logger.info(f"Loading topics from {TOPICS_FILE}")
    
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
    
    if os.path.exists(TOPICS_FILE):
        try:
            with open(TOPICS_FILE, 'r', encoding='utf-8') as f:
                topics = json.load(f)
            logger.info(f"Successfully loaded {len(topics)} topics")
            return topics
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in {TOPICS_FILE}: {e}", exc_info=True)
            raise ContentLoadError(
                f"Failed to parse topics file: {TOPICS_FILE}",
                details={"error": str(e), "file": TOPICS_FILE}
            )
        except Exception as e:
            logger.error(f"Unexpected error loading topics: {e}", exc_info=True)
            raise ContentLoadError(
                f"Unexpected error loading topics: {str(e)}",
                details={"error": str(e), "file": TOPICS_FILE}
            )
    else:
        logger.warning(f"Topics file not found, creating default: {TOPICS_FILE}")
        try:
            with open(TOPICS_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_topics, f, indent=2)
            logger.info("Default topics file created successfully")
            return default_topics
        except Exception as e:
            logger.error(f"Failed to create default topics file: {e}", exc_info=True)
            raise ContentLoadError(
                f"Failed to create default topics file",
                details={"error": str(e), "file": TOPICS_FILE}
            )

# ----------------------------------------------------------------------
# Database setup with error handling
# ----------------------------------------------------------------------
def init_db():
    """
    Create database tables if they don't exist.
    
    This function initializes the SQLite database with all necessary tables
    for storing student progress, topics, and session history.
    
    Raises:
        DatabaseError: If database initialization fails
    """
    logger.info(f"Initializing database: {DB_FILE}")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # Students table
        c.execute('''
            CREATE TABLE IF NOT EXISTS students (
                student_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP
            )
        ''')
        logger.debug("Students table created/verified")
        
        # Topics table
        c.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                topic_id TEXT PRIMARY KEY,
                topic_name TEXT,
                content TEXT   -- JSON dump of explanations, problems, etc.
            )
        ''')
        logger.debug("Topics table created/verified")
        
        # Student-topic progress table
        c.execute('''
            CREATE TABLE IF NOT EXISTS student_topics (
                student_id INTEGER,
                topic_id TEXT,
                mastery_level INTEGER DEFAULT 0,
                status TEXT DEFAULT 'learning',  -- learning, mastered, review
                ease_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 0,
                next_review_date DATE,
                last_reviewed_date DATE,
                consecutive_correct INTEGER DEFAULT 0,
                total_attempts INTEGER DEFAULT 0,
                misconceptions TEXT,  -- JSON array
                PRIMARY KEY (student_id, topic_id),
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
            )
        ''')
        logger.debug("Student_topics table created/verified")
        
        # Session history table
        c.execute('''
            CREATE TABLE IF NOT EXISTS session_history (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER,
                topic_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                interaction_log TEXT,  -- JSON
                duration_minutes INTEGER,
                performance_score REAL,
                FOREIGN KEY (student_id) REFERENCES students(student_id),
                FOREIGN KEY (topic_id) REFERENCES topics(topic_id)
            )
        ''')
        logger.debug("Session_history table created/verified")
        
        conn.commit()
        conn.close()
        logger.info("Database initialization completed successfully")
        
    except sqlite3.Error as e:
        logger.error(f"SQLite error during initialization: {e}", exc_info=True)
        raise DatabaseError(
            "Failed to initialize database",
            details={"error": str(e), "database": DB_FILE}
        )
    except Exception as e:
        logger.error(f"Unexpected error during database initialization: {e}", exc_info=True)
        raise DatabaseError(
            f"Unexpected database error: {str(e)}",
            details={"error": str(e), "database": DB_FILE}
        )

def populate_topics():
    """
    Insert topics from JSON into the topics table.
    
    Raises:
        DatabaseError: If database operations fail
        ContentLoadError: If topics cannot be loaded
    """
    logger.info("Populating topics in database")
    
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
            except Exception as e:
                logger.warning(f"Failed to insert topic {topic_id}: {e}")
                continue
        
        conn.commit()
        conn.close()
        logger.info(f"Successfully populated {len(topics)} topics")
        
    except ContentLoadError:
        raise  # Re-raise ContentLoadError as-is
    except sqlite3.Error as e:
        logger.error(f"Database error during topic population: {e}", exc_info=True)
        raise DatabaseError(
            "Failed to populate topics",
            details={"error": str(e)}
        )
    except Exception as e:
        logger.error(f"Unexpected error populating topics: {e}", exc_info=True)
        raise DatabaseError(
            f"Unexpected error: {str(e)}",
            details={"error": str(e)}
        )

def get_student_id(name: str) -> int:
    """
    Get or create a student by name.
    
    Args:
        name: Student's name
        
    Returns:
        Student ID (integer)
        
    Raises:
        StudentDataError: If student operations fail
    """
    logger.info(f"Getting/creating student: {name}")
    
    if not name or not name.strip():
        raise StudentDataError("Student name cannot be empty")
    
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT student_id FROM students WHERE name = ?', (name,))
        row = c.fetchone()
        
        if row:
    