---
name: setup
description: When the user wants to configure clims, set API keys, set up Telegram, add allowed users, change the LLM provider, or run initial setup for any credential or integration -- run this skill
---

Walk the user through setting up or updating clims credentials interactively.

All credentials are stored in `.clims/credentials.json` in the current working directory.

The LLM provider and model are stored in `.clims/settings.json`.

---

## WHAT TO COLLECT

Ask for each of the following, one at a time. Show the current value (masked if a key) and let the user press Enter to keep it. Only update values the user provides.

Read the current credentials file first:
- Path: `.clims/credentials.json` (in the directory where `clims` was launched)
- If it doesn't exist, start with an empty dict `{}`

### 1. Telegram Bot Token
- Tell the user: "Go to Telegram → message @BotFather → /newbot to get a token"
- Field: `telegram_bot_token`

### 2. Telegram Allowed Users
- Tell the user: "Message @userinfobot from each Telegram account to get their ID. The FIRST ID in the list is the admin."
- Field: `telegram_allowed_users` (list of integers)
- Parse comma-separated input into a list

### 3. LLM Provider
- Options: deepseek, anthropic, openai, gemini, ollama
- Field: `llm_provider` in credentials.json AND `provider` in settings.json
- Default models per provider:
  - deepseek → deepseek-chat
  - anthropic → claude-sonnet-4-6
  - openai → gpt-4o
  - gemini → gemini-2.5-flash
  - ollama → llama3.2

### 4. LLM Model
- Field: `llm_model` in credentials.json AND `model` in settings.json
- Default based on provider chosen above

### 5. LLM API Key
- Skip if provider is ollama
- Field: `llm_api_key` in credentials.json
- Note: this is NEVER written to settings.json (by design) — only credentials.json

### 6. Google / Gemini API Key (optional)
- Used for image generation (nano-banana / Gemini), vision sidecar, Gemini provider
- Field: `google_api_key`

### 7. Meta Ads Access Token (optional)
- Used by the Meta Ads MCP for autonomous ad campaign management
- Field: `meta_ads_token`

### 8. ComfyUI API URL (optional)
- Used for local AI image generation (Flux, SDXL, etc.) via a local ComfyUI server
- Example: `http://100.84.108.103:8188`
- Field: `comfyui_api_url`
- Also ask for the model checkpoint name (default: `flux1-dev.safetensors`)
- Field: `comfyui_model`

---

## WHAT TO WRITE

After collecting values, write two files:

### `.clims/credentials.json`
```json
{
  "telegram_bot_token": "...",
  "telegram_allowed_users": [123456789],
  "llm_provider": "deepseek",
  "llm_model": "deepseek-chat",
  "llm_api_key": "sk-...",
  "google_api_key": "AIza...",
  "meta_ads_token": "EAA..."
}
```
Only include keys that have values — don't write empty strings for skipped fields.

### `.clims/settings.json`
Merge with any existing content (don't overwrite unrelated settings):
```json
{
  "provider": "deepseek",
  "model": "deepseek-chat"
}
```

---

## AFTER SAVING

Tell the user:
1. ✓ Credentials saved
2. The Telegram bot will start automatically within ~15 seconds (a background watcher detects the new credentials and launches it). No action needed.
3. To check bot status or force-start immediately: type `/bot` or `/bot start` in this chat
4. To see bot logs if something goes wrong: `/bot log`
5. To add more Telegram users later: use `/adduser <id>` in the bot chat (admin only)
6. To update any key later: use `/setkey <service> <value>` in the bot chat, OR run `/setup` again here

---

## SECURITY NOTE

Remind the user that `credentials.json` contains sensitive keys. It should be added to `.gitignore`. Confirm `.gitignore` exists and contains `.clims/credentials.json` or `.clims/*.json` — if not, add it.
