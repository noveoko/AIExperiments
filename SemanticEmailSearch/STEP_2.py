import sqlite3
import json
import ollama  # Assuming this is the package providing embeddings
from tqdm import tqdm

def embed_string(string, model='all-minilm'):
    return ollama.embeddings(model, string)['embedding']

def update_embeddings(db_path, model='all-minilm'):
    # Connect to the SQLite3 database
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Select all emails where embeddings are missing
    c.execute('SELECT id, body FROM emails WHERE embeddings IS NULL')
    emails = c.fetchall()

    # Update each email's embeddings with tqdm progress bar
    for email_id, body in tqdm(emails, desc="Updating embeddings", unit="email"):
        # Generate embeddings for the email body
        embeddings = embed_string(body, model)
        
        # Convert embeddings to a JSON string for storage as BLOB
        embeddings_blob = json.dumps(embeddings)

        # Update the email record with the new embeddings
        c.execute('''
            UPDATE emails
            SET embeddings = ?
            WHERE id = ?
        ''', (embeddings_blob, email_id))

    # Commit changes and close the connection
    conn.commit()
    conn.close()
    print("Embeddings updated successfully!")

if __name__ == "__main__":
    # Specify the path to your SQLite database
    sqlite_db_path = <path_to_sqlite3_db>
    
    # Update embeddings with the specified model
    update_embeddings(sqlite_db_path)
