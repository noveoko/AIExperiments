# Spec: `optout-bot` — Local Data Broker Removal CLI

## Overview

A locally-running Python CLI tool that automates opt-out requests to people-search/data broker sites on a schedule, with proxy rotation to avoid blocks — no subscription fees.

---

## Goals

- Automate opt-out submissions to 115+ data brokers
- Run on a cron schedule (monthly re-checks)
- Rotate proxies to avoid rate limiting / IP bans
- Track removal status with progress bars and persistent state
- Zero cloud dependency — all data stays local

---

## Directory Structure

```
optout-bot/
├── main.py                  # CLI entrypoint
├── config.yaml              # User personal data + settings
├── brokers/
│   ├── __init__.py
│   ├── base.py              # Abstract broker class
│   ├── whitepages.py        # Per-broker implementations
│   ├── spokeo.py
│   └── ...                  # One file per broker
├── core/
│   ├── scheduler.py         # Cron job manager
│   ├── proxy_manager.py     # Proxy rotation logic
│   ├── state_manager.py     # Persistent JSON state
│   └── mailer.py            # Email confirmation handler (IMAP)
├── state/
│   └── submissions.json     # Run history and status per broker
├── logs/
│   └── optout.log
├── requirements.txt
└── README.md
```

---

## config.yaml (User Input)

```yaml
personal_data:
  first_name: "Jane"
  last_name: "Doe"
  aliases: ["J. Doe"]
  dob: "1990-01-15"
  emails:
    - "jane@example.com"
  phone_numbers:
    - "555-123-4567"
  addresses:
    - street: "123 Main St"
      city: "Austin"
      state: "TX"
      zip: "78701"

settings:
  recheck_interval_days: 30
  request_delay_seconds: [3, 8]   # Random range to appear human
  proxy_list_path: "./proxies.txt" # Optional
  use_tor: false
  confirmation_email_imap:
    host: "imap.gmail.com"
    user: "jane@example.com"
    password: "app-password"
```

---

## Core Components

### 1. `BrokerBase` (Abstract Class)

Every broker inherits from this. Enforces a consistent interface:

```python
from abc import ABC, abstractmethod

class BrokerBase(ABC):
    name: str
    opt_out_url: str
    method: str  # "form", "email", "api"
    requires_email_confirm: bool

    @abstractmethod
    def search(self, profile: dict) -> list[dict]:
        """Search for matching records. Returns list of found profiles."""
        pass

    @abstractmethod
    def submit_removal(self, record: dict, session) -> SubmissionResult:
        """Submit opt-out for a specific record."""
        pass

    def verify_removal(self, record: dict, session) -> bool:
        """Optional: re-check if record is gone."""
        return False
```

`SubmissionResult` is a dataclass:

```python
@dataclass
class SubmissionResult:
    broker: str
    status: str        # "submitted" | "confirmed" | "failed" | "not_found"
    record_url: str
    timestamp: str
    notes: str = ""
```

---

### 2. `ProxyManager`

```python
# Loads from proxies.txt or fetches free proxies
# Rotates per-request with health checking
# Falls back to direct connection if all proxies fail

class ProxyManager:
    def get_session(self) -> requests.Session
    def rotate(self)
    def mark_dead(self, proxy: str)
    def health_check(self)
```

Proxy sources (in priority order):
1. User-supplied `proxies.txt` (HTTP/SOCKS5)
2. Tor SOCKS5 (`127.0.0.1:9050`) if `use_tor: true`
3. Free proxy scraping fallback (with quality filter)

---

### 3. `StateManager`

Persists all submission history to `state/submissions.json`:

```json
{
  "whitepages": {
    "last_checked": "2026-04-01T10:00:00",
    "status": "confirmed",
    "next_check": "2026-05-01T10:00:00",
    "record_url": "https://whitepages.com/..."
  },
  "spokeo": {
    "last_checked": "2026-04-01T10:05:00",
    "status": "submitted",
    "next_check": "2026-05-01T10:05:00"
  }
}
```

Methods: `get(broker)`, `update(broker, result)`, `due_for_recheck(broker) -> bool`

---

### 4. CLI (`main.py` via `click` or `argparse`)

