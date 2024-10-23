import sqlite3
import json
import numpy as np
from tqdm import tqdm
from STEP_2_embed import embed_string

def cosine_similarity(v1, v2):
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

def get_sorted_emails_by_similarity(db_path, target_embedding):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Fetch all emails with embeddings
    c.execute('SELECT id, subject, embeddings FROM emails WHERE embeddings IS NOT NULL')
    emails = c.fetchall()
    conn.close()

    target_embedding_np = np.array(target_embedding)

    similarity_scores = []
    for email_id, subject, embeddings_blob in tqdm(emails, desc="Calculating similarities", unit="email"):
        if not embeddings_blob:
            continue  # Skip if embeddings are missing or empty
        
        try:
            email_embedding = json.loads(embeddings_blob)
            email_embedding_np = np.array(email_embedding)

            if len(email_embedding_np) != len(target_embedding_np):
                print(f"Skipping email ID {email_id} due to dimension mismatch.")
                continue  # Skip if dimensions do not match

            similarity = cosine_similarity(target_embedding_np, email_embedding_np)
            similarity_scores.append((similarity, email_id, subject))
        
        except (json.JSONDecodeError, TypeError) as e:
            print(f"Skipping email ID {email_id} due to invalid embedding.", str(e))
            continue  # Skip if there's an error decoding or processing the embedding

    similarity_scores.sort(reverse=True, key=lambda x: x[0])

    return similarity_scores[:20]

if __name__ == "__main__":
    sqlite_db_path = <path_to_sqlite3_db>

    while True:
        target_for_search = input("Enter search term (or 'exit' to quit): ")
        if target_for_search.lower() == 'exit':
            break

        target_embedding = embed_string(target_for_search)
        
        sorted_emails = get_sorted_emails_by_similarity(sqlite_db_path, target_embedding)

        print("\nTop 20 closest matches:")
        for score, email_id, subject in sorted_emails:
            print(f"Email ID: {email_id}, Subject: {subject}, Similarity: {score:.4f}")

        print("\nSearch again or type 'exit' to quit.\n")
