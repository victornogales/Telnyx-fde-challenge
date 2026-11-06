"""
Local development entry-point for uvicorn.
Run with:
    uvicorn app:app --port 8080 --interface asgi3 --lifespan off
"""

from function import new

app = new()
