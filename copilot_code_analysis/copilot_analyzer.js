#!/usr/bin/env node
/**
 * copilot_analyzer.js
 *
 * Browser automation wrapper for Microsoft 365 Copilot.
 *
 * The source file is uploaded as a FILE ATTACHMENT through Copilot's
 * paperclip UI — the code is never pasted into the chat textarea.
 * This sidesteps the ~16,000-character UI input limit entirely.
 *
 * Usage:
 *   node copilot_analyzer.js /absolute/path/to/myfile.py
 *
 * Exit codes:
 *   0 – success
 *   1 – general error
 *   2 – authentication failure (session expired)
 *   3 – file upload failed / attachment not accepted
 */

const { chromium } = require("playwright-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
const fs = require("fs");
const path = require("path");

// ── Stealth mode to reduce bot-detection risk ─────────────────────────────────
chromium.use(StealthPlugin());

// ── Constants ─────────────────────────────────────────────────────────────────
const STATE_FILE = path.join(__dirname, "state.json");
const COPILOT_URL = "https://copilot.microsoft.com";
const EXIT_AUTH_FAILURE = 2;
const EXIT_UPLOAD_FAILED = 3;

// The text prompt is intentionally tiny — the code lives in the attachment.
const ANALYSIS_PROMPT =
  "You are a senior Python engineer performing a code review of the attached file. " +
  "Return EXACTLY 5 to 10 concrete, actionable improvement suggestions as a plain " +
  "numbered list (1. through 10. maximum). Each item must be one self-contained " +
  "improvement on a single line. Cover: code quality, performance, security, " +
  "readability, Python best practices, error handling, and potential bugs. " +
  "Do NOT add any preamble or closing summary outside the numbered list.";

// ── Logging helpers (stderr only — stdout is reserved for JSON output) ────────
const log  = (msg) => process.stderr.write(`[INFO]  ${msg}\n`);
const warn = (msg) => process.stderr.write(`[WARN]  ${msg}\n`);
const err  = (msg) => process.stderr.write(`[ERROR] ${msg}\n`);

// ── Parse the numbered list out of Copilot's free-text response ──────────────
function parseImprovements(rawText) {
  const improvements = [];
  for (const line of rawText.split("\n")) {
    // Match "1. ...", "2) ...", "  3. ..." etc.
    const m = line.match(/^\s*(\d+)[.)]\s+(.+)/);
    if (m) {
      const text = m[2].trim();
      if (text.length > 5) improvements.push(text);
    }
  }
  return improvements.slice(0, 10);
}

