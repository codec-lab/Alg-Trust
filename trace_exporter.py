"""
Trace Exporter for LLM Analysis

Exports learner traces in formats suitable for LLM reasoning:
1. Detailed format - shows all available actions and which was chosen
2. Compact format - just shows the steps taken
3. Comparison format - shows learner vs expert side by side
"""

from typing import List, Dict, Optional
from learner_integration import LearnerGraphWalker, extract_actions_from_tokens
from learner import create_learner, list_learner_profiles, LEARNER_PROFILES
from policies import PRECEDENCE_MAPS
from tokenizer import tokenize


def export_trace_detailed(expression: str, learner_name: str) -> str:
    """
    Export a detailed trace showing all actions at each step.

    Format:
    - Shows expression and learner info
    - For each step: state, all available actions, which was chosen
    - Marks valid/invalid actions according to learner's policies
    """
    learner = create_learner(learner_name)
    walker = LearnerGraphWalker(expression, learner)
    steps = walker.walk_deterministic()

    lines = []
    lines.append("=" * 60)
    lines.append("LEARNER TRACE")
    lines.append("=" * 60)
    lines.append(f"Expression: {expression}")
    lines.append(f"Learner Profile: {learner_name}")
    lines.append(f"Precedence Belief: {learner.precedence_name}")
    lines.append(f"  Precedence values: {learner.precedence_map}")
    lines.append(f"Policies: {', '.join(learner.policy_names)}")
    lines.append(f"Description: {learner.description}")
    lines.append("=" * 60)
    lines.append("")

    for i, step in enumerate(steps):
        lines.append(f"STEP {i + 1}: {step['state']}")
        lines.append("-" * 40)

        if step.get('is_final'):
            lines.append(f"  FINAL RESULT: {step['result']}")
        else:
            lines.append("  Available actions:")
            for action in step.get('all_actions', []):
                is_valid = action in step.get('valid_actions', [])
                is_chosen = step.get('chosen_action') == action

                validity = "[VALID]" if is_valid else "[INVALID]"
                chosen_mark = " <-- CHOSEN" if is_chosen else ""

                lines.append(f"    {validity} {action.action_type}: {action.description}{chosen_mark}")

            if step.get('chosen_action'):
                lines.append(f"  ")
                lines.append(f"  Action taken: {step['chosen_action'].description}")

        lines.append("")

    return "\n".join(lines)


def export_trace_compact(expression: str, learner_name: str) -> str:
    """
    Export a compact trace showing just the steps taken.

    Format:
    Expression: (4+3)*5+2
    Learner: multiplication_first

    (4+3)*5+2
      -> distribute (4+3)*5
    (4*5+3*5)+2
      -> evaluate 4*5
    ...
    Result: 37
    """
    learner = create_learner(learner_name)
    walker = LearnerGraphWalker(expression, learner)
    steps = walker.walk_deterministic()

    lines = []
    lines.append(f"Expression: {expression}")
    lines.append(f"Learner: {learner_name} ({learner.precedence_name} precedence)")
    lines.append("")

    for i, step in enumerate(steps):
        lines.append(step['state'])

        if step.get('is_final'):
            lines.append(f"")
            lines.append(f"Final Result: {step['result']}")
        elif step.get('chosen_action'):
            action = step['chosen_action']
            lines.append(f"  -> {action.action_type}: {action.description}")

    return "\n".join(lines)


