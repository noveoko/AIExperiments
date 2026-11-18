Rules understood. I'll teach one concept at a time, give you a challenge each time, and never hand you solutions. When you're stuck, I'll ask guiding questions instead. We only move on once you've solved the challenge and explained it back in your own words.

**First, one question:** How would you rate your current experience with Azure/Microsoft Entra ID, REST APIs, and Databricks? (Even "zero on Azure, comfortable with Python `requests`" is useful.)

---

## Concept 1: Your code needs an identity

**Why it matters:** SharePoint won't answer anonymous requests. When a Databricks notebook calls Microsoft's API, nobody is sitting there to type a password, so Microsoft needs to know which *application* is asking and whether it's allowed. Every later step (tokens, permissions, API calls) depends on this identity existing first.

In Microsoft's world, that identity is called an **app registration** in **Microsoft Entra ID** (formerly Azure AD).

### Your challenge

1. In the Azure portal, find **Microsoft Entra ID → App registrations** and create a new registration for a hypothetical "databricks-sharepoint-reader" app. Skip the redirect URI.
2. Explore the **Overview** page and the **Certificates & secrets** page. Don't paste any actual secret values into this chat.
3. Report back with:
   - The names of the identifiers and credentials you found
   - Which ones you think are **secret** and which are **safe to share**, with your reasoning for each
   - Your best guess at what each one will be *used for* when your Python code eventually talks to Microsoft

**If you hit a wall** (for example, you can't register apps), tell me the exact error or what you see. That's useful information, and I'll ask you questions to help you work out why.

Go ahead and answer the experience question and attempt the challenge. I'm watching for your reasoning, not just your findings.