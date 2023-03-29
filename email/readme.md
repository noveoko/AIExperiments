## Plot my Emails

Replace the mbox_path variable with the path to your mbox file, then run the script. This script reads the mbox file in chunks, extracts the "from" and "to" email addresses, creates a network graph with edge thickness based on the number of emails sent, and plots a bar chart showing the number of emails sent between the top 10 most active accounts.

GPT-4 Prompt used:
Write a complete Python scipt that:
1. reads an mbox file in chunks
2. extract all from email and to email (John@k.com sent email to [Mary@t.com, Tori@la.com...])
3. draw a network graph with edge thickness determined by number of emails sent
4. plots a bar chart showing the number of emails sent between the top 10 most active accounts
