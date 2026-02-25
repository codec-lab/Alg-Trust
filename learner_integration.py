"""
Integration module connecting Learner/Policy system with ExpressionGraph2

This module provides:
1. Converting graph_builder2 actions to Policy Action objects
2. Filtering graph actions based on learner policies
3. Walking the graph with learner constraints
"""

from typing import List, Dict, Tuple, Optional, Set
from dataclasses import dataclass

from graph_builder2 import (
    ExpressionGraph2, Node, Edge,
    find_evaluatable_operations, find_distributable_brackets,
    find_bracket_groups, get_bracket_content
)
from policies import (
    Action, Policy, get_policy, PRECEDENCE_MAPS,
    get_evaluate_actions, POLICY_CATEGORIES
)
from learner import (
    Learner, create_learner, create_custom_learner,
    LEARNER_PROFILES, list_learner_profiles
)
from tokenizer import tokenize, OPEN_BRACKETS, CLOSE_BRACKETS


def extract_actions_from_tokens(tokens: List[str]) -> List[Action]:
    """
    Extract all possible Action objects from a token list.
    This creates Action objects for ALL possible actions (evaluate, distribute, drop_brackets).

    Returns:
        List of Action objects with proper indices and descriptions
    """
    actions = []

    # 1. EVALUATE actions - find all num op num patterns
    operations = find_evaluatable_operations(tokens)
    for op_index, operator in operations:
        left = tokens[op_index - 1]
        right = tokens[op_index + 1]
        actions.append(Action(
            action_type='evaluate',
            operator=operator,
            operator_index=op_index,
            description=f"Compute {left} {operator} {right}"
        ))

    # 2. DISTRIBUTE actions - find distributable brackets
    distributable = find_distributable_brackets(tokens, include_nested=True)
    for dist in distributable:
        inner = ''.join(get_bracket_content(tokens, dist['bracket_start'], dist['bracket_end']))
        operand_str = ''.join(dist['operand'])

        # Only add if distribution is actually possible (2+ terms inside)
        inner_tokens = get_bracket_content(tokens, dist['bracket_start'], dist['bracket_end'])
        has_additive_ops = any(t in ['+', '-'] for t in inner_tokens)

        if has_additive_ops:
            actions.append(Action(
                action_type='distribute',
                operator=dist['operator'],
                operator_index=dist['op_index'],
                description=f"Distribute ({inner}) {dist['operator']} {operand_str}"
            ))

    # 3. DROP_BRACKETS actions - find all bracket groups
    bracket_groups = find_bracket_groups(tokens, outermost_only=False)
    for start, end in bracket_groups:
        inner = ''.join(get_bracket_content(tokens, start, end))
        actions.append(Action(
            action_type='drop_brackets',
            operator=None,
            operator_index=start,  # Use bracket start as index
            description=f"Drop brackets: ({inner})"
        ))

    return actions


def graph_action_to_policy_action(graph_action: Dict, tokens: List[str]) -> Optional[Action]:
    """
    Convert a graph_builder2 action dict to a Policy Action object.

    Args:
        graph_action: Dict with 'type', 'description', 'result_tokens'
        tokens: Current state tokens

    Returns:
        Action object or None if conversion fails
    """
    action_type = graph_action['type']
    description = graph_action['description']

    if action_type == 'evaluate':
        # Parse "Compute X op Y" to get operator and find index
        parts = description.replace("Compute ", "").split()
        if len(parts) >= 3:
            left_operand = parts[0]
            operator = parts[1]
            right_operand = parts[2]

            # Find the operator index in tokens
            for i, tok in enumerate(tokens):
                if tok == operator and i > 0 and i < len(tokens) - 1:
                    if tokens[i-1] == left_operand and tokens[i+1] == right_operand:
                        return Action(
                            action_type='evaluate',
                            operator=operator,
                            operator_index=i,
                            description=description
                        )
        return None

    elif action_type == 'distribute':
        # Parse "Distribute (inner) op operand"
        for op in ['*', '/', '+', '-', '^']:
            if f") {op} " in description:
                # Find the operator in tokens after a closing bracket
                for i, tok in enumerate(tokens):
                    if tok == op and i > 0 and tokens[i-1] == ')':
                        return Action(
                            action_type='distribute',
                            operator=op,
                            operator_index=i,
                            description=description
                        )
                    elif tok == op and i < len(tokens) - 1 and tokens[i+1] == '(':
                        return Action(
                            action_type='distribute',
                            operator=op,
                            operator_index=i,
                            description=description
                        )
        return None

    elif action_type == 'drop_brackets':
        # Find the bracket being dropped
        # Parse "Drop brackets: (inner)"
        bracket_groups = find_bracket_groups(tokens, outermost_only=False)
        for start, end in bracket_groups:
            inner = ''.join(get_bracket_content(tokens, start, end))
            if f"({inner})" in description:
                return Action(
                    action_type='drop_brackets',
                    operator=None,
                    operator_index=start,
                    description=description
                )
        return None

    return None