```bash
# First-time full run
python main.py run --all

# Run only brokers due for recheck
python main.py run --due

# Show status dashboard
python main.py status

# Run a single broker
python main.py run --broker whitepages

# Install cron job
python main.py schedule --interval 30d

# Check email confirmations
python main.py check-confirmations
```

---

### 5. Scheduler

The `schedule` command writes a system crontab entry:

```
0 9 */30 * * /usr/bin/python3 /path/to/optout-bot/main.py run --due >> /path/to/logs/optout.log 2>&1
```

On Windows, uses Task Scheduler via `schtasks` subprocess call instead.

---

### 6. Progress Display (`tqdm`)

```python
from tqdm import tqdm

brokers_to_run = [b for b in all_brokers if state.due_for_recheck(b)]

for broker in tqdm(brokers_to_run, desc="Processing brokers", unit="broker"):
    tqdm.write(f"  → {broker.name}: searching...")
    records = broker.search(profile, session=proxy.get_session())
    
    for record in tqdm(records, desc=f"  {broker.name} records", leave=False):
        result = broker.submit_removal(record, session=proxy.get_session())
        state.update(broker.name, result)
        tqdm.write(f"    ✓ {result.status}")
```

---

## Broker Implementation Strategy

Brokers fall into three categories, requiring different automation approaches:

| Type | Examples | Approach |
|---|---|---|
| **Web form** | Whitepages, Spokeo, BeenVerified | `requests` + `BeautifulSoup` or `playwright` for JS-heavy sites |
| **Email request** | Some smaller brokers | SMTP send to `optout@broker.com` with templated body |
| **API/link** | Intelius, PeopleFinder | Direct GET/POST to documented removal endpoint |

For JS-heavy sites (most of the big ones), use `playwright` in headless mode with stealth plugin (`playwright-stealth`) to avoid bot detection.

---

## Status Dashboard Output

```
python main.py status

┌─────────────────────┬─────────────┬──────────────┬───────────────┐
│ Broker              │ Status      │ Last Checked │ Next Check    │
├─────────────────────┼─────────────┼──────────────┼───────────────┤
│ whitepages          │ ✅ confirmed │ 2026-04-01   │ 2026-05-01    │
│ spokeo              │ ⏳ submitted │ 2026-04-01   │ 2026-05-01    │
│ radaris             │ ❌ failed    │ 2026-04-01   │ 2026-04-08    │
│ intelius            │ 🔲 pending  │ never        │ now           │
└─────────────────────┴─────────────┴──────────────┴───────────────┘
Total: 87 confirmed | 12 submitted | 3 failed | 13 pending
```

---

## Requirements

```
requests
playwright
playwright-stealth
beautifulsoup4
tqdm
click
pyyaml
stem          # Tor control (optional)
imaplib2      # Email confirmation checking
rich          # Dashboard table rendering
schedule      # In-process scheduling alternative
```

---

## Key Design Decisions

**Why local over cloud?** Your PII (DOB, addresses, aliases) never leaves your machine. A subscription service holds all of that.

**Why proxy rotation?** Brokers rate-limit by IP. Submitting 115 requests from one IP in sequence is a fast track to a CAPTCHA wall or silent failure.

**Why cron + state file over a daemon?** Simpler, survives reboots, no background process eating RAM. The state JSON is human-readable so you can audit exactly what was submitted and when.

# CAPTCHA Handling — Spec Extension

## CAPTCHA Strategy Overview

Three tiers based on cost, automation level, and broker importance:

```
┌──────────────────────────────────────────────────────────┐
│                  CAPTCHA Decision Tree                   │
│                                                          │
│  Encountered CAPTCHA                                     │
│         │                                                │
│         ▼                                                │
│   broker.captcha_strategy?                               │
│    ├── "solver_api"  → 2captcha / CapSolver API          │
│    ├── "manual"      → Pause, open browser, user solves  │
│    ├── "playwright"  → Stealth evasion (avoid it firing) │
│    └── "skip"        → Log + move on, retry next cycle   │
└──────────────────────────────────────────────────────────┘
```

---

## 1. Config Changes

Add per-broker and global CAPTCHA config to `config.yaml`:

