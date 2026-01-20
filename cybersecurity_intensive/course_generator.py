import google.generativeai as genai
import os
import time
import re

# --- CONFIGURATION ---
# Replace with your actual API key
API_KEY = "YOUR_GOOGLE_API_KEY_HERE"

# Create a directory to save the tutorials
OUTPUT_DIR = "security_tutorials"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

# Configure the Gemini API
genai.configure(api_key=API_KEY)

# specific model configuration
generation_config = {
  "temperature": 0.7,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 4096,
}

model = genai.GenerativeModel(
    model_name="gemini-1.5-flash", # Flash is faster/cheaper for high volume tasks
    generation_config=generation_config,
)

# --- THE DATA ---
# The full list of 100 steps provided previously
steps_data = """
1. Define the CIA Triad: Write down one example each of a failure in Confidentiality, Integrity, and Availability.
2. Read the "Least Privilege" Principle: Audit one folder on your PC. Does "Everyone" have write access? Change it.
3. Browse the "Dark Reading" website: Bookmark it and read just one headline article to see what current breaches look like.
4. Study the Attack Lifecycle: Look up the "Cyber Kill Chain" diagram. Identify the "Delivery" phase.
5. Learn "Blue vs. Red vs. Purple": Spend 5 minutes reading the definitions of these three team types.
6. Create a "Burner" Email: Set up a ProtonMail or Tutanota account for your security testing/sign-ups.
7. Explore CVE Details: Go to cvedetails.com and search for a framework you use (e.g., "Django"). Look at the top vulnerability.
8. Understand "Zero Day": Read the definition and find one famous historical example (like Stuxnet).
9. Differentiate Threat vs. Vulnerability: Write down the difference in your own words.
10. Check HaveIBeenPwned: Run your personal email. If compromised, identify which breach it came from.
11. Download VirtualBox or VMware Player: Just download the installer.
12. Download Kali Linux ISO: Start the download for the "Installer" image.
13. Download OWASP Juice Shop: This is a purposefully insecure web app. Download the Docker container or Node source.
14. Configure VM Network Settings: Read a 5-minute guide on "NAT vs. Bridged Adapter" in VirtualBox.
15. Boot Kali Live: Spin it up just to see the desktop environment.
16. Explore the Kali Menu: Open the application menu and look at the "Top 10 Security Tools" category.
17. Terminal Check: Open the terminal in Kali. Type id and whoami.
18. Update Repositories: Run sudo apt update in your Kali VM.
19. Snapshot Your VM: Learn how to take a snapshot so you can break things and roll back.
20. Isolate the Lab: Ensure your VM cannot talk to your home printer or smart TV (check IP ranges).
21. Memorize the OSI Model: Don't memorize every detail, just the 7 layer names. Mnemonic: Please Do Not Throw Sausage Pizza Away.
22. Identify Layer 3 vs Layer 4: Write down which layer IP addresses live in and which layer TCP ports live in.
23. Install Wireshark: Install it on your main machine or verify it's on Kali.
24. Capture a Ping: Open Wireshark, filter for icmp, and ping 8.8.8.8. Watch the request and reply packets.
25. Filter for HTTP: Go to an HTTP (not HTTPS) site (like neverssl.com) while Wireshark is running. Filter for http.
26. Analyze a Handshake: Look for the SYN, SYN-ACK, ACK packets in Wireshark.
27. What is a MAC Address?: Find the MAC address of your local network card (ipconfig /all or ifconfig).
28. Subnetting Basics: Read a 5-minute explanation of CIDR notation (e.g., what /24 means).
29. Common Ports 1-3: Memorize ports for SSH (22), FTP (21), Telnet (23).
30. Common Ports 4-6: Memorize ports for HTTP (80), HTTPS (443), DNS (53).
31. DNS Query: In terminal, type nslookup google.com and analyze the output.
32. Use Netcat (Client): Use nc -v scanme.nmap.org 80 to manually connect to a server.
33. Use Netcat (Listener): Open two terminals. Listen on one (nc -lvp 4444). Connect from the other. Chat.
34. ARP Table: Type arp -a. See how your computer maps IP addresses to MAC addresses.
35. DHCP DORA: Read about the "Discovery, Offer, Request, Acknowledge" process.
36. Check Open Ports: Run netstat -antp (or ss -antp) to see what is listening on your machine.
37. Permissions 101: Create a file. Run chmod 777 file. Then run ls -l to see the dangers.
38. The /etc/passwd file: Cat this file. Identify the fields (Username, UID, GID, Shell).
39. The /etc/shadow file: Try to cat this file. Note the "Permission Denied". Sudo it. See the hashed passwords.
40. SSH Keys: Generate a keypair with ssh-keygen. Look at the public vs private key files.
41. Cron Jobs: Type crontab -e. Add a job that runs echo "hello" >> /tmp/test.txt every minute.
42. Process List: Run ps aux | grep python. Identify a Process ID (PID).
43. Kill a Process: Use kill -9 [PID] on the process you just found.
44. Logs (Auth): Tail the authentication log (tail -f /var/log/auth.log or similar) and try to sudo or login.
45. Sudoers: Read the /etc/sudoers file (use visudo). Understand who has root power.
46. OWASP Top 10: Read the titles of the current Top 10 vulnerabilities.
47. Inspect Element Hacking: Go to a login form. Change the password input type from "password" to "text" in the browser dev tools.
48. Cookie Manipulation: Open DevTools > Application > Cookies. Edit a cookie value and refresh.
49. SQL Injection (Concept): Draw a diagram of how ' OR 1=1 -- alters a SQL query.
50. SQL Injection (Practice): Try a basic payload on a legal practice site (like Juice Shop or testphp.vulnweb.com).
51. Reflected XSS: Enter <script>alert(1)</script> into a search bar on Juice Shop.
52. Burp Suite Proxy: Configure your browser to send traffic through Burp Suite (free version).
53. Intercept a Request: Catch a request in Burp, pause it, modify a parameter, and forward it.
54. HTTP Headers: Look at the headers in a Burp request. Identify User-Agent and Cookie.
55. Directory Traversal: Try accessing ../../../../etc/passwd on a vulnerable lab machine.
56. Command Injection: If an app pings an IP, try entering 127.0.0.1; whoami.
57. IDOR: Read about "Insecure Direct Object Reference". Imagine changing user_id=100 to user_id=101.
58. Robots.txt: Visit google.com/robots.txt. See what they are hiding/disallowing.
59. View Source: Right-click > View Source on a page. Search for "API", "Key", or "TODO".
60. Encoding: Go to CyberChef (online). Convert a string to Base64 and back.
61. Import socket: Write a 3-line script to connect to Google on port 80.
62. Port Scanner v1: Write a loop in Python that tries to connect to ports 20-100 on localhost.
63. Import requests: Script a GET request to a website and print the status code.
64. Header Grabber: Modify the previous script to print response.headers['Server'].
65. Brute Force (Concept): Write a script that iterates through a list of 5 passwords and prints them (don't send them yet).
66. User Agent Spoofing: Change the User-Agent string in your Python request to look like an iPhone.
67. Parsing HTML: Use BeautifulSoup to extract all <a href> links from a page (a basic crawler).
68. Subdomain Enumeration: Write a script that tries to request admin.site.com, dev.site.com from a list.
69. Encoding Script: Write a function that takes text and rotates it (ROT13) without using a library.
70. File Hash: Use hashlib to print the MD5 checksum of a string.
71. Banner Grabbing: Use Python sockets to grab the welcome message from an FTP server (port 21).
72. MAC Address Lookup: Write a script that takes a MAC address and looks up the manufacturer via an API.
73. JSON Parsing: Fetch a JSON object from an API and extract a specific security field.
74. Scapy Basics: Install Scapy (pip install scapy). Run it and type ls().
75. Craft a Packet: In Scapy, create a packet: p = IP(dst="8.8.8.8")/ICMP(). Print it.
76. Nmap Ping Scan: Run nmap -sn [network_range] to see live hosts.
77. Nmap Service Scan: Run nmap -sV [target_ip] to see versions of running services.
78. Nmap Scripts: Run nmap --script=default [target_ip].
79. Nikto Scan: Run nikto -h [target_url] (on your local vulnerable app) to find web configs.
80. Gobuster/Dirb: Use a directory buster to find hidden folders (like /admin) on your local lab.
81. Searchsploit: Run searchsploit apache in Kali to see available exploits for Apache.
82. Metasploit Setup: Type msfconsole and wait for it to load.
83. Metasploit Search: Inside msfconsole, type search vsftpd.
84. Metasploit Info: Type info [exploit_path] to read about a specific exploit.
85. WhatWeb: Run whatweb [url] to identify the technologies used on a site.
86. Windows Event Logs: Open Event Viewer on Windows. Look at "Security" logs. Find a "Logon" event (ID 4624).
87. Linux Auth Logs: Use grep "Failed password" /var/log/auth.log to see failed login attempts.
88. Firewall Rules (UFW): On Linux, type sudo ufw status. Read the docs on how to deny port 22.
89. Honeypot Concept: Read a 5-minute article on what a "Canary Token" is.
90. Create a Canary: Go to canarytokens.org. Generate a token (like a Word doc) that alerts you when opened.
91. SIEM Basics: Watch a 5-minute YouTube video on "What is Splunk?".
92. YARA Rules: Look up a sample YARA rule. It's essentially "grep" for malware signatures.
93. VirusTotal: Upload a harmless file (or a hash) to VirusTotal to see how AV engines scan it.
94. Phishing Analysis: Open a spam email (carefully) and look at the "Received-SPF" header.
95. Password Policy: Check the password policy on your local computer (gpedit.msc or /etc/login.defs).
96. Twitter/X Security: Follow 3 security accounts (e.g., SwiftOnSecurity, KrebsOnSecurity, HackersNews).
97. GitHub: Star a security repo (like SecLists).
98. CTF Time: Visit ctftime.org. See what a "Capture The Flag" competition schedule looks like.
99. TryHackMe: Create a free account. Look at the "Pre-Security" learning path.
100. The Next Step: Pick one domain from above (Web, Network, or Python) that you enjoyed the most to focus on for the next month.
"""

