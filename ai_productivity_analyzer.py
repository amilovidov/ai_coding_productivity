#!/usr/bin/env python3
"""
AI Coding Productivity Analyzer
Measures developer productivity before and after adopting AI coding tools like Claude Code.

Usage:
    python ai_productivity_analyzer.py --start-date 2025-06-21 --tool "Claude Code"
    python ai_productivity_analyzer.py --start-date 2025-06-21 --tool "Claude Code" --verbose
    
Requirements:
    - Run from root of a git repository
    - Git must be available in PATH
"""

import subprocess
import argparse
import json
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import re
from typing import Dict, List, Tuple, Optional, Iterator
import sys
import os
from functools import lru_cache
import time
import threading

# Try to import zoneinfo (Python 3.9+) or fallback to UTC only
try:
    from zoneinfo import ZoneInfo, available_timezones
    HAS_ZONEINFO = True
except ImportError:
    HAS_ZONEINFO = False
    available_timezones = None

# Configuration constants
DEFAULT_ANALYSIS_DAYS = 30
DEFAULT_TOP_FILES_LIMIT = 10
DEFAULT_TOP_DAYS_LIMIT = 5

# Expanded commit complexity keywords
COMPLEXITY_KEYWORDS = {
    'high': [
        'refactor', 'architecture', 'implement', 'integration', 'system', 
        'pipeline', 'migration', 'breaking', 'redesign', 'rewrite', 'major'
    ],
    'medium': [
        'feat', 'feature', 'enhance', 'improve', 'add', 'update', 'perf',
        'performance', 'optimize', 'test', 'tests', 'new', 'create'
    ],
    'low': [
        'fix', 'bug', 'typo', 'cleanup', 'docs', 'chore', 'style',
        'format', 'lint', 'ci', 'build', 'deps', 'dep', 'minor', 'patch'
    ]
}

# Git host patterns for repository detection
GIT_HOST_PATTERNS = [
    (r'github\.com[:/](.+?)(?:\.git)?$', 'GitHub'),
    (r'gitlab\.com[:/](.+?)(?:\.git)?$', 'GitLab'),
    (r'bitbucket\.org[:/](.+?)(?:\.git)?$', 'Bitbucket'),
    (r'dev\.azure\.com/[^/]+/([^/]+)', 'Azure DevOps'),
    (r'ssh://git@[^/]+/(.+?)(?:\.git)?$', 'Self-hosted'),
]

class ProgressIndicator:
    """Thread-safe progress indicator for long-running operations."""
    
    def __init__(self):
        """Initialize the progress indicator with spinner characters and thread lock."""
        self.spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self.index = 0
        self.last_message = ""
        self._lock = threading.Lock()
    
    def show(self, message: str):
        """Show progress with spinner (thread-safe)."""
        with self._lock:
            self.last_message = message
            spinner_char = self.spinner[self.index % len(self.spinner)]
            print(f"\r{spinner_char} {message}...", end='', flush=True)
            self.index += 1
    
    def clear(self):
        """Clear the progress line (thread-safe)."""
        with self._lock:
            print(f"\r{' ' * (len(self.last_message) + 10)}\r", end='', flush=True)

