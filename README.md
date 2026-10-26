# AI Document Comparison Assistant

An AI-powered Streamlit workspace for understanding what changed between two
documents.

The interface uses a clean light theme and a compact Doc Compare lettermark.

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
- Download a Word or PDF comparison report
- Ask evidence-backed questions about both documents
- Explore a guided sample comparison without signing in or configuring an API key
- Sign in with Google or Microsoft
- Save comparison history and manage user profiles

## Technologies

- Python
- Streamlit
- pypdf
- ReportLab
- Gemini API
- python-dotenv
- python-docx

## Screenshots

The live workspace includes document upload, AI comparison results, severity
filters, source citations, a visual diff, report download, and document chat.

## Project structure

```text
├── app.py
├── auth_utils.py
├── document_reader.py
├── comparison.py
├── demo_data.py
├── report_generator.py
├── user_data.py
├── workspace_state.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
├── assets/
└── tests/
    ├── test_auth_utils.py
    ├── test_comparison.py
    ├── test_demo_data.py
    ├── test_document_reader.py
    ├── test_report_generator.py
    ├── test_user_data.py
    └── test_workspace_state.py
```

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

### Secure phone access

The hosted app uses HTTPS. For phone testing, use the hosted HTTPS URL when
available. The local Wi-Fi address (`http://<computer-ip>:8501`) uses plain
HTTP, which is why the browser displays **Not secure**. Do not sign in or send
private documents over that HTTP connection.

For local phone testing, you can enable HTTPS with a locally trusted
development certificate:

1. Install `mkcert` for Windows using its
   [official installation instructions](https://github.com/FiloSottile/mkcert#installation).
2. In PowerShell, run `mkcert -install` once on the computer. This adds the
   local development CA to that computer's trusted certificate store.
3. Find the computer's local IPv4 address with `ipconfig`, then create a
   certificate containing that address:

   ```powershell
   mkcert -cert-file .streamlit\local-cert.pem -key-file .streamlit\local-key.pem localhost 127.0.0.1 <computer-ip>
   ```

4. Start Streamlit with HTTPS enabled:

   ```powershell
   python -m streamlit run app.py --server.address 0.0.0.0 --server.port 8502 --server.sslCertFile .streamlit\local-cert.pem --server.sslKeyFile .streamlit\local-key.pem
   ```

5. On the phone, install and trust the public root certificate shown by
   `mkcert -CAROOT` (the `rootCA.pem` file, commonly
   `%LOCALAPPDATA%\mkcert\rootCA.pem`). Transfer only `rootCA.pem` to the
   phone; never copy or share `rootCA-key.pem`. Recreate the local certificate
   if the computer's IP address changes.

Then open `https://<computer-ip>:8502` on the phone. If the phone does not
trust the local CA, the browser will still show a certificate warning; do not
bypass it. Local certificate setup is for development only. For sign-in and
real documents, use the deployed HTTPS domain and register its exact HTTPS
OAuth callback URI with Google and Microsoft.

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
5. Set `[auth].redirect_uri` to the deployed URL ending in `/oauth2callback`.
   For the live demo, this is `https://ai-document-comparison-assistant.streamlit.app/oauth2callback`.
6. Register that exact URL as a **Web** redirect URI with Google and Microsoft.
   The scheme, hostname, path, and trailing-slash choice must match exactly.
7. Add the host email under `[app].host_emails`.
8. Confirm `.env`, `.streamlit/secrets.toml`, and `data/` are not committed.

The local SQLite history database is suitable for development. For production,
use persistent storage if comparison history must survive redeployments.

## How to use

1. Upload Document A.
2. Upload Document B.
3. Click **Compare documents**.
4. Confirm the extracted page or unit counts and character counts for both files.
5. Review the summaries, similarities, differences, key details, and conclusion.
6. Download the comparison as a Word or PDF report.

The **Visual diff** tab highlights added, removed, and changed lines with
nearby context from both documents.
Gemini's structured comparison response is validated before it is displayed or
included in a report. If the response is malformed or incomplete, the app shows
an error and allows you to retry the comparison.

To explore the interface without signing in, select **Explore the guided
demo** on the welcome page. It uses fictional sample policies and preloaded
example findings; it does not upload files, call Gemini, or save history.

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
email; uploaded files are not stored. Clearing the workspace resets the document
upload controls and removes generated results but keeps saved history. Users can permanently delete
their own saved history from the **History** view after confirming. Users can
also choose a neon avatar instead of displaying their personal profile photo.

Host accounts also receive a private **Host dashboard** with total comparison
counts, recent activity, and a list of signed-in accounts with their display
name, email, provider, and most recent sign-in time. This account metadata is
recorded once per app session; users are informed on the sign-in page and in
their profile. Uploaded files and passwords are not stored.

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
- Add richer clause-level highlighting.
