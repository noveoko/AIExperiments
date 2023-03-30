import os
import pickle
import smtplib
import hashlib
from email.message import EmailMessage
from requests import get

# Set your email credentials and target email address
EMAIL_ADDRESS = os.environ.get('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
TO_EMAIL = 'your_email@example.com'

# List of URLs to visit
urls = [
    'https://example1.com',
    'https://example2.com'
]

# Load previous results or create a new empty dictionary
try:
    with open('prev_results.pkl', 'rb') as f:
        prev_results = pickle.load(f)
except FileNotFoundError:
    prev_results = {}

daily_results = {}

# Visit each URL and check for changes
for url in urls:
    response = get(url)
    content_hash = hashlib.md5(response.content).hexdigest()

    if url not in prev_results or prev_results[url] != content_hash:
        daily_results[url] = content_hash
        prev_results[url] = content_hash

# Save updated results
with open('prev_results.pkl', 'wb') as f:
    pickle.dump(prev_results, f)

# If there are changes, send an email
if daily_results:
    msg = EmailMessage()
    msg.set_content(str(daily_results))

    msg['Subject'] = 'Daily URL Changes'
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = TO_EMAIL

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
        smtp.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        smtp.send_message(msg)

    print('Email sent!')
else:
    print('No changes detected.')