def export_trace_comparison(expression: str, learner_name: str,
                            compare_to: str = "expert") -> str:
    """
    Export a side-by-side comparison of two learners.
    """
    learner1 = create_learner(learner_name)
    learner2 = create_learner(compare_to)

    walker1 = LearnerGraphWalker(expression, learner1)
    walker2 = LearnerGraphWalker(expression, learner2)

    steps1 = walker1.walk_deterministic()
    steps2 = walker2.walk_deterministic()

    lines = []
    lines.append("=" * 70)
    lines.append("COMPARISON: Two learners solving the same expression")
    lines.append("=" * 70)
    lines.append(f"Expression: {expression}")
    lines.append("")
    lines.append(f"LEARNER A: {learner_name}")
    lines.append(f"  Precedence: {learner1.precedence_name}")
    lines.append(f"  Policies: {', '.join(learner1.policy_names)}")
    lines.append("")
    lines.append(f"LEARNER B: {compare_to}")
    lines.append(f"  Precedence: {learner2.precedence_name}")
    lines.append(f"  Policies: {', '.join(learner2.policy_names)}")
    lines.append("=" * 70)
    lines.append("")

    # Show steps side by side
    max_steps = max(len(steps1), len(steps2))

    lines.append(f"{'LEARNER A':<35} | {'LEARNER B':<35}")
    lines.append("-" * 35 + " | " + "-" * 35)

    for i in range(max_steps):
        # Learner A
        if i < len(steps1):
            step1 = steps1[i]
            if step1.get('is_final'):
                a_text = f"RESULT: {step1['result']}"
            else:
                action = step1.get('chosen_action')
                a_text = f"{step1['state']}"
                if action:
                    a_text += f" -> {action.action_type[:4]}"
        else:
            a_text = ""

        # Learner B
        if i < len(steps2):
            step2 = steps2[i]
            if step2.get('is_final'):
                b_text = f"RESULT: {step2['result']}"
            else:
                action = step2.get('chosen_action')
                b_text = f"{step2['state']}"
                if action:
                    b_text += f" -> {action.action_type[:4]}"
        else:
            b_text = ""

        lines.append(f"{a_text:<35} | {b_text:<35}")

    # Summary
    result1 = steps1[-1].get('result') if steps1 else None
    result2 = steps2[-1].get('result') if steps2 else None

    lines.append("")
    lines.append("=" * 70)
    lines.append("SUMMARY")
    lines.append(f"  {learner_name}: {len(steps1)} steps, result = {result1}")
    lines.append(f"  {compare_to}: {len(steps2)} steps, result = {result2}")

    if result1 != result2:
        lines.append(f"  WARNING: DIFFERENT RESULTS!")
    else:
        lines.append(f"  Same result, different paths" if len(steps1) != len(steps2) else "  Same result and steps")

    return "\n".join(lines)


def export_for_llm_diagnosis(expression: str, learner_name: str,
                              hide_learner_name: bool = True) -> str:
    """
    Export a trace formatted for LLM diagnosis task.

    If hide_learner_name=True, the LLM has to figure out what learner this is.
    """
    learner = create_learner(learner_name)
    walker = LearnerGraphWalker(expression, learner)
    steps = walker.walk_deterministic()

    lines = []
    lines.append("A student solved the following math expression.")
    lines.append("Here is their step-by-step work:")
    lines.append("")
    lines.append(f"Expression: {expression}")
    lines.append("")

    for i, step in enumerate(steps):
        if step.get('is_final'):
            lines.append(f"Step {i + 1}: {step['state']} (FINAL ANSWER: {step['result']})")
        elif step.get('chosen_action'):
            action = step['chosen_action']
            lines.append(f"Step {i + 1}: {step['state']}")
            lines.append(f"         Student's action: {action.description}")
            lines.append("")

    if not hide_learner_name:
        lines.append("")
        lines.append("---")
        lines.append(f"[Ground truth: This was the '{learner_name}' learner profile]")

    return "\n".join(lines)


def export_all_traces(expression: str, learner_names: List[str] = None) -> Dict[str, str]:
    """
    Export traces for multiple learners on the same expression.
    """
    if learner_names is None:
        learner_names = list_learner_profiles()

    return {
        name: export_trace_compact(expression, name)
        for name in learner_names
    }


def get_learner_profiles_description() -> str:
    """
    Get a description of all available learner profiles for LLM context.
    """
    lines = []
    lines.append("AVAILABLE LEARNER PROFILES:")
    lines.append("")

    for name, profile in LEARNER_PROFILES.items():
        lines.append(f"• {name}:")
        lines.append(f"    Precedence: {profile['precedence']}")
        lines.append(f"    Policies: {', '.join(profile['policies'])}")
        lines.append(f"    Description: {profile['description']}")
        lines.append("")

    lines.append("PRECEDENCE BELIEFS:")
    for name, pmap in PRECEDENCE_MAPS.items():
        # Sort by precedence value to show order
        sorted_ops = sorted(pmap.items(), key=lambda x: -x[1])
        order = " > ".join([f"{op}({v})" for op, v in sorted_ops])
        lines.append(f"  • {name}: {order}")

    return "\n".join(lines)


if __name__ == "__main__":
    # Test the exporters
    expr = "(4+3)*5+2"

    print("=" * 70)
    print("TEST: Detailed Trace Export")
    print("=" * 70)
    print(export_trace_detailed(expr, "multiplication_first"))

    print("\n" * 2)
    print("=" * 70)
    print("TEST: Compact Trace Export")
    print("=" * 70)
    print(export_trace_compact(expr, "multiplication_first"))

    print("\n" * 2)
    print("=" * 70)
    print("TEST: Comparison Export")
    print("=" * 70)
    print(export_trace_comparison(expr, "multiplication_first", "expert"))

    print("\n" * 2)
    print("=" * 70)
    print("TEST: LLM Diagnosis Format")
    print("=" * 70)
    print(export_for_llm_diagnosis(expr, "addition_first", hide_learner_name=True))

    print("\n" * 2)
    print("=" * 70)
    print("TEST: Learner Profiles Description")
    print("=" * 70)
    print(get_learner_profiles_description())
