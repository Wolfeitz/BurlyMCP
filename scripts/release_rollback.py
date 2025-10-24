#!/usr/bin/env python3
"""
Release rollback script for Burly MCP

This script provides automated rollback capabilities for failed releases,
including reverting version changes, removing tags, and cleaning up artifacts.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from packaging.version import Version
except ImportError:
    print("Error: packaging library not found. Install with: pip install packaging")
    sys.exit(1)


class ReleaseRollback:
    """Handles release rollback operations."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.init_file = project_root / "src" / "burly_mcp" / "__init__.py"
        
    def get_current_version(self) -> str:
        """Get the current version from __init__.py."""
        if not self.init_file.exists():
            raise FileNotFoundError(f"Version file not found: {self.init_file}")
        
        import re
        content = self.init_file.read_text()
        match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
        
        if not match:
            raise ValueError("Version not found in __init__.py")
        
        return match.group(1)
    
    def set_version(self, new_version: str) -> None:
        """Update the version in __init__.py."""
        import re
        
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
        print(f"✅ Reverted version to {new_version} in {self.init_file}")
    
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
            
            return sorted(tags, key=version_key, reverse=True)
        
        except subprocess.CalledProcessError:
            return []
    
    def get_previous_version(self, current_tag: str) -> Optional[str]:
        """Get the previous version tag."""
        tags = self.get_git_tags()
        
        try:
            current_index = tags.index(current_tag)
            if current_index + 1 < len(tags):
                return tags[current_index + 1]
        except ValueError:
            pass
        
        return None
    
    def check_git_status(self) -> Tuple[bool, List[str]]:
        """Check git repository status."""
        issues = []
        
        try:
            # Check if working directory is clean
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=True
            )
            
            if result.stdout.strip():
                issues.append("Working directory has uncommitted changes")
            
            # Check current branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                check=True
            )
            
            current_branch = result.stdout.strip()
            if current_branch not in ["main", "master"]:
                issues.append(f"Not on main branch (current: {current_branch})")
            
            return len(issues) == 0, issues
        
        except subprocess.CalledProcessError as e:
            issues.append(f"Git command failed: {e}")
            return False, issues
    
    def remove_git_tag(self, tag: str, remote: bool = True) -> bool:
        """Remove a git tag locally and optionally from remote."""
        try:
            # Remove local tag
            subprocess.run(
                ["git", "tag", "-d", tag],
                cwd=self.project_root,
                check=True,
                capture_output=True
            )
            print(f"✅ Removed local tag: {tag}")
            
            if remote:
                # Remove remote tag
                subprocess.run(
                    ["git", "push", "origin", "--delete", tag],
                    cwd=self.project_root,
                    check=True,
                    capture_output=True
                )
                print(f"✅ Removed remote tag: {tag}")
            
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to remove tag {tag}: {e}")
            return False
    
    def revert_to_commit(self, commit_hash: str) -> bool:
        """Revert to a specific commit."""
        try:
            # Create a revert commit
            subprocess.run(
                ["git", "revert", "--no-edit", commit_hash],
                cwd=self.project_root,
                check=True,
                capture_output=True
            )
            print(f"✅ Created revert commit for {commit_hash}")
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to revert commit {commit_hash}: {e}")
            return False
    
    def reset_to_previous_version(self, previous_tag: str) -> bool:
        """Reset repository to previous version tag."""
        try:
            # Reset to previous tag
            subprocess.run(
                ["git", "reset", "--hard", previous_tag],
                cwd=self.project_root,
                check=True,
                capture_output=True
            )
            print(f"✅ Reset to previous version: {previous_tag}")
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to reset to {previous_tag}: {e}")
            return False
    
    def check_release_artifacts(self, version: str) -> Dict[str, bool]:
        """Check if release artifacts exist and can be removed."""
        artifacts = {
            "github_release": False,
            "pypi_package": False,
            "docker_image": False
        }
        
        # Check GitHub release
        try:
            result = subprocess.run([
                "gh", "release", "view", f"v{version}"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            artifacts["github_release"] = result.returncode == 0
        except FileNotFoundError:
            print("⚠️ GitHub CLI not available, cannot check GitHub releases")
        
        # Check PyPI package (basic check)
        try:
            import requests
            response = requests.get(f"https://pypi.org/pypi/burly-mingo-mcp/{version}/json", timeout=10)
            artifacts["pypi_package"] = response.status_code == 200
        except:
            print("⚠️ Cannot check PyPI package availability")
        
        # Check Docker image
        try:
            result = subprocess.run([
                "docker", "manifest", "inspect", f"ghcr.io/{self.get_repo_name()}:{version}"
            ], capture_output=True, text=True)
            
            artifacts["docker_image"] = result.returncode == 0
        except FileNotFoundError:
            print("⚠️ Docker not available, cannot check Docker images")
        
        return artifacts
    
    def get_repo_name(self) -> str:
        """Get repository name from git remote."""
        try:
            result = subprocess.run([
                "git", "remote", "get-url", "origin"
            ], capture_output=True, text=True, cwd=self.project_root, check=True)
            
            url = result.stdout.strip()
            # Extract owner/repo from various URL formats
            if "github.com" in url:
                if url.endswith(".git"):
                    url = url[:-4]
                return url.split("github.com/")[-1]
            
            return "unknown/repo"
        except:
            return "unknown/repo"
    
    def remove_github_release(self, version: str) -> bool:
        """Remove GitHub release."""
        try:
            subprocess.run([
                "gh", "release", "delete", f"v{version}", "--yes"
            ], cwd=self.project_root, check=True, capture_output=True)
            
            print(f"✅ Removed GitHub release: v{version}")
            return True
        
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to remove GitHub release v{version}: {e}")
            return False
        except FileNotFoundError:
            print("❌ GitHub CLI not available")
            return False
    
    def create_rollback_plan(self, failed_version: str) -> Dict:
        """Create a rollback execution plan."""
        plan = {
            "failed_version": failed_version,
            "failed_tag": f"v{failed_version}",
            "previous_version": None,
            "previous_tag": None,
            "actions": [],
            "artifacts": {}
        }
        
        # Find previous version
        previous_tag = self.get_previous_version(f"v{failed_version}")
        if previous_tag:
            plan["previous_tag"] = previous_tag
            plan["previous_version"] = previous_tag.lstrip('v')
        
        # Check what artifacts exist
        plan["artifacts"] = self.check_release_artifacts(failed_version)
        
        # Plan actions
        if plan["artifacts"]["github_release"]:
            plan["actions"].append({
                "type": "remove_github_release",
                "description": f"Remove GitHub release v{failed_version}",
                "critical": True
            })
        
        plan["actions"].append({
            "type": "remove_git_tag",
            "description": f"Remove git tag v{failed_version}",
            "critical": True
        })
        
        if plan["previous_version"]:
            plan["actions"].append({
                "type": "revert_version",
                "description": f"Revert version from {failed_version} to {plan['previous_version']}",
                "critical": True
            })
        
        plan["actions"].append({
            "type": "commit_rollback",
            "description": "Commit rollback changes",
            "critical": True
        })
        
        # Add warnings for artifacts that can't be automatically removed
        if plan["artifacts"]["pypi_package"]:
            plan["actions"].append({
                "type": "manual_warning",
                "description": f"⚠️ MANUAL ACTION REQUIRED: PyPI package {failed_version} cannot be automatically removed",
                "critical": False
            })
        
        if plan["artifacts"]["docker_image"]:
            plan["actions"].append({
                "type": "manual_warning", 
                "description": f"⚠️ MANUAL ACTION REQUIRED: Docker image {failed_version} should be manually removed or marked as deprecated",
                "critical": False
            })
        
        return plan
    
    def execute_rollback_plan(self, plan: Dict, dry_run: bool = False) -> bool:
        """Execute the rollback plan."""
        print(f"{'🔍 DRY RUN: ' if dry_run else '🚀 '}Executing rollback plan...")
        print("=" * 60)
        
        success = True
        
        for action in plan["actions"]:
            action_type = action["type"]
            description = action["description"]
            critical = action["critical"]
            
            print(f"{'[DRY RUN] ' if dry_run else ''}📋 {description}")
            
            if dry_run:
                print(f"  Would execute: {action_type}")
                continue
            
            try:
                if action_type == "remove_github_release":
                    result = self.remove_github_release(plan["failed_version"])
                
                elif action_type == "remove_git_tag":
                    result = self.remove_git_tag(plan["failed_tag"])
                
                elif action_type == "revert_version":
                    self.set_version(plan["previous_version"])
                    result = True
                
                elif action_type == "commit_rollback":
                    subprocess.run([
                        "git", "add", str(self.init_file)
                    ], cwd=self.project_root, check=True)
                    
                    subprocess.run([
                        "git", "commit", "-m", f"chore: rollback version to {plan['previous_version']}"
                    ], cwd=self.project_root, check=True)
                    
                    subprocess.run([
                        "git", "push", "origin", "main"
                    ], cwd=self.project_root, check=True)
                    
                    print("✅ Committed and pushed rollback changes")
                    result = True
                
                elif action_type == "manual_warning":
                    print(f"  {description}")
                    result = True
                
                else:
                    print(f"  ❌ Unknown action type: {action_type}")
                    result = False
                
                if not result and critical:
                    success = False
                    print(f"  ❌ Critical action failed: {description}")
                
            except Exception as e:
                print(f"  ❌ Action failed: {e}")
                if critical:
                    success = False
        
        print("=" * 60)
        
        if dry_run:
            print("🔍 Dry run completed. Use --execute to perform actual rollback.")
        elif success:
            print("🎉 Rollback completed successfully!")
        else:
            print("❌ Rollback completed with errors. Manual intervention may be required.")
        
        return success


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Rollback failed releases for Burly MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s plan 1.2.3                # Create rollback plan for version 1.2.3
  %(prog)s execute 1.2.3             # Execute rollback for version 1.2.3
  %(prog)s status                     # Check current release status
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Plan command
    plan_parser = subparsers.add_parser("plan", help="Create rollback plan")
    plan_parser.add_argument("version", help="Version to rollback (e.g., 1.2.3)")
    
    # Execute command
    execute_parser = subparsers.add_parser("execute", help="Execute rollback")
    execute_parser.add_argument("version", help="Version to rollback (e.g., 1.2.3)")
    execute_parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    execute_parser.add_argument("--force", action="store_true", help="Skip safety checks")
    
    # Status command
    subparsers.add_parser("status", help="Check current release status")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Find project root
    project_root = Path(__file__).parent.parent
    rollback = ReleaseRollback(project_root)
    
    try:
        if args.command == "status":
            current_version = rollback.get_current_version()
            tags = rollback.get_git_tags()
            
            print(f"Current version: {current_version}")
            print(f"Latest tags: {', '.join(tags[:5])}")
            
            # Check git status
            clean, issues = rollback.check_git_status()
            if clean:
                print("✅ Repository is clean")
            else:
                print("⚠️ Repository issues:")
                for issue in issues:
                    print(f"  - {issue}")
        
        elif args.command == "plan":
            plan = rollback.create_rollback_plan(args.version)
            
            print(f"Rollback Plan for v{args.version}")
            print("=" * 40)
            print(f"Failed version: {plan['failed_version']}")
            print(f"Previous version: {plan['previous_version'] or 'None found'}")
            print("")
            
            print("Detected artifacts:")
            for artifact, exists in plan["artifacts"].items():
                status = "✅ Found" if exists else "❌ Not found"
                print(f"  {artifact}: {status}")
            print("")
            
            print("Planned actions:")
            for i, action in enumerate(plan["actions"], 1):
                critical = "🔴 CRITICAL" if action["critical"] else "🟡 WARNING"
                print(f"  {i}. [{critical}] {action['description']}")
            
            print("")
            print("Use 'rollback execute' to perform the rollback.")
        
        elif args.command == "execute":
            if not args.force:
                # Safety checks
                clean, issues = rollback.check_git_status()
                if not clean:
                    print("❌ Repository is not clean:")
                    for issue in issues:
                        print(f"  - {issue}")
                    print("Use --force to override safety checks")
                    sys.exit(1)
            
            plan = rollback.create_rollback_plan(args.version)
            
            if not args.dry_run:
                # Confirm with user
                print(f"⚠️ About to rollback version {args.version}")
                print("This action will:")
                for action in plan["actions"]:
                    if action["critical"]:
                        print(f"  - {action['description']}")
                
                response = input("\nContinue? (yes/no): ")
                if response.lower() not in ["yes", "y"]:
                    print("Rollback cancelled")
                    return
            
            success = rollback.execute_rollback_plan(plan, dry_run=args.dry_run)
            
            if not success:
                sys.exit(1)
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()