// ── Main Playwright automation ────────────────────────────────────────────────
async function runCopilot(filepath) {
  const filename = path.basename(filepath);

  if (!fs.existsSync(STATE_FILE)) {
    err("state.json not found. Run  node setup_session.js  first to capture your login.");
    process.exit(EXIT_AUTH_FAILURE);
  }
  if (!fs.existsSync(filepath)) {
    err(`Source file not found: ${filepath}`);
    process.exit(1);
  }

  log("Launching headless browser with saved session state…");
  const browser = await chromium.launch({
    headless: true,
    args: [
      "--disable-blink-features=AutomationControlled",
      "--no-sandbox",
    ],
  });

  const context = await browser.newContext({
    storageState: STATE_FILE,
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    locale: "en-US",
    timezoneId: "America/New_York",
    // Grant clipboard read permission so the browser doesn't block anything
    permissions: ["clipboard-read", "clipboard-write"],
  });

  const page = await context.newPage();

  // ── Phase 1: Page Load ────────────────────────────────────────────────────
  log("Navigating to Copilot…");
  try {
    await page.goto(COPILOT_URL, { waitUntil: "networkidle", timeout: 45_000 });
  } catch (e) {
    warn(`Navigation timeout (continuing anyway): ${e.message}`);
  }

  // ── Auth check ────────────────────────────────────────────────────────────
  const inputLocator = page
    .locator(
      "textarea#userInput, " +
      "[role='textbox'][aria-label*='message' i], " +
      "cib-text-input textarea"
    )
    .first();

  const isAuthenticated = await inputLocator
    .isVisible({ timeout: 12_000 })
    .catch(() => false);

  if (!isAuthenticated) {
    err("Chat input not found — session has likely expired.");
    err("Run  node setup_session.js  to refresh state.json.");
    await browser.close();
    process.exit(EXIT_AUTH_FAILURE);
  }
  log("Authentication confirmed.");

  // ── Phase 2a: File Upload ─────────────────────────────────────────────────
  // Strategy: Copilot renders a hidden <input type="file"> that is wired to
  // the attachment button. We call setInputFiles() on it directly — this is
  // equivalent to the user clicking the paperclip and selecting the file via
  // the OS file dialog, but without any dialog interaction.
  //
  // Why not paste the code into the textarea?
  //   Copilot's web UI enforces a ~16,000 character hard cap on typed/pasted
  //   input. Uploading as a file bypasses this limit entirely and is also how
  //   a real user would submit a large file for review.

  log(`Uploading file as attachment: ${filename}`);

  // First try: hidden file input wired to the attachment button
  const fileInput = page.locator("input[type='file']").first();
  const fileInputExists = await fileInput.count().then((n) => n > 0).catch(() => false);

  if (fileInputExists) {
    log("Found hidden file input — setting file directly.");
    await fileInput.setInputFiles(filepath);
  } else {
    // Second try: click the attachment / paperclip button to reveal the input,
    // then intercept the resulting file chooser dialog via Playwright's
    // filechooser event, which avoids the OS dialog entirely.
    log("Hidden file input not found — triggering via attachment button + filechooser.");
    const attachBtn = page
      .getByRole("button", { name: /attach|upload|add file|paperclip/i })
      .or(page.locator("[aria-label*='attach' i], [aria-label*='upload' i], [data-testid*='attach' i]"))
      .first();

    const attachVisible = await attachBtn.isVisible({ timeout: 5_000 }).catch(() => false);
    if (!attachVisible) {
      err("Could not locate an attachment button or file input in the Copilot UI.");
      err("The UI may have changed. Check selectors in copilot_analyzer.js Phase 2a.");
      await browser.close();
      process.exit(EXIT_UPLOAD_FAILED);
    }

    // Playwright's fileChooser event fires synchronously when the button opens
    // a file dialog — we intercept it before the OS dialog appears.
    const [fileChooser] = await Promise.all([
      page.waitForEvent("filechooser", { timeout: 10_000 }),
      attachBtn.click(),
    ]);
    await fileChooser.setFiles(filepath);
  }

  // ── Phase 2b: Confirm attachment rendered ─────────────────────────────────
  // After setInputFiles / fileChooser.setFiles, Copilot should show a small
  // attachment chip or thumbnail in the composer area.
  log("Waiting for attachment chip to appear in the composer…");
  const attachmentConfirmed = await page
    .locator(
      // Common patterns for Copilot's file chip; broaden if UI changes
      "[class*='attachment'], [class*='fileChip'], [aria-label*='" + filename + "'], " +
      "[data-testid*='attachment'], [class*='upload']"
    )
    .first()
    .isVisible({ timeout: 15_000 })
    .catch(() => false);

  if (!attachmentConfirmed) {
    warn(
      "Attachment chip not detected. The file may still have been accepted — " +
      "proceeding, but verify selectors if results look wrong."
    );
  } else {
    log("Attachment confirmed in UI.");
  }

  // ── Phase 2c: Type the (short) analysis prompt into the textarea ──────────
  // ANALYSIS_PROMPT is ~350 characters — well within any text input limit.
  // The actual code is in the uploaded file, not in this text.
  log("Typing analysis prompt into chat textarea…");
  await inputLocator.click();
  await inputLocator.fill(ANALYSIS_PROMPT);

  // ── Phase 3: Submission ───────────────────────────────────────────────────
  log("Submitting…");
  const submitBtn = page
    .getByRole("button", { name: /^send$/i })
    .or(page.locator("button[data-testid='submit-button']"))
    .or(page.locator("button[aria-label*='Send' i]"))
    .first();

  const submitVisible = await submitBtn.isVisible({ timeout: 5_000 }).catch(() => false);
  if (submitVisible) {
    await submitBtn.click();
  } else {
    warn("Submit button not found — pressing Ctrl+Enter as fallback.");
    await inputLocator.press("Control+Enter");
  }

  // ── Phase 4: Await Generation ─────────────────────────────────────────────
  log("Waiting for Copilot to finish generating…");

  const stopBtn = page.getByRole("button", { name: /stop responding|stop generating/i });
  await stopBtn
    .waitFor({ state: "visible", timeout: 20_000 })
    .catch(() => warn("'Stop' button never appeared — response may have been instant."));

  await stopBtn
    .waitFor({ state: "hidden", timeout: 180_000 })
    .catch(() => warn("Timed out waiting for generation — extracting partial response."));

  // Let the DOM settle after streaming ends
  await page.waitForTimeout(2_000);

  // ── Phase 5: Extraction ───────────────────────────────────────────────────
  log("Extracting response from DOM…");
  let rawText = "";

  const candidateSelectors = [
    ".ac-textBlock",
    "cib-message-group[source='bot'] cib-message .content",
    "[data-testid='message-content']",
    "[class*='responseText']",
    "[class*='chatMessage'][class*='assistant']",
  ];

  for (const sel of candidateSelectors) {
    const els = page.locator(sel);
    const count = await els.count().catch(() => 0);
    if (count > 0) {
      rawText = (await els.last().innerText().catch(() => "")).trim();
      if (rawText.length > 20) {
        log(`Extracted via selector: ${sel}`);
        break;
      }
    }
  }

  if (!rawText) {
    warn("Named selectors failed — using in-page evaluation fallback.");
    rawText = await page.evaluate(() => {
      const candidates = [
        ...document.querySelectorAll('[class*="message"], [class*="response"], [class*="bubble"]'),
      ];
      const last = [...candidates].reverse().find((el) => {
        const cls = el.className || "";
        return !cls.includes("user") && el.innerText.length > 20;
      });
      return last ? last.innerText : "";
    });
  }

  await browser.close();

  if (!rawText) {
    throw new Error("Could not extract any response text from the page.");
  }

  return rawText;
}

// ── Entry point ───────────────────────────────────────────────────────────────
async function main() {
  const filepath = process.argv[2];
  if (!filepath) {
    err("Usage: node copilot_analyzer.js /path/to/file.py");
    process.exit(1);
  }

  const filename = path.basename(filepath);
  log(`Analyzer started for: ${filename}`);
  log(`Upload strategy: file attachment (no text pasting — bypasses UI char limit)`);

  const rawResponse = await runCopilot(filepath);
  const improvements = parseImprovements(rawResponse);

  const output = {
    file: filepath,
    filename,
    improvements,
    improvement_count: improvements.length,
    raw_response: rawResponse,
    timestamp: new Date().toISOString(),
  };

  process.stdout.write(JSON.stringify(output, null, 2) + "\n");
  log(`Done. ${improvements.length} improvement(s) extracted.`);
}

main().catch((e) => {
  err(`Unhandled error: ${e.message}`);
  if (process.env.DEBUG) process.stderr.write(e.stack + "\n");
  process.exit(1);
});