```yaml
captcha:
  default_strategy: "manual"      # fallback for any broker not explicitly set
  solver_api:
    provider: "capsolver"         # "capsolver" | "2captcha" | "anticaptcha"
    api_key: "YOUR_KEY_HERE"
    timeout_seconds: 120
    max_cost_per_session_usd: 0.10  # safety cap — stops if spend exceeds this
  manual:
    browser: "chromium"           # opens a real visible browser window
    timeout_seconds: 300          # give user 5 mins before marking as failed
  playwright_stealth:
    slow_mo_ms: 150               # humanise timing
    human_typing: true            # type char-by-char with random delays
```

Per-broker override in `brokers/registry.yaml`:

```yaml
- name: whitepages
  captcha_strategy: solver_api    # high value, worth spending a fraction of a cent
  
- name: spokeo
  captcha_strategy: playwright    # stealth usually avoids it firing at all

- name: radaris
  captcha_strategy: manual        # JS fingerprinting too aggressive for stealth

- name: some_small_broker
  captcha_strategy: skip          # not worth effort
```

---

## 2. New Component: `CaptchaSolver`

Add `core/captcha_solver.py`:

```python
from dataclasses import dataclass
from enum import Enum
import time, base64, httpx
from playwright.sync_api import Page

class CaptchaType(Enum):
    RECAPTCHA_V2   = "recaptcha_v2"    # classic checkbox / image grid
    RECAPTCHA_V3   = "recaptcha_v3"    # invisible score-based
    HCAPTCHA       = "hcaptcha"        # common on Cloudflare-protected sites
    IMAGE_PUZZLE   = "image_puzzle"    # "click all traffic lights" style
    TEXT_IMAGE     = "text_image"      # distorted text in an image

@dataclass
class CaptchaChallenge:
    type: CaptchaType
    site_key: str | None     # for reCAPTCHA / hCaptcha
    page_url: str
    image_b64: str | None    # for image-based CAPTCHAs


class CaptchaSolver:
    def __init__(self, config: dict):
        self.config = config
        self.spend_usd = 0.0

    # ── Detection ──────────────────────────────────────────
    def detect(self, page: Page) -> CaptchaChallenge | None:
        """
        Inspect the live Playwright page and return a
        CaptchaChallenge if one is present, else None.
        """
        if page.query_selector("iframe[src*='recaptcha']"):
            site_key = self._extract_site_key(page, "recaptcha")
            return CaptchaChallenge(CaptchaType.RECAPTCHA_V2, site_key, page.url, None)

        if page.query_selector("iframe[src*='hcaptcha']"):
            site_key = self._extract_site_key(page, "hcaptcha")
            return CaptchaChallenge(CaptchaType.HCAPTCHA, site_key, page.url, None)

        if page.query_selector(".captcha-image, img[id*='captcha']"):
            img_el = page.query_selector(".captcha-image")
            img_b64 = self._screenshot_element_b64(page, img_el)
            return CaptchaChallenge(CaptchaType.TEXT_IMAGE, None, page.url, img_b64)

        return None  # No CAPTCHA found

    # ── Strategy dispatcher ────────────────────────────────
    def solve(self, challenge: CaptchaChallenge, strategy: str, page: Page) -> str | None:
        """
        Returns the token/answer string, or None on failure.
        Callers inject the token into the page form.
        """
        match strategy:
            case "solver_api":  return self._solve_via_api(challenge)
            case "manual":      return self._solve_manually(challenge, page)
            case "playwright":  return self._solve_via_stealth(challenge, page)
            case "skip":        return None
            case _:             raise ValueError(f"Unknown strategy: {strategy}")

    # ── Solver API (CapSolver / 2captcha) ──────────────────
    def _solve_via_api(self, challenge: CaptchaChallenge) -> str | None:
        cap = self.config["solver_api"]

        # Safety spend cap
        if self.spend_usd >= cap["max_cost_per_session_usd"]:
            raise RuntimeError("CAPTCHA spend cap reached. Stopping.")

        provider = cap["provider"]
        api_key   = cap["api_key"]

        if provider == "capsolver":
            return self._capsolver(challenge, api_key, cap["timeout_seconds"])
        elif provider == "2captcha":
            return self._twocaptcha(challenge, api_key, cap["timeout_seconds"])

    def _capsolver(self, challenge: CaptchaChallenge, api_key: str, timeout: int) -> str | None:
        """
        CapSolver API flow:
          1. POST createTask  → get taskId
          2. Poll getTaskResult every 3s until ready or timeout
          3. Return the solution token
        """
        base = "https://api.capsolver.com"

        # Build task payload based on CAPTCHA type
        if challenge.type == CaptchaType.RECAPTCHA_V2:
            task = {
                "type": "ReCaptchaV2TaskProxyLess",
                "websiteURL": challenge.page_url,
                "websiteKey": challenge.site_key,
            }
            cost_per_solve = 0.0008  # ~$0.80 per 1000

        elif challenge.type == CaptchaType.HCAPTCHA:
            task = {
                "type": "HCaptchaTaskProxyLess",
                "websiteURL": challenge.page_url,
                "websiteKey": challenge.site_key,
            }
            cost_per_solve = 0.0008

        elif challenge.type == CaptchaType.TEXT_IMAGE:
            task = {
                "type": "ImageToTextTask",
                "body": challenge.image_b64,
            }
            cost_per_solve = 0.0002  # very cheap

        # Step 1: Create task
        resp = httpx.post(f"{base}/createTask", json={
            "clientKey": api_key,
            "task": task
        }).json()

        if resp.get("errorId") != 0:
            return None

        task_id = resp["taskId"]
        self.spend_usd += cost_per_solve

        # Step 2: Poll for result
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(3)
            result = httpx.post(f"{base}/getTaskResult", json={
                "clientKey": api_key,
                "taskId": task_id
            }).json()

            if result.get("status") == "ready":
                solution = result["solution"]
                # reCAPTCHA/hCaptcha return gRecaptchaResponse token
                # ImageToText returns "text"
                return solution.get("gRecaptchaResponse") or solution.get("text")

        return None  # Timed out

    # ── Manual solve ───────────────────────────────────────
    def _solve_manually(self, challenge: CaptchaChallenge, page: Page) -> str | None:
        """
        Re-launches the page in a VISIBLE (non-headless) browser window,
        pauses execution, and waits for the user to solve it.
        The solved token is then extracted from the page's DOM.
        """
        from tqdm import tqdm
        import sys

        tqdm.write(f"\n⚠️  MANUAL CAPTCHA REQUIRED: {challenge.page_url}")
        tqdm.write("   A browser window has opened. Please solve the CAPTCHA.")
        tqdm.write("   Press ENTER here once you've completed it.")

        # Note: caller must have launched page in headed mode for manual strategy
        input()  # Block until user confirms

        # Extract token after user solves it
        token = page.evaluate("""
            () => {
                const el = document.getElementById('g-recaptcha-response')
                        || document.querySelector('[name=h-captcha-response]');
                return el ? el.value : null;
            }
        """)
        return token

    # ── Playwright stealth (avoidance) ────────────────────
    def _solve_via_stealth(self, challenge: CaptchaChallenge, page: Page) -> str | None:
        """
        Not a solver — this strategy means we tried stealth and still
        hit a CAPTCHA. Log it and return None so the caller can retry
        with a different proxy/user-agent before escalating.
        """
        return None  # signal: retry with new proxy

    # ── Helpers ────────────────────────────────────────────
    def _extract_site_key(self, page: Page, provider: str) -> str | None:
        attr = "data-sitekey"
        el = page.query_selector(f"[{attr}]")
        return el.get_attribute(attr) if el else None

    def _screenshot_element_b64(self, page: Page, element) -> str:
        png_bytes = element.screenshot()
        return base64.b64encode(png_bytes).decode()
```

