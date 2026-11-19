from pathlib import Path
import os
import signal
import subprocess
import tempfile
import time

here = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='tdp-2d-browser-') as profile:
    with (here/'browser.log').open('w') as log:
        process = subprocess.Popen([
            'google-chrome', '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
            '--no-first-run', '--no-default-browser-check', '--disable-gpu',
            '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
            '--user-data-dir='+profile, 'about:blank',
        ], stdout=log, stderr=log, start_new_session=True)
        try:
            for _ in range(100):
                if (Path(profile)/'DevToolsActivePort').exists():
                    break
                if process.poll() is not None:
                    raise RuntimeError('Browser exited during startup')
                time.sleep(.1)
            else:
                raise RuntimeError('Browser debugging port did not become ready')
            subprocess.run(['node', str(here/'browser_check.mjs')], check=True, timeout=40,
                           env={**os.environ, 'TDP_2D_QA_PROFILE': profile})
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
