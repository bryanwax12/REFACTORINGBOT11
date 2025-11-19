"""
Upload Router
Endpoints for file uploads
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Request, Depends
from handlers.admin_handlers import verify_admin_key
from fastapi.responses import JSONResponse
import logging
import os
from pathlib import Path
import aiofiles
from typing import Optional
import uuid

router = APIRouter(prefix="/api", tags=["upload"])
logger = logging.getLogger(__name__)

# Upload directory
UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Max file size (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


@router.post("/upload-image", dependencies=[Depends(verify_admin_key)])
async def upload_image(
    request: Request,
    file: UploadFile = File(...)
):
    """
    Upload image and optionally send to Telegram bot to get file_id - ADMIN ONLY
    
    Returns:
        {
            "success": true,
            "file_id": "telegram_file_id",  // if bot available
            "url": "file_url",              // if file saved locally
            "filename": "original_filename"
        }
    """
    try:
        # Validate file type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only images are allowed."
            )
        
        # Read file content
        content = await file.read()
        
        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size is {MAX_FILE_SIZE / (1024*1024)}MB"
            )
        
        # Generate unique filename
        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename
        
        # Save file locally
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        logger.info(f"Image uploaded: {unique_filename} ({len(content)} bytes)")
        
        # Try to upload to Telegram to get file_id
        bot_instance = getattr(request.app.state, 'bot_instance', None)
        file_id = None
        
        if bot_instance:
            try:
                # Send to a safe chat (can be admin chat or file channel)
                # For now, we'll use the bot's own chat to get file_id
                from telegram import InputFile
                import io
                
                # Send photo to get file_id
                message = await bot_instance.send_photo(
                    chat_id=bot_instance.bot.id,  # Send to self
                    photo=io.BytesIO(content),
                    caption="Uploaded via admin panel"
                )
                
                if message.photo:
                    # Get largest photo size
                    file_id = message.photo[-1].file_id
                    logger.info(f"Got Telegram file_id: {file_id}")
            except Exception as e:
                logger.warning(f"Could not upload to Telegram: {e}")
        
        # Construct response
        response_data = {
            "success": True,
            "filename": file.filename,
            "size": len(content)
        }
        
        if file_id:
            response_data["file_id"] = file_id
        else:
            # Return local file URL
            response_data["url"] = f"/uploads/{unique_filename}"
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading image: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/upload-image/{filename}", dependencies=[Depends(verify_admin_key)])
async def delete_uploaded_image(filename: str):
    """Delete uploaded image - ADMIN ONLY"""
    try:
        file_path = UPLOAD_DIR / filename
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        os.remove(file_path)
        logger.info(f"Deleted uploaded image: {filename}")
        
        return {"success": True, "message": "File deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting image: {e}")
        raise HTTPException(status_code=500, detail=str(e))
