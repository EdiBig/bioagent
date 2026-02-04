#!/usr/bin/env python3
"""
BioAgent CLI — Interactive bioinformatics assistant.

Usage:
    python run.py                    # Interactive chat mode
    python run.py --query "..."      # Single query mode
    python run.py --complex "..."    # Use advanced model for complex queries

Environment Variables:
    ANTHROPIC_API_KEY       Required. Your Anthropic API key.
    NCBI_API_KEY            Optional. NCBI E-utilities API key.
    NCBI_EMAIL              Recommended. Your email for NCBI.
    BIOAGENT_WORKSPACE      Workspace directory (default: /workspace).
    BIOAGENT_MODEL          Model to use (default: claude-sonnet-4-20250514).
    BIOAGENT_VERBOSE        Show tool calls (default: true).
"""

import argparse
import os
import sys
from pathlib import Path

# Load .env file if it exists
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

from agent import BioAgent
from config import Config


def main():
    parser = argparse.ArgumentParser(
        description="BioAgent — AI-powered bioinformatics assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Run a single query and exit",
    )
    parser.add_argument(
        "--complex", "-c",
        type=str,
        help="Run a single complex query using the advanced model",
    )
    parser.add_argument(
        "--workspace", "-w",
        type=str,
        default=None,
        help="Workspace directory for analysis files",
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default=None,
        help="Override the default model",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress verbose tool-use logging",
    )
    parser.add_argument(
        "--save-session",
        type=str,
        default=None,
        help="Save session to this file on exit",
    )
    parser.add_argument(
        "--load-session",
        type=str,
        default=None,
        help="Load a previous session file",
    )

    args = parser.parse_args()

    # Build config
    config = Config.from_env()

    if args.workspace:
        config.workspace_dir = args.workspace
    if args.model:
        config.model = args.model
    if args.quiet:
        config.verbose = False

    # Initialise agent
    try:
        agent = BioAgent(config=config)
    except ValueError as e:
        print(f"❌ {e}", file=sys.stderr)
        print("\nSet your API key:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        print("  # or create a .env file in the project directory")
        sys.exit(1)

    # Load session if specified
    if args.load_session:
        agent.load_session(args.load_session)

    # Single query mode
    if args.query:
        response = agent.run(args.query)
        # Handle Unicode characters that Windows console can't display
        try:
            print(response)
        except UnicodeEncodeError:
            print(response.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        if args.save_session:
            agent.save_session(args.save_session)
        return

    if args.complex:
        response = agent.run(args.complex, use_complex_model=True)
        try:
            print(response)
        except UnicodeEncodeError:
            print(response.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
        if args.save_session:
            agent.save_session(args.save_session)
        return

    # Interactive mode
    try:
        agent.chat()
    finally:
        if args.save_session:
            agent.save_session(args.save_session)


if __name__ == "__main__":
    main()
