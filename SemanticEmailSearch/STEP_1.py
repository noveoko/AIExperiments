import mailbox
import sqlite3
import os
from email.header import decode_header, make_header
from tqdm import tqdm

def create_database(db_path):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # Create a table to store email data if it doesn't exist
    c.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject TEXT,
            from_email TEXT,
            to_email TEXT,
            date TEXT,
            body TEXT,
            embeddings BLOB
        )
    ''')
    conn.commit()
    
    return conn

def save_to_database(conn, email_data):
    c = conn.cursor()
    c.execute('''
        INSERT INTO emails (subject, from_email, to_email, date, body, embeddings)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', email_data)
    conn.commit()

def extract_email_data(email):
    def decode_header_part(header_value):
        headers = decode_header(header_value or "")
        return str(make_header(headers))

    subject = decode_header_part(email.get('subject', ''))
    from_email = decode_header_part(email.get('from', ''))
    to_email = decode_header_part(email.get('to', ''))
    date = decode_header_part(email.get('date', ''))

    if email.is_multipart():
        body = ''
        for part in email.walk():
            if part.get_content_type() == 'text/plain':
                body += part.get_payload(decode=True).decode('utf-8', errors='ignore')
    else:
        body = email.get_payload(decode=True).decode('utf-8', errors='ignore')

    embeddings = None

    return subject, from_email, to_email, date, body, embeddings

def process_mbox(mbox_path, db_path):
    if not os.path.exists(mbox_path):
        print(f"Error: {mbox_path} does not exist")
        return
    
    conn = create_database(db_path)
    mbox = mailbox.mbox(mbox_path)

    # Use tqdm to wrap message processing for progress indication
    for message in tqdm(mbox, desc="Processing emails", unit="email"):
        email_data = extract_email_data(message)
        save_to_database(conn, email_data)
    
    conn.close()
    print("Processing complete!")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Usage: python mbox_to_sqlite3_db.py <path_to_mbox> <sqlite_db_path>")
        sys.exit(1)

    mbox_file_path = sys.argv[1]
    sqlite_db_path = sys.argv[2]
    
    process_mbox(mbox_file_path, sqlite_db_path)
