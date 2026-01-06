import os
import httpx
from dotenv import load_dotenv
load_dotenv()

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
        return res.json()


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
