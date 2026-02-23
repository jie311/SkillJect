"""
Presentation layer CLI commands.

Provides implementations of various command line interface commands.
"""

from pathlib import Path
from typing import Any

from src.shared.types import AttackType, InjectionLayer
from application.use_cases.run_experiment import ExperimentConfig
from infrastructure.indexing.skill_index import SkillIndex
from infrastructure.config.managers.config_manager import get_config

# Import two-phase command
from presentation.cli.commands.two_phase_command import TwoPhaseCommand


class CLICommand:
    """CLI command base class."""

    def __init__(self):
        self._config = get_config()

    def execute(self, **kwargs) -> Any:
        """Execute command.

        Args:
            **kwargs: Command parameters

        Returns:
            Command result
        """
        raise NotImplementedError


class RunExperimentCommand(CLICommand):
    """Run experiment command."""

    def execute(
        self,
        name: str = "security_experiment",
        attack_types: list[str] | None = None,
        injection_layers: list[str] | None = None,
        max_concurrency: int = 4,
        timeout: int = 120,
        max_tests: int | None = None,
        output_dir: str = "experiment_results",
        **kwargs,
    ) -> dict[str, Any]:
        """Execute experiment.

        Args:
            name: Experiment name
            attack_types: List of attack types
            injection_layers: List of injection layers
            max_concurrency: Maximum concurrency
            timeout: Timeout duration
            max_tests: Maximum number of tests
            output_dir: Output directory

        Returns:
            Experiment result
        """
        # Create configuration
        config = ExperimentConfig(
            name=name,
            attack_types=[AttackType(at) for at in attack_types] if attack_types else [],
            injection_layers=[InjectionLayer(il) for il in injection_layers]
            if injection_layers
            else [],
            max_concurrency=max_concurrency,
            timeout_seconds=timeout,
            max_tests=max_tests,
            output_dir=output_dir,
        )

        # Create use case
        skill_index = SkillIndex(
            skills_dir=Path(self._config.skills_dir),
            tests_dir=Path(self._config.test_dir),
        )

        # TODO: Create test runner
        # test_runner = ...

        # use_case = RunExperimentUseCase(
        #     skill_index=skill_index,
        #     test_runner=test_runner,
        # )

        # result = use_case.execute(config)

        return {
            "experiment_id": f"{name}_pending",
            "status": "pending",
            "message": "Experiment execution feature is under refactoring",
        }


class GenerateTestsCommand(CLICommand):
    """Generate tests command."""

    def execute(
        self,
        attack_types: list[str] | None = None,
        injection_layers: list[str] | None = None,
        output_dir: str = "generated_tests",
        **kwargs,
    ) -> dict[str, Any]:
        """Generate test cases.

        Args:
            attack_types: List of attack types
            injection_layers: List of injection layers
            output_dir: Output directory

        Returns:
            Generation result
        """
        # Create skill index
        skill_index = SkillIndex(
            skills_dir=Path(self._config.skills_dir),
            tests_dir=Path(self._config.test_dir),
        )

        # Create generation use case
        from ...application.use_cases.run_experiment import GenerateTestsUseCase

        use_case = GenerateTestsUseCase(
            skill_index=skill_index,
            skills_dir=Path(self._config.skills_dir),
        )

        # Execute generation
        result = use_case.execute(
            attack_types=[AttackType(at) for at in attack_types] if attack_types else None,
            injection_layers=[InjectionLayer(il) for il in injection_layers]
            if injection_layers
            else None,
            output_dir=output_dir,
        )

        return result


