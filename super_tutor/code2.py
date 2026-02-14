#!/usr/bin/env python3
"""
Mathematics Tutor Pro – LLM‑powered adaptive tutor using Ollama.

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
  python tutor_pro.py
"""

import json
import sqlite3
import time
import random
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
import requests  # for calling Ollama's API

# ----------------------------------------------------------------------
# Configuration
# ----------------------------------------------------------------------
OLLAMA_API = "http://localhost:11434/api/generate"
MODEL = "llama3"          # change to any model you have pulled
TOPICS_FILE = "topics.json"
DB_FILE = "tutor.db"

# ----------------------------------------------------------------------
# Content loading
# ----------------------------------------------------------------------
def load_topics() -> Dict:
    """Load topic data from JSON file. Creates a default if file missing."""
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
        with open(TOPICS_FILE, 'r') as f:
            return json.load(f)
    else:
        with open(TOPICS_FILE, 'w') as f:
            json.dump(default_topics, f, indent=2)
        return default_topics

# ----------------------------------------------------------------------
# Database setup
# ----------------------------------------------------------------------
def init_db():
    """Create tables if they don't exist."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS students (
            student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS topics (
            topic_id TEXT PRIMARY KEY,
            topic_name TEXT,
            content TEXT   -- JSON dump of explanations, problems, etc.
        )
    ''')
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
    conn.commit()
    conn.close()

def populate_topics():
    """Insert topics from JSON into the topics table."""
    topics = load_topics()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    for topic_id, data in topics.items():
        c.execute('''
            INSERT OR IGNORE INTO topics (topic_id, topic_name, content)
            VALUES (?, ?, ?)
        ''', (topic_id, data['name'], json.dumps(data)))
    conn.commit()
    conn.close()

def get_student_id(name: str) -> int:
    """Get or create a student by name. Return student_id."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT student_id FROM students WHERE name = ?', (name,))
    row = c.fetchone()
    if row:
        sid = row[0]
    else:
        c.execute('INSERT INTO students (name, last_active) VALUES (?, ?)',
                  (name, datetime.now()))
        sid = c.lastrowid
    conn.commit()
    conn.close()
    return sid

def update_last_active(sid: int):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE students SET last_active = ? WHERE student_id = ?',
              (datetime.now(), sid))
    conn.commit()
    conn.close()

# ----------------------------------------------------------------------
# LLM interface
# ----------------------------------------------------------------------
def llm_generate(prompt: str, system: str = "", max_tokens: int = 500) -> str:
    """Call Ollama's generate API with the given prompt."""
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {
            "num_predict": max_tokens,
            "temperature": 0.7
        }
    }
    try:
        resp = requests.post(OLLAMA_API, json=payload)
        resp.raise_for_status()
        return resp.json()["response"]
    except Exception as e:
        print(f"LLM error: {e}")
        return "I'm having trouble responding right now."

def assess_response(question: str, student_answer: str, context: str = "") -> Tuple[int, str, List[str]]:
    """
    Ask LLM to grade the student's answer on 0-5, provide feedback, and list misconceptions.
    Returns (grade, feedback, misconceptions_list)
    """
    system_prompt = """You are a mathematics tutor. Assess the student's answer to the given question.
Rate it on a scale of 0 to 5:
0 = completely wrong / no understanding
1 = minimal understanding, major errors
2 = partial understanding, some correct ideas but significant errors
3 = mostly correct, minor errors or unclear explanation
4 = correct with good explanation, maybe minor slip
5 = perfect understanding, clearly explained

Also list any misconceptions you detect. Be concise."""
    prompt = f"""Question: {question}
Student's answer: {student_answer}
Context: {context}

First, output a single number (0-5) on a line by itself. Then on the next line, give brief feedback. Then on subsequent lines, list any misconceptions (one per line)."""
    response = llm_generate(prompt, system=system_prompt, max_tokens=300)
    lines = response.strip().split('\n')
    grade = 3  # default
    feedback = ""
    misconceptions = []
    try:
        # first line should be a number
        grade = int(lines[0].strip())
        if len(lines) > 1:
            feedback = lines[1].strip()
        if len(lines) > 2:
            misconceptions = [l.strip() for l in lines[2:] if l.strip()]
    except:
        # fallback: try to parse anyway
        pass
    return grade, feedback, misconceptions

def generate_alternative_explanation(topic_id: str, style: str, student_level: str) -> str:
    """Ask LLM to generate an explanation in a given style."""
    topics = load_topics()
    topic_data = topics.get(topic_id, {})
    base = topic_data.get('explanations', {}).get(style, "")
    prompt = f"""Explain the concept of '{topic_data.get('name', topic_id)}' to a student who is at level '{student_level}'.
Use a {style} style explanation. Be clear and encouraging.
Base explanation to inspire you (optional): {base}
"""
    return llm_generate(prompt, max_tokens=400)