class LearnerGraphWalker:
    """
    Walks an ExpressionGraph2 while filtering actions based on learner policies.

    This allows you to see which paths a specific learner would take through
    the expression evaluation graph.
    """

    def __init__(self, expression: str, learner: Learner):
        """
        Initialize the walker with an expression and learner.

        Args:
            expression: Mathematical expression string
            learner: Learner instance with policies and precedence
        """
        self.expression = expression
        self.learner = learner
        self.graph = ExpressionGraph2(expression)

    def get_valid_actions_for_state(self, tokens: List[str]) -> Tuple[List[Action], List[Action]]:
        """
        Get valid and invalid actions for a state according to the learner.

        Args:
            tokens: Current state as list of tokens

        Returns:
            Tuple of (valid_actions, invalid_actions)
        """
        state = tuple(tokens)
        all_actions = extract_actions_from_tokens(tokens)

        valid = self.learner.valid_actions(state, all_actions)
        invalid = [a for a in all_actions if a not in valid]

        return valid, invalid

    def get_valid_actions_for_node(self, node_id: str) -> Tuple[List[Action], List[Action]]:
        """
        Get valid and invalid actions for a specific node in the graph.

        Args:
            node_id: ID of the node in the graph

        Returns:
            Tuple of (valid_actions, invalid_actions)
        """
        node = self.graph.nodes.get(node_id)
        if not node:
            return [], []

        return self.get_valid_actions_for_state(node.tokens)

    def walk_deterministic(self) -> List[Dict]:
        """
        Walk the graph deterministically, always choosing the first valid action.

        Returns:
            List of steps, each containing:
            - state: current expression
            - tokens: token list
            - valid_actions: actions the learner considers valid
            - chosen_action: the action taken (first valid)
            - all_actions: all possible actions
        """
        tokens = tokenize(self.expression)
        steps = []

        while len(tokens) > 1:  # Until we reach a single value
            state = tuple(tokens)
            all_actions = extract_actions_from_tokens(tokens)

            if not all_actions:
                break  # No more actions possible

            valid_actions = self.learner.valid_actions(state, all_actions)

            step = {
                'state': ''.join(tokens),
                'tokens': list(tokens),
                'all_actions': all_actions,
                'valid_actions': valid_actions,
                'chosen_action': valid_actions[0] if valid_actions else None,
            }
            steps.append(step)

            if not valid_actions:
                break  # Learner is stuck (no valid actions)

            # Execute the chosen action to get next state
            chosen = valid_actions[0]
            tokens = self._execute_action(tokens, chosen)

            if tokens is None:
                break

        # Add final state
        if len(tokens) == 1:
            steps.append({
                'state': ''.join(tokens),
                'tokens': list(tokens),
                'all_actions': [],
                'valid_actions': [],
                'chosen_action': None,
                'is_final': True,
                'result': float(tokens[0])
            })

        return steps

    def _execute_action(self, tokens: List[str], action: Action) -> Optional[List[str]]:
        """
        Execute an action and return the resulting tokens.

        This uses graph_builder2's functions to perform the actual computation.
        """
        from graph_builder2 import (
            perform_operation, distribute_bracket, drop_brackets,
            simplify_brackets, find_distributable_brackets
        )

        try:
            if action.action_type == 'evaluate':
                return perform_operation(tokens, action.operator_index, action.operator)

            elif action.action_type == 'distribute':
                # Find the matching distributable bracket
                distributable = find_distributable_brackets(tokens, include_nested=True)
                for dist in distributable:
                    if dist['op_index'] == action.operator_index:
                        result = distribute_bracket(
                            tokens,
                            dist['bracket_start'],
                            dist['bracket_end'],
                            dist['op_side'],
                            dist['op_index'],
                            dist['operand']
                        )
                        if result:
                            return simplify_brackets(result)
                return None

            elif action.action_type == 'drop_brackets':
                # Find the bracket at the given index
                bracket_groups = find_bracket_groups(tokens, outermost_only=False)
                for start, end in bracket_groups:
                    if start == action.operator_index:
                        result = drop_brackets(tokens, start, end)
                        return simplify_brackets(result)
                return None

        except Exception as e:
            return None

        return None

    def get_all_learner_paths(self, max_depth: int = 20) -> List[List[Dict]]:
        """
        Get all possible paths the learner could take (when multiple valid actions exist).

        This is useful for understanding the learner's decision space.

        Args:
            max_depth: Maximum number of steps to explore

        Returns:
            List of paths, where each path is a list of steps
        """
        paths = []

        def explore(tokens: List[str], current_path: List[Dict], depth: int):
            if depth > max_depth:
                paths.append(current_path)
                return

            if len(tokens) == 1:
                # Final state
                final_step = {
                    'state': ''.join(tokens),
                    'tokens': list(tokens),
                    'is_final': True,
                    'result': float(tokens[0])
                }
                paths.append(current_path + [final_step])
                return

            state = tuple(tokens)
            all_actions = extract_actions_from_tokens(tokens)

            if not all_actions:
                paths.append(current_path)
                return

            valid_actions = self.learner.valid_actions(state, all_actions)

            if not valid_actions:
                # Learner is stuck
                stuck_step = {
                    'state': ''.join(tokens),
                    'tokens': list(tokens),
                    'all_actions': all_actions,
                    'valid_actions': [],
                    'stuck': True
                }
                paths.append(current_path + [stuck_step])
                return

            # Explore each valid action
            for action in valid_actions:
                step = {
                    'state': ''.join(tokens),
                    'tokens': list(tokens),
                    'all_actions': all_actions,
                    'valid_actions': valid_actions,
                    'chosen_action': action,
                }

                new_tokens = self._execute_action(list(tokens), action)
                if new_tokens:
                    explore(new_tokens, current_path + [step], depth + 1)
                else:
                    paths.append(current_path + [step])

        tokens = tokenize(self.expression)
        explore(tokens, [], 0)

        return paths


