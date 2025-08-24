#!/usr/bin/env python3
"""
Quick script to clear any cached Streamlit session and restart fresh
"""

import os
import shutil
from pathlib import Path

def clear_streamlit_cache():
    """Clear Streamlit cache directories"""
    cache_dirs = [
        Path.home() / ".streamlit",
        Path("/tmp") / "streamlit",
        Path(".streamlit")
    ]
    
    for cache_dir in cache_dirs:
        if cache_dir.exists():
            try:
                shutil.rmtree(cache_dir)
                print(f"✅ Cleared cache: {cache_dir}")
            except Exception as e:
                print(f"⚠️  Could not clear {cache_dir}: {e}")

def restart_app():
    """Restart the Streamlit application"""
    print("🔄 Clearing Streamlit cache...")
    clear_streamlit_cache()
    
    print("🚀 Starting fresh Streamlit application...")
    os.system("cd /workspaces/Impact-Assessment && bash start.sh")

if __name__ == "__main__":
    restart_app()