def generate_diagnostic_question(topic_id: str, misconception: str) -> str:
    """Generate a question to probe a specific misconception."""
    topics = load_topics()
    topic_name = topics.get(topic_id, {}).get('name', topic_id)
    prompt = f"""The student is learning '{topic_name}' and may have the misconception: '{misconception}'.
Generate a single diagnostic question that will help uncover whether they truly have this misconception.
The question should be simple and focused."""
    return llm_generate(prompt, max_tokens=200)

# ----------------------------------------------------------------------
# SM-2 spaced repetition
# ----------------------------------------------------------------------
def sm2_update(ease_factor: float, interval: int, grade: int) -> Tuple[float, int]:
    """
    Apply SM-2 algorithm given current ease factor, interval (days), and grade (0-5).
    Returns new (ease_factor, interval_days).
    """
    if grade >= 3:
        # correct response
        if interval == 0:
            new_interval = 1
        elif interval == 1:
            new_interval = 6
        else:
            new_interval = round(interval * ease_factor)
        new_ease = ease_factor + (0.1 - (5 - grade) * (0.08 + (5 - grade) * 0.02))
    else:
        # incorrect response
        new_interval = 1  # reset to 1 day
        new_ease = ease_factor
    # Ensure ease factor stays within [1.3, 2.5]
    new_ease = max(1.3, min(2.5, new_ease))
    return new_ease, new_interval

