import os
import sys

# Add the current directory to Python path
sys.path.insert(0, '/app')

# Import the app directly
import uvicorn

# Import the app components
from app import app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