---

## 3. Token Injection

After getting a token back from the solver, inject it into the page before submitting:

```python
def inject_captcha_token(page: Page, token: str, captcha_type: CaptchaType):
    """
    Browsers hide the reCAPTCHA/hCaptcha response in a
    hidden textarea. We write directly to it, then trigger
    the callback so the form thinks the human solved it.
    """
    if captcha_type in (CaptchaType.RECAPTCHA_V2, CaptchaType.RECAPTCHA_V3):
        page.evaluate(f"""
            document.getElementById('g-recaptcha-response').value = '{token}';
            if (typeof ___grecaptcha_cfg !== 'undefined') {{
                Object.entries(___grecaptcha_cfg.clients).forEach(([id, client]) => {{
                    const callback = client?.U?.l?.callback
                                  || client?.aa?.l?.callback;
                    if (callback) callback('{token}');
                }});
            }}
        """)

    elif captcha_type == CaptchaType.HCAPTCHA:
        page.evaluate(f"""
            document.querySelector('[name=h-captcha-response]').value = '{token}';
            document.querySelector('[name=g-recaptcha-response]').value = '{token}';
            if (window.hcaptcha) hcaptcha.execute();
        """)

    elif captcha_type == CaptchaType.TEXT_IMAGE:
        # Plain text answer goes into a visible input field
        input_el = page.query_selector("input[name*='captcha'], input[id*='captcha']")
        if input_el:
            input_el.fill(token)
```

