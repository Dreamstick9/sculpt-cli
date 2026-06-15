#!/usr/bin/env python3
"""Pull upstream LICENSE files into sculpt/licenses/ for audit trail."""

import subprocess
from pathlib import Path

# Model repos to fetch licenses from
REPOS = {
    "sf3d": "https://github.com/Stability-AI/stable-fast-3d.git",
    "trellis2": "https://github.com/microsoft/TRELLIS.2.git",
    "trellis_original": "https://github.com/microsoft/TRELLIS.git",
    "hi3dgen": "https://github.com/Stable-X/Hi3DGen.git",
    "triposg": "https://github.com/VAST-AI-Research/TripoSG.git",
    "triposr": "https://github.com/VAST-AI-Research/TripoSR.git",
}


def main():
    out_dir = Path(__file__).parent.parent / "sculpt" / "licenses"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    for name, url in REPOS.items():
        dest = out_dir / f"{name}.LICENSE"
        try:
            # Clone repo shallowly, just to get LICENSE
            import tempfile
            with tempfile.TemporaryDirectory() as tmp:
                subprocess.run(
                    ["git", "clone", "--depth", "1", url, tmp + "/repo"],
                    check=True, capture_output=True
                )
                import shutil
                repo_path = Path(tmp) / "repo"
                license_files = list(repo_path.glob("LICENSE*")) + list(repo_path.glob("LICENCE*"))
                for lf in license_files:
                    shutil.copy2(lf, out_dir / f"{name}_{lf.name}")
                print(f"[OK] {name}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")


if __name__ == "__main__":
    main()