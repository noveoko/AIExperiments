import mailbox
import email
from collections import defaultdict
from itertools import combinations
import networkx as nx
import matplotlib.pyplot as plt
import sys

def read_mbox_chunk(mbox_path, chunk_size):
    mbox = mailbox.mbox(mbox_path)
    chunk = []
    for message in mbox:
        chunk.append(message)
        if len(chunk) == chunk_size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk

def extract_from_to_emails(msg):
    def decode_email_header(header):
        decoded = decode_header(header)
        return ' '.join([str(t[0], t[1] or 'ascii') for t in decoded])

    msg_from = email.utils.parseaddr(decode_email_header(msg['From']))[1]
    msg_to = msg.get_all('To', [])
    msg_cc = msg.get_all('Cc', [])
    msg_bcc = msg.get_all('Bcc', [])
    all_recipients = msg_to + msg_cc + msg_bcc

    recipients = [email.utils.parseaddr(decode_email_header(addr))[1] for addr in all_recipients]

    return msg_from, recipients

def process_mbox(mbox_path, chunk_size=500):
    email_count = defaultdict(int)
    for chunk in read_mbox_chunk(mbox_path, chunk_size):
        email_pairs = extract_from_to_emails(chunk)
        for email_pair in email_pairs:
            email_count[email_pair] += 1
    return email_count

def draw_network_graph(email_count):
    G = nx.DiGraph()
    for email_pair, count in email_count.items():
        G.add_edge(email_pair[0], email_pair[1], weight=count)

    pos = nx.spring_layout(G, seed=42)
    edge_widths = [count for _, _, count in G.edges(data="weight")]

    plt.figure(figsize=(10, 8))
    nx.draw(G, pos, with_labels=True, node_size=2000, font_size=10,
            node_color="skyblue", edge_color="b", width=edge_widths, alpha=0.8)
    plt.title("Network graph of email communication")
    plt.show()

def plot_bar_chart(email_count):
    top_10_email_count = sorted(email_count.items(), key=lambda x: x[1], reverse=True)[:10]
    email_pairs, counts = zip(*top_10_email_count)

    plt.figure(figsize=(12, 6))
    plt.bar(range(len(email_pairs)), counts)
    plt.xticks(range(len(email_pairs)), [f"{pair[0]}\n->\n{pair[1]}" for pair in email_pairs], fontsize=10, rotation=45)
    plt.xlabel("Email Pairs")
    plt.ylabel("Number of Emails Sent")
    plt.title("Top 10 Most Active Email Accounts")
    plt.show()

def main(mbox_path):
    email_count = process_mbox(mbox_path)
    draw_network_graph(email_count)
    plot_bar_chart(email_count)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 script.py <path_to_mbox>")
        sys.exit(1)

    mbox_path = sys.argv[1]
    main(mbox_path)
