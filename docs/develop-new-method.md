# Developing New Test Generation Methods

A quick start guide for developers who want to create new test generation strategies in SkillJect.

## Overview

In SkillJect, a **Method** (or Strategy) is a test case generation approach. Each method represents a different way to create skill files containing malicious content for testing AI agent security defenses.

**Existing Methods:**
- `template_injection` - Inject attack payloads into existing skill templates
- `llm_intelligent` - Use LLM to generate adaptive attacks
- `skillject` - Combine pre-generated scripts with LLM fusion

## Architecture

```
src/domain/generation/services/
├── generation_strategy.py          # Abstract base class
├── generation_factory.py           # Factory for creating strategies
├── template_injection_generator.py # Template injection method
├── llm_intelligent_generator.py    # LLM intelligent method
└── skillject_generator.py          # SkillJect method
```

All methods inherit from `TestGenerationStrategy` and are registered in the factory.

---

## Part 1: The Template Injection Method (Example)

`template_injection` is the simplest and most understandable method. It generates test cases by injecting predefined attack payloads directly into skill templates.

### 1.1 Core Implementation

**File:** `src/domain/generation/services/template_injection_generator.py`

**Class Structure:**
```python
class TemplateInjectionGenerator(TestGenerationStrategy):
    """Template injection test generator

    Generates test cases by injecting attack payloads into existing skill templates
    """
```

### 1.2 Generation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Template Injection Flow                          │
├─────────────────────────────────────────────────────────────────────┤
│  1. Scan skill directory → Get all SKILL.md files                   │
│  2. Filter payloads → By attack_type and severity                    │
│  3. Combine generation → For each (skill × payload × layer):        │
│     a. Create test directory test_details/{strategy}/{dataset}/...   │
│     b. Copy skill directory to test location                        │
│     c. Inject payload into SKILL.md                                  │
│     d. Save test case metadata                                      │
│  4. Return GeneratedTestSuite                                        │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Injection Logic

Injection location determined by `InjectionLayer`:

| Layer | Location | Example |
|-------|----------|---------|
| `description` | frontmatter description field | `description: "malicious original"` |
| `instruction` | Body content after frontmatter | Payload inserted after `---` |
| `resource` | Resource files | Requires additional processing |

---

## Part 2: Registering a New Method

### 2.1 Add Strategy Enum

**File:** `src/domain/testing/value_objects/execution_config.py`

```python
class GenerationStrategy(Enum):
    """Generation strategy type"""

    TEMPLATE_INJECTION = "template_injection"
    LLM_INTELLIGENT = "llm_intelligent"
    SECURITY_TEST_INPUTS = "security_test_inputs"
    SKILLJECT = "skillject"
    # YOUR_NEW_STRATEGY = "your_strategy_name"  # Add new enum value
```

### 2.2 Register in Factory

**File:** `src/domain/generation/services/generation_factory.py`

```python
from .your_generator import YourGenerator

class TestGenerationStrategyFactory:
    """Test generation strategy factory"""

    _strategies = {
        GenerationStrategy.TEMPLATE_INJECTION: TemplateInjectionGenerator,
        GenerationStrategy.LLM_INTELLIGENT: LLMIntelligentGenerator,
        GenerationStrategy.SKILLJECT: SkilljectGenerator,
        # GenerationStrategy.YOUR_NEW_STRATEGY: YourGenerator,  # Register here
    }
```

### 2.3 Create Config File

**File:** `config/your_strategy.yaml`

```yaml
# Your Strategy Test Case Generation Configuration

# Generation Method Identifier
method: your_strategy_name
description: "Description of your generation method"

# Template Configuration
template:
  base_dir: "{dataset_base_dir}"
  output_dir: your_output_directory

# Attack Payload Configuration
payloads:
  attack_types:
    - information_disclosure
    - privilege_escalation
  severities:
    - high
    - critical
  injection_layers:
    - instruction

# Skill Filter
skills:
  target_names: []  # Empty means all skills

# Generation Limits
limits:
  max_tests: null
```

---

## Part 3: Implementation Checklist

### 3.1 Required Files

| File | Purpose | Reference |
|------|---------|-----------|
| `src/domain/generation/services/your_generator.py` | Generator implementation | `template_injection_generator.py` |
| `config/your_strategy.yaml` | Method configuration | `template_injection.yaml` |

### 3.2 Required Modifications

| File | Modification |
|------|--------------|
| `execution_config.py` | Add `GenerationStrategy` enum value |
| `generation_factory.py` | Import and register generator class |

### 3.3 Must Implement Methods

```python
from abc import ABC, abstractmethod

class TestGenerationStrategy(ABC):
    @abstractmethod
    async def generate(self) -> GeneratedTestSuite:
        """Batch generate test suite"""
        pass

    @abstractmethod
    async def generate_stream_with_feedback(
        self,
        skill_name: str,
        attack_type,
        adaptive_params,
        output_dir: Path | None = None,
    ):
        """Generate with feedback (streaming iteration)"""
        pass

    @abstractmethod
    def validate_config(self) -> list[str]:
        """Validate configuration (empty list = valid)"""
        pass
```

### 3.4 Optional Helper Methods

| Method | Purpose |
|--------|---------|
| `is_test_case_already_exists()` | Check if test is already completed |
| `create_progress_bar()` | Create unified progress bar |
| `_create_suite_id()` | Generate suite ID |
| `_get_attack_type_dir()` | Get attack type directory name |

---

## Part 4: Quick Reference

### Attack Types

```python
class AttackType(str, Enum):
    INFORMATION_DISCLOSURE = "information_disclosure"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    UNAUTHORIZED_WRITE = "unauthorized_write"
    BACKDOOR_INJECTION = "backdoor_injection"
```

### Injection Layers

```python
class InjectionLayer(str, Enum):
    DESCRIPTION = "description"       # frontmatter description field
    INSTRUCTION = "instruction"       # Body content
    RESOURCE = "resource"             # Resource files
    ALL = "all"                       # All layers
```

### Severity Levels

```python
class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

### Output Directory Structure

```
test_details/
└── {strategy}/              # Strategy name
    └── {dataset}/           # Dataset name
        └── {skill_name}/    # Skill name
            └── {attack_type}/  # Attack type
                └── iteration_0/  # Iteration number
                    ├── SKILL.md  # Injected skill file
                    └── result.json # Test result
```

---

## Part 5: Running Your New Method

```bash
# Use your custom config
python run.py --config config/your_strategy.yaml

# Or specify method directly
python run.py --method your_strategy_name
```

---

## Related Files

- `src/shared/types.py` - Shared type definitions
- `src/domain/payload/registries/payload_registry.py` - Attack payload definitions
- `src/domain/generation/entities/test_suite.py` - Test suite entities
- `run.py` - Main entry point
