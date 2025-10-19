#!/usr/bin/env python3
"""
Coverage validation script for Burly MCP project.

This script runs tests with coverage reporting and validates that coverage
meets the minimum threshold. It generates reports in multiple formats and
provides detailed feedback on coverage gaps.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional


class CoverageChecker:
    """Coverage validation and reporting tool."""
    
    def __init__(self, min_coverage: float = 80.0, project_root: Optional[Path] = None):
        """Initialize coverage checker.
        
        Args:
            min_coverage: Minimum coverage percentage required
            project_root: Project root directory (defaults to script parent)
        """
        self.min_coverage = min_coverage
        self.project_root = project_root or Path(__file__).parent.parent
        self.coverage_file = self.project_root / "coverage.json"
        
    def run_tests_with_coverage(self, test_path: str = "tests/", verbose: bool = False) -> bool:
        """Run tests with coverage reporting.
        
        Args:
            test_path: Path to tests directory
            verbose: Enable verbose output
            
        Returns:
            bool: True if tests passed, False otherwise
        """
        cmd = [
            sys.executable, "-m", "pytest",
            test_path,
            "--cov=burly_mcp",
            "--cov-report=term-missing",
            "--cov-report=html",
            "--cov-report=xml",
            "--cov-report=json",
            f"--cov-fail-under={self.min_coverage}",
        ]
        
        if verbose:
            cmd.append("-v")
            
        print(f"Running tests with coverage: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=not verbose,
                text=True,
                check=False
            )
            
            if not verbose and result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
                
            return result.returncode == 0
            
        except subprocess.SubprocessError as e:
            print(f"Error running tests: {e}", file=sys.stderr)
            return False
    
    def load_coverage_data(self) -> Optional[Dict]:
        """Load coverage data from JSON report.
        
        Returns:
            dict: Coverage data or None if not available
        """
        if not self.coverage_file.exists():
            print(f"Coverage file not found: {self.coverage_file}")
            return None
            
        try:
            with open(self.coverage_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading coverage data: {e}")
            return None
    
    def analyze_coverage(self, coverage_data: Dict) -> Dict[str, float]:
        """Analyze coverage data and extract key metrics.
        
        Args:
            coverage_data: Coverage data from JSON report
            
        Returns:
            dict: Coverage metrics by file
        """
        files_coverage = {}
        
        for filename, file_data in coverage_data.get("files", {}).items():
            summary = file_data.get("summary", {})
            covered_lines = summary.get("covered_lines", 0)
            num_statements = summary.get("num_statements", 0)
            
            if num_statements > 0:
                coverage_percent = (covered_lines / num_statements) * 100
                files_coverage[filename] = coverage_percent
            else:
                files_coverage[filename] = 100.0  # No statements to cover
                
        return files_coverage
    
    def find_low_coverage_files(self, files_coverage: Dict[str, float]) -> List[tuple]:
        """Find files with coverage below threshold.
        
        Args:
            files_coverage: Coverage percentages by file
            
        Returns:
            list: List of (filename, coverage) tuples below threshold
        """
        low_coverage = []
        
        for filename, coverage in files_coverage.items():
            if coverage < self.min_coverage:
                low_coverage.append((filename, coverage))
                
        # Sort by coverage percentage (lowest first)
        low_coverage.sort(key=lambda x: x[1])
        return low_coverage
    
    def generate_coverage_report(self, coverage_data: Dict) -> str:
        """Generate a detailed coverage report.
        
        Args:
            coverage_data: Coverage data from JSON report
            
        Returns:
            str: Formatted coverage report
        """
        total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
        files_coverage = self.analyze_coverage(coverage_data)
        low_coverage_files = self.find_low_coverage_files(files_coverage)
        
        report = []
        report.append("=" * 60)
        report.append("COVERAGE REPORT")
        report.append("=" * 60)
        report.append(f"Overall Coverage: {total_coverage:.2f}%")
        report.append(f"Minimum Required: {self.min_coverage:.2f}%")
        
        if total_coverage >= self.min_coverage:
            report.append("✅ Coverage threshold MET")
        else:
            report.append("❌ Coverage threshold NOT MET")
            
        report.append("")
        report.append(f"Total Files: {len(files_coverage)}")
        report.append(f"Files Below Threshold: {len(low_coverage_files)}")
        
        if low_coverage_files:
            report.append("")
            report.append("FILES NEEDING ATTENTION:")
            report.append("-" * 40)
            
            for filename, coverage in low_coverage_files:
                # Shorten filename for display
                display_name = filename.replace("src/burly_mcp/", "")
                report.append(f"{display_name:<30} {coverage:>6.2f}%")
                
        report.append("")
        report.append("COVERAGE BY MODULE:")
        report.append("-" * 40)
        
        # Group by module
        modules = {}
        for filename, coverage in files_coverage.items():
            if "src/burly_mcp/" in filename:
                module = filename.replace("src/burly_mcp/", "").split("/")[0]
                if module not in modules:
                    modules[module] = []
                modules[module].append(coverage)
        
        for module, coverages in sorted(modules.items()):
            avg_coverage = sum(coverages) / len(coverages)
            status = "✅" if avg_coverage >= self.min_coverage else "❌"
            report.append(f"{status} {module:<20} {avg_coverage:>6.2f}% ({len(coverages)} files)")
            
        return "\n".join(report)
    
    def validate_coverage(self, show_report: bool = True) -> bool:
        """Validate that coverage meets minimum threshold.
        
        Args:
            show_report: Whether to display detailed report
            
        Returns:
            bool: True if coverage is sufficient, False otherwise
        """
        coverage_data = self.load_coverage_data()
        if not coverage_data:
            return False
            
        total_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
        
        if show_report:
            report = self.generate_coverage_report(coverage_data)
            print(report)
            
        return total_coverage >= self.min_coverage
    
    def run_unit_tests_only(self) -> bool:
        """Run only unit tests with coverage.
        
        Returns:
            bool: True if tests passed and coverage is sufficient
        """
        return self.run_tests_with_coverage("tests/unit/")
    
    def run_integration_tests_only(self) -> bool:
        """Run only integration tests with coverage.
        
        Returns:
            bool: True if tests passed and coverage is sufficient
        """
        return self.run_tests_with_coverage("tests/integration/")
    
    def run_all_tests(self) -> bool:
        """Run all tests with coverage.
        
        Returns:
            bool: True if tests passed and coverage is sufficient
        """
        return self.run_tests_with_coverage("tests/")


def main():
    """Main entry point for coverage checker."""
    parser = argparse.ArgumentParser(
        description="Run tests with coverage validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/check_coverage.py                    # Run all tests
  python scripts/check_coverage.py --unit-only       # Run unit tests only
  python scripts/check_coverage.py --integration-only # Run integration tests only
  python scripts/check_coverage.py --min-coverage 85 # Set custom threshold
  python scripts/check_coverage.py --validate-only   # Just validate existing coverage
        """
    )
    
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=80.0,
        help="Minimum coverage percentage required (default: 80.0)"
    )
    
    parser.add_argument(
        "--unit-only",
        action="store_true",
        help="Run only unit tests"
    )
    
    parser.add_argument(
        "--integration-only", 
        action="store_true",
        help="Run only integration tests"
    )
    
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate existing coverage (don't run tests)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Don't show detailed coverage report"
    )
    
    args = parser.parse_args()
    
    checker = CoverageChecker(min_coverage=args.min_coverage)
    
    success = True
    
    if args.validate_only:
        # Just validate existing coverage
        success = checker.validate_coverage(show_report=not args.no_report)
    elif args.unit_only:
        # Run unit tests only
        success = checker.run_unit_tests_only()
        if success:
            success = checker.validate_coverage(show_report=not args.no_report)
    elif args.integration_only:
        # Run integration tests only
        success = checker.run_integration_tests_only()
        if success:
            success = checker.validate_coverage(show_report=not args.no_report)
    else:
        # Run all tests
        success = checker.run_all_tests()
        if success:
            success = checker.validate_coverage(show_report=not args.no_report)
    
    if success:
        print("\n✅ Coverage validation PASSED")
        sys.exit(0)
    else:
        print("\n❌ Coverage validation FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()