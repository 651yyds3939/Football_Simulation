from pathlib import Path
import os
import signal
import subprocess
import tempfile
import time

here = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='football-single-html-') as profile:
    with (here/'browser.log').open('w') as log:
        browser = subprocess.Popen(['google-chrome', '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
            '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--remote-debugging-port=0',
            '--remote-debugging-address=127.0.0.1', '--user-data-dir='+profile, 'about:blank'],
            stdout=log, stderr=log, start_new_session=True)
        try:
            for _ in range(100):
                if (Path(profile)/'DevToolsActivePort').exists():
                    break
                time.sleep(.05)
            subprocess.run(['node', str(here/'browser.mjs')], check=True, timeout=600,
                           env={**os.environ, 'DEMO_BROWSER_PROFILE': profile})
        finally:
            if browser.poll() is None:
                os.killpg(browser.pid, signal.SIGTERM)
                try:
                    browser.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(browser.pid, signal.SIGKILL)
                    browser.wait()