class ListTestsCommand(CLICommand):
    """List tests command."""

    def execute(
        self,
        skill_name: str | None = None,
        layer: str | None = None,
        attack_type: str | None = None,
        limit: int | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """List test cases.

        Args:
            skill_name: Skill name filter
            layer: Injection layer filter
            attack_type: Attack type filter
            limit: Limit count

        Returns:
            List of test cases
        """
        # Create skill index
        skill_index = SkillIndex(
            skills_dir=Path(self._config.skills_dir),
            tests_dir=Path(self._config.test_dir),
        )

        # List tests
        tests = skill_index.list_tests(
            skill_name=skill_name,
            layer=layer,
            attack_type=attack_type,
            limit=limit,
        )

        # Convert to dictionary list
        return [
            {
                "test_id": t.test_id,
                "skill_name": t.skill_name,
                "layer": t.layer,
                "attack_type": t.attack_type,
                "severity": t.severity,
                "path": t.path,
            }
            for t in tests
        ]


class ValidateTestsCommand(CLICommand):
    """Validate tests command."""

    def execute(
        self,
        test_dir: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Validate test cases.

        Args:
            test_dir: Test directory

        Returns:
            Validation result
        """
        # TODO: Integrate test validator
        return {
            "is_valid": False,
            "message": "Test validation feature is under refactoring",
        }


class GetStatusCommand(CLICommand):
    """Get status command."""

    def execute(
        self,
        experiment_id: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """Get experiment status.

        Args:
            experiment_id: Experiment ID

        Returns:
            Experiment status
        """
        # TODO: Integrate status query
        return {
            "experiment_id": experiment_id or "unknown",
            "status": "unknown",
            "message": "Status query feature is under refactoring",
        }


class GenerateIntelligentTestsCommand(CLICommand):
    """Generate intelligent tests command."""

    def execute(
        self,
        skill: str = "",
        strategy: str = "comprehensive",
        attack_types: list[str] | None = None,
        payload: str = "",
        output_dir: str = "intelligent_tests",
        llm_provider: str = "mock",
        max_concurrency: int = 4,
        no_code_cache: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute intelligent test generation.

        Args:
            skill: Single skill name (empty for all skills)
            strategy: Injection strategy
            attack_types: List of attack types
            payload: Custom payload
            output_dir: Output directory
            llm_provider: LLM provider
            max_concurrency: Maximum concurrency
            no_code_cache: Whether to disable code cache

        Returns:
            Generation result
        """
        import asyncio

        from application.use_cases.generate_intelligent_tests import (
            GenerateIntelligentTestsUseCase,
            IntelligentTestGenerationRequest,
        )

        # Create use case
        use_case = GenerateIntelligentTestsUseCase(
            skills_dir=Path(self._config.skills_dir),
        )

        # Create request
        request = IntelligentTestGenerationRequest(
            skill_name=skill,
            strategy=strategy,
            attack_types=attack_types or [],
            payload=payload,
            output_dir=output_dir,
            llm_provider=llm_provider,
            max_concurrency=max_concurrency,
        )

        # Execute generation
        result = asyncio.run(use_case.execute(request))

        return result.to_dict()


class GenerateCodeCacheCommand(CLICommand):
    """Generate code cache command."""

    def execute(
        self,
        attack_types: list[str] | None = None,
        all_types: bool = False,
        llm_provider: str = "mock",
        cache_dir: str = "data/malicious_code_cache",
        overwrite: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute code cache generation.

        Args:
            attack_types: Specified list of attack types
            all_types: Whether to generate all types
            llm_provider: LLM provider
            cache_dir: Cache directory
            overwrite: Whether to overwrite existing cache

        Returns:
            Generation result
        """
        import asyncio

        from domain.generation.services.code_cache_generator import CodeCacheGenerator
        from infrastructure.llm.factory import create_client

        # Create LLM client
        llm_client = create_client(llm_provider)

        # Create generator
        generator = CodeCacheGenerator(
            llm_client=llm_client,
            cache_dir=Path(cache_dir),
        )

        # Determine attack types to generate
        types_to_generate = []
        if all_types:
            from src.shared.types import AttackType

            types_to_generate = list(AttackType)
        elif attack_types:
            from src.shared.types import AttackType

            types_to_generate = [AttackType(at) for at in attack_types]
        else:
            from src.shared.types import AttackType

            types_to_generate = list(AttackType)

        # Generate cache
        if len(types_to_generate) == 1:
            # Single type
            result = asyncio.run(generator.generate_for_attack_type(types_to_generate[0]))
            return {
                "success": True,
                "message": f"Generated code cache for {types_to_generate[0].value}",
                "cache_dir": cache_dir,
            }
        else:
            # Multiple types
            results = asyncio.run(generator.generate_all_caches())
            return {
                "success": results["total"] == len(results["successful"]),
                "message": f"Generated {len(results['successful'])}/{results['total']} code caches",
                "successful": results["successful"],
                "failed": results["failed"],
                "errors": results["errors"],
                "cache_dir": cache_dir,
            }


class TwoPhaseEvalCommand(CLICommand):
    """Two-phase framework command wrapper."""

    def __init__(self):
        super().__init__()
        self._two_phase_cmd = TwoPhaseCommand()

    def execute(
        self,
        action: str = "run",
        config: str | None = None,
        output_dir: str | None = None,
        verbose: bool = False,
        **kwargs,
    ) -> dict[str, Any]:
        """Execute two-phase framework command.

        Args:
            action: Action type (run, generate, execute, validate, init)
            config: Configuration file path
            output_dir: Output directory
            verbose: Verbose output
            **kwargs: Other parameters

        Returns:
            Execution result
        """
        # Build override parameters
        overrides = {}
        for key, value in kwargs.items():
            if value is not None and key not in ("action", "verbose"):
                # Convert parameter name to config path
                config_key = key.replace("_", ".")
                overrides[config_key] = value

        if action == "run":
            return self._two_phase_cmd.execute(
                config=config,
                output_dir=output_dir,
                verbose=verbose,
                **overrides,
            )
        elif action == "generate":
            return self._two_phase_cmd.execute_phase1_only(
                config=config,
                output_dir=output_dir,
                verbose=verbose,
                **overrides,
            )
        elif action == "execute":
            return self._two_phase_cmd.execute_phase2_only(
                config=config,
                test_dir=kwargs.get("test_dir"),
                output_dir=output_dir,
                verbose=verbose,
                **overrides,
            )
        elif action == "validate":
            return self._two_phase_cmd.validate_config(
                config=config or kwargs.get("config"),
            )
        elif action == "init":
            output_path = kwargs.get("output", "two_phase_config.yaml")
            example = kwargs.get("example", False)

            if example:
                return self._two_phase_cmd.create_example_config(output_path)
            else:
                from infrastructure.config.loaders.config_loader import ConfigLoader

                ConfigLoader.save_default_config(output_path)
                return {
                    "success": True,
                    "output_file": output_path,
                    "message": "Configuration file created",
                }

        return {
            "success": False,
            "error": f"Unknown action: {action}",
        }
