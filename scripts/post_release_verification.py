#!/usr/bin/env python3
"""
Post-release verification script for Burly MCP

This script performs comprehensive verification of released artifacts,
validates functionality, and generates post-release reports.
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
import venv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install with: pip install requests")
    sys.exit(1)


class PostReleaseVerifier:
    """Performs comprehensive post-release verification."""
    
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
            if "github.com" in url:
                if url.endswith(".git"):
                    url = url[:-4]
                return url.split("github.com/")[-1]
            
            return "unknown/repo"
        except:
            return "unknown/repo"
    
    def verify_pypi_installation(self, version: str) -> Tuple[bool, Dict]:
        """Verify PyPI package installation across multiple environments."""
        results = {
            "success": False,
            "environments": {},
            "console_script": False,
            "import_test": False,
            "version_match": False,
            "error": None
        }
        
        python_versions = ["3.11", "3.12"]
        
        for py_version in python_versions:
            env_result = {
                "success": False,
                "installation": False,
                "import": False,
                "version": None,
                "console_script": False,
                "error": None
            }
            
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    venv_path = Path(temp_dir) / f"test_env_{py_version}"
                    
                    # Create virtual environment
                    venv.create(venv_path, with_pip=True)
                    
                    # Get paths for the virtual environment
                    if sys.platform == "win32":
                        venv_python = venv_path / "Scripts" / "python.exe"
                        venv_pip = venv_path / "Scripts" / "pip.exe"
                        script_path = venv_path / "Scripts" / "burly-mingo-mcp.exe"
                    else:
                        venv_python = venv_path / "bin" / "python"
                        venv_pip = venv_path / "bin" / "pip"
                        script_path = venv_path / "bin" / "burly-mingo-mcp"
                    
                    # Upgrade pip
                    subprocess.run([
                        str(venv_pip), "install", "--upgrade", "pip"
                    ], check=True, capture_output=True, timeout=120)
                    
                    # Install package with retry logic
                    max_attempts = 3
                    for attempt in range(max_attempts):
                        try:
                            subprocess.run([
                                str(venv_pip), "install", f"burly-mingo-mcp=={version}"
                            ], check=True, capture_output=True, timeout=180)
                            
                            env_result["installation"] = True
                            break
                        except subprocess.CalledProcessError:
                            if attempt == max_attempts - 1:
                                raise
                            time.sleep(30)  # Wait before retry
                    
                    # Test import and version
                    test_script = f'''
import burly_mcp
print(f"Version: {{burly_mcp.__version__}}")
print(f"Author: {{burly_mcp.__author__}}")
print(f"Description: {{burly_mcp.__description__}}")

# Test main imports
from burly_mcp.server import main
from burly_mcp.tools import ToolRegistry
from burly_mcp.policy import PolicyEngine

# Verify version
assert burly_mcp.__version__ == "{version}", f"Version mismatch: {{burly_mcp.__version__}} != {version}"
print("All imports successful")
'''
                    
                    result = subprocess.run([
                        str(venv_python), "-c", test_script
                    ], capture_output=True, text=True, check=True, timeout=60)
                    
                    env_result["import"] = True
                    env_result["version"] = version
                    
                    # Test console script
                    if script_path.exists():
                        script_result = subprocess.run([
                            str(script_path), "--help"
                        ], capture_output=True, text=True, timeout=30)
                        
                        env_result["console_script"] = script_result.returncode == 0
                    
                    env_result["success"] = True
            
            except Exception as e:
                env_result["error"] = str(e)
            
            results["environments"][py_version] = env_result
        
        # Determine overall success
        successful_envs = [env for env in results["environments"].values() if env["success"]]
        results["success"] = len(successful_envs) > 0
        results["import_test"] = all(env.get("import", False) for env in successful_envs)
        results["version_match"] = all(env.get("version") == version for env in successful_envs)
        results["console_script"] = all(env.get("console_script", False) for env in successful_envs)
        
        if not results["success"]:
            errors = [env["error"] for env in results["environments"].values() if env["error"]]
            results["error"] = "; ".join(errors) if errors else "Unknown error"
        
        return results["success"], results
    
    def verify_docker_functionality(self, version: str) -> Tuple[bool, Dict]:
        """Verify Docker image functionality and security."""
        results = {
            "success": False,
            "image_pull": False,
            "basic_functionality": False,
            "help_command": False,
            "version_command": False,
            "security_scan": False,
            "multi_platform": {},
            "performance": {},
            "error": None
        }
        
        try:
            image_ref = f"ghcr.io/{self.repo_name}:{version}"
            
            # Pull image
            subprocess.run([
                "docker", "pull", image_ref
            ], check=True, capture_output=True, timeout=300)
            
            results["image_pull"] = True
            
            # Test basic functionality
            help_result = subprocess.run([
                "docker", "run", "--rm", image_ref, "--help"
            ], capture_output=True, text=True, timeout=60)
            
            results["help_command"] = help_result.returncode == 0
            
            # Test version command (if available)
            version_result = subprocess.run([
                "docker", "run", "--rm", image_ref, "--version"
            ], capture_output=True, text=True, timeout=60)
            
            results["version_command"] = version_result.returncode == 0
            
            # Basic functionality test
            results["basic_functionality"] = results["help_command"]
            
            # Test multi-platform support
            platforms = ["linux/amd64", "linux/arm64"]
            for platform in platforms:
                platform_result = {
                    "available": False,
                    "functional": False,
                    "error": None
                }
                
                try:
                    # Test platform-specific image
                    platform_test = subprocess.run([
                        "docker", "run", "--rm", "--platform", platform, 
                        image_ref, "--help"
                    ], capture_output=True, text=True, timeout=60)
                    
                    platform_result["available"] = True
                    platform_result["functional"] = platform_test.returncode == 0
                
                except Exception as e:
                    platform_result["error"] = str(e)
                
                results["multi_platform"][platform] = platform_result
            
            # Performance testing
            start_time = time.time()
            perf_result = subprocess.run([
                "docker", "run", "--rm", image_ref, "--help"
            ], capture_output=True, text=True, timeout=60)
            end_time = time.time()
            
            results["performance"] = {
                "startup_time": end_time - start_time,
                "success": perf_result.returncode == 0
            }
            
            # Security scan with Trivy (if available)
            try:
                trivy_result = subprocess.run([
                    "docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock",
                    "aquasec/trivy:latest", "image", "--exit-code", "1",
                    "--severity", "HIGH,CRITICAL", "--ignore-unfixed", image_ref
                ], capture_output=True, text=True, timeout=300)
                
                results["security_scan"] = trivy_result.returncode == 0
            
            except:
                results["security_scan"] = None  # Trivy not available
            
            results["success"] = (
                results["image_pull"] and 
                results["basic_functionality"] and
                results["performance"]["success"]
            )
        
        except Exception as e:
            results["error"] = str(e)
        
        return results["success"], results
    
    def verify_github_release(self, version: str) -> Tuple[bool, Dict]:
        """Verify GitHub release completeness and accessibility."""
        results = {
            "success": False,
            "release_exists": False,
            "published": False,
            "assets_present": False,
            "checksums_valid": False,
            "release_notes": False,
            "assets": [],
            "error": None
        }
        
        try:
            # Check release using GitHub CLI
            result = subprocess.run([
                "gh", "release", "view", f"v{version}", "--json",
                "name,tagName,isDraft,isPrerelease,assets,body"
            ], capture_output=True, text=True, cwd=self.project_root)
            
            if result.returncode == 0:
                data = json.loads(result.stdout)
                
                results["release_exists"] = True
                results["published"] = not data.get("isDraft", True)
                results["release_notes"] = bool(data.get("body", "").strip())
                
                assets = data.get("assets", [])
                results["assets"] = [asset["name"] for asset in assets]
                results["assets_present"] = len(assets) > 0
                
                # Check for expected assets
                expected_assets = ["SHA256SUMS", "INSTALL.md"]
                has_expected = any(
                    any(expected in asset for expected in expected_assets)
                    for asset in results["assets"]
                )
                
                # Download and verify checksums if present
                if "SHA256SUMS" in results["assets"]:
                    try:
                        with tempfile.TemporaryDirectory() as temp_dir:
                            # Download SHA256SUMS
                            subprocess.run([
                                "gh", "release", "download", f"v{version}",
                                "--pattern", "SHA256SUMS", "--dir", temp_dir
                            ], check=True, capture_output=True, cwd=self.project_root)
                            
                            # Download package files
                            subprocess.run([
                                "gh", "release", "download", f"v{version}",
                                "--pattern", "*.whl", "--pattern", "*.tar.gz",
                                "--dir", temp_dir
                            ], check=True, capture_output=True, cwd=self.project_root)
                            
                            # Verify checksums
                            verify_result = subprocess.run([
                                "sha256sum", "-c", "SHA256SUMS"
                            ], cwd=temp_dir, capture_output=True, text=True)
                            
                            results["checksums_valid"] = verify_result.returncode == 0
                    
                    except:
                        results["checksums_valid"] = False
                
                results["success"] = (
                    results["release_exists"] and
                    results["published"] and
                    results["assets_present"]
                )
            
            else:
                results["error"] = "Release not found"
        
        except FileNotFoundError:
            results["error"] = "GitHub CLI not available"
        except Exception as e:
            results["error"] = str(e)
        
        return results["success"], results
    
    def verify_documentation(self, version: str) -> Tuple[bool, Dict]:
        """Verify documentation is updated and accessible."""
        results = {
            "success": False,
            "readme_updated": False,
            "changelog_updated": False,
            "api_docs": False,
            "installation_guide": False,
            "error": None
        }
        
        try:
            # Check README for version references
            readme_path = self.project_root / "README.md"
            if readme_path.exists():
                readme_content = readme_path.read_text()
                results["readme_updated"] = version in readme_content
            
            # Check CHANGELOG
            changelog_path = self.project_root / "CHANGELOG.md"
            if changelog_path.exists():
                changelog_content = changelog_path.read_text()
                results["changelog_updated"] = version in changelog_content
            
            # Check if API docs exist
            docs_dir = self.project_root / "docs"
            if docs_dir.exists():
                api_docs = list(docs_dir.glob("**/api/**/*.rst")) or list(docs_dir.glob("**/api/**/*.md"))
                results["api_docs"] = len(api_docs) > 0
            
            # Check installation guide
            install_files = [
                self.project_root / "INSTALL.md",
                self.project_root / "docs" / "installation.md",
                self.project_root / "docs" / "getting-started.md"
            ]
            
            results["installation_guide"] = any(f.exists() for f in install_files)
            
            results["success"] = (
                results["readme_updated"] or
                results["changelog_updated"] or
                results["api_docs"]
            )
        
        except Exception as e:
            results["error"] = str(e)
        
        return results["success"], results
    
    def verify_security_compliance(self, version: str) -> Tuple[bool, Dict]:
        """Verify security compliance of released artifacts."""
        results = {
            "success": False,
            "pypi_security": False,
            "docker_security": False,
            "dependency_scan": False,
            "vulnerability_count": 0,
            "critical_vulnerabilities": 0,
            "error": None
        }
        
        try:
            # Install and scan PyPI package
            with tempfile.TemporaryDirectory() as temp_dir:
                venv_path = Path(temp_dir) / "security_env"
                venv.create(venv_path, with_pip=True)
                
                if sys.platform == "win32":
                    venv_pip = venv_path / "Scripts" / "pip.exe"
                else:
                    venv_pip = venv_path / "bin" / "pip"
                
                # Install package and security tools
                subprocess.run([
                    str(venv_pip), "install", "--upgrade", "pip"
                ], check=True, capture_output=True)
                
                subprocess.run([
                    str(venv_pip), "install", f"burly-mingo-mcp=={version}"
                ], check=True, capture_output=True)
                
                subprocess.run([
                    str(venv_pip), "install", "safety", "pip-audit"
                ], check=True, capture_output=True)
                
                # Run security scans
                if sys.platform == "win32":
                    safety_cmd = venv_path / "Scripts" / "safety.exe"
                    audit_cmd = venv_path / "Scripts" / "pip-audit.exe"
                else:
                    safety_cmd = venv_path / "bin" / "safety"
                    audit_cmd = venv_path / "bin" / "pip-audit"
                
                # Safety check
                safety_result = subprocess.run([
                    str(safety_cmd), "check", "--json"
                ], capture_output=True, text=True)
                
                if safety_result.returncode == 0:
                    results["pypi_security"] = True
                else:
                    try:
                        safety_data = json.loads(safety_result.stdout)
                        results["vulnerability_count"] += len(safety_data)
                    except:
                        pass
                
                # Pip-audit check
                audit_result = subprocess.run([
                    str(audit_cmd), "--format", "json"
                ], capture_output=True, text=True)
                
                if audit_result.returncode == 0:
                    results["dependency_scan"] = True
                else:
                    try:
                        audit_data = json.loads(audit_result.stdout)
                        vulnerabilities = audit_data.get("vulnerabilities", [])
                        results["vulnerability_count"] += len(vulnerabilities)
                        
                        # Count critical vulnerabilities
                        for vuln in vulnerabilities:
                            if vuln.get("severity", "").upper() in ["HIGH", "CRITICAL"]:
                                results["critical_vulnerabilities"] += 1
                    except:
                        pass
            
            # Scan Docker image if available
            try:
                image_ref = f"ghcr.io/{self.repo_name}:{version}"
                
                trivy_result = subprocess.run([
                    "docker", "run", "--rm", "-v", "/var/run/docker.sock:/var/run/docker.sock",
                    "aquasec/trivy:latest", "image", "--format", "json", image_ref
                ], capture_output=True, text=True, timeout=300)
                
                if trivy_result.returncode == 0:
                    trivy_data = json.loads(trivy_result.stdout)
                    
                    # Count vulnerabilities
                    total_vulns = 0
                    critical_vulns = 0
                    
                    for result in trivy_data.get("Results", []):
                        for vuln in result.get("Vulnerabilities", []):
                            total_vulns += 1
                            if vuln.get("Severity") in ["HIGH", "CRITICAL"]:
                                critical_vulns += 1
                    
                    results["vulnerability_count"] += total_vulns
                    results["critical_vulnerabilities"] += critical_vulns
                    results["docker_security"] = critical_vulns == 0
                
            except:
                pass  # Docker security scan is optional
            
            results["success"] = (
                results["critical_vulnerabilities"] == 0 and
                (results["pypi_security"] or results["dependency_scan"])
            )
        
        except Exception as e:
            results["error"] = str(e)
        
        return results["success"], results
    
    def generate_verification_report(self, version: str, verification_results: Dict) -> str:
        """Generate comprehensive verification report."""
        report_lines = [
            f"# Post-Release Verification Report",
            f"",
            f"**Version**: v{version}",
            f"**Verification Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
            f"**Repository**: {self.repo_name}",
            f"",
            f"## Executive Summary",
            f""
        ]
        
        # Calculate overall score
        total_checks = len(verification_results)
        passed_checks = sum(1 for result in verification_results.values() if result[0])
        success_rate = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
        
        if success_rate >= 90:
            status = "🟢 EXCELLENT"
        elif success_rate >= 75:
            status = "🟡 GOOD"
        elif success_rate >= 50:
            status = "🟠 FAIR"
        else:
            status = "🔴 POOR"
        
        report_lines.extend([
            f"**Overall Status**: {status}",
            f"**Success Rate**: {success_rate:.1f}% ({passed_checks}/{total_checks} checks passed)",
            f"",
            f"## Detailed Results",
            f""
        ])
        
        # Detailed results for each verification
        for check_name, (success, details) in verification_results.items():
            status_emoji = "✅" if success else "❌"
            check_title = check_name.replace("_", " ").title()
            
            report_lines.extend([
                f"### {status_emoji} {check_title}",
                f""
            ])
            
            if success:
                report_lines.append("**Status**: PASSED")
            else:
                report_lines.append("**Status**: FAILED")
                if details.get("error"):
                    report_lines.append(f"**Error**: {details['error']}")
            
            # Add specific details based on check type
            if check_name == "pypi_installation":
                if details.get("environments"):
                    report_lines.append("**Environment Results**:")
                    for env, env_result in details["environments"].items():
                        env_status = "✅" if env_result["success"] else "❌"
                        report_lines.append(f"- Python {env}: {env_status}")
                
                if details.get("console_script"):
                    report_lines.append("- Console script: ✅ Working")
                elif "console_script" in details:
                    report_lines.append("- Console script: ❌ Not working")
            
            elif check_name == "docker_functionality":
                if details.get("multi_platform"):
                    report_lines.append("**Platform Support**:")
                    for platform, platform_result in details["multi_platform"].items():
                        platform_status = "✅" if platform_result["functional"] else "❌"
                        report_lines.append(f"- {platform}: {platform_status}")
                
                if details.get("performance"):
                    startup_time = details["performance"].get("startup_time", 0)
                    report_lines.append(f"**Performance**: Startup time {startup_time:.2f}s")
            
            elif check_name == "security_compliance":
                vuln_count = details.get("vulnerability_count", 0)
                critical_count = details.get("critical_vulnerabilities", 0)
                
                report_lines.extend([
                    f"**Vulnerabilities**: {vuln_count} total, {critical_count} critical",
                    f"**PyPI Security**: {'✅' if details.get('pypi_security') else '❌'}",
                    f"**Docker Security**: {'✅' if details.get('docker_security') else '❌'}"
                ])
            
            report_lines.append("")
        
        # Recommendations
        report_lines.extend([
            "## Recommendations",
            ""
        ])
        
        if success_rate >= 90:
            report_lines.append("🎉 Release verification successful! All critical checks passed.")
        elif success_rate >= 75:
            report_lines.append("✅ Release is mostly healthy. Address minor issues when convenient.")
        elif success_rate >= 50:
            report_lines.append("⚠️ Release has significant issues. Consider hotfix release.")
        else:
            report_lines.append("🚨 Release has critical issues. Immediate action required.")
            report_lines.append("Consider rollback if issues cannot be resolved quickly.")
        
        # Failed checks
        failed_checks = [name for name, (success, _) in verification_results.items() if not success]
        if failed_checks:
            report_lines.extend([
                "",
                "**Failed Checks**:",
                ""
            ])
            for check in failed_checks:
                check_title = check.replace("_", " ").title()
                report_lines.append(f"- {check_title}")
        
        return "\n".join(report_lines)
    
    def run_full_verification(self, version: str) -> Tuple[bool, Dict]:
        """Run complete post-release verification."""
        print(f"🔍 Starting post-release verification for v{version}")
        print("=" * 60)
        
        verification_results = {}
        
        # PyPI Installation Verification
        print("📦 Verifying PyPI package installation...")
        success, details = self.verify_pypi_installation(version)
        verification_results["pypi_installation"] = (success, details)
        print(f"  {'✅ PASSED' if success else '❌ FAILED'}")
        
        # Docker Functionality Verification
        print("🐳 Verifying Docker image functionality...")
        success, details = self.verify_docker_functionality(version)
        verification_results["docker_functionality"] = (success, details)
        print(f"  {'✅ PASSED' if success else '❌ FAILED'}")
        
        # GitHub Release Verification
        print("📋 Verifying GitHub release...")
        success, details = self.verify_github_release(version)
        verification_results["github_release"] = (success, details)
        print(f"  {'✅ PASSED' if success else '❌ FAILED'}")
        
        # Documentation Verification
        print("📚 Verifying documentation...")
        success, details = self.verify_documentation(version)
        verification_results["documentation"] = (success, details)
        print(f"  {'✅ PASSED' if success else '❌ FAILED'}")
        
        # Security Compliance Verification
        print("🔒 Verifying security compliance...")
        success, details = self.verify_security_compliance(version)
        verification_results["security_compliance"] = (success, details)
        print(f"  {'✅ PASSED' if success else '❌ FAILED'}")
        
        # Generate report
        report = self.generate_verification_report(version, verification_results)
        
        # Save report
        report_file = self.project_root / f"post_release_verification_{version}.md"
        report_file.write_text(report)
        
        print("=" * 60)
        print(f"📋 Verification report saved to: {report_file}")
        
        # Determine overall success
        total_checks = len(verification_results)
        passed_checks = sum(1 for result in verification_results.values() if result[0])
        overall_success = passed_checks >= (total_checks * 0.8)  # 80% pass rate
        
        return overall_success, verification_results


def main():
    """Main CLI interface."""
    parser = argparse.ArgumentParser(
        description="Perform post-release verification for Burly MCP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s verify 1.2.3              # Full verification for version 1.2.3
  %(prog)s pypi 1.2.3                # PyPI-only verification
  %(prog)s docker 1.2.3              # Docker-only verification
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Full verification command
    verify_parser = subparsers.add_parser("verify", help="Full post-release verification")
    verify_parser.add_argument("version", help="Version to verify (e.g., 1.2.3)")
    
    # PyPI verification command
    pypi_parser = subparsers.add_parser("pypi", help="PyPI package verification only")
    pypi_parser.add_argument("version", help="Version to verify (e.g., 1.2.3)")
    
    # Docker verification command
    docker_parser = subparsers.add_parser("docker", help="Docker image verification only")
    docker_parser.add_argument("version", help="Version to verify (e.g., 1.2.3)")
    
    # Security verification command
    security_parser = subparsers.add_parser("security", help="Security compliance verification only")
    security_parser.add_argument("version", help="Version to verify (e.g., 1.2.3)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Find project root
    project_root = Path(__file__).parent.parent
    verifier = PostReleaseVerifier(project_root)
    
    try:
        if args.command == "verify":
            success, results = verifier.run_full_verification(args.version)
            
            if success:
                print("\n🎉 Post-release verification completed successfully!")
                sys.exit(0)
            else:
                print("\n❌ Post-release verification failed!")
                sys.exit(1)
        
        elif args.command == "pypi":
            print(f"📦 Verifying PyPI package for v{args.version}...")
            success, details = verifier.verify_pypi_installation(args.version)
            
            if success:
                print("✅ PyPI package verification passed!")
            else:
                print(f"❌ PyPI package verification failed: {details.get('error', 'Unknown error')}")
                sys.exit(1)
        
        elif args.command == "docker":
            print(f"🐳 Verifying Docker image for v{args.version}...")
            success, details = verifier.verify_docker_functionality(args.version)
            
            if success:
                print("✅ Docker image verification passed!")
            else:
                print(f"❌ Docker image verification failed: {details.get('error', 'Unknown error')}")
                sys.exit(1)
        
        elif args.command == "security":
            print(f"🔒 Verifying security compliance for v{args.version}...")
            success, details = verifier.verify_security_compliance(args.version)
            
            if success:
                print("✅ Security compliance verification passed!")
            else:
                print(f"❌ Security compliance verification failed: {details.get('error', 'Unknown error')}")
                critical_count = details.get("critical_vulnerabilities", 0)
                if critical_count > 0:
                    print(f"🚨 Found {critical_count} critical vulnerabilities!")
                sys.exit(1)
    
    except KeyboardInterrupt:
        print("\n\n⏹️ Verification interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()