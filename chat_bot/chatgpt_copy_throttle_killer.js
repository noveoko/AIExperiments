// === BEST WORKING VERSION - ChatGPT Last Response Copy (2026) ===
(function() {
    console.log("🔍 Searching for the last assistant response...");

    // More robust selectors for current ChatGPT
    const selectors = [
        '[data-message-author-role="assistant"]',
        'article[data-role="assistant"]',
        '.prose', 
        '.markdown',
        'div[data-testid="conversation-turn"] .whitespace-pre-wrap', // common text container
        'div.relative > div > div > div' // fallback broad
    ];

    let lastMessage = null;

    for (const sel of selectors) {
        const found = document.querySelectorAll(sel);
        if (found.length > 0) {
            lastMessage = found[found.length - 1];
            console.log(`✅ Found using selector: ${sel}`);
            break;
        }
    }

    if (!lastMessage) {
        console.log("❌ Could not find any assistant message");
        return;
    }

    // Extract clean text
    let textToCopy = lastMessage.innerText || lastMessage.textContent || '';

    // Better cleaning
    textToCopy = textToCopy
        .replace(/\u200B/g, '') // zero-width spaces
        .trim();

    if (textToCopy.length < 10) {
        console.log("❌ Extracted text too short");
        return;
    }

    // === Reliable clipboard method (textarea + execCommand) ===
    function copyToClipboard(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.style.position = 'fixed';
        textarea.style.left = '-999999px';
        textarea.style.top = '-999999px';
        document.body.appendChild(textarea);
        
        textarea.focus();
        textarea.select();
        
        let success = false;
        try {
            success = document.execCommand('copy');
        } catch (err) {
            console.error("execCommand failed", err);
        }
        
        document.body.removeChild(textarea);
        return success;
    }

    const copied = copyToClipboard(textToCopy);

    if (copied) {
        console.log("✅ SUCCESS! Last response copied to clipboard.");
        
        // Visual feedback
        lastMessage.style.transition = 'background-color 0.4s';
        lastMessage.style.backgroundColor = '#052e16';
        setTimeout(() => lastMessage.style.backgroundColor = '', 800);
    } else {
        console.log("⚠️ Copy failed. Text is printed below:");
        console.log("%c" + "═".repeat(80), "color: #22c55e");
        console.log(textToCopy);
        console.log("%c" + "═".repeat(80), "color: #22c55e");
        alert("Copy failed.\n\nThe full text has been printed in the Console (F12). You can copy it from there.");
    }
})();
