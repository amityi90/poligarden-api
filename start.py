"""App Runner entry point — runs gunicorn without needing it on PATH."""
import sys
sys.argv = ["gunicorn", "run:app", "--bind", "0.0.0.0:8080"]
from gunicorn.app.wsgiapp import run
run()
