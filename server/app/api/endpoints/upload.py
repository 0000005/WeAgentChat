from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
import shutil
import os
from pathlib import Path
from uuid import uuid4
from PIL import Image

router = APIRouter()

# Define paths relative to the project root (where the app runs)
# Assuming execution from server/ directory
UPLOAD_DIR = Path("data/uploads/avatars")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}

@router.post("/image")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload an image file.
    Constraints: < 10MB, formats: .jpg, .png, .webp
    Algorithm:
    1. Validate extension
    2. Validate size (soft check) and content
    3. Save with unique name
    4. Verify with Pillow
    5. Return relative URL
    """
    # 1. Validate file extension
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is missing")
        
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PNG, JPG, and WEBP formats are allowed.")
    
    # 2. Generate unique filename
    filename = f"{uuid4()}{ext}"
    file_path = UPLOAD_DIR / filename
    
    # 3. Save file
    try:
        # Use a buffer to control memory usage and check size
        # Note: writing directly to file is memory efficient for large files compared to reading into RAM first
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 4. Check file size after writing (or during if we implemented custom chunk reading)
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="File too large (max 10MB).")

        # 5. Verify image integrity with Pillow
        try:
            with Image.open(file_path) as img:
                img.verify()
        except Exception:
            os.remove(file_path)
            raise HTTPException(status_code=400, detail="Invalid image file or corrupted data.")
            
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Clean up if something went wrong
        if file_path.exists():
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")
        
    return {"url": f"/uploads/avatars/{filename}"}
