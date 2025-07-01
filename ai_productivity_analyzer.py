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
from datetime import datetime, timedelta
from collections import defaultdict
import re
from typing import Dict, List, Tuple, Optional
import sys
import os

# Configuration constants
DEFAULT_ANALYSIS_DAYS = 30
TOP_FILES_LIMIT = 10
TOP_DAYS_LIMIT = 5

class ProductivityAnalyzer:
    def __init__(self, ai_start_date: str, tool_name: str = "AI Coding Tool", analysis_days: int = DEFAULT_ANALYSIS_DAYS):
        """Initialize the analyzer with validated parameters."""
        try:
            self.ai_start_date = datetime.strptime(ai_start_date, "%Y-%m-%d")
        except ValueError:
            raise ValueError(f"Invalid date format: {ai_start_date}. Please use YYYY-MM-DD format.")
        
        # Validate date is not in the future
        if self.ai_start_date > datetime.now():
            raise ValueError("Start date cannot be in the future.")
        
        self.tool_name = tool_name
        self.analysis_days = analysis_days
        
        # Calculate periods
        self.before_start = self.ai_start_date - timedelta(days=analysis_days)
        self.before_end = self.ai_start_date - timedelta(days=1)
        self.after_start = self.ai_start_date
        self.after_end = self.ai_start_date + timedelta(days=analysis_days)
        
    def run_git_command(self, command_parts: List[str]) -> str:
        """Execute git command safely and return output."""
        try:
            # Ensure we're in a git repository
            if not os.path.exists('.git'):
                raise RuntimeError("Not in a git repository. Please run from the root of a git repository.")
            
            result = subprocess.run(command_parts, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Git command failed: {' '.join(command_parts)}")
            print(f"Error: {e.stderr}")
            return ""
        except FileNotFoundError:
            print("Error: Git is not installed or not in PATH")
            sys.exit(1)
    
    def get_commit_count(self, start_date: datetime, end_date: datetime) -> int:
        """Get number of commits in date range."""
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
        """Get detailed commit information."""
        cmd_parts = [
            'git', 'log',
            f'--since={start_date.strftime("%Y-%m-%d")}',
            f'--until={end_date.strftime("%Y-%m-%d")}',
            '--pretty=format:%cd|%s',
            '--date=short'
        ]
        result = self.run_git_command(cmd_parts)
        
        commits_by_date = defaultdict(int)
        commit_messages = []
        
        if result:
            for line in result.split('\n'):
                if '|' in line:
                    date, message = line.split('|', 1)
                    commits_by_date[date] += 1
                    commit_messages.append(message.strip())
        
        return dict(commits_by_date), commit_messages
    
    def get_lines_changed(self, start_date: datetime, end_date: datetime) -> Tuple[int, int]:
        """Get lines added/removed in date range."""
        cmd_parts = [
            'git', 'log',
            f'--since={start_date.strftime("%Y-%m-%d")}',
            f'--until={end_date.strftime("%Y-%m-%d")}',
            '--numstat',
            '--pretty=format:'
        ]
        result = self.run_git_command(cmd_parts)
        
        total_insertions = 0
        total_deletions = 0
        
        if result:
            for line in result.split('\n'):
                parts = line.strip().split('\t')
                if len(parts) >= 3 and parts[0].isdigit() and parts[1].isdigit():
                    total_insertions += int(parts[0])
                    total_deletions += int(parts[1])
        
        return total_insertions, total_deletions
    
    def get_file_changes(self, start_date: datetime, end_date: datetime) -> Dict[str, int]:
        """Get most frequently changed files."""
        cmd_parts = [
            'git', 'log',
            f'--since={start_date.strftime("%Y-%m-%d")}',
            f'--until={end_date.strftime("%Y-%m-%d")}',
            '--name-only',
            '--pretty=format:'
        ]
        result = self.run_git_command(cmd_parts)
        
        file_counts = defaultdict(int)
        if result:
            for line in result.split('\n'):
                if line.strip():
                    file_counts[line.strip()] += 1
        
        # Sort by count and return top files
        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_files[:TOP_FILES_LIMIT])
    
    def analyze_commit_complexity(self, commit_messages: List[str]) -> Dict[str, int]:
        """Analyze commit message complexity and types."""
        complexity_keywords = {
            'high': ['refactor', 'architecture', 'implement', 'integration', 'system', 'pipeline', 'migration'],
            'medium': ['feat', 'feature', 'enhance', 'improve', 'add', 'update'],
            'low': ['fix', 'bug', 'typo', 'cleanup', 'docs', 'chore']
        }
        
        complexity_counts = {'high': 0, 'medium': 0, 'low': 0}
        
        for message in commit_messages:
            message_lower = message.lower()
            categorized = False
            
            for level, keywords in complexity_keywords.items():
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
        # Calculate daily averages
        before_daily = before_commits / self.analysis_days
        after_daily = after_commits / self.analysis_days
        
        productivity_increase, multiplier = self.calculate_productivity_change(before_daily, after_daily)
        
        print(f"\n📊 CORE RESULTS")
        print(f"Before {self.tool_name}: {before_commits} commits in {self.analysis_days} days ({before_daily:.1f}/day)")
        print(f"After {self.tool_name}: {after_commits} commits in {self.analysis_days} days ({after_daily:.1f}/day)")
        
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
        """Helper to print complexity breakdown."""
        print(f"{period} {self.tool_name}:")
        for level in ['high', 'medium', 'low']:
            count = complexity[level]
            percentage = (count / max(total_commits, 1)) * 100
            print(f"  • {level.capitalize()} complexity: {count} ({percentage:.1f}%)")
    
    def _print_top_days(self, period: str, commits_by_date: Dict[str, int]):
        """Helper to print most productive days."""
        print(f"{period}:")
        sorted_days = sorted(commits_by_date.items(), key=lambda x: x[1], reverse=True)[:TOP_DAYS_LIMIT]
        for date, count in sorted_days:
            print(f"  • {date}: {count} commits")
    
    def _print_top_files(self, period: str, file_changes: Dict[str, int]):
        """Helper to print most changed files."""
        print(f"{period} (top 5):")
        for filename, count in list(file_changes.items())[:5]:
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
        
        print(f"Analysis period: {self.analysis_days} days before/after")
        print(f"Repository: {self.get_repo_info()}")
    
    def print_verification_commands(self):
        """Print commands others can use to verify results."""
        print(f"\n💡 HOW OTHERS CAN VERIFY")
        print(f"Run these commands in any git repo:")
        print(f'git rev-list --count --since="{self.before_start.strftime("%Y-%m-%d")}" --until="{self.before_end.strftime("%Y-%m-%d")}" HEAD')
        print(f'git rev-list --count --since="{self.after_start.strftime("%Y-%m-%d")}" --until="{self.after_end.strftime("%Y-%m-%d")}" HEAD')
    
    def get_repo_info(self) -> str:
        """Get repository information."""
        try:
            remote_url = self.run_git_command(['git', 'config', '--get', 'remote.origin.url'])
            if remote_url and "github.com" in remote_url:
                # Extract repo name from GitHub URL
                repo_name = remote_url.split("/")[-1].replace(".git", "")
                return repo_name
            return "Local repository"
        except:
            return "Local repository"
    
    def generate_report(self, verbose: bool = False):
        """Generate productivity report (concise by default, detailed with verbose=True)."""
        print(f"\n🚀 AI Coding Productivity Report")
        print(f"Tool: {self.tool_name}")
        print(f"Analysis Period: {self.analysis_days} days before/after")
        print(f"AI Adoption Date: {self.ai_start_date.strftime('%Y-%m-%d')}")
        print("=" * 60)
        
        # Get basic metrics
        before_commits = self.get_commit_count(self.before_start, self.before_end)
        after_commits = self.get_commit_count(self.after_start, self.after_end)
        
        # Print core metrics
        before_daily, after_daily = self.print_core_metrics(before_commits, after_commits)
        
        # Collect detailed data if needed
        before_complexity = None
        after_complexity = None
        
        if verbose:
            # Gather all detailed data
            before_commits_by_date, before_messages = self.get_commit_details(self.before_start, self.before_end)
            after_commits_by_date, after_messages = self.get_commit_details(self.after_start, self.after_end)
            
            before_insertions, before_deletions = self.get_lines_changed(self.before_start, self.before_end)
            after_insertions, after_deletions = self.get_lines_changed(self.after_start, self.after_end)
            
            before_complexity = self.analyze_commit_complexity(before_messages)
            after_complexity = self.analyze_commit_complexity(after_messages)
            
            before_files = self.get_file_changes(self.before_start, self.before_end)
            after_files = self.get_file_changes(self.after_start, self.after_end)
            
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

def main():
    parser = argparse.ArgumentParser(description="Analyze coding productivity before/after AI tool adoption")
    parser.add_argument("--start-date", required=True, help="Date when you started using AI tool (YYYY-MM-DD)")
    parser.add_argument("--tool", default="AI Coding Tool", help="Name of the AI tool (e.g., 'Claude Code')")
    parser.add_argument("--days", type=int, default=DEFAULT_ANALYSIS_DAYS, help="Number of days to analyze before/after (default: 30)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed analysis (default: concise LinkedIn-ready output)")
    
    args = parser.parse_args()
    
    try:
        # Validate days parameter
        if args.days <= 0:
            raise ValueError("Number of days must be positive")
        
        analyzer = ProductivityAnalyzer(args.start_date, args.tool, args.days)
        analyzer.generate_report(verbose=args.verbose)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nAnalysis cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        print("Please report this issue with the full error message.")
        sys.exit(1)

if __name__ == "__main__":
    main()