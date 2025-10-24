#!/usr/bin/env python3
"""
Release monitoring script for Burly MCP

This script monitors release health, tracks deployment status, and provides
real-time feedback on release success metrics.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


class ReleaseMonitor:
    """Monitors release health and deployment status."""
    
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.repo_name = self.get_repo_name()
        
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
    
    def check_github_release(self, version: str) -> Dict:
        """Check GitHub release status."""
        status = {
            "exists": False,
            "published": False,
            "draft": False,
            "prerelease": False,
            "assets": [],
            "created_at": None,
            "published_at": None,
            "error": None
        }
        
        try:
            # Use GitHub CLI if available
            result = subprocess.run([
                "gh", "release", "view", f"v{version}", "--json", 
                "name,tagName,isDraft,isPrerelease,assets,createdAt,publishedAt"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                status.update({
                    "exists": True,
                    "published": not data.get("isDraft", True),
                    "draft": data.get("isDraft", False),
                    "prerelease": data.get("isPrerelease", False),
                    "assets": [asset["name"] for asset in data.get("assets", [])],
                    "created_at": data.get("createdAt"),
                    "published_at": data.get("publishedAt")
                })
            else:
                status["error"] = "Release not found"
        
        except FileNotFoundError:
            # Fallback to GitHub API
            try:
                url = f"https://api.github.com/repos/{self.repo_name}/releases/tags/v{version}"
                response = requests.get(url, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    status.update({
                        "exists": True,
                        "published": not data.get("draft", True),
                        "draft": data.get("draft", False),
                        "prerelease": data.get("prerelease", False),
                        "assets": [asset["name"] for asset in data.get("assets", [])],
                        "created_at": data.get("created_at"),
                        "published_at": data.get("published_at")
                    })
                else:
                    status["error"] = f"API request failed: {response.status_code}"
            
            except Exception as e:
                status["error"] = f"GitHub CLI not available and API failed: {e}"
        
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    def check_pypi_package(self, version: str) -> Dict:
        """Check PyPI package availability and download stats."""
        status = {
            "exists": False,
            "version_available": False,
            "upload_time": None,
            "files": [],
            "downloads": {},
            "error": None
        }
        
        try:
            # Check package existence and version
            url = f"https://pypi.org/pypi/burly-mingo-mcp/{version}/json"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                status.update({
                    "exists": True,
                    "version_available": True,
                    "upload_time": data["info"].get("upload_time"),
                    "files": [f["filename"] for f in data.get("urls", [])]
                })
            elif response.status_code == 404:
                # Check if package exists at all
                general_url = "https://pypi.org/pypi/burly-mingo-mcp/json"
                general_response = requests.get(general_url, timeout=10)
                
                if general_response.status_code == 200:
                    status["exists"] = True
                    status["error"] = f"Version {version} not found"
                else:
                    status["error"] = "Package not found on PyPI"
            else:
                status["error"] = f"PyPI API error: {response.status_code}"
            
            # Get download stats if package exists
            if status["exists"]:
                try:
                    stats_url = f"https://pypistats.org/api/packages/burly-mingo-mcp/recent"
                    stats_response = requests.get(stats_url, timeout=10)
                    
                    if stats_response.status_code == 200:
                        stats_data = stats_response.json()
                        status["downloads"] = stats_data.get("data", {})
                except:
                    pass  # Download stats are optional
        
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    def check_docker_image(self, version: str) -> Dict:
        """Check Docker image availability and metadata."""
        status = {
            "exists": False,
            "platforms": [],
            "size": None,
            "created": None,
            "digest": None,
            "error": None
        }
        
        try:
            image_ref = f"ghcr.io/{self.repo_name}:{version}"
            
            # Check if image exists
            result = subprocess.run([
                "docker", "manifest", "inspect", image_ref
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                manifest = json.loads(result.stdout)
                status["exists"] = True
                
                # Extract platform information
                if "manifests" in manifest:
                    # Multi-platform manifest
                    platforms = []
                    for m in manifest["manifests"]:
                        platform = m.get("platform", {})
                        arch = platform.get("architecture", "unknown")
                        os = platform.get("os", "unknown")
                        platforms.append(f"{os}/{arch}")
                    status["platforms"] = platforms
                else:
                    # Single platform
                    status["platforms"] = ["linux/amd64"]  # Default assumption
                
                # Get image details
                inspect_result = subprocess.run([
                    "docker", "inspect", image_ref
                ], capture_output=True, text=True)
                
                if inspect_result.returncode == 0:
                    inspect_data = json.loads(inspect_result.stdout)[0]
                    status.update({
                        "size": inspect_data.get("Size"),
                        "created": inspect_data.get("Created"),
                        "digest": inspect_data.get("RepoDigests", [None])[0]
                    })
            else:
                status["error"] = "Image not found or not accessible"
        
        except FileNotFoundError:
            status["error"] = "Docker not available"
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    def check_ci_pipeline(self, version: str) -> Dict:
        """Check CI/CD pipeline status for the release."""
        status = {
            "workflow_runs": [],
            "latest_status": None,
            "error": None
        }
        
        try:
            # Get workflow runs for the release tag
            result = subprocess.run([
                "gh", "run", "list", "--branch", f"v{version}", "--json",
                "status,conclusion,workflowName,createdAt,updatedAt,url"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                runs = json.loads(result.stdout)
                status["workflow_runs"] = runs
                
                if runs:
                    latest_run = runs[0]  # Most recent run
                    status["latest_status"] = {
                        "status": latest_run.get("status"),
                        "conclusion": latest_run.get("conclusion"),
                        "workflow": latest_run.get("workflowName"),
                        "url": latest_run.get("url")
                    }
            else:
                status["error"] = "Failed to get workflow runs"
        
        except FileNotFoundError:
            status["error"] = "GitHub CLI not available"
        except Exception as e:
            status["error"] = str(e)
        
        return status
    
    def generate_health_score(self, checks: Dict) -> Tuple[int, List[str]]:
        """Generate a health score (0-100) based on release checks."""
        score = 0
        issues = []
        
        # GitHub Release (25 points)
        github = checks.get("github_release", {})
        if github.get("exists") and github.get("published"):
            score += 25
        elif github.get("exists"):
            score += 15
            issues.append("GitHub release exists but not published")
        else:
            issues.append("GitHub release not found")
        
        # PyPI Package (25 points)
        pypi = checks.get("pypi_package", {})
        if pypi.get("version_available"):
            score += 25
        elif pypi.get("exists"):
            score += 10
            issues.append("PyPI package exists but version not available")
        else:
            issues.append("PyPI package not found")
        
        # Docker Image (25 points)
        docker = checks.get("docker_image", {})
        if docker.get("exists"):
            score += 20
            if len(docker.get("platforms", [])) > 1:
                score += 5  # Bonus for multi-platform
        else:
            issues.append("Docker image not found")
        
        # CI Pipeline (25 points)
        ci = checks.get("ci_pipeline", {})
        latest_status = ci.get("latest_status", {})
        if latest_status:
            if latest_status.get("conclusion") == "success":
                score += 25
            elif latest_status.get("status") == "in_progress":
                score += 15
                issues.append("CI pipeline still running")
            else:
                score += 5
                issues.append(f"CI pipeline failed: {latest_status.get('conclusion')}")
        else:
            issues.append("No CI pipeline information available")
        
        return min(score, 100), issues
    
    def monitor_release(self, version: str, duration_minutes: int = 30, 
                       check_interval: int = 60) -> Dict:
        """Monitor a release for a specified duration."""
        print(f"🔍 Starting release monitoring for v{version}")
        print(f"Duration: {duration_minutes} minutes, Check interval: {check_interval} seconds")
        print("=" * 60)
        
        start_time = datetime.now()
        end_time = start_time + timedelta(minutes=duration_minutes)
        
        monitoring_data = {
            "version": version,
            "start_time": start_time.isoformat(),
            "checks": [],
            "final_status": None
        }
        
        check_count = 0
        
        while datetime.now() < end_time:
            check_count += 1
            current_time = datetime.now()
            
            print(f"\n📊 Check #{check_count} at {current_time.strftime('%H:%M:%S')}")
            print("-" * 40)
            
            # Perform all checks
            checks = {
                "timestamp": current_time.isoformat(),
                "github_release": self.check_github_release(version),
                "pypi_package": self.check_pypi_package(version),
                "docker_image": self.check_docker_image(version),
                "ci_pipeline": self.check_ci_pipeline(version)
            }
            
            # Calculate health score
            health_score, issues = self.generate_health_score(checks)
            checks["health_score"] = health_score
            checks["issues"] = issues
            
            # Display results
            self.display_check_results(checks)
            
            monitoring_data["checks"].append(checks)
            
            # Check if we've reached 100% health
            if health_score == 100:
                print(f"\n🎉 Release v{version} is fully healthy!")
                monitoring_data["final_status"] = "success"
                break
            
            # Wait for next check
            if datetime.now() < end_time:
                time.sleep(check_interval)
        
        # Final summary
        if monitoring_data["final_status"] != "success":
            final_checks = monitoring_data["checks"][-1] if monitoring_data["checks"] else {}
            final_score = final_checks.get("health_score", 0)
            
            if final_score >= 80:
                monitoring_data["final_status"] = "mostly_healthy"
            elif final_score >= 50:
                monitoring_data["final_status"] = "partially_healthy"
            else:
                monitoring_data["final_status"] = "unhealthy"
        
        self.display_final_summary(monitoring_data)
        
        return monitoring_data
    
    def display_check_results(self, checks: Dict) -> None:
        """Display the results of a single check."""
        # GitHub Release
        github = checks["github_release"]
        if github.get("exists"):
            status = "✅ Published" if github.get("published") else "🟡 Draft"
            print(f"GitHub Release: {status}")
            if github.get("assets"):
                print(f"  Assets: {', '.join(github['assets'])}")
        else:
            print(f"GitHub Release: ❌ Not found ({github.get('error', 'Unknown error')})")
        
        # PyPI Package
        pypi = checks["pypi_package"]
        if pypi.get("version_available"):
            print(f"PyPI Package: ✅ Available")
            if pypi.get("files"):
                print(f"  Files: {', '.join(pypi['files'])}")
        else:
            print(f"PyPI Package: ❌ Not available ({pypi.get('error', 'Unknown error')})")
        
        # Docker Image
        docker = checks["docker_image"]
        if docker.get("exists"):
            platforms = ", ".join(docker.get("platforms", []))
            print(f"Docker Image: ✅ Available ({platforms})")
            if docker.get("size"):
                size_mb = docker["size"] / (1024 * 1024)
                print(f"  Size: {size_mb:.1f} MB")
        else:
            print(f"Docker Image: ❌ Not found ({docker.get('error', 'Unknown error')})")
        
        # CI Pipeline
        ci = checks["ci_pipeline"]
        latest = ci.get("latest_status")
        if latest:
            status_emoji = {
                "success": "✅",
                "failure": "❌", 
                "cancelled": "🟡",
                "in_progress": "🔄"
            }.get(latest.get("conclusion") or latest.get("status"), "❓")
            
            print(f"CI Pipeline: {status_emoji} {latest.get('conclusion') or latest.get('status')}")
            print(f"  Workflow: {latest.get('workflow')}")
        else:
            print(f"CI Pipeline: ❓ No information ({ci.get('error', 'Unknown error')})")
        
        # Health Score
        health_score = checks.get("health_score", 0)
        score_emoji = "🟢" if health_score >= 80 else "🟡" if health_score >= 50 else "🔴"
        print(f"\nHealth Score: {score_emoji} {health_score}/100")
        
        if checks.get("issues"):
            print("Issues:")
            for issue in checks["issues"]:
                print(f"  - {issue}")
    
    def display_final_summary(self, monitoring_data: Dict) -> None:
        """Display final monitoring summary."""
        print("\n" + "=" * 60)
        print("📋 RELEASE MONITORING SUMMARY")
        print("=" * 60)
        
        version = monitoring_data["version"]
        final_status = monitoring_data["final_status"]
        
        status_emoji = {
            "success": "🎉",
            "mostly_healthy": "🟢",
            "partially_healthy": "🟡",
            "unhealthy": "🔴"
        }.get(final_status, "❓")
        
        print(f"Version: v{version}")
        print(f"Final Status: {status_emoji} {final_status.replace('_', ' ').title()}")
        
        if monitoring_data["checks"]:
            final_checks = monitoring_data["checks"][-1]
            final_score = final_checks.get("health_score", 0)
            print(f"Final Health Score: {final_score}/100")
            
            if final_checks.get("issues"):
                print("\nRemaining Issues:")
                for issue in final_checks["issues"]:
                    print(f"  - {issue}")
        
        print(f"\nTotal Checks: {len(monitoring_data['checks'])}")
        print(f"Monitoring Duration: {monitoring_data['start_time']} to {datetime.now().isoformat()}")
        
        # Recommendations
        if final_status == "success":
            print("\n✅ Release is fully deployed and healthy!")
        elif final_status == "mostly_healthy":
            print("\n🟢 Release is mostly healthy. Minor issues may resolve automatically.")
        elif final_status == "partially_healthy":
            print("\n🟡 Release has significant issues. Manual intervention may be required.")
        else:
            print("\n🔴 Release is unhealthy. Immediate attention required.")
            print("Consider running rollback procedures if issues persist.")


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Monitor release health and deployment status",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s check 1.2.3               # Single health check for version 1.2.3
  %(prog)s monitor 1.2.3             # Monitor version 1.2.3 for 30 minutes
  %(prog)s monitor 1.2.3 --duration 60 --interval 30  # Custom monitoring
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Check command
    check_parser = subparsers.add_parser("check", help="Single health check")
    check_parser.add_argument("version", help="Version to check (e.g., 1.2.3)")
    
    # Monitor command
    monitor_parser = subparsers.add_parser("monitor", help="Continuous monitoring")
    monitor_parser.add_argument("version", help="Version to monitor (e.g., 1.2.3)")
    monitor_parser.add_argument("--duration", type=int, default=30, 
                               help="Monitoring duration in minutes (default: 30)")
    monitor_parser.add_argument("--interval", type=int, default=60,
                               help="Check interval in seconds (default: 60)")
    monitor_parser.add_argument("--output", help="Save monitoring data to JSON file")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Find project root
    project_root = Path(__file__).parent.parent
    monitor = ReleaseMonitor(project_root)
    
    try:
        if args.command == "check":
            print(f"🔍 Checking release health for v{args.version}")
            print("=" * 50)
            
            checks = {
                "timestamp": datetime.now().isoformat(),
                "github_release": monitor.check_github_release(args.version),
                "pypi_package": monitor.check_pypi_package(args.version),
                "docker_image": monitor.check_docker_image(args.version),
                "ci_pipeline": monitor.check_ci_pipeline(args.version)
            }
            
            health_score, issues = monitor.generate_health_score(checks)
            checks["health_score"] = health_score
            checks["issues"] = issues
            
            monitor.display_check_results(checks)
        
        elif args.command == "monitor":
            monitoring_data = monitor.monitor_release(
                args.version, 
                duration_minutes=args.duration,
                check_interval=args.interval
            )
            
            # Save monitoring data if requested
            if args.output:
                output_file = Path(args.output)
                output_file.write_text(json.dumps(monitoring_data, indent=2))
                print(f"\n💾 Monitoring data saved to: {output_file}")
            
            # Exit with appropriate code based on final status
            final_status = monitoring_data.get("final_status")
            if final_status == "success":
                sys.exit(0)
            elif final_status in ["mostly_healthy", "partially_healthy"]:
                sys.exit(1)
            else:
                sys.exit(2)
    
    except KeyboardInterrupt:
        print("\n\n⏹️ Monitoring interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()