#!/usr/bin/env python3
"""
Version management script for Burly MCP

This script helps manage semantic versioning, validation, and release preparation.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from packaging.version import Version
except ImportError:
    print("Error: packaging library not found. Install with: pip install packaging")
    sys.exit(1)


class VersionManager:
    """Manages semantic versioning for the Burly MCP project."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.init_file = project_root / "src" / "burly_mcp" / "__init__.py"
        self.pyproject_file = project_root / "pyproject.toml"
        
    def get_current_version(self) -> str:
        """Get the current version from __init__.py."""
        if not self.init_file.exists():
            raise FileNotFoundError(f"Version file not found: {self.init_file}")
        
        content = self.init_file.read_text()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        
        if not match:
            raise ValueError("Version not found in __init__.py")
        
        return match.group(1)
    
    def set_version(self, new_version: str) -> None:
        """Update the version in __init__.py."""
        # Validate version format
        try:
            Version(new_version)
        except Exception as e:
            raise ValueError(f"Invalid version format '{new_version}': {e}")
        
        if not self.init_file.exists():
            raise FileNotFoundError(f"Version file not found: {self.init_file}")
        
        content = self.init_file.read_text()
        updated_content = re.sub(
            r'(__version__\s*=\s*["\'])([^"\']+)(["\'])',
            f'\\g<1>{new_version}\\g<3>',
            content
        )
        
        if content == updated_content:
            raise ValueError("Version pattern not found in __init__.py")
        
        self.init_file.write_text(updated_content)
        print(f"✅ Updated version to {new_version} in {self.init_file}")
    
    def bump_version(self, bump_type: str) -> str:
        """Bump version according to semantic versioning rules."""
        current = Version(self.get_current_version())
        
        if bump_type == "major":
            new_version = f"{current.major + 1}.0.0"
        elif bump_type == "minor":
            new_version = f"{current.major}.{current.minor + 1}.0"
        elif bump_type == "patch":
            new_version = f"{current.major}.{current.minor}.{current.micro + 1}"
        else:
            raise ValueError(f"Invalid bump type: {bump_type}. Use: major, minor, patch")
        
        return new_version
    
    def get_git_tags(self) -> List[str]:
        """Get all git tags sorted by version."""
        try:
            result = subprocess.run(
                ["git", "tag", "-l", "v*"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=True
            )
            
            tags = [tag.strip() for tag in result.stdout.split('\n') if tag.strip()]
            
            # Sort by version
            def version_key(tag: str) -> Version:
                try:
                    return Version(tag.lstrip('v'))
                except:
                    return Version("0.0.0")
            
            return sorted(tags, key=version_key)
        
        except subprocess.CalledProcessError:
            return []
    
    def get_commits_since_tag(self, tag: Optional[str] = None) -> List[str]:
        """Get commit messages since the specified tag (or all if no tag)."""
        try:
            if tag:
                cmd = ["git", "log", f"{tag}..HEAD", "--oneline", "--no-merges"]
            else:
                cmd = ["git", "log", "--oneline", "--no-merges", "--max-count=20"]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=True
            )
            
            return [line.strip() for line in result.stdout.split('\n') if line.strip()]
        
        except subprocess.CalledProcessError:
            return []
    
    def analyze_commits(self, commits: List[str]) -> str:
        """Analyze commit messages to determine appropriate version bump."""
        has_breaking = False
        has_feature = False
        has_fix = False
        
        for commit in commits:
            # Check for breaking changes
            if re.search(r'(feat|feature|fix|bugfix)(\(.+\))?!:|BREAKING CHANGE:', commit):
                has_breaking = True
            # Check for features
            elif re.search(r'^[a-f0-9]+ (feat|feature)(\(.+\))?:', commit):
                has_feature = True
            # Check for fixes
            elif re.search(r'^[a-f0-9]+ (fix|bugfix|patch)(\(.+\))?:', commit):
                has_fix = True
        
        if has_breaking:
            return "major"
        elif has_feature:
            return "minor"
        elif has_fix:
            return "patch"
        else:
            return "none"
    
    def suggest_version_bump(self) -> Tuple[str, str]:
        """Suggest version bump based on git history."""
        tags = self.get_git_tags()
        last_tag = tags[-1] if tags else None
        
        commits = self.get_commits_since_tag(last_tag)
        suggested_bump = self.analyze_commits(commits)
        
        return suggested_bump, last_tag or "v0.0.0"
    
    def validate_release_readiness(self) -> Dict[str, bool]:
        """Validate that the project is ready for release."""
        checks = {}
        
        # Check if working directory is clean
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=True
            )
            checks["clean_working_dir"] = len(result.stdout.strip()) == 0
        except subprocess.CalledProcessError:
            checks["clean_working_dir"] = False
        
        # Check if on main branch
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=True
            )
            checks["on_main_branch"] = result.stdout.strip() in ["main", "master"]
        except subprocess.CalledProcessError:
            checks["on_main_branch"] = False
        
        # Check if version files exist and are valid
        try:
            current_version = self.get_current_version()
            Version(current_version)  # Validate format
            checks["valid_version"] = True
        except:
            checks["valid_version"] = False
        
        # Check if pyproject.toml exists
        checks["pyproject_exists"] = self.pyproject_file.exists()
        
        # Check if tests pass (basic check)
        try:
            result = subprocess.run(
                ["python", "-m", "pytest", "--version"],
                capture_output=True,
                cwd=self.project_root,
                check=True
            )
            checks["pytest_available"] = True
        except:
            checks["pytest_available"] = False
        
        return checks
    
    def create_release_notes(self, from_tag: Optional[str] = None) -> str:
        """Generate release notes from git history."""
        commits = self.get_commits_since_tag(from_tag)
        
        if not commits:
            return "No changes since last release."
        
        # Categorize commits
        features = []
        fixes = []
        breaking = []
        other = []
        
        for commit in commits:
            if re.search(r'(feat|feature|fix|bugfix)(\(.+\))?!:|BREAKING CHANGE:', commit):
                breaking.append(commit)
            elif re.search(r'^[a-f0-9]+ (feat|feature)(\(.+\))?:', commit):
                features.append(commit)
            elif re.search(r'^[a-f0-9]+ (fix|bugfix|patch)(\(.+\))?:', commit):
                fixes.append(commit)
            else:
                other.append(commit)
        
        notes = []
        
        if breaking:
            notes.append("## 💥 Breaking Changes")
            for commit in breaking:
                notes.append(f"- {commit}")
            notes.append("")
        
        if features:
            notes.append("## ✨ New Features")
            for commit in features:
                notes.append(f"- {commit}")
            notes.append("")
        
        if fixes:
            notes.append("## 🐛 Bug Fixes")
            for commit in fixes:
                notes.append(f"- {commit}")
            notes.append("")
        
        if other:
            notes.append("## 🔧 Other Changes")
            for commit in other:
                notes.append(f"- {commit}")
            notes.append("")
        
        return "\n".join(notes)


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Manage versions and releases for Burly MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s current                    # Show current version
  %(prog)s bump patch                 # Bump patch version
  %(prog)s set 1.2.3                  # Set specific version
  %(prog)s suggest                    # Suggest version bump from git history
  %(prog)s validate                   # Check release readiness
  %(prog)s notes                      # Generate release notes
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Current version command
    subparsers.add_parser("current", help="Show current version")
    
    # Bump version command
    bump_parser = subparsers.add_parser("bump", help="Bump version")
    bump_parser.add_argument(
        "type", 
        choices=["major", "minor", "patch"],
        help="Type of version bump"
    )
    bump_parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    # Set version command
    set_parser = subparsers.add_parser("set", help="Set specific version")
    set_parser.add_argument("version", help="Version to set (e.g., 1.2.3)")
    set_parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be done without making changes"
    )
    
    # Suggest version command
    subparsers.add_parser("suggest", help="Suggest version bump from git history")
    
    # Validate release readiness
    subparsers.add_parser("validate", help="Validate release readiness")
    
    # Generate release notes
    notes_parser = subparsers.add_parser("notes", help="Generate release notes")
    notes_parser.add_argument(
        "--from-tag",
        help="Generate notes from specific tag (default: last tag)"
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Find project root
    project_root = Path(__file__).parent.parent
    vm = VersionManager(project_root)
    
    try:
        if args.command == "current":
            version = vm.get_current_version()
            print(f"Current version: {version}")
        
        elif args.command == "bump":
            current = vm.get_current_version()
            new_version = vm.bump_version(args.type)
            
            if args.dry_run:
                print(f"Would bump version: {current} → {new_version}")
            else:
                vm.set_version(new_version)
                print(f"Bumped version: {current} → {new_version}")
        
        elif args.command == "set":
            current = vm.get_current_version()
            
            if args.dry_run:
                print(f"Would set version: {current} → {args.version}")
            else:
                vm.set_version(args.version)
                print(f"Set version: {current} → {args.version}")
        
        elif args.command == "suggest":
            suggested_bump, last_tag = vm.suggest_version_bump()
            current = vm.get_current_version()
            
            if suggested_bump == "none":
                print(f"No version bump suggested (current: {current})")
                print("No conventional commits found since last tag")
            else:
                new_version = vm.bump_version(suggested_bump)
                print(f"Suggested bump: {suggested_bump}")
                print(f"Current version: {current}")
                print(f"Suggested version: {new_version}")
                print(f"Based on commits since: {last_tag}")
        
        elif args.command == "validate":
            checks = vm.validate_release_readiness()
            
            print("Release readiness validation:")
            print("=" * 40)
            
            all_passed = True
            for check, passed in checks.items():
                status = "✅" if passed else "❌"
                check_name = check.replace("_", " ").title()
                print(f"{status} {check_name}")
                if not passed:
                    all_passed = False
            
            print("=" * 40)
            if all_passed:
                print("🎉 Ready for release!")
            else:
                print("⚠️  Not ready for release. Fix issues above.")
                sys.exit(1)
        
        elif args.command == "notes":
            from_tag = getattr(args, 'from_tag', None)
            notes = vm.create_release_notes(from_tag)
            print("Release Notes:")
            print("=" * 40)
            print(notes)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()