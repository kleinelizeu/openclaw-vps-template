"""Local test runner — runs the wizard on localhost:5555 for UI testing."""
import os
import sys
import tempfile
import json

# Create temp directories to simulate VPS paths
TMPDIR = tempfile.mkdtemp(prefix="openclaw-test-")
os.makedirs(os.path.join(TMPDIR, "openclaw"), exist_ok=True)
os.makedirs(os.path.join(TMPDIR, "config/agents/main/agent"), exist_ok=True)
os.makedirs(os.path.join(TMPDIR, "config/workspace"), exist_ok=True)
os.makedirs(os.path.join(TMPDIR, "config/cron"), exist_ok=True)

# Write a fake .env
with open(os.path.join(TMPDIR, "openclaw/.env"), "w") as f:
    f.write("# test env\n")

# Write a fake token
token_path = os.path.join(TMPDIR, "token")
with open(token_path, "w") as f:
    f.write("test-token-local-12345")

# Now patch app.py module-level constants
import app as wizard_app

wizard_app.OPENCLAW_DIR = os.path.join(TMPDIR, "openclaw")
wizard_app.ENV_FILE = os.path.join(TMPDIR, "openclaw/.env")
wizard_app.TOKEN_FILE = token_path
wizard_app.SETUP_DONE_FILE = os.path.join(TMPDIR, "setup-done")
wizard_app.OPENCLAW_CONFIG_DIR = os.path.join(TMPDIR, "config")
wizard_app.AGENT_DIR = os.path.join(TMPDIR, "config/agents/main/agent")
wizard_app.WORKSPACE_DIR = os.path.join(TMPDIR, "config/workspace")

print(f"\n{'='*50}")
print(f"  OpenClaw Setup Wizard — LOCAL TEST")
print(f"{'='*50}")
print(f"  Temp dir: {TMPDIR}")
print(f"  Open: http://localhost:5555")
print(f"{'='*50}\n")
print("  NOTA: API keys validation e deploy vao falhar")
print("  (sem Docker/OpenClaw), mas o fluxo visual")
print("  dos 12 steps funciona normalmente.\n")

wizard_app.app.run(host="127.0.0.1", port=5555, debug=True)
