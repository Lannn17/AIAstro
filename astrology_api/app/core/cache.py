"""
Cache module for astrological calculations.

Implements a cache system for frequent astrological calculations,
reducing response time for repeated requests.
"""
from typing import Dict, Any, Optional, Tuple
import time
import pickle
import os
import hashlib
import json

# Directory to store cache files
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "cache")

# Create cache directory if it doesn't exist
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# In-memory cache for fast access
MEMORY_CACHE = {}

# Cache expiration time in seconds (24 hours)
CACHE_EXPIRATION = 24 * 60 * 60

def get_cache_key(prefix: str, **kwargs) -> str:
    """
    Generates a cache key based on the given parameters.

    Args:
        prefix (str): Key prefix (e.g. 'natal', 'transit').
        **kwargs: Parameters used to generate the key.

    Returns:
        str: Cache key.
    """
    # Build a string representing the parameters
    param_str = json.dumps(kwargs, sort_keys=True)

    # Generate a SHA-256 hash of the string
    hash_obj = hashlib.sha256(param_str.encode())
    hash_str = hash_obj.hexdigest()

    # Return key in format prefix_hash
    return f"{prefix}_{hash_str}"

def get_from_cache(key: str) -> Optional[Any]:
    """
    Retrieves a value from the cache.

    Args:
        key (str): Cache key.

    Returns:
        Optional[Any]: Cached value or None if not found or expired.
    """
    # Check in-memory cache first
    if key in MEMORY_CACHE:
        timestamp, value = MEMORY_CACHE[key]

        # Check if cache has expired
        if time.time() - timestamp < CACHE_EXPIRATION:
            return value
        else:
            # Remove from memory cache if expired
            del MEMORY_CACHE[key]

    # Check disk cache
    cache_file = os.path.join(CACHE_DIR, f"{key}.pickle")
    if os.path.exists(cache_file):
        # Check file modification time
        mod_time = os.path.getmtime(cache_file)

        # Check if cache has expired
        if time.time() - mod_time < CACHE_EXPIRATION:
            try:
                with open(cache_file, 'rb') as f:
                    value = pickle.load(f)

                # Update in-memory cache
                MEMORY_CACHE[key] = (time.time(), value)

                return value
            except:
                # Remove file if loading fails
                os.remove(cache_file)
        else:
            # Remove file if expired
            os.remove(cache_file)

    return None

def save_to_cache(key: str, value: Any) -> None:
    """
    Saves a value to the cache.

    Args:
        key (str): Cache key.
        value (Any): Value to store.
    """
    # Save to in-memory cache
    MEMORY_CACHE[key] = (time.time(), value)

    # Save to disk cache
    cache_file = os.path.join(CACHE_DIR, f"{key}.pickle")
    try:
        with open(cache_file, 'wb') as f:
            pickle.dump(value, f)
    except:
        # Silently ignore save errors
        pass

def clear_cache() -> None:
    """
    Clears all cache entries.
    """
    # Clear in-memory cache
    MEMORY_CACHE.clear()

    # Clear disk cache
    for filename in os.listdir(CACHE_DIR):
        file_path = os.path.join(CACHE_DIR, filename)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except:
            pass

def clear_expired_cache() -> None:
    """
    Clears only expired cache entries.
    """
    current_time = time.time()

    # Clear expired in-memory cache entries
    keys_to_remove = []
    for key, (timestamp, _) in MEMORY_CACHE.items():
        if current_time - timestamp >= CACHE_EXPIRATION:
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del MEMORY_CACHE[key]

    # Clear expired disk cache files
    for filename in os.listdir(CACHE_DIR):
        file_path = os.path.join(CACHE_DIR, filename)
        try:
            if os.path.isfile(file_path):
                mod_time = os.path.getmtime(file_path)
                if current_time - mod_time >= CACHE_EXPIRATION:
                    os.remove(file_path)
        except:
            pass
