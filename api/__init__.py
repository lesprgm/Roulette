import os
from pathlib import Path


def _load_dotenv_if_needed() -> None:
	# Do not auto-load .env during pytest to keep tests offline
	if os.getenv("PYTEST_CURRENT_TEST"):
		return
	env_path = Path(".env")
	if not env_path.exists():
		return
	try:
		for line in env_path.read_text(encoding="utf-8").splitlines():
			s = line.strip()
			if not s or s.startswith("#") or "=" not in s:
				continue
			key, val = s.split("=", 1)
			key = key.strip()
			val = val.strip()
			if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
				val = val[1:-1]
			# Do not overwrite if already set in environment
			if key and key not in os.environ:
				os.environ[key] = val
	except Exception:
		# Fail open: environment loading is best-effort
		pass


_load_dotenv_if_needed()
