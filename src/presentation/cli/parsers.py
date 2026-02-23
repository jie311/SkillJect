"""
Presentation layer CLI argument parser.

Provides command line argument parsing functionality.
"""

import argparse
from typing import Any

from ..dto.requests import (
    ExperimentRequestDTO,
    IntelligentTestGenerationRequestDTO,
    TestGenerationRequestDTO,
)
from src.shared.types import AttackType, InjectionLayer, Severity


class ArgumentParser:
    """Argument parser.

    Provides unified command line argument parsing.
    """

    def __init__(self, prog: str = "python -m evaluation"):
        """Initialize parser.

        Args:
            prog: Program name
        """
        self._parser = argparse.ArgumentParser(prog=prog)
        self._subparsers = self._parser.add_subparsers(dest="command", help="Available commands")

        # Add global arguments
        self._add_global_arguments()

        # Add subcommands
        self._add_run_command()
        self._add_generate_command()
        self._add_generate_intelligent_command()
        self._add_generate_code_cache_command()
        self._add_list_command()
        self._add_validate_command()
        self._add_status_command()
        self._add_two_phase_command()

    def _add_global_arguments(self) -> None:
        """Add global arguments."""
        self._parser.add_argument(
            "-v",
            "--verbose",
            action="store_true",
            help="Verbose output",
        )
        self._parser.add_argument(
            "-c",
            "--config",
            type=str,
            help="Configuration file path",
        )
        self._parser.add_argument(
            "--output-dir",
            type=str,
            default="experiment_results",
            help="Output directory",
        )

    def _add_run_command(self) -> None:
        """Add run command."""
        run_parser = self._subparsers.add_parser(
            "run",
            help="Run security test experiment",
        )

        run_parser.add_argument(
            "-n",
            "--name",
            type=str,
            default="security_experiment",
            help="Experiment name",
        )

        run_parser.add_argument(
            "-a",
            "--attack-types",
            nargs="+",
            choices=[at.value for at in AttackType],
            help="Attack types",
        )

        run_parser.add_argument(
            "-l",
            "--layers",
            nargs="+",
            choices=[il.value for il in InjectionLayer],
            help="Injection layers",
        )

        run_parser.add_argument(
            "-s",
            "--severities",
            nargs="+",
            choices=[s.value for s in Severity],
            help="Severity levels",
        )

        run_parser.add_argument(
            "--skills",
            nargs="+",
            help="List of skill names",
        )

        run_parser.add_argument(
            "-j",
            "--max-concurrency",
            type=int,
            default=4,
            help="Maximum concurrency",
        )

        run_parser.add_argument(
            "-t",
            "--timeout",
            type=int,
            default=120,
            help="Timeout in seconds",
        )

        run_parser.add_argument(
            "--max-tests",
            type=int,
            help="Maximum number of tests",
        )

    def _add_generate_command(self) -> None:
        """Add generate command."""
        gen_parser = self._subparsers.add_parser(
            "generate",
            help="Generate injection test cases",
        )

        gen_parser.add_argument(
            "-a",
            "--attack-types",
            nargs="+",
            choices=[at.value for at in AttackType],
            help="Attack types",
        )

        gen_parser.add_argument(
            "-l",
            "--layers",
            nargs="+",
            choices=[il.value for il in InjectionLayer],
            help="Injection layers",
        )

        gen_parser.add_argument(
            "-s",
            "--severities",
            nargs="+",
            choices=[s.value for s in Severity],
            help="Severity levels",
        )

        gen_parser.add_argument(
            "--skills",
            nargs="+",
            help="List of skill names",
        )

        gen_parser.add_argument(
            "-o",
            "--output-dir",
            type=str,
            default="generated_tests",
            help="Output directory",
        )

    def _add_list_command(self) -> None:
        """Add list command."""
        list_parser = self._subparsers.add_parser(
            "list",
            help="List test cases",
        )

        list_parser.add_argument(
            "--skill",
            type=str,
            help="Filter by skill name",
        )

        list_parser.add_argument(
            "--layer",
            choices=[il.value for il in InjectionLayer],
            help="Filter by injection layer",
        )

        list_parser.add_argument(
            "--attack-type",
            choices=[at.value for at in AttackType],
            help="Filter by attack type",
        )

        list_parser.add_argument(
            "--limit",
            type=int,
            help="Limit count",
        )

        list_parser.add_argument(
            "--format",
            choices=["table", "json", "text"],
            default="table",
            help="Output format",
        )

    def _add_validate_command(self) -> None:
        """Add validate command."""
        validate_parser = self._subparsers.add_parser(
            "validate",
            help="Validate test cases",
        )

        validate_parser.add_argument(
            "--test-dir",
            type=str,
            help="Test directory path",
        )

    def _add_status_command(self) -> None:
        """Add status command."""
        status_parser = self._subparsers.add_parser(
            "status",
            help="Get experiment status",
        )

        status_parser.add_argument(
            "experiment_id",
            nargs="?",
            help="Experiment ID",
        )

    def _add_generate_intelligent_command(self) -> None:
        """Add intelligent generation command."""
        gen_parser = self._subparsers.add_parser(
            "generate-intelligent",
            help="Use LLM to intelligently generate injection test cases",
        )

        gen_parser.add_argument(
            "--skill",
            type=str,
            help="Single skill name (empty for all skills)",
        )

        gen_parser.add_argument(
            "--strategy",
            type=str,
            default="comprehensive",
            choices=IntelligentTestGenerationRequestDTO.STRATEGY_CHOICES,
            help="Injection strategy",
        )

        gen_parser.add_argument(
            "-a",
            "--attack-types",
            nargs="+",
            choices=[at.value for at in AttackType],
            help="Attack types",
        )

        gen_parser.add_argument(
            "--payload",
            type=str,
            help="Custom attack payload (empty for default payload)",
        )

        gen_parser.add_argument(
            "-o",
            "--output-dir",
            type=str,
            default="intelligent_tests",
            help="Output directory",
        )

        gen_parser.add_argument(
            "--llm-provider",
            type=str,
            default="openai",
            choices=IntelligentTestGenerationRequestDTO.PROVIDER_CHOICES,
            help="LLM provider",
        )

        gen_parser.add_argument(
            "-j",
            "--max-concurrency",
            type=int,
            default=4,
            help="Maximum concurrency",
        )

        gen_parser.add_argument(
            "--no-code-cache",
            action="store_true",
            help="Disable code file caching",
        )

    def _add_generate_code_cache_command(self) -> None:
        """Add generate code cache command."""
        cache_parser = self._subparsers.add_parser(
            "generate-code-cache",
            help="Generate malicious code file cache",
        )

        cache_parser.add_argument(
            "-a",
            "--attack-types",
            nargs="+",
            choices=[at.value for at in AttackType],
            help="Specified attack types (empty for all)",
        )

        cache_parser.add_argument(
            "--all",
            action="store_true",
            help="Generate code cache for all attack types",
        )

        cache_parser.add_argument(
            "--llm-provider",
            type=str,
            default="openai",
            choices=["anthropic", "openai"],
            help="LLM provider",
        )

        cache_parser.add_argument(
            "--cache-dir",
            type=str,
            default="data/malicious_code_cache",
            help="Cache directory path",
        )

        cache_parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing cache files",
        )

    def parse_args(self, args: list[str] | None = None) -> dict[str, Any]:
        """Parse arguments.

        Args:
            args: List of arguments (None for sys.argv)

        Returns:
            Dictionary of parsed arguments
        """
        parsed = self._parser.parse_args(args)

        return {
            "command": parsed.command,
            "verbose": parsed.verbose if hasattr(parsed, "verbose") else False,
            "config": parsed.config if hasattr(parsed, "config") else None,
            "output_dir": parsed.output_dir
            if hasattr(parsed, "output_dir")
            else "experiment_results",
            # Command-specific arguments
            **vars(parsed),
        }

    def parse_run_request(self, args: dict[str, Any]) -> ExperimentRequestDTO:
        """Parse run request.

        Args:
            args: Parsed arguments

        Returns:
            Experiment request DTO
        """
        return ExperimentRequestDTO(
            name=args.get("name", "security_experiment"),
            attack_types=args.get("attack_types", []),
            injection_layers=args.get("layers", []),
            severities=args.get("severities", []),
            skill_names=args.get("skills", []),
            max_concurrency=args.get("max_concurrency", 4),
            timeout_seconds=args.get("timeout", 120),
            max_tests=args.get("max_tests"),
            output_dir=args.get("output_dir", "experiment_results"),
        )

    def parse_generate_request(self, args: dict[str, Any]) -> TestGenerationRequestDTO:
        """Parse generate request.

        Args:
            args: Parsed arguments

        Returns:
            Test generation request DTO
        """
        return TestGenerationRequestDTO(
            attack_types=args.get("attack_types", []),
            injection_layers=args.get("layers", []),
            severities=args.get("severities", []),
            skill_names=args.get("skills", []),
            output_dir=args.get("output_dir", "generated_tests"),
        )

    def parse_generate_intelligent_request(
        self, args: dict[str, Any]
    ) -> IntelligentTestGenerationRequestDTO:
        """Parse intelligent generation request.

        Args:
            args: Parsed arguments

        Returns:
            Intelligent test generation request DTO
        """
        return IntelligentTestGenerationRequestDTO(
            skill_name=args.get("skill", ""),
            strategy=args.get("strategy", "comprehensive"),
            attack_types=args.get("attack_types", []),
            payload=args.get("payload", ""),
            output_dir=args.get("output_dir", "intelligent_tests"),
            llm_provider=args.get("llm_provider", "openai"),
            max_concurrency=args.get("max_concurrency", 4),
        )

    def parse_generate_code_cache_request(self, args: dict[str, Any]) -> dict[str, Any]:
        """Parse code cache generation request.

        Args:
            args: Parsed arguments

        Returns:
            Code cache generation request dictionary
        """
        return {
            "attack_types": args.get("attack_types", []),
            "all_types": args.get("all", False),
            "llm_provider": args.get("llm_provider", "openai"),
            "cache_dir": args.get("cache_dir", "data/malicious_code_cache"),
            "overwrite": args.get("overwrite", False),
        }

    def _add_two_phase_command(self) -> None:
        """Add two-phase framework command."""
        two_phase_parser = self._subparsers.add_parser(
            "two-phase",
            help="Run two-phase security testing framework",
        )

        # Add subcommand group
        two_phase_subparsers = two_phase_parser.add_subparsers(
            dest="two_phase_action",
            help="Two-phase framework actions",
        )

        # two-phase run - Run complete two-phase flow
        run_parser = two_phase_subparsers.add_parser(
            "run",
            help="Run complete two-phase evaluation flow (generation + execution)",
        )

        run_parser.add_argument(
            "-c",
            "--config",
            type=str,
            help="Configuration file path",
        )

        run_parser.add_argument(
            "-o",
            "--output-dir",
            type=str,
            help="Output directory (overrides config file)",
        )

        run_parser.add_argument(
            "--generation-strategy",
            type=str,
            choices=["template_injection", "llm_intelligent"],
            help="Generation strategy (overrides config file)",
        )

        run_parser.add_argument(
            "--max-concurrency",
            type=int,
            help="Maximum concurrency (overrides config file)",
        )

        run_parser.add_argument(
            "--max-tests",
            type=int,
            help="Maximum tests (overrides config file)",
        )

        # two-phase generate - Run phase 1 only
        gen_parser = two_phase_subparsers.add_parser(
            "generate",
            help="Run phase 1 only: Generate test cases",
        )

        gen_parser.add_argument(
            "-c",
            "--config",
            type=str,
            help="Configuration file path",
        )

        gen_parser.add_argument(
            "-o",
            "--output-dir",
            type=str,
            help="Output directory (overrides config file)",
        )

        gen_parser.add_argument(
            "--strategy",
            type=str,
            choices=["template_injection", "llm_intelligent"],
            help="Generation strategy (overrides config file)",
        )

        # two-phase execute - Run phase 2 only
        exec_parser = two_phase_subparsers.add_parser(
            "execute",
            help="Run phase 2 only: Execute test cases",
        )

        exec_parser.add_argument(
            "-c",
            "--config",
            type=str,
            help="Configuration file path",
        )

        exec_parser.add_argument(
            "-t",
            "--test-dir",
            type=str,
            help="Test directory (generated from phase 1)",
        )

        exec_parser.add_argument(
            "-o",
            "--output-dir",
            type=str,
            help="Output directory (overrides config file)",
        )

        # two-phase validate - Validate configuration
        validate_parser = two_phase_subparsers.add_parser(
            "validate",
            help="Validate configuration file",
        )

        validate_parser.add_argument(
            "config",
            type=str,
            help="Configuration file path",
        )

        # two-phase init - Create example configuration
        init_parser = two_phase_subparsers.add_parser(
            "init",
            help="Create example configuration file",
        )

        init_parser.add_argument(
            "output",
            type=str,
            nargs="?",
            default="two_phase_config.yaml",
            help="Output file path",
        )

        init_parser.add_argument(
            "--example",
            action="store_true",
            help="Create example configuration with all options",
        )

    def parse_two_phase_request(self, args: dict[str, Any]) -> dict[str, Any]:
        """Parse two-phase framework request.

        Args:
            args: Parsed arguments

        Returns:
            Two-phase framework request dictionary
        """
        action = args.get("two_phase_action", "")

        if action == "run":
            return {
                "action": "run",
                "config": args.get("config"),
                "output_dir": args.get("output_dir"),
                "generation_strategy": args.get("generation_strategy"),
                "max_concurrency": args.get("max_concurrency"),
                "max_tests": args.get("max_tests"),
            }
        elif action == "generate":
            return {
                "action": "generate",
                "config": args.get("config"),
                "output_dir": args.get("output_dir"),
                "strategy": args.get("strategy"),
            }
        elif action == "execute":
            return {
                "action": "execute",
                "config": args.get("config"),
                "test_dir": args.get("test_dir"),
                "output_dir": args.get("output_dir"),
            }
        elif action == "validate":
            return {
                "action": "validate",
                "config": args.get("config"),
            }
        elif action == "init":
            return {
                "action": "init",
                "output": args.get("output", "two_phase_config.yaml"),
                "example": args.get("example", False),
            }

        return {"action": action}
