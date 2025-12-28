import hashlib
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

# Storage configuration
ATTACHMENTS_DIR = Path("/app/uploads/attachments")
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
}

# Maximum file size (30 MB)
MAX_FILE_SIZE = 30 * 1024 * 1024


def validate_file_type(mime_type: str) -> bool:
    """Check if MIME type is allowed"""
    return mime_type in ALLOWED_MIME_TYPES


def validate_file_extension(filename: str) -> bool:
    """Check if file extension is allowed"""
    allowed_extensions = {".pdf", ".jpg", ".jpeg", ".png", ".gif"}
    ext = Path(filename).suffix.lower()
    return ext in allowed_extensions


def get_mime_type_from_extension(filename: str) -> str:
    """Get MIME type from file extension"""
    ext = Path(filename).suffix.lower()
    mime_map = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
    }
    return mime_map.get(ext, "application/octet-stream")


def generate_storage_filename(original_filename: str) -> str:
    """Generate unique storage filename using UUID"""
    ext = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4()}{ext}"


def get_file_path(storage_filename: str) -> Path:
    """Get full path for a storage filename"""
    return ATTACHMENTS_DIR / storage_filename


async def save_file(file: UploadFile, storage_filename: str) -> tuple[int, str]:
    """
    Save uploaded file to storage.
    Returns (size_bytes, checksum_sha256)
    """
    file_path = get_file_path(storage_filename)

    # Read file content
    content = await file.read()
    size_bytes = len(content)

    # Check file size
    if size_bytes > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
        )

    # Calculate checksum
    checksum = hashlib.sha256(content).hexdigest()

    # Save to disk
    with open(file_path, "wb") as f:
        f.write(content)

    return size_bytes, checksum


def delete_file(storage_filename: str) -> bool:
    """Delete file from storage. Returns True if deleted, False if not found."""
    file_path = get_file_path(storage_filename)
    if file_path.exists():
        file_path.unlink()
        return True
    return False


def file_exists(storage_filename: str) -> bool:
    """Check if file exists in storage"""
    return get_file_path(storage_filename).exists()


def validate_upload(file: UploadFile) -> str:
    """
    Validate uploaded file.
    Returns the validated MIME type.
    Raises HTTPException if invalid.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    # Validate extension
    if not validate_file_extension(file.filename):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Allowed types: PDF, JPG, PNG, GIF",
        )

    # Get MIME type (prefer content_type from upload, fallback to extension)
    mime_type = file.content_type
    if not mime_type or mime_type == "application/octet-stream":
        mime_type = get_mime_type_from_extension(file.filename)

    # Validate MIME type
    if not validate_file_type(mime_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid MIME type: {mime_type}. Allowed types: PDF, JPG, PNG, GIF",
        )

    return mime_type