# --- MAIN LOGIC ---

def generate_tutorials():
    # Split the raw text into a list of lines, removing empty ones
    lines = [line.strip() for line in steps_data.split('\n') if line.strip()]
    
    print(f"Found {len(lines)} tasks. Starting generation...")

    for line in lines:
        # Regex to capture the number and the task text
        # Example: "1. Define the CIA Triad: Write down..."
        match = re.match(r"^(\d+)\.\s*(.*)", line)
        
        if not match:
            continue
            
        step_number = match.group(1)
        task_text = match.group(2)
        
        # File naming
        safe_title = "".join(x for x in task_text[:30] if x.isalnum() or x in " _-").strip().replace(" ", "_")
        filename = f"{OUTPUT_DIR}/Step_{step_number.zfill(3)}_{safe_title}.md"
        
        # Skip if already exists (resume capability)
        if os.path.exists(filename):
            print(f"Skipping {filename} (already exists)")
            continue

        print(f"Generating Step {step_number}: {task_text[:50]}...")

        # The Prompt
        prompt = f"""
        You are an expert cybersecurity instructor. 
        Create a self-contained, hands-on tutorial in Markdown format for the following task:
        
        TASK: "{task_text}"
        
        Target Audience: An experienced Python developer with 10 years of IT experience who is new to security.
        Constraints:
        - Keep it doable in 5-10 minutes.
        - Include code snippets (Python/Bash) where relevant.
        - Explain *why* this matters for security.
        - If tools are required, briefly list how to install/access them.
        """

        try:
            response = model.generate_content(prompt)
            
            with open(filename, "w", encoding="utf-8") as f:
                f.write(response.text)
                
            # Sleep to avoid Rate Limiting (RPM limits on free tier)
            # Adjust this based on your API quota. 4 seconds is usually safe for free tier.
            time.sleep(4) 
            
        except Exception as e:
            print(f"Error generating step {step_number}: {e}")
            # Wait a bit longer if we hit an error (likely rate limit)
            time.sleep(20)

    print("All tutorials generated!")

if __name__ == "__main__":
    generate_tutorials()
