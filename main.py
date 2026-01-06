from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import io

from helpers.token import get_access_token
from helpers.upload import upload_file, convert_to_pdf, delete_file

app = FastAPI()


@app.post("/convert-to-pdf")
async def convert(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".docx", ".pptx")):
        raise HTTPException(status_code=400, detail="Only DOCX or PPTX supported")

    token = await get_access_token()
    content = await file.read()

    try:
        await upload_file(token, file.filename, content)
        pdf_bytes = await convert_to_pdf(token, file.filename)
    finally:
        await delete_file(token, file.filename)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={file.filename}.pdf"
        },
    )