def compare_learners_on_expression(expression: str, learner_names: List[str] = None) -> Dict:
    """
    Compare how different learners would solve an expression.

    Args:
        expression: Mathematical expression
        learner_names: List of learner profile names (default: all)

    Returns:
        Dict with comparison results
    """
    if learner_names is None:
        learner_names = list_learner_profiles()

    results = {
        'expression': expression,
        'learners': {}
    }

    for name in learner_names:
        learner = create_learner(name)
        walker = LearnerGraphWalker(expression, learner)

        steps = walker.walk_deterministic()

        final_result = None
        if steps and 'result' in steps[-1]:
            final_result = steps[-1]['result']

        results['learners'][name] = {
            'precedence': learner.precedence_name,
            'policies': learner.policy_names,
            'steps': steps,
            'num_steps': len(steps),
            'final_result': final_result,
            'description': learner.description
        }

    return results


def print_learner_walkthrough(expression: str, learner_name: str):
    """
    Print a detailed walkthrough of how a learner solves an expression.
    """
    learner = create_learner(learner_name)
    walker = LearnerGraphWalker(expression, learner)

    print(f"\n{'='*70}")
    print(f"LEARNER WALKTHROUGH: {learner_name}")
    print(f"{'='*70}")
    print(f"Expression: {expression}")
    print(f"Precedence: {learner.precedence_name}")
    print(f"Policies: {learner.policy_names}")
    print(f"Description: {learner.description}")
    print(f"{'='*70}")

    steps = walker.walk_deterministic()

    for i, step in enumerate(steps):
        print(f"\nStep {i + 1}: {step['state']}")

        if step.get('is_final'):
            print(f"  FINAL RESULT: {step['result']}")
            continue

        print(f"  All actions: {len(step['all_actions'])}")
        for a in step['all_actions']:
            is_valid = a in step['valid_actions']
            marker = "[Y]" if is_valid else "[N]"
            print(f"    {marker} {a}")

        if step['chosen_action']:
            print(f"  CHOSEN: {step['chosen_action']}")
        elif not step['valid_actions']:
            print(f"  STUCK! No valid actions according to learner's policies.")


