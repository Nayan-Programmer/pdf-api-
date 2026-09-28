import os
import httpx

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field


app = FastAPI(
    title="EchooAI PDF Generator",
    version="1.0.0",
    description="HTML to PDF API powered by FastAPI and Gotenberg",
)

GOTENBERG_URL = os.getenv(
    "GOTENBERG_URL",
    "http://localhost:3000"
).rstrip("/")

API_KEY = os.getenv("API_KEY")


class PDFRequest(BaseModel):
    html: str = Field(..., min_length=1)
    filename: str = Field(default="document.pdf", max_length=100)


def check_api_key(authorization: str | None):
    # Authentication is optional locally.
    if not API_KEY:
        return

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Use Bearer authentication"
        )

    token = authorization[7:]

    if token != API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )


@app.get("/")
async def root():
    return {
        "name": "EchooAI PDF Generator",
        "status": "online",
        "engine": "Gotenberg",
        "version": "1.0.0",
    }


@app.get("/health")
async def health():
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                f"{GOTENBERG_URL}/health"
            )

        return {
            "api": "ok",
            "gotenberg": response.status_code == 200
        }

    except Exception:
        return {
            "api": "ok",
            "gotenberg": False
        }


@app.post("/api/generate")
async def generate_pdf(
    request: PDFRequest,
    authorization: str | None = Header(default=None),
):
    check_api_key(authorization)

    html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">

<style>

@page {{
    size: A4;
    margin: 20mm;
}}

body {{
    font-family: Arial, Helvetica, sans-serif;
    color: #111827;
    line-height: 1.6;
    font-size: 14px;
}}

h1 {{
    font-size: 30px;
    margin-bottom: 20px;
}}

h2 {{
    font-size: 20px;
    margin-top: 25px;
}}

</style>

</head>

<body>

{request.html}

</body>
</html>
"""

    files = {
        "files": (
            "index.html",
            html.encode("utf-8"),
            "text/html",
        )
    }

    try:
        async with httpx.AsyncClient(
            timeout=60
        ) as client:

            response = await client.post(
                f"{GOTENBERG_URL}/forms/chromium/convert/html",
                files=files,
            )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Gotenberg unavailable: {str(e)}"
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail={
                "message": "Gotenberg failed",
                "status": response.status_code,
                "response": response.text[:1000],
            }
        )

    filename = request.filename

    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"

    return Response(
        content=response.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"'
        },
    )
