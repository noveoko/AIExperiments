#!/usr/bin/env node
/**
 * setup_session.js
 *
 * ONE-TIME setup script — run this manually in headed mode so you can
 * log in to Microsoft 365 Copilot (including MFA) and save the session.
 *
 * Usage:
 *   node setup_session.js
 *
 * What it does:
 *   1. Opens a real (headed) browser window
 *   2. Navigates to copilot.microsoft.com
 *   3. Waits for you to log in manually (including MFA)
 *   4. Detects when you've landed on the chat interface
 *   5. Saves cookies + storage to state.json
 *
 * After this runs successfully, copilot_analyzer.js will use state.json
 * for headless sessions until the token expires (typically 7–30 days
 * depending on your org's Entra ID policy).
 */

const { chromium } = require("playwright");
const path = require("path");
const fs = require("fs");

const STATE_FILE = path.join(__dirname, "state.json");
const COPILOT_URL = "https://copilot.microsoft.com";

// Timeout to wait for the user to complete login (10 minutes)
const LOGIN_TIMEOUT_MS = 10 * 60 * 1000;

async function main() {
  console.log("──────────────────────────────────────────────────────────");
  console.log("  Microsoft Copilot — One-Time Session Setup");
  console.log("──────────────────────────────────────────────────────────");
  console.log("");
  console.log("A browser window will open. Please:");
  console.log("  1. Sign in with your Microsoft 365 account");
  console.log("  2. Complete any MFA prompts");
  console.log("  3. Wait until you can see the Copilot chat interface");
  console.log("");
  console.log(`You have ${LOGIN_TIMEOUT_MS / 60000} minutes to complete login.`);
  console.log("This script will automatically save your session once detected.");
  console.log("");

  // Launch in HEADED mode so the user can interact
  const browser = await chromium.launch({
    headless: false,
    args: ["--start-maximized"],
  });

  const context = await browser.newContext({
    userAgent:
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    viewport: null, // use full window size
  });

  const page = await context.newPage();
  await page.goto(COPILOT_URL, { waitUntil: "domcontentloaded" });

  console.log("[*] Waiting for you to log in…");

  // Poll until the chat textarea appears — that confirms successful login
  const deadline = Date.now() + LOGIN_TIMEOUT_MS;
  let loggedIn = false;

  while (Date.now() < deadline) {
    const visible = await page
      .locator(
        "textarea#userInput, [role='textbox'][aria-label*='message' i], cib-text-input textarea"
      )
      .first()
      .isVisible({ timeout: 5_000 })
      .catch(() => false);

    if (visible) {
      loggedIn = true;
      break;
    }

    process.stdout.write(".");
    await page.waitForTimeout(5_000);
  }

  console.log(""); // newline after dots

  if (!loggedIn) {
    console.error("\n[ERROR] Login timeout — state NOT saved.");
    await browser.close();
    process.exit(1);
  }

  console.log("[✓] Login detected! Saving session state…");

  // Capture the full browser context (cookies + local/session storage)
  const state = await context.storageState();
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2), "utf-8");

  console.log(`[✓] Session saved to: ${STATE_FILE}`);
  console.log("");
  console.log("You can now run the pipeline in headless mode.");
  console.log(
    "Remember: tokens typically expire every 7–30 days. " +
    "Re-run this script when pipeline.py reports an auth failure."
  );

  await browser.close();
}

main().catch((e) => {
  console.error(`[FATAL] ${e.message}`);
  process.exit(1);
});