# ----------------------------------------------------------------------
# Finite State Machine Tutor
# ----------------------------------------------------------------------
class TutorSession:
    def __init__(self, student_id: int, student_name: str):
        self.sid = student_id
        self.name = student_name
        self.topics = load_topics()
        self.current_topic_id = None
        self.current_topic_data = None
        self.state = "START"
        self.session_start = datetime.now()
        self.last_activity = self.session_start
        self.consecutive_errors = 0
        self.fatigue_threshold_minutes = 25
        self.slow_response_seconds = 120
        self.break_suggested = False
        self.interaction_log = []

        # Load student's progress for all topics from DB
        self.student_topics = self._load_student_topics()

    def _load_student_topics(self) -> Dict[str, Any]:
        """Return dict mapping topic_id to progress data."""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            SELECT topic_id, mastery_level, status, ease_factor, interval_days,
                   next_review_date, consecutive_correct, total_attempts, misconceptions
            FROM student_topics WHERE student_id = ?
        ''', (self.sid,))
        rows = c.fetchall()
        conn.close()
        data = {}
        for row in rows:
            data[row[0]] = {
                'mastery': row[1],
                'status': row[2],
                'ease': row[3],
                'interval': row[4],
                'next_review': row[5],
                'consecutive_correct': row[6],
                'attempts': row[7],
                'misconceptions': json.loads(row[8]) if row[8] else []
            }
        return data

    def _save_topic_progress(self, topic_id: str):
        """Save current topic progress to DB."""
        p = self.student_topics.get(topic_id, {})
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO student_topics
            (student_id, topic_id, mastery_level, status, ease_factor, interval_days,
             next_review_date, consecutive_correct, total_attempts, misconceptions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            self.sid, topic_id,
            p.get('mastery', 0),
            p.get('status', 'learning'),
            p.get('ease', 2.5),
            p.get('interval', 0),
            p.get('next_review', None),
            p.get('consecutive_correct', 0),
            p.get('attempts', 0),
            json.dumps(p.get('misconceptions', []))
        ))
        conn.commit()
        conn.close()

    def log_interaction(self, topic_id: str, data: Dict):
        self.interaction_log.append(data)
        # optionally write to session_history periodically

    def run(self):
        """Main loop: process states until done."""
        print(f"\n--- Mathematics Tutor Pro ---")
        print(f"Hello {self.name}! Let's learn some math.\n")
        while self.state != "END":
            # Check for fatigue periodically
            self._check_fatigue()
            # Dispatch current state
            state_method = getattr(self, f"state_{self.state}", None)
            if state_method:
                state_method()
            else:
                print(f"Unknown state {self.state}, ending.")
                break
        print("Session ended. Great work!")

    def _check_fatigue(self):
        """Suggest a break if session too long or consecutive errors."""
        elapsed = (datetime.now() - self.session_start).total_seconds() / 60
        if elapsed > self.fatigue_threshold_minutes and not self.break_suggested:
            print("\n[System: You've been studying for a while. Would you like a 5‑minute break? (yes/no)]")
            resp = input().strip().lower()
            if resp in ('yes', 'y'):
                print("Take your time. Type 'ready' when you're back.")
                while True:
                    if input().strip().lower() == 'ready':
                        break
                self.break_suggested = True
                self.session_start = datetime.now()  # reset timer
            else:
                self.break_suggested = True  # don't ask again

    # ----- State definitions -----

    def state_START(self):
        """Initial state: decide what to do next."""
        # Check for topics due for review
        due = self._get_due_reviews()
        if due:
            print(f"You have {len(due)} topic(s) due for review.")
            self.current_topic_id = due[0]
            self.current_topic_data = self.topics[self.current_topic_id]
            self.state = "REVIEW"
        else:
            # Pick a new topic (simplest: first not mastered)
            for tid in self.topics:
                if tid not in self.student_topics or self.student_topics[tid]['status'] != 'mastered':
                    self.current_topic_id = tid
                    self.current_topic_data = self.topics[tid]
                    self.state = "TOPIC_INTRODUCTION"
                    break
            if not self.current_topic_id:
                print("Congratulations! You've mastered all topics!")
                self.state = "END"

    def _get_due_reviews(self) -> List[str]:
        """Return list of topic ids whose next_review_date <= today."""
        due = []
        today = datetime.now().date()
        for tid, prog in self.student_topics.items():
            if prog.get('next_review'):
                next_review = datetime.strptime(prog['next_review'], '%Y-%m-%d').date()
                if next_review <= today:
                    due.append(tid)
        return due

    def state_TOPIC_INTRODUCTION(self):
        """Introduce the topic and ask if they're ready."""
        print(f"\nTopic: {self.current_topic_data['name']}")
        print("Let's start learning. I'll explain the concept, then we'll practice.")
        # Provide a brief intro explanation (use LLM or stored)
        intro = self.current_topic_data['explanations']['procedural']
        print(f"\n{intro}\n")
        input("Press Enter when you're ready to try a problem.")
        self.state = "TEACHING"

    def state_TEACHING(self):
        """Present a problem and assess."""
        # Pick a problem from the topic (simple random)
        problems = self.current_topic_data['problems']
        prob = random.choice(problems)
        print(f"\nProblem: {prob['text']}")
        start_time = time.time()
        student_input = input("Your answer (or type 'help' for a hint): ").strip()
        response_time = time.time() - start_time

        if student_input.lower() == 'help':
            # Generate a hint using LLM
            hint = llm_generate(f"Give a brief hint for solving: {prob['text']} (don't give the answer)")
            print(f"Hint: {hint}")
            # After hint, ask again (simple loop back)
            self.state = "TEACHING"
            return

        # Use LLM to assess
        context = f"Topic: {self.current_topic_data['name']}. Correct answer is {prob['answer']}."
        grade, feedback, misconceptions = assess_response(prob['text'], student_input, context)
        print(f"Feedback: {feedback}")
        if misconceptions:
            print("Possible misconceptions:", ", ".join(misconceptions))

        # Record attempt
        prog = self.student_topics.setdefault(self.current_topic_id, {
            'mastery': 0,
            'status': 'learning',
            'ease': 2.5,
            'interval': 0,
            'consecutive_correct': 0,
            'attempts': 0,
            'misconceptions': []
        })
        prog['attempts'] += 1
        if grade >= 4:
            prog['consecutive_correct'] += 1
        else:
            prog['consecutive_correct'] = 0

        # Check for mastery (3 consecutive correct with grade>=4)
        if prog['consecutive_correct'] >= 3:
            print("Great! You've mastered this concept for now.")
            # Update SM-2
            prog['status'] = 'review'
            prog['next_review'] = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            self._save_topic_progress(self.current_topic_id)
            self.state = "ASSESSMENT"  # move to final assessment
        else:
            # Decide next action based on grade and errors
            if grade < 3:
                self.consecutive_errors += 1
                if self.consecutive_errors >= 3:
                    print("You seem to be struggling. Let's try a different explanation.")
                    self.state = "REMEDIATION"
                else:
                    # Stay in teaching, give another problem
                    print("Let's try another problem.")
                    self.state = "TEACHING"
            else:
                self.consecutive_errors = 0
                print("Good progress. Let's try another problem.")
                self.state = "TEACHING"

    def state_REMEDIATION(self):
        """Provide alternative explanation or break down concept."""
        print("\nLet's approach this differently.")
        # Choose a style different from the default
        styles = list(self.current_topic_data['explanations'].keys())
        chosen = random.choice(styles)
        explanation = generate_alternative_explanation(
            self.current_topic_id,
            chosen,
            "struggling"
        )
        print