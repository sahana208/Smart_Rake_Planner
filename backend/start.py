import uvicorn
from app.main import app
from app.db import get_app_port

if __name__ == "__main__":
    port = get_app_port()
    uvicorn.run(app, host="0.0.0.0", port=port)
