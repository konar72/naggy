import os
from app.bootstrap import build_app

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    app = build_app()
    app.run_polling()
