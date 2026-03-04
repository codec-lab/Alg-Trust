"""
LLM Teacher Module

Uses LLMs to:
1. Diagnose learner misconceptions from their traces
2. Generate teaching situations/interventions
3. Create targeted practice problems

Supports multiple LLM providers: OpenAI, Anthropic (Claude)
"""

import os
import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, skip

from trace_exporter import (
    export_trace_detailed,
    export_trace_compact,
    export_for_llm_diagnosis,
    export_trace_comparison,
    get_learner_profiles_description
)
from learner import list_learner_profiles, LEARNER_PROFILES


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

DIAGNOSIS_PROMPT = """You are an expert math education researcher analyzing student work.

A student solved a mathematical expression. Your task is to analyze their work and identify:
1. What order of operations rules do they seem to believe?
2. How do they handle brackets/parentheses?
3. What direction do they evaluate (left-to-right, right-to-left)?
4. Did they make any mathematical errors?

Here is the student's work:

{trace}

---

Based on this trace, provide your analysis:

1. PRECEDENCE BELIEF: What does this student believe about operator precedence?
   (e.g., BODMAS/PEMDAS, addition before multiplication, all operators equal, etc.)

2. BRACKET HANDLING: How do they handle brackets?
   (e.g., evaluate inside first, distribute, ignore/drop brackets)

3. DIRECTION: What direction do they evaluate same-precedence operators?
   (e.g., left-to-right, right-to-left)

4. ERRORS: Did they make any mathematical errors? If so, what?

5. DIAGNOSIS: In one sentence, summarize this student's understanding of order of operations.
"""

PROFILE_MATCHING_PROMPT = """You are an expert math education researcher.

A student solved a mathematical expression. I want you to identify which "learner profile" best matches their behavior.

Here is the student's work:
{trace}

---

Here are the available learner profiles:
{profiles}

---

Based on the student's work, which profile BEST matches their behavior?

Respond with:
1. MATCHED PROFILE: [profile name]
2. CONFIDENCE: [high/medium/low]
3. REASONING: [2-3 sentences explaining why this profile matches]
"""

# =============================================================================
# LLM CLIENT WRAPPERS
# =============================================================================

@dataclass
class LLMResponse:
    """Standardized response from any LLM provider."""
    content: str
    model: str
    usage: Dict = None
    raw_response: any = None


class LLMClient:
    """Base class for LLM clients."""

    def complete(self, prompt: str, system_prompt: str = None) -> LLMResponse:
        raise NotImplementedError


class OpenAIClient(LLMClient):
    """OpenAI API client."""

    def __init__(self, api_key: str = None, model: str = "gpt-4"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("OpenAI API key required. Set OPENAI_API_KEY env var or pass api_key.")

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError("openai package required. Install with: pip install openai")

    def complete(self, prompt: str, system_prompt: str = None) -> LLMResponse:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=self.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens
            },
            raw_response=response
        )


