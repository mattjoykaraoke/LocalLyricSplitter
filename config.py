import json
import os
import shutil
import sys
from pathlib import Path

APP_VERSION = "2.3.2"

def get_config_path():
    """
    Priority logic:
    1. If NOT compiled (Dev mode): Use config.json in the script folder.
    2. If compiled (Installed mode): Use %APPDATA% ONLY.
    """
    is_frozen = getattr(sys, "frozen", False)

    if not is_frozen:
        local_config = Path(__file__).parent / "config.json"
        return str(local_config)

    app_data_dir = Path(os.getenv("APPDATA", "")) / "LocalLyricSplitter"
    config_file = app_data_dir / "config.json"

    if not app_data_dir.exists():
        app_data_dir.mkdir(parents=True)

    if not config_file.exists():
        bundled_config = Path(getattr(sys, "_MEIPASS", "")) / "config.json"
        if bundled_config.exists():
            try:
                shutil.copy(bundled_config, config_file)
                return str(config_file)
            except Exception:
                pass

        default_config = {"trip_up_words": {"into": "in/to"}, "false_positives": []}
        with open(config_file, "w") as f:
            json.dump(default_config, f, indent=4)

    return str(config_file)
