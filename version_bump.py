#!/usr/bin/env python3
"""
G.L.A.D.O.S — Automatic Version Bump Tool

Analyzes staged git changes and automatically bumps the version in VERSION.json.

Rules:
  - MAJOR (x.0.0): breaking changes — new system_panel_app.py with class/route restructure,
                    or commit message contains "breaking" / "major"
  - MINOR (x.y.0): new features — new files added, commit message contains "feat" / "feature" / "minor"
  - PATCH (x.y.z): bug fixes, docs, refactors — default for all other changes

Usage:
  python version_bump.py                  # Auto-detect from git staged changes
  python version_bump.py patch "Fix bug"  # Manual: bump patch with note
  python version_bump.py minor "New feat" # Manual: bump minor with note
  python version_bump.py major "Rewrite"  # Manual: bump major with note
"""

import json
import os
import subprocess
import sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
VERSION_FILE = os.path.join(SCRIPT_DIR, 'VERSION.json')


def load_version():
    try:
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"version": "0.0.0", "codename": "", "build": 0, "updated": "", "changelog": []}


def save_version(data):
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    f.close()


def bump(data, bump_type, note=None):
    parts = data['version'].split('.')
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    else:
        patch += 1

    old_ver = data['version']
    data['version'] = f"{major}.{minor}.{patch}"
    data['build'] = data.get('build', 0) + 1
    data['updated'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if note:
        entry = f"v{data['version']} - {note}"
    else:
        entry = f"v{data['version']} - {bump_type} bump"

    data['changelog'].insert(0, entry)
    data['changelog'] = data['changelog'][:30]  # Keep last 30 entries

    return data, old_ver


def detect_bump_type():
    """Analyze staged git changes to determine bump type."""

    # Get commit message from file (when called from pre-commit, message isn't available yet)
    # So we analyze staged files instead
    try:
        staged = subprocess.check_output(
            ['git', 'diff', '--cached', '--name-status'],
            cwd=SCRIPT_DIR, text=True, timeout=10
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return 'patch', 'Auto version bump'

    if not staged:
        return 'patch', 'Auto version bump'

    lines = staged.split('\n')
    added_files = []
    modified_files = []
    deleted_files = []

    for line in lines:
        parts = line.split('\t')
        if len(parts) < 2:
            continue
        status, filepath = parts[0], parts[1]
        if filepath == 'VERSION.json':
            continue  # Skip VERSION.json itself
        if status.startswith('A'):
            added_files.append(filepath)
        elif status.startswith('M'):
            modified_files.append(filepath)
        elif status.startswith('D'):
            deleted_files.append(filepath)

    all_files = added_files + modified_files + deleted_files

    # Check for major changes
    major_indicators = False
    try:
        diff_stat = subprocess.check_output(
            ['git', 'diff', '--cached', '--stat'],
            cwd=SCRIPT_DIR, text=True, timeout=10
        )
        # If system_panel_app.py has 500+ line changes, it's likely a major rewrite
        for line in diff_stat.split('\n'):
            if 'system_panel_app.py' in line:
                # Extract insertions+deletions count
                numbers = [int(s) for s in line.split() if s.isdigit()]
                if numbers and numbers[-1] > 500:
                    major_indicators = True
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    if major_indicators:
        return 'major', auto_generate_note(added_files, modified_files, deleted_files)

    # Check for new feature files
    new_feature_files = [f for f in added_files if f.endswith(('.py', '.js', '.html', '.json'))
                         and not f.startswith('.')]
    if len(new_feature_files) >= 2:
        return 'minor', auto_generate_note(added_files, modified_files, deleted_files)

    # Default: patch
    return 'patch', auto_generate_note(added_files, modified_files, deleted_files)


def auto_generate_note(added, modified, deleted):
    """Generate a short changelog note from file changes."""
    parts = []
    if added:
        names = [os.path.basename(f) for f in added[:3]]
        parts.append(f"Added: {', '.join(names)}")
    if modified:
        names = [os.path.basename(f) for f in modified[:3]]
        parts.append(f"Updated: {', '.join(names)}")
    if deleted:
        names = [os.path.basename(f) for f in deleted[:3]]
        parts.append(f"Removed: {', '.join(names)}")
    return '; '.join(parts) if parts else 'Auto version bump'


def main():
    data = load_version()
    old_version = data['version']

    if len(sys.argv) >= 2:
        # Manual mode: version_bump.py <type> [note]
        bump_type = sys.argv[1]
        if bump_type not in ('major', 'minor', 'patch'):
            print(f"Error: Invalid bump type '{bump_type}'. Use: major, minor, patch")
            sys.exit(1)
        note = sys.argv[2] if len(sys.argv) >= 3 else None
    else:
        # Auto mode: detect from git changes
        bump_type, note = detect_bump_type()

    data, old_ver = bump(data, bump_type, note)
    save_version(data)

    print(f"  Version: {old_ver} → {data['version']} ({bump_type})")
    if note:
        print(f"  Note: {note}")

    # Stage the updated VERSION.json
    try:
        subprocess.run(['git', 'add', VERSION_FILE], cwd=SCRIPT_DIR, timeout=10)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass


if __name__ == '__main__':
    main()
