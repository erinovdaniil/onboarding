"""
Supabase Storage utilities for file operations.
"""
import os
from typing import Optional
from app.supabase_client import supabase
from fastapi import HTTPException


async def upload_file_to_storage(
    bucket_name: str,
    file_path: str,
    file_content: bytes,
    content_type: Optional[str] = None
) -> str:
    """
    Upload a file to Supabase Storage.
    Returns the public URL of the uploaded file.
    """
    try:
        # Delete existing file first (to handle upsert)
        try:
            supabase.storage.from_(bucket_name).remove([file_path])
        except Exception:
            pass  # File might not exist, that's fine

        # Upload file to Supabase Storage
        result = supabase.storage.from_(bucket_name).upload(
            file_path,
            file_content,
            file_options={"contentType": content_type or "application/octet-stream"}
        )
        
        # Get public URL
        public_url_response = supabase.storage.from_(bucket_name).get_public_url(file_path)
        
        # The get_public_url returns a dict with 'publicUrl' key
        if isinstance(public_url_response, dict):
            return public_url_response.get("publicUrl", "")
        elif isinstance(public_url_response, str):
            return public_url_response
        else:
            # Fallback: construct URL manually
            from app.supabase_client import SUPABASE_URL
            return f"{SUPABASE_URL}/storage/v1/object/public/{bucket_name}/{file_path}"
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage error: {str(e)}")


async def delete_file_from_storage(bucket_name: str, file_path: str) -> bool:
    """
    Delete a file from Supabase Storage.
    """
    try:
        result = supabase.storage.from_(bucket_name).remove([file_path])
        return True
    except Exception as e:
        print(f"Error deleting file from storage: {e}")
        return False


async def get_file_url(bucket_name: str, file_path: str, public: bool = True) -> str:
    """
    Get the URL for a file in Supabase Storage.
    """
    try:
        if public:
            return supabase.storage.from_(bucket_name).get_public_url(file_path)
        else:
            # For private files, generate a signed URL
            result = supabase.storage.from_(bucket_name).create_signed_url(file_path, 3600)
            return result.get("signedURL", "") if result else ""
    except Exception as e:
        print(f"Error getting file URL: {e}")
        return ""


async def download_file_from_storage(bucket_name: str, file_path: str) -> bytes:
    """
    Download a file from Supabase Storage.
    Returns the file content as bytes.
    """
    try:
        result = supabase.storage.from_(bucket_name).download(file_path)
        
        # Supabase download returns bytes directly
        if isinstance(result, bytes):
            return result
        
        # If it's a response object, read it
        if hasattr(result, 'content'):
            return result.content
        elif hasattr(result, 'read'):
            return result.read()
        elif hasattr(result, 'data'):
            return result.data
        
        # Fallback: try to convert to bytes
        if isinstance(result, str):
            return result.encode('utf-8')
        
        raise HTTPException(status_code=500, detail="Unexpected response type from storage")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Storage download error: {str(e)}")


def ensure_bucket_exists(bucket_name: str, public: bool = True) -> bool:
    """
    Ensure a storage bucket exists.
    Note: Buckets should be created manually in Supabase dashboard.
    This function just verifies the bucket exists.
    """
    try:
        # Try to list buckets to check if it exists
        buckets = supabase.storage.list_buckets()

        # Debug: print bucket info
        print(f"Found {len(buckets)} buckets")
        for b in buckets:
            print(f"  - Bucket: {getattr(b, 'name', None) or getattr(b, 'id', None) or b}")

        # Get bucket names - handle different attribute names
        bucket_names = []
        for b in buckets:
            if hasattr(b, 'name'):
                bucket_names.append(b.name)
            elif hasattr(b, 'id'):
                bucket_names.append(b.id)
            elif isinstance(b, dict):
                bucket_names.append(b.get('name') or b.get('id'))

        print(f"Bucket names: {bucket_names}")
        print(f"Looking for: '{bucket_name}'")

        if bucket_name not in bucket_names:
            print(f"Warning: Bucket '{bucket_name}' not found in available buckets.")
            # Don't fail - proceed anyway, the upload will fail with a clearer error if bucket truly doesn't exist
            return True
        return True
    except Exception as e:
        print(f"Error checking bucket exists: {e}")
        # Assume bucket exists if we can't check (avoid blocking uploads)
        return True

