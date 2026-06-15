import hashlib
import os
from typing import Tuple

def calculate_sha256(file_path: str) -> str:
    """Calculate the SHA-256 hash of a file."""
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return ""
    
    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        # Read in 8KB chunks
        for byte_block in iter(lambda: f.read(8192), b""):
            sha256_hash.update(byte_block)
            
    return sha256_hash.hexdigest()

def get_file_metadata(file_path: str) -> Tuple[int, str]:
    """Return the tuple of (size_bytes, sha256_hash) for a file."""
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return 0, ""
    
    size = os.path.getsize(file_path)
    sha = calculate_sha256(file_path)
    return size, sha