def get_state_analysis(expression: str, learner_name: str = None) -> Dict:
    """
    Get detailed analysis of the initial state for an expression.

    Useful for UI to show what each learner would do at the start.

    Args:
        expression: Mathematical expression
        learner_name: Optional learner to analyze (if None, analyzes all)

    Returns:
        Dict with state analysis
    """
    tokens = tokenize(expression)
    state = tuple(tokens)
    all_actions = extract_actions_from_tokens(tokens)

    result = {
        'expression': expression,
        'tokens': tokens,
        'all_actions': [
            {
                'type': a.action_type,
                'operator': a.operator,
                'operator_index': a.operator_index,
                'description': a.description
            }
            for a in all_actions
        ],
    }

    if learner_name:
        learner = create_learner(learner_name)
        valid = learner.valid_actions(state, all_actions)
        result['learner'] = {
            'name': learner_name,
            'precedence': learner.precedence_name,
            'policies': learner.policy_names,
            'valid_actions': [
                {
                    'type': a.action_type,
                    'operator': a.operator,
                    'operator_index': a.operator_index,
                    'description': a.description
                }
                for a in valid
            ]
        }
    else:
        # Analyze all learners
        result['learners'] = {}
        for name in list_learner_profiles():
            learner = create_learner(name)
            valid = learner.valid_actions(state, all_actions)
            result['learners'][name] = {
                'precedence': learner.precedence_name,
                'policies': learner.policy_names,
                'valid_action_indices': [
                    all_actions.index(a) for a in valid
                ]
            }

    return result


if __name__ == "__main__":
    # Test the integration
    print("="*70)
    print("LEARNER-GRAPH INTEGRATION TEST")
    print("="*70)

    # Test 1: Simple expression without brackets
    expr1 = "4-5*2+3"
    print(f"\n\nTest 1: {expr1}")
    print("-"*70)

    for learner_name in ['expert', 'addition_first', 'left_to_right_only']:
        print_learner_walkthrough(expr1, learner_name)

    # Test 2: Expression with brackets
    expr2 = "(2+3)*4"
    print(f"\n\nTest 2: {expr2}")
    print("-"*70)

    for learner_name in ['expert', 'addition_first', 'bracket_ignorer']:
        print_learner_walkthrough(expr2, learner_name)

    # Test 3: Compare all learners
    expr3 = "2+3*4"
    print(f"\n\n{'='*70}")
    print(f"COMPARISON: {expr3}")
    print("="*70)

    comparison = compare_learners_on_expression(expr3)
    for name, data in comparison['learners'].items():
        print(f"\n{name}:")
        print(f"  Precedence: {data['precedence']}")
        print(f"  Steps: {data['num_steps']}")
        print(f"  Result: {data['final_result']}")
