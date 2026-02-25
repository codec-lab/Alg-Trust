"""
Test Script for Policy and Learner System

Tests policies on example expressions and shows:
1. Individual policy results for each action
2. Learner results (conjunction of policies with precedence belief)
3. Comparison across learner profiles
"""

from tokenizer import tokenize
from policies import (
    Policy, Action, POLICY_REGISTRY, get_policy, list_policies,
    PRECEDENCE_MAPS, PRECEDENCE_BODMAS, get_evaluate_actions,
    list_precedence_maps, POLICY_CATEGORIES
)
from learner import (
    Learner, create_learner, create_custom_learner,
    list_learner_profiles, compare_learners, LEARNER_PROFILES,
    get_learner_builder_options
)


def create_actions_from_tokens(tokens: list) -> list:
    """
    Create Action objects for all possible evaluate actions from tokens.
    (Simplified version - only handles evaluate actions for testing)
    """
    actions = []
    operators = ['+', '-', '*', '/', '^']

    for i, token in enumerate(tokens):
        if token in operators and i > 0 and i < len(tokens) - 1:
            actions.append(Action(
                action_type='evaluate',
                operator=token,
                operator_index=i,
                description=f"Compute {tokens[i-1]} {token} {tokens[i+1]}"
            ))

    return actions


def print_policy_table(state: tuple, actions: list, policy_names: list, precedence_name: str = 'bodmas'):
    """
    Print a table showing policy results for each action.
    """
    precedence_map = PRECEDENCE_MAPS[precedence_name]

    # Header
    header = f"| Policy (prec={precedence_name:12}) |"
    for a in actions:
        header += f" {a.operator} ({a.operator_index}) |"

    print(header)
    print("|" + "-" * 35 + "|" + "--------|" * len(actions))

    # Each policy row
    for policy_name in policy_names:
        policy = get_policy(policy_name)
        row = f"| {policy_name:33} |"

        for action in actions:
            result = policy.evaluate(state, action, actions, precedence_map)
            symbol = "Y" if result else "N"
            row += f"   {symbol}    |"

        print(row)


def print_learner_table(state: tuple, actions: list, learner_names: list):
    """
    Print a table showing which actions each learner considers valid.
    """
    print("\n" + "=" * 90)
    print("LEARNER VALID ACTIONS (conjunction of policies + precedence belief)")
    print("=" * 90)

    # Header
    header = "| Learner               | Prec        |"
    for a in actions:
        header += f" {a.operator}({a.operator_index}) |"
    header += " Valid Actions          |"

    print(header)
    print("|" + "-" * 23 + "|" + "-" * 13 + "|" + "------|" * len(actions) + "-" * 24 + "|")

    for learner_name in learner_names:
        learner = create_learner(learner_name)
        valid = learner.valid_actions(state, actions)

        row = f"| {learner_name:21} | {learner.precedence_name:11} |"

        for action in actions:
            is_valid = action in valid
            symbol = "Y" if is_valid else "N"
            row += f"  {symbol}   |"

        # Show valid actions summary
        valid_summary = [f"{a.operator}({a.operator_index})" for a in valid]
        row += f" {', '.join(valid_summary) if valid_summary else 'none':22} |"

        print(row)


