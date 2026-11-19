from pathlib import Path
import os
import signal
import subprocess
import sys
import tempfile
import time

here = Path(__file__).resolve().parent
root = here.parents[1]
with tempfile.TemporaryDirectory(prefix='shared-policy-browser-') as profile:
    with (here/'shared-server.log').open('w') as server_log, (here/'shared-browser.log').open('w') as browser_log:
        command = [sys.executable, str(root/'2D_Shared_Policy_2026-11-11/server.py'), '--seed', '27', '--seconds', '30']
        server = subprocess.Popen(command, stdout=server_log, stderr=server_log, start_new_session=True)
        browser = None
        try:
            for _ in range(100):
                text = (here/'shared-server.log').read_text()
                if 'SHARED_POLICY_VIEWER ' in text:
                    url = text.split('SHARED_POLICY_VIEWER ', 1)[1].splitlines()[0]
                    break
                if server.poll() is not None:
                    raise RuntimeError(text)
                time.sleep(.05)
            else:
                raise RuntimeError('Server did not start')
            browser = subprocess.Popen(['google-chrome', '--headless=new', '--no-sandbox', '--disable-dev-shm-usage',
                '--no-first-run', '--no-default-browser-check', '--disable-gpu', '--remote-debugging-port=0',
                '--remote-debugging-address=127.0.0.1', '--user-data-dir='+profile, 'about:blank'],
                stdout=browser_log, stderr=browser_log, start_new_session=True)
            for _ in range(100):
                if (Path(profile)/'DevToolsActivePort').exists():
                    break
                time.sleep(.05)
            subprocess.run(['node', str(here/'check_shared_browser.mjs')], check=True, timeout=60,
                env={**os.environ, 'TDP_SHARED_URL': url, 'TDP_1V1_QA_PROFILE': profile})
        finally:
            for process in (browser, server):
                if process is not None and process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        os.killpg(process.pid, signal.SIGKILL)
                        process.wait()
