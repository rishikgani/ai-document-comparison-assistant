# AI Document Comparison Assistant

An AI-powered Streamlit workspace for understanding what changed between two
documents.

**Live demo:** [ai-document-comparison-assistant.streamlit.app](https://ai-document-comparison-assistant.streamlit.app)

Compare contracts, policies, proposals, requirements, and everyday documents
with AI-generated summaries, evidence, risks, and a visual side-by-side diff.

## Features

- Upload two PDF, DOCX, or TXT documents
- Extract readable text from supported documents
- Display page and character counts
- Generate a summary for each document
- Identify similarities
- Identify meaningful differences
- View a highlighted side-by-side visual diff
- Classify differences by severity and category
- Review each change side by side with Document A and Document B values
- Filter findings by severity and category
- Compare dates, names, amounts, and requirements
- Display limitations and missing information
- Download a Word comparison report
- Ask evidence-backed questions about both documents
- Sign in with Google or Microsoft
- Save comparison history and manage user profiles

## Technologies

- Python
- Streamlit
- pypdf
- Gemini API
- python-dotenv
- python-docx

## Screenshots

The live workspace includes document upload, AI comparison results, severity
filters, source citations, a visual diff, report download, and document chat.

## Project structure

```text
├── app.py
├── document_reader.py
├── comparison.py
├── report_generator.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
## Installation

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Install the required packages:

```powershell
pip install -r requirements.txt
```

## Environment variable

Create a `.env` file in the project folder:

```env
GEMINI_API_KEY=your_actual_gemini_api_key
```

Never upload `.env` to GitHub.

## Sign-in setup

The app supports both Google and Microsoft sign-in through OpenID Connect.
Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml`, then fill
in the client ID and client secret for each provider you want to enable.

Register this callback URL with both providers during local development:

```text
http://localhost:8501/oauth2callback
```

### Open the app on a phone

The phone and computer must be connected to the same Wi-Fi network. Start the
app, find the computer's local IPv4 address with `ipconfig`, and open this URL
on the phone:

```text
http://<computer-ip>:8501
```

For example, if the computer address is `10.59.93.208`, use
`http://10.59.93.208:8501`. Do not use `localhost` on the phone: it refers to
the phone itself.

If sign-in redirects back to an error, add the phone-access callback URL to
your Google/Microsoft OAuth provider and set the same value in
`.streamlit/secrets.toml`:

```text
http://<computer-ip>:8501/oauth2callback
```

The computer's local IP can change when it reconnects to Wi-Fi, so update the
OAuth callback when that happens. Windows Firewall may also need to allow
Python/Streamlit on Private networks.

The `cookie_secret` should be a long, random value. The secrets file is ignored
by Git and must not be uploaded or committed.

## Run the application

```powershell
python -m streamlit run app.py
```

Open the local address shown in the terminal, usually:

```text
http://localhost:8501
```

## Deployment checklist

For Streamlit Community Cloud or another hosted Streamlit service:

1. Push the project files to a private or public Git repository.
2. Set the app entry point to `app.py`.
3. Configure `GEMINI_API_KEY` in the platform's secrets manager.
4. Copy the structure from `.streamlit/secrets.example.toml` into the platform secrets manager.
5. Replace `redirect_uri` with the deployed URL ending in `/oauth2callback`.
6. Register that exact callback URL with Google and Microsoft.
7. Add the host email under `[app].host_emails`.
8. Confirm `.env`, `.streamlit/secrets.toml`, and `data/` are not committed.

The local SQLite history database is suitable for development. For production,
use persistent storage if comparison history must survive redeployments.

## How to use

1. Upload Document A.
2. Upload Document B.
3. Click **Compare documents**.
4. Review the summaries, similarities, differences, key details, and conclusion.
5. Click **Download comparison report**.

The **Visual diff** tab highlights added, removed, and changed lines with
nearby context from both documents.

## Limitations

- Scanned image-only PDFs may not contain readable text.
- Images, videos, and program files are not supported.
- The application depends on Gemini API availability.
- Very large documents may exceed model input limits.
- Results should be reviewed by a human.
- This application is not a legal or compliance decision-maker.

## Profile and history

Signed-in users can open the **Profile** view to see their account identity,
role, and saved comparison count. The **History** view shows their recent
comparisons. History is stored locally in `data/app.db`, keyed by signed-in
email; uploaded files are not stored. Users can also choose a neon avatar
instead of displaying their personal profile photo.

Host accounts also receive a private **Host dashboard** with total comparison
counts and recent activity across signed-in users.

## Account roles

Add the host email address to `.streamlit/secrets.toml`:

```toml
[app]
host_emails = ["your-email@example.com"]
```

Emails listed there are shown as host accounts. Everyone else who signs in is
treated as a regular user account.

## Future improvements

- Add document chunking for long files.
- Add PDF report export.
- Add richer clause-level highlighting.
