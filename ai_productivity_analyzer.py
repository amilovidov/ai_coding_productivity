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

class ProductivityAnalyzer:
    def __init__(self, ai_start_date, tool_name="AI Coding Tool", analysis_days=30):
        self.ai_start_date = datetime.strptime(ai_start_date, "%Y-%m-%d")
        self.tool_name = tool_name
        self.analysis_days = analysis_days
        
        # Calculate periods
        self.before_start = self.ai_start_date - timedelta(days=analysis_days)
        self.before_end = self.ai_start_date - timedelta(days=1)
        self.after_start = self.ai_start_date
        self.after_end = self.ai_start_date + timedelta(days=analysis_days)
        
    def run_git_command(self, command):
        """Execute git command and return output"""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Git command failed: {command}")
            print(f"Error: {e.stderr}")
            return ""
    
    def get_commit_count(self, start_date, end_date):
        """Get number of commits in date range"""
        cmd = f'git log --since="{start_date.strftime("%Y-%m-%d")}" --until="{end_date.strftime("%Y-%m-%d")}" --oneline | wc -l'
        result = self.run_git_command(cmd)
        return int(result) if result else 0
    
    def get_commit_details(self, start_date, end_date):
        """Get detailed commit information"""
        cmd = f'git log --since="{start_date.strftime("%Y-%m-%d")}" --until="{end_date.strftime("%Y-%m-%d")}" --pretty=format:"%cd|%s" --date=short'
        result = self.run_git_command(cmd)
        
        commits_by_date = defaultdict(int)
        commit_messages = []
        
        for line in result.split('\n'):
            if '|' in line:
                date, message = line.split('|', 1)
                commits_by_date[date] += 1
                commit_messages.append(message.strip())
        
        return commits_by_date, commit_messages
    
    def get_lines_changed(self, start_date, end_date):
        """Get lines added/removed in date range"""
        cmd = f'git log --since="{start_date.strftime("%Y-%m-%d")}" --until="{end_date.strftime("%Y-%m-%d")}" --stat --pretty=format:""'
        result = self.run_git_command(cmd)
        
        total_insertions = 0
        total_deletions = 0
        
        for line in result.split('\n'):
            if 'insertion' in line or 'deletion' in line:
                # Extract numbers from lines like "5 files changed, 123 insertions(+), 45 deletions(-)"
                insertions = re.findall(r'(\d+) insertion', line)
                deletions = re.findall(r'(\d+) deletion', line)
                
                if insertions:
                    total_insertions += int(insertions[0])
                if deletions:
                    total_deletions += int(deletions[0])
        
        return total_insertions, total_deletions
    
    def get_file_changes(self, start_date, end_date):
        """Get most frequently changed files"""
        cmd = f'git log --since="{start_date.strftime("%Y-%m-%d")}" --until="{end_date.strftime("%Y-%m-%d")}" --name-only --pretty=format:"" | sort | uniq -c | sort -nr'
        result = self.run_git_command(cmd)
        
        file_changes = {}
        for line in result.split('\n')[:10]:  # Top 10 files
            if line.strip():
                parts = line.strip().split()
                if len(parts) >= 2:
                    count = int(parts[0])
                    filename = ' '.join(parts[1:])
                    file_changes[filename] = count
        
        return file_changes
    
    def analyze_commit_complexity(self, commit_messages):
        """Analyze commit message complexity and types"""
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
    
    def generate_report(self, verbose=False):
        """Generate productivity report (concise by default, detailed with verbose=True)"""
        print(f"\n🚀 AI Coding Productivity Report")
        print(f"Tool: {self.tool_name}")
        print(f"Analysis Period: {self.analysis_days} days before/after")
        print(f"AI Adoption Date: {self.ai_start_date.strftime('%Y-%m-%d')}")
        print("=" * 60)
        
        # Get basic metrics
        before_commits = self.get_commit_count(self.before_start, self.before_end)
        after_commits = self.get_commit_count(self.after_start, self.after_end)
        
        # Calculate daily averages
        before_daily = before_commits / self.analysis_days
        after_daily = after_commits / self.analysis_days
        
        productivity_increase = ((after_daily - before_daily) / before_daily * 100) if before_daily > 0 else 0
        
        # Always show core metrics
        print(f"\n📊 CORE RESULTS")
        print(f"Before {self.tool_name}: {before_commits} commits in {self.analysis_days} days ({before_daily:.1f}/day)")
        print(f"After {self.tool_name}: {after_commits} commits in {self.analysis_days} days ({after_daily:.1f}/day)")
        print(f"Productivity increase: {productivity_increase:+.1f}% ({after_daily/before_daily:.1f}x multiplier)" if before_daily > 0 else "Productivity increase: N/A")
        
        # Only show detailed analysis if verbose flag is set
        if verbose:
            before_commits_by_date, before_messages = self.get_commit_details(self.before_start, self.before_end)
            after_commits_by_date, after_messages = self.get_commit_details(self.after_start, self.after_end)
            
            before_insertions, before_deletions = self.get_lines_changed(self.before_start, self.before_end)
            after_insertions, after_deletions = self.get_lines_changed(self.after_start, self.after_end)
            
            print(f"\n📊 DETAILED METRICS")
            print(f"Before {self.tool_name}:")
            print(f"  • Lines added: {before_insertions:,}")
            print(f"  • Lines removed: {before_deletions:,}")
            
            print(f"\nAfter {self.tool_name}:")
            print(f"  • Lines added: {after_insertions:,}")
            print(f"  • Lines removed: {after_deletions:,}")
            
            # Commit complexity analysis
            before_complexity = self.analyze_commit_complexity(before_messages)
            after_complexity = self.analyze_commit_complexity(after_messages)
            
            print(f"\n🧠 COMMIT COMPLEXITY")
            print(f"Before {self.tool_name}:")
            print(f"  • High complexity: {before_complexity['high']} ({before_complexity['high']/max(before_commits,1)*100:.1f}%)")
            print(f"  • Medium complexity: {before_complexity['medium']} ({before_complexity['medium']/max(before_commits,1)*100:.1f}%)")
            print(f"  • Low complexity: {before_complexity['low']} ({before_complexity['low']/max(before_commits,1)*100:.1f}%)")
            
            print(f"\nAfter {self.tool_name}:")
            print(f"  • High complexity: {after_complexity['high']} ({after_complexity['high']/max(after_commits,1)*100:.1f}%)")
            print(f"  • Medium complexity: {after_complexity['medium']} ({after_complexity['medium']/max(after_commits,1)*100:.1f}%)")
            print(f"  • Low complexity: {after_complexity['low']} ({after_complexity['low']/max(after_commits,1)*100:.1f}%)")
            
            # Most active days
            print(f"\n📅 MOST PRODUCTIVE DAYS")
            print("Before:")
            sorted_before = sorted(before_commits_by_date.items(), key=lambda x: x[1], reverse=True)[:5]
            for date, count in sorted_before:
                print(f"  • {date}: {count} commits")
            
            print("After:")
            sorted_after = sorted(after_commits_by_date.items(), key=lambda x: x[1], reverse=True)[:5]
            for date, count in sorted_after:
                print(f"  • {date}: {count} commits")
            
            # File activity
            before_files = self.get_file_changes(self.before_start, self.before_end)
            after_files = self.get_file_changes(self.after_start, self.after_end)
            
            print(f"\n📁 MOST CHANGED FILES")
            print("Before (top 5):")
            for filename, count in list(before_files.items())[:5]:
                print(f"  • {filename}: {count} changes")
            
            print("After (top 5):")
            for filename, count in list(after_files.items())[:5]:
                print(f"  • {filename}: {count} changes")
        
        # Generate shareable summary (always show)
        print(f"\n📋 SUMMARY")
        print(f"Started using {self.tool_name} on {self.ai_start_date.strftime('%Y-%m-%d')}")
        print(f"Commit frequency: {before_daily:.1f} → {after_daily:.1f} commits/day ({productivity_increase:+.1f}%)")
        print(f"Productivity multiplier: {after_daily/before_daily:.1f}x" if before_daily > 0 else "Productivity multiplier: N/A")
        if verbose:
            before_complexity = self.analyze_commit_complexity(before_messages) if 'before_messages' in locals() else {'high': 0}
            after_complexity = self.analyze_commit_complexity(after_messages) if 'after_messages' in locals() else {'high': 0}
            print(f"Complex feature commits: {before_complexity['high']} → {after_complexity['high']}")
        print(f"Analysis period: {self.analysis_days} days before/after")
        print(f"Repository: {self.get_repo_info()}")
        
        print(f"\n💡 HOW OTHERS CAN VERIFY")
        print(f"Run these commands in any git repo:")
        print(f'git log --since="{self.before_start.strftime("%Y-%m-%d")}" --until="{self.before_end.strftime("%Y-%m-%d")}" --oneline | wc -l')
        print(f'git log --since="{self.after_start.strftime("%Y-%m-%d")}" --until="{self.after_end.strftime("%Y-%m-%d")}" --oneline | wc -l')
        
        if not verbose:
            print(f"\n💬 Want detailed analysis? Run with --verbose flag")
    
    def get_repo_info(self):
        """Get repository information"""
        try:
            remote_url = self.run_git_command("git config --get remote.origin.url")
            if "github.com" in remote_url:
                # Extract repo name from GitHub URL
                repo_name = remote_url.split("/")[-1].replace(".git", "")
                return repo_name
            return "Local repository"
        except:
            return "Local repository"

def main():
    parser = argparse.ArgumentParser(description="Analyze coding productivity before/after AI tool adoption")
    parser.add_argument("--start-date", required=True, help="Date when you started using AI tool (YYYY-MM-DD)")
    parser.add_argument("--tool", default="AI Coding Tool", help="Name of the AI tool (e.g., 'Claude Code')")
    parser.add_argument("--days", type=int, default=30, help="Number of days to analyze before/after (default: 30)")
    parser.add_argument("--verbose", action="store_true", help="Show detailed analysis (default: concise LinkedIn-ready output)")
    
    args = parser.parse_args()
    
    try:
        analyzer = ProductivityAnalyzer(args.start_date, args.tool, args.days)
        analyzer.generate_report(verbose=args.verbose)
    except ValueError as e:
        print(f"Error: Invalid date format. Use YYYY-MM-DD (e.g., 2025-06-21)")
    except Exception as e:
        print(f"Error: {e}")
        print("Make sure you're running this from the root of a git repository.")

if __name__ == "__main__":
    main()