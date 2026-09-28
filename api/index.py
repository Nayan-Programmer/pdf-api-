import os
import httpx

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

app = FastAPI(
    title="EchooAI PDF Generator API",
    version="1.0.0",
)

GOTENBERG_URL = os.getenv("GOTENBERG_URL", "").rstrip("/")
API_KEY = os.getenv("API_KEY")


class PDFRequest(BaseModel):
    html: str = Field(..., min_length=1)
    filename: str = "document.pdf"


def authenticate(authorization: str | None):
    if not API_KEY:
        return

    if authorization != f"Bearer {API_KEY}":
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )


@app.get("/")
async def root():
    return {
        "service": "EchooAI PDF Generator",
        "status": "online",
        "docs": "/docs"
    }


@app.get("/health")
async def health():
    if not GOTENBERG_URL:
        return {
            "api": "ok",
            "gotenberg": "not configured"
        }

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                f"{GOTENBERG_URL}/health"
            )

        return {
            "api": "ok",
            "gotenberg": r.status_code == 200
        }

    except Exception:
        return {
            "api": "ok",
            "gotenberg": False
        }


@app.post("/api/generate")
async def generate(
    request: PDFRequest,
    authorization: str | None = Header(default=None)
):
    authenticate(authorization)

    if not GOTENBERG_URL:
        raise HTTPException(
            status_code=500,
            detail="GOTENBERG_URL is not configured"
        )

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
    font-family: Arial, sans-serif;
    color: #111827;
    line-height: 1.6;
}}

h1 {{
    font-size: 30px;
}}

h2 {{
    font-size: 20px;
}}

</style>

</head>

<body>
{request.html}
</body>

</html>
"""

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{GOTENBERG_URL}/forms/chromium/convert/html",
                files={
                    "files": (
                        "index.html",
                        html.encode("utf-8"),
                        "text/html"
                    )
                }
            )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Gotenberg connection failed: {e}"
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail="Gotenberg failed to generate PDF"
        )

    filename = request.filename

    if not filename.endswith(".pdf"):
        filename += ".pdf"

    return Response(
        content=response.content,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                f'attachment; filename="{filename}"'
        }
    )