def test_expression(expression: str):
    """Run full policy and learner test on an expression."""
    print("\n" + "=" * 90)
    print(f"TESTING: {expression}")
    print("=" * 90)

    # Tokenize
    tokens = tokenize(expression)
    state = tuple(tokens)

    print(f"\nState (tokens): {state}")

    # Create actions
    actions = create_actions_from_tokens(tokens)

    if not actions:
        print("No evaluate actions available (expression may have brackets)")
        return

    print(f"Available actions:")
    for a in actions:
        print(f"  - {a}")

    # Show precedence maps for reference
    print(f"\nPrecedence maps:")
    for name, pmap in PRECEDENCE_MAPS.items():
        print(f"  {name:20}: {pmap}")

    # Policy table with BODMAS
    print("\n" + "-" * 90)
    print("INDIVIDUAL POLICY RESULTS (with BODMAS precedence)")
    print("-" * 90)

    relevant_policies = [
        'highest_precedence_first',
        'leftmost_first',
        'rightmost_first',
        'left_to_right_strict',
    ]

    print_policy_table(state, actions, relevant_policies, 'bodmas')

    # Policy table with addition_first
    print("\n" + "-" * 90)
    print("INDIVIDUAL POLICY RESULTS (with ADDITION_FIRST precedence)")
    print("-" * 90)

    print_policy_table(state, actions, relevant_policies, 'addition_first')

    # Policy table with flat
    print("\n" + "-" * 90)
    print("INDIVIDUAL POLICY RESULTS (with FLAT precedence)")
    print("-" * 90)

    print_policy_table(state, actions, relevant_policies, 'flat')

    # Learner table
    relevant_learners = [
        'expert',
        'bodmas_correct',
        'addition_first',
        'left_to_right_only',
        'right_to_left',
        'novice',
    ]

    print_learner_table(state, actions, relevant_learners)

    # Show detailed breakdown for one learner
    print("\n" + "-" * 90)
    print("DETAILED: 'addition_first' learner policy evaluation")
    print("-" * 90)

    learner = create_learner('addition_first')
    print(f"Learner: {learner}")
    print(f"Precedence map: {learner.precedence_map}")

    for action in actions:
        results = learner.evaluate_all(state, action, actions)
        is_valid = learner.is_valid(state, action, actions)

        print(f"\n{action}:")
        for policy_name, result in results.items():
            print(f"  {policy_name}: {'Y' if result else 'N'}")
        print(f"  -> VALID: {'Y' if is_valid else 'N'}")


def test_custom_learner():
    """Demonstrate creating a custom learner."""
    print("\n" + "=" * 90)
    print("CUSTOM LEARNER EXAMPLE")
    print("=" * 90)

    # Create a custom learner who:
    # - Believes addition comes first (wrong precedence)
    # - Goes right-to-left (wrong direction)
    custom = create_custom_learner(
        name="confused_student",
        policy_names=["highest_precedence_first", "rightmost_first", "brackets_optional"],
        precedence_name="addition_first",
        description="Believes addition first AND goes right-to-left"
    )

    print(f"\nCreated: {custom}")
    print(f"Precedence: {custom.precedence_name} = {custom.precedence_map}")
    print(f"Policies: {custom.policy_names}")
    print(f"Description: {custom.description}")

    # Test on expression
    expression = "4-5*2+3"
    tokens = tokenize(expression)
    state = tuple(tokens)
    actions = create_actions_from_tokens(tokens)

    print(f"\nTesting on: {expression}")
    print(f"Actions: {actions}")

    valid = custom.valid_actions(state, actions)
    print(f"Valid actions: {valid}")

    # Compare with expert
    expert = create_learner('expert')
    expert_valid = expert.valid_actions(state, actions)
    print(f"\nExpert would choose: {expert_valid}")


def show_builder_options():
    """Show all available options for building learners."""
    print("\n" + "=" * 90)
    print("LEARNER BUILDER OPTIONS")
    print("=" * 90)

    options = get_learner_builder_options()

    print("\n1. PRECEDENCE MAPS (pick one):")
    for name, info in options['precedence_maps'].items():
        print(f"   - {name}: {info['description']}")
        print(f"     Operators: {info['operators']}")

    print("\n2. POLICY CATEGORIES:")
    for cat_name, cat_info in options['policy_categories'].items():
        exclusive = "pick ONE" if cat_info['exclusive'] else "can combine"
        print(f"\n   {cat_info['name']} ({exclusive}):")
        print(f"   {cat_info['description']}")
        for policy in cat_info['policies']:
            p = get_policy(policy)
            print(f"     - {policy}: {p.description}")

    print("\n3. PRESET PROFILES:")
    for name, profile in options['preset_profiles'].items():
        print(f"   - {name}:")
        print(f"     Precedence: {profile['precedence']}")
        print(f"     Policies: {profile['policies']}")
        print(f"     Description: {profile['description']}")


def main():
    """Run all tests."""
    print("=" * 90)
    print("POLICY & LEARNER SYSTEM TEST (v2 with Precedence Maps)")
    print("=" * 90)

    # Show builder options
    show_builder_options()

    # Test expressions
    test_expressions = [
        "4-5*2+3",      # Your example from the whiteboard
        "2+3*4",        # Simple precedence test
        "8-4+2",        # Same precedence test (should go left-to-right)
        "2*3+4*5",      # Multiple multiplications
    ]

    for expr in test_expressions:
        test_expression(expr)

    # Custom learner demo
    test_custom_learner()

    print("\n" + "=" * 90)
    print("TESTS COMPLETE")
    print("=" * 90)


if __name__ == "__main__":
    main()