---

## 4. Integration into Broker Base Class

Update `base.py` to wire CAPTCHA handling into the submission flow:

```python
class BrokerBase(ABC):

    def run(self, profile: dict, session, solver: CaptchaSolver) -> SubmissionResult:
        """
        Standard execution flow every broker goes through.
        Handles CAPTCHA detection/solving transparently.
        """
        strategy = self.captcha_strategy  # set per-broker in registry.yaml

        with get_playwright_page(headless=(strategy != "manual")) as page:
            page.goto(self.opt_out_url)

            # Stealth headers / timing applied here
            apply_stealth(page, self.config)

            # Fill the opt-out form (broker-specific)
            self.fill_form(page, profile)

            # Check for CAPTCHA before submitting
            challenge = solver.detect(page)
            if challenge:
                token = solver.solve(challenge, strategy, page)

                if token is None and strategy == "playwright":
                    # Stealth failed — rotate proxy and retry once
                    page.close()
                    return self.run(profile, rotate_proxy(session), solver)

                if token is None:
                    return SubmissionResult(self.name, "failed", page.url,
                                           now(), notes="CAPTCHA unsolved")

                inject_captcha_token(page, token, challenge.type)

            # Submit and check result
            page.click(self.submit_selector)
            return self.parse_result(page)
```

---

## 5. Updated Status Dashboard

The status output gains a CAPTCHA column:

```
┌──────────────────┬─────────────┬──────────────┬──────────────┬────────────────┐
│ Broker           │ Status      │ Last Checked │ CAPTCHA      │ Solve Cost     │
├──────────────────┼─────────────┼──────────────┼──────────────┼────────────────┤
│ whitepages       │ ✅ confirmed │ 2026-04-01   │ reCAPTCHA v2 │ $0.0008        │
│ spokeo           │ ✅ confirmed │ 2026-04-01   │ stealth bypass│ $0.00         │
│ radaris          │ ⏳ pending   │ —            │ manual req.  │ —              │
│ beenverified     │ ❌ failed    │ 2026-04-01   │ unsolved     │ $0.00          │
└──────────────────┴─────────────┴──────────────┴──────────────┴────────────────┘
Session CAPTCHA spend: $0.0024  |  Cap: $0.10
```

---

## 6. Retry & Escalation Logic

```
First attempt
    └── playwright stealth (free, avoids CAPTCHA firing)
            │
            ├── Success → done ✓
            │
            └── CAPTCHA detected
                    │
                    ├── rotate proxy → retry stealth (once)
                    │       │
                    │       ├── Success → done ✓
                    │       │
                    │       └── Still blocked
                    │               │
                    │               ├── solver_api configured? → solve + inject
                    │               │
                    │               └── no API key → manual pause
                    │                       │
                    │                       └── user timeout → skip + log
                    │                               │
                    │                               └── retry next cron cycle
```

---

## Approximate CAPTCHA Solving Costs

| Provider | reCAPTCHA v2 | hCaptcha | Image/Text |
|---|---|---|---|
| CapSolver | $0.80/1000 | $0.80/1000 | $0.20/1000 |
| 2captcha | $0.99/1000 | $1.00/1000 | $0.70/1000 |
| **115 brokers (all CAPTCHA)** | **~$0.09** | **~$0.09** | **~$0.02** |

A full monthly run across all 115 brokers, even assuming every single one throws a CAPTCHA, costs under **$0.10** — vs $10/month for RemoveMe.