class AnthropicClient(LLMClient):
    """Anthropic (Claude) API client."""

    def __init__(self, api_key: str = None, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

        if not self.api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY env var or pass api_key.")

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("anthropic package required. Install with: pip install anthropic")

    def complete(self, prompt: str, system_prompt: str = None) -> LLMResponse:
        kwargs = {
            "model": self.model,
            "max_tokens": 2000,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.client.messages.create(**kwargs)

        return LLMResponse(
            content=response.content[0].text,
            model=self.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            },
            raw_response=response
        )


class MockLLMClient(LLMClient):
    """Mock client for testing without API calls."""

    def __init__(self):
        self.model = "mock-model"
        self.call_history = []

    def complete(self, prompt: str, system_prompt: str = None) -> LLMResponse:
        self.call_history.append({"prompt": prompt, "system": system_prompt})

        # Return a mock response
        return LLMResponse(
            content="[MOCK RESPONSE] This is a placeholder. Use a real LLM client for actual diagnosis.",
            model=self.model,
            usage={"prompt_tokens": len(prompt.split()), "completion_tokens": 20}
        )


def get_llm_client(provider: str = "auto", **kwargs) -> LLMClient:
    """
    Get an LLM client based on available API keys.

    Args:
        provider: "openai", "anthropic", "mock", or "auto" (tries to detect)
        **kwargs: Additional arguments for the client

    Returns:
        LLMClient instance
    """
    if provider == "mock":
        return MockLLMClient()

    if provider == "auto":
        # Try to detect available API keys
        if os.getenv("ANTHROPIC_API_KEY"):
            provider = "anthropic"
        elif os.getenv("OPENAI_API_KEY"):
            provider = "openai"
        else:
            print("Warning: No API keys found. Using mock client.")
            return MockLLMClient()

    if provider == "openai":
        return OpenAIClient(**kwargs)
    elif provider == "anthropic":
        return AnthropicClient(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}")


# =============================================================================
# TEACHER FUNCTIONS
# =============================================================================

class LLMTeacher:
    """
    LLM-based teacher that can diagnose student work and generate teaching interventions.
    """

    def __init__(self, client: LLMClient = None, provider: str = "auto"):
        """
        Initialize the teacher.

        Args:
            client: Pre-configured LLM client
            provider: If client not provided, create one with this provider
        """
        self.client = client or get_llm_client(provider)

    def diagnose_trace(self, expression: str, learner_name: str,
                       hide_identity: bool = True) -> Dict:
        """
        Diagnose a learner's work on an expression.

        Args:
            expression: The math expression
            learner_name: Name of the learner profile (used to generate trace)
            hide_identity: If True, don't tell LLM which learner it is

        Returns:
            Dict with trace, prompt, and LLM response
        """
        trace = export_for_llm_diagnosis(expression, learner_name, hide_learner_name=hide_identity)
        prompt = DIAGNOSIS_PROMPT.format(trace=trace)

        response = self.client.complete(prompt)

        return {
            "expression": expression,
            "learner_name": learner_name,
            "trace": trace,
            "diagnosis": response.content,
            "model": response.model
        }

    def match_profile(self, expression: str, learner_name: str) -> Dict:
        """
        Ask LLM to identify which learner profile matches the trace.

        Args:
            expression: The math expression
            learner_name: Actual learner (hidden from LLM)

        Returns:
            Dict with trace, LLM's guess, and whether it was correct
        """
        trace = export_for_llm_diagnosis(expression, learner_name, hide_learner_name=True)
        profiles = get_learner_profiles_description()

        prompt = PROFILE_MATCHING_PROMPT.format(trace=trace, profiles=profiles)

        response = self.client.complete(prompt)

        # Try to extract the matched profile from response
        matched = None
        for profile_name in list_learner_profiles():
            if profile_name.lower() in response.content.lower():
                matched = profile_name
                break

        return {
            "expression": expression,
            "actual_learner": learner_name,
            "llm_guess": matched,
            "correct": matched == learner_name if matched else False,
            "llm_response": response.content,
            "model": response.model
        }

# =============================================================================
# EVALUATION FUNCTIONS
# =============================================================================

def evaluate_profile_matching(expressions: List[str], learner_names: List[str],
                               teacher: LLMTeacher) -> Dict:
    """
    Evaluate how well the LLM can identify learner profiles.

    Args:
        expressions: List of expressions to test
        learner_names: List of learner profiles to test
        teacher: LLMTeacher instance

    Returns:
        Dict with accuracy and detailed results
    """
    results = []
    correct = 0
    total = 0

    for expr in expressions:
        for learner in learner_names:
            result = teacher.match_profile(expr, learner)
            results.append(result)

            total += 1
            if result["correct"]:
                correct += 1

            print(f"  {expr} | {learner} → LLM guessed: {result['llm_guess']} | {'✓' if result['correct'] else '✗'}")

    accuracy = correct / total if total > 0 else 0

    return {
        "accuracy": accuracy,
        "correct": correct,
        "total": total,
        "results": results
    }


# =============================================================================
# MAIN / CLI
# =============================================================================

def run_demo(provider: str = "auto"):
    """Run a demo of the LLM teacher."""
    print("=" * 70)
    print("LLM TEACHER DEMO")
    print("=" * 70)

    try:
        teacher = LLMTeacher(provider=provider)
        print(f"Using LLM provider: {teacher.client.model}")
    except Exception as e:
        print(f"Error initializing LLM client: {e}")
        print("Using mock client for demo...")
        teacher = LLMTeacher(provider="mock")

    # Demo 1: Diagnose a trace
    print("\n" + "=" * 70)
    print("DEMO 1: Diagnose a student trace")
    print("=" * 70)

    expr = "2+3*4"
    learner = "addition_first"

    print(f"\nExpression: {expr}")
    print(f"Learner: {learner} (hidden from LLM)")
    print("\nStudent's work:")
    print(export_trace_compact(expr, learner))

    print("\nAsking LLM to diagnose...")
    diagnosis = teacher.diagnose_trace(expr, learner)
    print("\nLLM DIAGNOSIS:")
    print(diagnosis["diagnosis"])

    # Demo 2: Profile matching
    print("\n" + "=" * 70)
    print("DEMO 2: Match learner profile")
    print("=" * 70)

    result = teacher.match_profile(expr, learner)
    print(f"\nActual learner: {result['actual_learner']}")
    print(f"LLM's guess: {result['llm_guess']}")
    print(f"Correct: {result['correct']}")
    print(f"\nLLM's reasoning:")
    print(result['llm_response'][:500] + "..." if len(result['llm_response']) > 500 else result['llm_response'])


if __name__ == "__main__":
    import sys

    provider = sys.argv[1] if len(sys.argv) > 1 else "auto"
    run_demo(provider)
