# DOCX / PPTX → PDF Conversion using Microsoft Graph + FastAPI

This guide documents the **complete, real-world steps** to build a backend service that converts **DOCX and PPTX files to PDF** using **Microsoft Graph API** with **FastAPI**.

It is written for someone who wants to reproduce the solution **without hitting the same blockers** (auth, licensing, `/me` vs app-only, OneDrive provisioning, etc.).

---

## 1. Architecture Overview

**Why Microsoft Graph?**
- Best fidelity (same engine as Office)
- Supports DOCX, PPTX, XLSX → PDF
- No LibreOffice / Docker / native Office needed

**Flow:**

1. Client uploads DOCX/PPTX
2. FastAPI backend authenticates using **app-only OAuth (client credentials)**
3. File is uploaded to a **specific user’s OneDrive**
4. Microsoft Graph converts file to PDF
5. Backend downloads PDF
6. Temporary file is deleted

---

## 2. Prerequisites (Important)

### ❗ Critical Requirement

You **must** have a **Work/School (Entra ID) tenant** with:
- App registrations enabled
- OneDrive / SharePoint available

❌ Personal Microsoft accounts (gmail / outlook.com) **do not work** for app-only Graph access.

---

## 3. Azure / Entra ID Setup

### 3.1 Create App Registration (Service Principal)

1. Go to **Azure Portal**
2. Open **Azure Entra ID**
3. Navigate to **App registrations → New registration**
4. Fill:
   - **Name**: `office-pdf-converter`
   - **Supported account types**: Single tenant
   - Redirect URI: leave empty
5. Click **Register**

Save:
- **Tenant ID**
- **Client ID**

---

### 3.2 Create Client Secret

1. App registration → **Certificates & secrets**
2. **New client secret**
3. Copy the secret value immediately

Save:
- **Client Secret**

---

### 3.3 Assign Microsoft Graph Permissions

App registration → **API permissions** → Add permission → Microsoft Graph → **Application permissions**

Add:
- `Files.ReadWrite.All`

Then:
- Click **Grant admin consent**

> These permissions allow the backend (no user login) to access OneDrive files.

---

## 4. Create a Dedicated OneDrive User

This user will act as a **service user** whose OneDrive is used for temporary storage.

### 4.1 Create User

Azure Entra ID → Users → New user

Example:
- `pdfconverter@yourtenant.onmicrosoft.com`

Save:
- **User Object ID** (recommended over email)

---

### 4.2 Assign License (Required)

From **Microsoft 365 Admin Center**:

- Users → Active users → pdfconverter
- Licenses and apps
- Ensure **SharePoint / OneDrive** is enabled

> Without this, OneDrive will never provision and Graph will return 400 errors.

---

### 4.3 Provision OneDrive (One-time step)

1. Open **Incognito window**
2. Go to `https://www.office.com`
3. Login as `pdfconverter@...`
4. Click **OneDrive**

Wait until it loads.

> This step is mandatory. Graph APIs do NOT auto-create OneDrive.

---

## 5. Why `/me` Does NOT Work

Because this solution uses:

```
grant_type = client_credentials
```

There is **no signed-in user**, so:

❌ `/me/drive`

Will always fail.

✅ Correct pattern:

```
/users/{USER_OBJECT_ID}/drive
```

---

## 6. FastAPI Implementation

### 6.1 Dependencies

```bash
pip install fastapi uvicorn httpx python-multipart python-dotenv
```

---

### 6.2 Environment Variables (`.env`)

```env
TENANT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx
CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx
CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxx

GRAPH_USER_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxx
```

---

### 6.3 Authentication (`auth.py`)

```python
import os
import httpx

TENANT_ID = os.getenv("TENANT_ID")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"


async def get_access_token():
    async with httpx.AsyncClient() as client:
        res = await client.post(
            TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "grant_type": "client_credentials",
                "scope": "https://graph.microsoft.com/.default",
            },
        )
        res.raise_for_status()
        return res.json()["access_token"]
```

---

### 6.4 OneDrive Operations (`onedrive.py`)

```python
import os
import httpx

GRAPH_USER_ID = os.getenv("GRAPH_USER_ID")
BASE_URL = f"https://graph.microsoft.com/v1.0/users/{GRAPH_USER_ID}/drive"


async def upload_file(token: str, filename: str, content: bytes):
    url = f"{BASE_URL}/root:/{filename}:/content"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/octet-stream",
    }

    async with httpx.AsyncClient() as client:
        res = await client.put(url, headers=headers, content=content)
        res.raise_for_status()


async def convert_to_pdf(token: str, filename: str) -> bytes:
    url = f"{BASE_URL}/root:/{filename}:/content?format=pdf"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        res = await client.get(url, headers=headers)
        res.raise_for_status()
        return res.content


async def delete_file(token: str, filename: str):
    url = f"{BASE_URL}/root:/{filename}"
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient() as client:
        await client.delete(url, headers=headers)
```

---

### 6.5 FastAPI Endpoint (`main.py`)

```python
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import io
import re

from auth import get_access_token
from onedrive import upload_file, convert_to_pdf, delete_file

app = FastAPI()


def safe_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", name)


@app.post("/convert-to-pdf")
async def convert(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".docx", ".pptx")):
        raise HTTPException(status_code=400, detail="Only DOCX or PPTX supported")

    token = await get_access_token()
    content = await file.read()
    filename = safe_filename(file.filename)

    try:
        await upload_file(token, filename, content)
        pdf_bytes = await convert_to_pdf(token, filename)
    finally:
        await delete_file(token, filename)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}.pdf"},
    )
```

---

## 7. Common Errors & Fixes

### 400 Bad Request on Upload
- OneDrive not provisioned
- License not assigned
- Using `/me`

### Cannot access Admin Center
- Logged in as service user instead of admin

### Dev Program Sandbox Not Available
- Use org tenant or Microsoft 365 trial

---

## 8. Cost Considerations

| Item | Cost |
|----|----|
| App registration | Free |
| Graph API calls | Free |
| OneDrive usage | Free (if files deleted) |
| Conversion | Free |

> Storage cost only applies if files are retained.

---

## 9. Final Notes

- This is an **enterprise-grade approach**
- Exact same pattern used in production systems
- SharePoint-based approach can replace OneDrive later if needed

---

## 10. Summary

- Use **App-only Graph auth**
- Never use `/me`
- OneDrive must be provisioned once
- Delete files after conversion

This guide intentionally includes the **real pitfalls** so others don’t repeat them.