class ProductivityAnalyzer:
    """Analyzes developer productivity changes before and after AI tool adoption.
    
    This class provides comprehensive git repository analysis to measure
    productivity improvements, including commit frequency, code volume,
    complexity analysis, and activity patterns.
    
    Attributes:
        ai_start_date: Date when AI tool adoption began
        tool_name: Name of the AI coding tool
        analysis_days: Number of days to analyze before/after
        top_files_limit: Maximum number of files to display in reports
        top_days_limit: Maximum number of days to display in reports
        tz: Timezone object for date handling
    """
    def __init__(self, ai_start_date: str, tool_name: str = "AI Coding Tool", 
                 analysis_days: int = DEFAULT_ANALYSIS_DAYS,
                 days_before: Optional[int] = None,
                 days_after: Optional[int] = None,
                 timezone_str: str = "UTC",
                 top_files: int = DEFAULT_TOP_FILES_LIMIT,
                 top_days: int = DEFAULT_TOP_DAYS_LIMIT):
        """Initialize the analyzer with validated parameters.
        
        Args:
            ai_start_date: Date when AI tool adoption began (YYYY-MM-DD)
            tool_name: Name of the AI coding tool
            analysis_days: Number of days to analyze before/after (default for both)
            days_before: Override days to analyze before AI adoption (optional)
            days_after: Override days to analyze after AI adoption (optional)
            timezone_str: Timezone for date calculations
            top_files: Maximum number of files to display
            top_days: Maximum number of days to display
        """
        # Validate timezone parameter
        if not timezone_str or not isinstance(timezone_str, str):
            raise ValueError("Timezone must be a non-empty string")
            
        try:
            # Parse date with timezone awareness
            naive_date = datetime.strptime(ai_start_date, "%Y-%m-%d")
            
            # Handle timezone
            if timezone_str.upper() == "UTC":
                self.ai_start_date = naive_date.replace(tzinfo=timezone.utc)
                self.tz = timezone.utc
            elif HAS_ZONEINFO:
                try:
                    # Validate timezone exists
                    if timezone_str not in available_timezones():
                        # Provide helpful suggestions
                        suggestions = [tz for tz in get_common_timezones() if tz.lower().startswith(timezone_str.lower())]
                        if suggestions:
                            raise ValueError(f"Invalid timezone '{timezone_str}'. Did you mean: {', '.join(suggestions[:3])}?")
                        else:
                            raise ValueError(f"Invalid timezone '{timezone_str}'. Use --timezone UTC or check available timezones.")
                    
                    tz = ZoneInfo(timezone_str)
                    self.ai_start_date = naive_date.replace(tzinfo=tz)
                    self.tz = tz
                except ValueError:
                    # Re-raise our custom error messages
                    raise
                except Exception as e:
                    raise ValueError(f"Invalid timezone: {timezone_str}. Error: {e}")
            else:
                # Fallback for Python < 3.9
                if timezone_str.upper() != "UTC":
                    print(f"Note: timezone support requires Python 3.9+. Using UTC instead of {timezone_str}.")
                self.ai_start_date = naive_date.replace(tzinfo=timezone.utc)
                self.tz = timezone.utc
                
        except ValueError as e:
            if "Invalid date format" in str(e) or "Invalid timezone" in str(e):
                raise
            raise ValueError(f"Invalid date format: {ai_start_date}. Please use YYYY-MM-DD format.")
        
        # Validate date is not in the future
        if self.ai_start_date > datetime.now(self.tz):
            raise ValueError("Start date cannot be in the future.")
        
        self.tool_name = tool_name
        self.analysis_days = analysis_days
        self.top_files_limit = top_files
        self.top_days_limit = top_days
        self.progress = ProgressIndicator()
        self._command_cache: Dict[str, str] = {}
        
        # Use specific periods if provided, otherwise use analysis_days for both
        self.days_before = days_before if days_before is not None else analysis_days
        self.days_after = days_after if days_after is not None else analysis_days
        
        # Validate periods
        if self.days_before <= 0:
            raise ValueError("Days before must be positive")
        if self.days_after <= 0:
            raise ValueError("Days after must be positive")
        
        # Calculate periods
        self.before_start = self.ai_start_date - timedelta(days=self.days_before)
        self.before_end = self.ai_start_date - timedelta(days=1)
        self.after_start = self.ai_start_date
        self.after_end = self.ai_start_date + timedelta(days=self.days_after)
    
    def run_git_command(self, command_parts: List[str], use_cache: bool = True) -> str:
        """Execute git command safely and return output."""
        cache_key = ' '.join(command_parts)
        
        # Check cache first
        if use_cache and cache_key in self._command_cache:
            return self._command_cache[cache_key]
        
        try:
            # Ensure we're in a git repository
            if not os.path.exists('.git'):
                raise RuntimeError("Not in a git repository. Please run from the root of a git repository.")
            
            result = subprocess.run(command_parts, capture_output=True, text=True, check=True)
            output = result.stdout.strip()
            
            # Cache the result
            if use_cache:
                self._command_cache[cache_key] = output
            
            return output
        except subprocess.CalledProcessError as e:
            print(f"\nGit command failed: {' '.join(command_parts)}")
            print(f"Error: {e.stderr}")
            return ""
        except FileNotFoundError:
            print("\nError: Git is not installed or not in PATH")
            sys.exit(1)
    
    def run_git_command_streaming(self, command_parts: List[str]) -> Iterator[str]:
        """Execute git command and stream output line by line for memory efficiency."""
        try:
            # Ensure we're in a git repository
            if not os.path.exists('.git'):
                raise RuntimeError("Not in a git repository. Please run from the root of a git repository.")
            
            with subprocess.Popen(command_parts, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                text=True, bufsize=1) as proc:
                for line in proc.stdout:
                    yield line.strip()
                
                # Check for errors
                proc.wait()
                if proc.returncode != 0:
                    stderr = proc.stderr.read()
                    print(f"\nGit command failed: {' '.join(command_parts)}")
                    print(f"Error: {stderr}")
                    
        except FileNotFoundError:
            print("\nError: Git is not installed or not in PATH")
            sys.exit(1)
    
    @lru_cache(maxsize=32)
    def get_commit_count(self, start_date: datetime, end_date: datetime) -> int:
        """Get number of commits in date range with caching."""
        self.progress.show("Counting commits")
        
        # Using git rev-list for more accurate counting
        cmd_parts = [
            'git', 'rev-list', '--count',
            f'--since={start_date.strftime("%Y-%m-%d")}',
            f'--until={end_date.strftime("%Y-%m-%d")}',
            'HEAD'
        ]
        result = self.run_git_command(cmd_parts)
        return int(result) if result and result.isdigit() else 0
    
    def get_commit_details(self, start_date: datetime, end_date: datetime) -> Tuple[Dict[str, int], List[str]]:
        """Get detailed commit information with streaming for large repos."""
        self.progress.show("Analyzing commit details")
        
        cmd_parts = [
            'git', 'log',
            f'--since={start_date.strftime("%Y-%m-%d")}',
            f'--until={end_date.strftime("%Y-%m-%d")}',
            '--pretty=format:%cd|%s',
            '--date=iso-strict'  # Use ISO format with timezone
        ]
        
        commits_by_date = defaultdict(int)
        commit_messages = []
        
        for line in self.run_git_command_streaming(cmd_parts):
            if '|' in line:
                date_str, message = line.split('|', 1)
                # Parse ISO date and convert to simple date string
                try:
                    commit_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    date_key = commit_date.strftime('%Y-%m-%d')
                    commits_by_date[date_key] += 1
                    commit_messages.append(message.strip())
                except ValueError:
                    continue
        
        return dict(commits_by_date), commit_messages
    
    def get_lines_changed(self, start_date: datetime, end_date: datetime) -> Tuple[int, int]:
        """Get lines added/removed in date range, handling binary files."""
        self.progress.show("Calculating lines changed")
        
        cmd_parts = [
            'git', 'log',
            f'--since={start_date.strftime("%Y-%m-%d")}',
            f'--until={end_date.strftime("%Y-%m-%d")}',
            '--numstat',
            '--pretty=format:'
        ]
        
        total_insertions = 0
        total_deletions = 0
        binary_files = 0
        
        for line in self.run_git_command_streaming(cmd_parts):
            parts = line.strip().split('\t')
            if len(parts) >= 3:
                # Check for binary files (shown as - -)
                if parts[0] == '-' or parts[1] == '-':
                    binary_files += 1
                    continue
                    
                if parts[0].isdigit() and parts[1].isdigit():
                    total_insertions += int(parts[0])
                    total_deletions += int(parts[1])
        
        if binary_files > 0:
            print(f"\n  Note: {binary_files} binary file(s) excluded from line count")
        
        return total_insertions, total_deletions
    
    def get_file_changes(self, start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get most frequently changed files with streaming."""
        self.progress.show("Analyzing file changes")
        
        cmd_parts = [
            'git', 'log',
            f'--since={start_date.strftime("%Y-%m-%d")}',
            f'--until={end_date.strftime("%Y-%m-%d")}',
            '--name-only',
            '--pretty=format:'
        ]
        
        file_counts = defaultdict(int)
        
        for line in self.run_git_command_streaming(cmd_parts):
            if line.strip():
                file_counts[line.strip()] += 1
        
        # Sort by count and return top files
        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_files[:self.top_files_limit])
    
    def analyze_commit_complexity(self, commit_messages: List[str]) -> Dict[str, int]:
        """Analyze commit message complexity with expanded keywords."""
        complexity_counts = {'high': 0, 'medium': 0, 'low': 0}
        
        for message in commit_messages:
            message_lower = message.lower()
            categorized = False
            
            for level, keywords in COMPLEXITY_KEYWORDS.items():
                if any(keyword in message_lower for keyword in keywords):
                    complexity_counts[level] += 1
                    categorized = True
                    break
            
            if not categorized:
                complexity_counts['medium'] += 1  # Default to medium
        
        return complexity_counts
    
    def calculate_productivity_change(self, before_value: float, after_value: float) -> Tuple[float, float]:
        """Calculate percentage change and multiplier safely."""
        if before_value > 0:
            percentage_change = ((after_value - before_value) / before_value * 100)
            multiplier = after_value / before_value
        else:
            percentage_change = 0.0
            multiplier = 0.0
        return percentage_change, multiplier
    
    def print_core_metrics(self, before_commits: int, after_commits: int) -> Tuple[float, float]:
        """Print core productivity metrics and return daily averages."""
        # Calculate daily averages using the specific periods
        before_daily = before_commits / self.days_before
        after_daily = after_commits / self.days_after
        
        productivity_increase, multiplier = self.calculate_productivity_change(before_daily, after_daily)
        
        print(f"\n📊 CORE RESULTS")
        print(f"Before {self.tool_name}: {before_commits} commits in {self.days_before} days ({before_daily:.1f}/day)")
        print(f"After {self.tool_name}: {after_commits} commits in {self.days_after} days ({after_daily:.1f}/day)")
        
        if before_daily > 0:
            print(f"Productivity increase: {productivity_increase:+.1f}% ({multiplier:.1f}x multiplier)")
        else:
            print("Productivity increase: N/A (no commits in before period)")
        
        return before_daily, after_daily
    
    def print_detailed_metrics(self, before_data: dict, after_data: dict):
        """Print detailed productivity metrics."""
        # Lines changed
        print(f"\n📊 DETAILED METRICS")
        print(f"Before {self.tool_name}:")
        print(f"  • Lines added: {before_data['insertions']:,}")
        print(f"  • Lines removed: {before_data['deletions']:,}")
        
        print(f"\nAfter {self.tool_name}:")
        print(f"  • Lines added: {after_data['insertions']:,}")
        print(f"  • Lines removed: {after_data['deletions']:,}")
        
        # Commit complexity
        print(f"\n🧠 COMMIT COMPLEXITY")
        self._print_complexity_breakdown("Before", before_data['complexity'], before_data['commit_count'])
        self._print_complexity_breakdown("After", after_data['complexity'], after_data['commit_count'])
        
        # Most active days
        print(f"\n📅 MOST PRODUCTIVE DAYS")
        self._print_top_days("Before", before_data['commits_by_date'])
        self._print_top_days("After", after_data['commits_by_date'])
        
        # File activity
        print(f"\n📁 MOST CHANGED FILES")
        self._print_top_files("Before", before_data['file_changes'])
        self._print_top_files("After", after_data['file_changes'])
    
    def _print_complexity_breakdown(self, period: str, complexity: Dict[str, int], total_commits: int):
        """Helper to print complexity breakdown.
        
        Args:
            period: Time period label (e.g., 'Before', 'After')
            complexity: Dictionary of complexity counts by level
            total_commits: Total number of commits for percentage calculation
        """
        print(f"{period} {self.tool_name}:")
        for level in ['high', 'medium', 'low']:
            count = complexity[level]
            percentage = (count / max(total_commits, 1)) * 100
            print(f"  • {level.capitalize()} complexity: {count} ({percentage:.1f}%)")
    
    def _print_top_days(self, period: str, commits_by_date: Dict[str, int]):
        """Helper to print most productive days.
        
        Args:
            period: Time period label (e.g., 'Before', 'After')
            commits_by_date: Dictionary mapping dates to commit counts
        """
        print(f"{period}:")
        sorted_days = sorted(commits_by_date.items(), key=lambda x: x[1], reverse=True)[:self.top_days_limit]
        for date, count in sorted_days:
            print(f"  • {date}: {count} commits")
    
    def _print_top_files(self, period: str, file_changes: Dict[str, int]):
        """Helper to print most changed files.
        
        Args:
            period: Time period label (e.g., 'Before', 'After')
            file_changes: Dictionary mapping filenames to change counts
        """
        # Use configured limit, but show fewer if less files available
        display_limit = min(self.top_files_limit, len(file_changes))
        print(f"{period} (top {display_limit}):")
        for filename, count in list(file_changes.items())[:display_limit]:
            print(f"  • {filename}: {count} changes")
    
    def print_summary(self, before_daily: float, after_daily: float, before_complexity: Optional[Dict[str, int]] = None, 
                     after_complexity: Optional[Dict[str, int]] = None):
        """Print shareable summary."""
        productivity_increase, multiplier = self.calculate_productivity_change(before_daily, after_daily)
        
        print(f"\n📋 SUMMARY")
        print(f"Started using {self.tool_name} on {self.ai_start_date.strftime('%Y-%m-%d')}")
        print(f"Commit frequency: {before_daily:.1f} → {after_daily:.1f} commits/day ({productivity_increase:+.1f}%)")
        
        if before_daily > 0:
            print(f"Productivity multiplier: {multiplier:.1f}x")
        else:
            print("Productivity multiplier: N/A")
        
        if before_complexity and after_complexity:
            print(f"Complex feature commits: {before_complexity['high']} → {after_complexity['high']}")
        
        if self.days_before == self.days_after:
            print(f"Analysis period: {self.days_before} days before/after")
        else:
            print(f"Analysis period: {self.days_before} days before, {self.days_after} days after")
        print(f"Repository: {self.get_repo_info()}")
    
    def print_verification_commands(self):
        """Print git commands others can use to independently verify results.
        
        Outputs commands that can be run in any git repository to
        reproduce the commit count analysis.
        """
        print(f"\n💡 HOW OTHERS CAN VERIFY")
        print(f"Run these commands in any git repo:")
        print(f'git rev-list --count --since="{self.before_start.strftime("%Y-%m-%d")}" --until="{self.before_end.strftime("%Y-%m-%d")}" HEAD')
        print(f'git rev-list --count --since="{self.after_start.strftime("%Y-%m-%d")}" --until="{self.after_end.strftime("%Y-%m-%d")}" HEAD')
    
    def get_repo_info(self) -> str:
        """Get repository information with support for multiple git hosts."""
        try:
            remote_url = self.run_git_command(['git', 'config', '--get', 'remote.origin.url'])
            if remote_url:
                # Try to match against known patterns
                for pattern, host in GIT_HOST_PATTERNS:
                    match = re.search(pattern, remote_url, re.IGNORECASE)
                    if match:
                        repo_name = match.group(1)
                        # Clean up repo name
                        repo_name = repo_name.replace('.git', '')
                        return f"{repo_name} ({host})"
                
                # Generic git URL
                if '.git' in remote_url or 'git@' in remote_url:
                    # Extract last part of URL as repo name
                    parts = remote_url.rstrip('/').split('/')
                    if parts:
                        repo_name = parts[-1].replace('.git', '')
                        return f"{repo_name} (Git)"
            
            return "Local repository"
        except:
            return "Local repository"
    
    def generate_report(self, verbose: bool = False):
        """Generate productivity report (concise by default, detailed with verbose=True)."""
        print(f"\n🚀 AI Coding Productivity Report")
        print(f"Tool: {self.tool_name}")
        if self.days_before == self.days_after:
            print(f"Analysis Period: {self.days_before} days before/after")
        else:
            print(f"Analysis Period: {self.days_before} days before, {self.days_after} days after")
        print(f"AI Adoption Date: {self.ai_start_date.strftime('%Y-%m-%d')}")
        print("=" * 60)
        
        # Get basic metrics
        self.progress.show("Analyzing commit history")
        before_commits = self.get_commit_count(self.before_start, self.before_end)
        
        self.progress.show("Analyzing recent commits")
        after_commits = self.get_commit_count(self.after_start, self.after_end)
        
        # Clear progress indicator
        self.progress.clear()
        
        # Print core metrics
        before_daily, after_daily = self.print_core_metrics(before_commits, after_commits)
        
        # Collect detailed data if needed
        before_complexity = None
        after_complexity = None
        
        if verbose:
            print("\n⏳ Gathering detailed metrics...")
            
            # Gather all detailed data
            before_commits_by_date, before_messages = self.get_commit_details(self.before_start, self.before_end)
            after_commits_by_date, after_messages = self.get_commit_details(self.after_start, self.after_end)
            
            before_insertions, before_deletions = self.get_lines_changed(self.before_start, self.before_end)
            after_insertions, after_deletions = self.get_lines_changed(self.after_start, self.after_end)
            
            before_complexity = self.analyze_commit_complexity(before_messages)
            after_complexity = self.analyze_commit_complexity(after_messages)
            
            before_files = self.get_file_changes(self.before_start, self.before_end)
            after_files = self.get_file_changes(self.after_start, self.after_end)
            
            # Clear final progress
            self.progress.clear()
            
            # Package data for detailed metrics
            before_data = {
                'insertions': before_insertions,
                'deletions': before_deletions,
                'complexity': before_complexity,
                'commit_count': before_commits,
                'commits_by_date': before_commits_by_date,
                'file_changes': before_files
            }
            
            after_data = {
                'insertions': after_insertions,
                'deletions': after_deletions,
                'complexity': after_complexity,
                'commit_count': after_commits,
                'commits_by_date': after_commits_by_date,
                'file_changes': after_files
            }
            
            self.print_detailed_metrics(before_data, after_data)
        
        # Print summary
        self.print_summary(before_daily, after_daily, before_complexity, after_complexity)
        
        # Print verification commands
        self.print_verification_commands()
        
        if not verbose:
            print(f"\n💬 Want detailed analysis? Run with --verbose flag")

def get_common_timezones() -> List[str]:
    """Get a list of common timezones for help text.
    
    Returns:
        List of common timezone strings that are valid on the system.
        Falls back to ['UTC'] if zoneinfo is not available.
    """
    common = [
        "UTC", "US/Eastern", "US/Central", "US/Mountain", "US/Pacific",
        "Europe/London", "Europe/Paris", "Europe/Berlin", "Asia/Tokyo",
        "Asia/Shanghai", "Australia/Sydney"
    ]
    if HAS_ZONEINFO:
        # Verify these are valid
        return [tz for tz in common if tz in available_timezones() or tz == "UTC"]
    return ["UTC"]

def main():
    parser = argparse.ArgumentParser(description="Analyze coding productivity before/after AI tool adoption")
    parser.add_argument("--start-date", required=True, help="Date when you started using AI tool (YYYY-MM-DD)")
    parser.add_argument("--tool", default="AI Coding Tool", help="Name of the AI tool (e.g., 'Claude Code')")
    parser.add_argument("--days", type=int, default=DEFAULT_ANALYSIS_DAYS, help="Number of days to analyze before/after (default: 30)")
    parser.add_argument("--days-before", type=int, help="Override days to analyze before AI adoption (default: --days value)")
    parser.add_argument("--days-after", type=int, help="Override days to analyze after AI adoption (default: --days value)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed analysis (default: concise LinkedIn-ready output)")
    
    # New configurable options
    parser.add_argument("--top-files", type=int, default=DEFAULT_TOP_FILES_LIMIT, 
                       help="Number of top files to display (default: 10)")
    parser.add_argument("--top-days", type=int, default=DEFAULT_TOP_DAYS_LIMIT,
                       help="Number of most productive days to show (default: 5)")
    # Build timezone help text
    tz_help = "Timezone for analysis (default: UTC)"
    if HAS_ZONEINFO:
        common_tz = get_common_timezones()
        tz_help += f". Examples: {', '.join(common_tz[:5])}"
    else:
        tz_help += ". Note: Full timezone support requires Python 3.9+"
    
    parser.add_argument("--timezone", default="UTC", help=tz_help)
    
    args = parser.parse_args()
    
    try:
        # Validate days parameter
        if args.days <= 0:
            raise ValueError("Number of days must be positive")
        
        # Validate specific period overrides
        if args.days_before is not None and args.days_before <= 0:
            raise ValueError("Days before must be positive")
        if args.days_after is not None and args.days_after <= 0:
            raise ValueError("Days after must be positive")
        
        # Validate top files/days parameters
        if args.top_files <= 0:
            raise ValueError("Number of top files must be positive")
        if args.top_days <= 0:
            raise ValueError("Number of top days must be positive")
        
        analyzer = ProductivityAnalyzer(
            args.start_date, 
            args.tool, 
            args.days,
            args.days_before,
            args.days_after,
            args.timezone,
            args.top_files,
            args.top_days
        )
        analyzer.generate_report(verbose=args.verbose)
        
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nAnalysis cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        print("Please report this issue with the full error message.")
        sys.exit(1)

if __name__ == "__main__":
    main()