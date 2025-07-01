# AI Coding Productivity Analyzer 🚀

A Python tool that quantifies developer productivity improvements when adopting AI coding assistants like Claude Code, GitHub Copilot, or other AI tools. Generate data-driven insights perfect for LinkedIn posts, performance reviews, or team presentations.

## 📊 What It Does

This tool analyzes your git commit history to measure productivity changes before and after adopting an AI coding tool. It provides:

- **Commit frequency analysis** - Daily commit rates and productivity multipliers
- **Code volume metrics** - Lines added/removed before and after AI adoption
- **Commit complexity analysis** - Categorizes commits by complexity (high/medium/low)
- **Activity patterns** - Most productive days and frequently changed files
- **Shareable summaries** - LinkedIn-ready statistics with verification commands

## 🎯 Key Features

- **Concise Mode** (default): Get LinkedIn-ready statistics in seconds
- **Verbose Mode**: Deep dive into detailed productivity metrics
- **Flexible Analysis**: Customize the analysis period (default: 30 days)
- **Easy Verification**: Provides git commands others can run to verify your results
- **Repository Agnostic**: Works with any git repository

## 📋 Requirements

- Python 3.6+
- Git (must be available in PATH)
- Run from the root directory of a git repository

## 🚀 Quick Start

### Basic Usage

Analyze productivity changes after adopting Claude Code on June 21, 2025:

```bash
python ai_productivity_analyzer.py --start-date 2025-06-21 --tool "Claude Code"
```

### Example Output (Concise Mode)

```
🚀 AI Coding Productivity Report
Tool: Claude Code
Analysis Period: 30 days before/after
AI Adoption Date: 2025-06-21
============================================================

📊 CORE RESULTS
Before Claude Code: 12 commits in 30 days (0.4/day)
After Claude Code: 47 commits in 30 days (1.6/day)
Productivity increase: +290.0% (3.9x multiplier)

📋 SUMMARY
Started using Claude Code on 2025-06-21
Commit frequency: 0.4 → 1.6 commits/day (+290.0%)
Productivity multiplier: 3.9x
Analysis period: 30 days before/after
Repository: ai_coding_productivity

💡 HOW OTHERS CAN VERIFY
Run these commands in any git repo:
git log --since="2025-05-22" --until="2025-06-20" --oneline | wc -l
git log --since="2025-06-21" --until="2025-07-21" --oneline | wc -l
```

### Detailed Analysis

For comprehensive metrics including commit complexity, file changes, and activity patterns:

```bash
python ai_productivity_analyzer.py --start-date 2025-06-21 --tool "Claude Code" --verbose
```

## 📖 Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--start-date` | Date when you started using the AI tool (YYYY-MM-DD) | Required |
| `--tool` | Name of the AI tool (e.g., 'Claude Code', 'GitHub Copilot') | "AI Coding Tool" |
| `--days` | Number of days to analyze before/after | 30 |
| `--verbose` | Show detailed analysis with all metrics | False (concise mode) |

## 📊 Metrics Explained

### Core Metrics (Always Shown)
- **Commit Frequency**: Average commits per day before/after AI adoption
- **Productivity Increase**: Percentage change in commit frequency
- **Productivity Multiplier**: How many times more productive (e.g., 3.9x)

### Detailed Metrics (Verbose Mode)
- **Lines Changed**: Total insertions and deletions
- **Commit Complexity**: Distribution of high/medium/low complexity commits
- **Most Productive Days**: Top 5 days by commit count
- **Most Changed Files**: Files with the most modifications

### Commit Complexity Classification
- **High**: Refactoring, architecture changes, implementations, integrations
- **Medium**: Features, enhancements, improvements, additions
- **Low**: Bug fixes, typos, cleanup, documentation, chores

## 💡 Use Cases

1. **LinkedIn Posts**: Share your AI productivity gains with professional network
2. **Performance Reviews**: Quantify the impact of AI tools on your productivity
3. **Team Presentations**: Demonstrate ROI of AI tool adoption
4. **Personal Tracking**: Monitor your productivity trends over time

## 🔧 How It Works

The tool uses git log commands to:
1. Define two time periods: before and after AI tool adoption
2. Count commits, analyze commit messages, and track file changes
3. Calculate productivity metrics and generate insights
4. Provide verification commands for transparency

## 📝 Example LinkedIn Post

> 🚀 Started using Claude Code 30 days ago and the results are incredible:
> 
> • Commit frequency: 0.4 → 1.6 commits/day (+290%)
> • Productivity multiplier: 3.9x
> • Complex feature commits increased by 150%
> 
> AI coding assistants aren't just hype - they're game changers for developer productivity! 
> 
> #AI #CodingProductivity #ClaudeCode #DeveloperTools

## 🤝 Contributing

Contributions are welcome! Feel free to:
- Add new metrics or analysis features
- Improve the complexity classification algorithm
- Add support for other version control systems
- Enhance the output formatting

## 📄 License

This project is open source and available under the MIT License.

## 🙏 Acknowledgments

Built to help developers quantify and share their AI-enhanced productivity gains. Special thanks to the AI coding assistant community for inspiring this tool!

---

*Made with ❤️ for developers embracing AI-powered coding*