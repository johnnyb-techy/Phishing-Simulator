# Phishing-Simulator

AI-Powered Cyber Phishing Simulator + Training Portal.

A Flask web app for running simulated phishing-awareness campaigns inside an organisation. Admins can manage employees/departments, generate safe, realistic phishing scenarios with Google's Gemini AI, group scenarios into campaigns, and let employees practice spotting phishing emails in a sandbox environment, with scores captured based on response accuracy.

## Contributors

- Johnny Baillie
- Joe Thompson
- Joel G
- Beth Fisher

## Features

- **Authentication** — username/password login followed by a TOTP one-time-passcode step (`pyotp`).
- **Dashboard** — live stats: total users, campaigns, scenarios, responses, and phishing-detection success/failure rates.
- **User management** — add employees and assign them to a department and role (`admin` / `learner`).
- **Departments** — organise users by department (e.g. Finance, Engineering, HR).
- **Scenario builder** — create phishing scenarios manually, or generate one with AI (Gemini `gemini-2.5-flash`) from a scenario type prompt. Generated emails are stored and reused as training content.
- **Campaigns** — group scenarios into a training campaign with a start/end date and status.
- **Train mode** — a simulated inbox where a random scenario is shown and the user decides "Phishing" or "Safe". The app records the response and gives immediate feedback.

### Ethical AI guardrails

Scenario generation is deliberately constrained via the prompt sent to Gemini:

- No real malicious URLs/IPs — a literal `[SIMULATED_LINK_HERE]` placeholder is used instead.
- No malware payloads, scripts, or weaponized attachments.
- No real company names — generic placeholders like "Acme Corp" are used.
- Emails are capped at ~300 words.

This is intended purely for internal security-awareness training, not for crafting real phishing attacks.

## Tech stack

- **Backend:** Python, Flask
- **Database:** SQLite (`portal.db`, created automatically on first run)
- **AI:** Google Gemini via the `google-genai` SDK
- **Auth:** `pyotp` for TOTP-based two-factor login
- **Templating:** Jinja2 / Flask templates

## Prerequisites

- Python 3.10+
- A [Google Gemini API key](https://aistudio.google.com/apikey) (only needed for AI-generated scenarios — the rest of the app works without it)

## Setup

1. **Clone the repo and enter the directory**

   ```bash
   git clone https://github.com/johnnyb-techy/Phishing-Simulator
   cd Phishing-Simulator
   ```

2. **Create and activate a virtual environment**

   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**

   Create a `.env` file in the project root:

   ```bash
   GEMINI_API_KEY=your-gemini-api-key-here
   ```

   If this is omitted, the app still runs — the AI scenario generator just won't be able to call Gemini.

5. **Run the app**

   ```bash
   python app.py
   ```

   The database (`portal.db`) and seed data (sample departments, users, scenarios, and a campaign) are created automatically on first run.

6. **Open the app**

   Go to [http://127.0.0.1:5000](http://127.0.0.1:5000)

## Logging in

The app runs in `DEV_MODE = True` by default (see `app.py`), which enables a couple of shortcuts for local testing:

- **Username:** `joe`
- **Password:** `password123`
- **OTP:** the real TOTP code is printed to the terminal on startup and on each `/otp` page load, but in dev mode you can also just enter `000000`.

> Set `DEV_MODE = False` before using this anywhere beyond local development!

## Project structure

```
app.py               Flask app: routes, DB schema/seed data, AI integration
requirements.txt     Python dependencies
templates/           Jinja2 templates (dashboard, users, scenarios, campaigns, train, etc.)
portal.db            SQLite database (created at runtime, git-ignored)
```

## Notes

- `portal.db` and `.env` are git-ignored — each environment builds/configures its own.
- The app is currently being developed based off the Minimal Viable Product The Flask `secret_key` and mock auth store (`users_auth`) in `app.py` are hardcoded for demo purposes and should be replaced with proper secrets management and a real user store before any production use.
