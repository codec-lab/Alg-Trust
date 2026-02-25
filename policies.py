"""
Policy System for Expression Evaluation

A policy φ(state, action, available_actions, precedence_map) → bool determines whether
an action should be taken given the current state and all available actions.

The conjunction of multiple policies defines a learner's behavior:
valid_action = φ₁(s,a,A,P) ∧ φ₂(s,a,A,P) ∧ ... ∧ φₙ(s,a,A,P)

Policies are organized into CATEGORIES:
1. PRECEDENCE BELIEF - defines operator ordering (pick one, mutually exclusive)
2. DIRECTION - tiebreaker for same precedence (pick one)
3. BRACKET HANDLING - how to handle brackets (pick one)
4. ACTION PREFERENCE - evaluate vs distribute preference (optional)
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Set, Any, Optional
from dataclasses import dataclass
from tokenizer import OPEN_BRACKETS, CLOSE_BRACKETS


# =============================================================================
# PRECEDENCE MAPS - Different beliefs about operator ordering
# =============================================================================

PRECEDENCE_BODMAS = {
    '+': 1,
    '-': 1,
    '*': 2,
    '/': 2,
    '^': 3,
}

PRECEDENCE_ADDITION_FIRST = {
    # Addition/subtraction have HIGHEST precedence (wrong!)
    '+': 3,
    '-': 3,
    '*': 1,
    '/': 1,
    '^': 2,
}

PRECEDENCE_MULTIPLICATION_FIRST = {
    # Only multiplication is special
    '*': 3,
    '/': 2,
    '+': 1,
    '-': 1,
    '^': 2,
}

PRECEDENCE_FLAT = {
    # All operators have same precedence
    '+': 1,
    '-': 1,
    '*': 1,
    '/': 1,
    '^': 1,
}

# Registry of all precedence maps
PRECEDENCE_MAPS = {
    'bodmas': PRECEDENCE_BODMAS,
    'addition_first': PRECEDENCE_ADDITION_FIRST,
    'multiplication_first': PRECEDENCE_MULTIPLICATION_FIRST,
    'flat': PRECEDENCE_FLAT,
}

# Default precedence (for backward compatibility)
PRECEDENCE = PRECEDENCE_BODMAS


# Action types from graph_builder2
ACTION_TYPES = ['evaluate', 'distribute', 'drop_brackets']


@dataclass
class Action:
    """
    Represents an action that can be taken on an expression.

    Attributes:
        action_type: 'evaluate', 'distribute', or 'drop_brackets'
        operator: The operator involved ('+', '-', '*', '/', '^') or None
        operator_index: Index of the operator in the token list (for evaluate actions)
        description: Human-readable description of the action
    """
    action_type: str
    operator: str = None
    operator_index: int = None
    description: str = ""

    def __hash__(self):
        return hash((self.action_type, self.operator, self.operator_index))

    def __eq__(self, other):
        if not isinstance(other, Action):
            return False
        return (self.action_type == other.action_type and
                self.operator == other.operator and
                self.operator_index == other.operator_index)

    def __repr__(self):
        if self.operator_index is not None:
            return f"Action({self.action_type}, '{self.operator}', idx={self.operator_index})"
        return f"Action({self.action_type}, '{self.operator}')"


def extract_actions_from_graph_actions(graph_actions: List[Dict], tokens: List[str]) -> List[Action]:
    """
    Convert graph_builder2's action dicts to Action objects.

    Args:
        graph_actions: List of action dicts from graph_builder2._find_all_actions()
        tokens: Current state tokens

    Returns:
        List of Action objects
    """
    actions = []

    for ga in graph_actions:
        action_type = ga['type']
        description = ga['description']

        if action_type == 'evaluate':
            # Parse "Compute X op Y" to get operator
            # Description format: "Compute 4 * 5"
            parts = description.replace("Compute ", "").split()
            if len(parts) >= 3:
                operator = parts[1]
                left_operand = parts[0]
                # Find operator index in tokens
                for i, tok in enumerate(tokens):
                    if tok == operator and i > 0 and i < len(tokens) - 1:
                        if tokens[i-1] == left_operand:
                            actions.append(Action(
                                action_type='evaluate',
                                operator=operator,
                                operator_index=i,
                                description=description
                            ))
                            break

        elif action_type == 'distribute':
            # Extract operator from description "Distribute (...) op X"
            # Find the operator between ) and the operand
            for op in ['*', '/', '+', '-', '^']:
                if f") {op} " in description or f") {op}" in description:
                    actions.append(Action(
                        action_type='distribute',
                        operator=op,
                        description=description
                    ))
                    break

        elif action_type == 'drop_brackets':
            actions.append(Action(
                action_type='drop_brackets',
                operator=None,
                description=description
            ))

    return actions


def get_available_operators(actions: List[Action]) -> Set[str]:
    """Get set of all operators available across actions."""
    return {a.operator for a in actions if a.operator is not None}


def get_actions_by_type(actions: List[Action], action_type: str) -> List[Action]:
    """Filter actions by type."""
    return [a for a in actions if a.action_type == action_type]


def get_evaluate_actions(actions: List[Action]) -> List[Action]:
    """Get only evaluate actions."""
    return get_actions_by_type(actions, 'evaluate')


# =============================================================================
# POLICY BASE CLASS
# =============================================================================

class Policy(ABC):
    """
    Abstract base class for evaluation policies.

    A policy takes (state, action, available_actions, precedence_map) and returns True/False
    indicating whether the action should be considered valid.
    """

    # Policy category - used for organization and mutual exclusion
    category: str = "general"

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        """
        Evaluate whether an action is valid under this policy.

        Args:
            state: Tuple of tokens representing current expression
            action: The action being considered
            available_actions: All actions available in this state
            precedence_map: Operator precedence mapping (learner's belief)

        Returns:
            True if action is valid under this policy, False otherwise
        """
        pass

    def __repr__(self):
        return f"Policy({self.name})"


# =============================================================================
# CATEGORY 1: PRECEDENCE BELIEF POLICIES (mutually exclusive)
# =============================================================================

class HighestPrecedenceFirst(Policy):
    """
    Only allow evaluation of highest-precedence operators among available evaluate actions.
    Uses the learner's precedence_map to determine precedence.
    """
    category = "precedence"

    def __init__(self):
        super().__init__(
            name="highest_precedence_first",
            description="Only evaluate operators with highest precedence among available"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        if action.action_type != 'evaluate':
            return True

        prec_map = precedence_map or PRECEDENCE_BODMAS

        eval_actions = get_evaluate_actions(available_actions)
        if not eval_actions:
            return True

        # Find highest precedence among available evaluate actions
        max_prec = max(prec_map.get(a.operator, 0) for a in eval_actions)

        # This action is valid if it has the highest precedence
        return prec_map.get(action.operator, 0) == max_prec


class NoHigherPrecedenceLeft(Policy):
    """
    No higher-precedence operator exists to the LEFT of this operator.
    Uses the learner's precedence_map.
    """
    category = "precedence"

    def __init__(self):
        super().__init__(
            name="no_higher_prec_left",
            description="No higher-precedence operator to the left"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        if action.action_type != 'evaluate':
            return True

        if action.operator_index is None:
            return True

        prec_map = precedence_map or PRECEDENCE_BODMAS
        my_prec = prec_map.get(action.operator, 0)

        # Check all tokens to the left for higher precedence operators
        depth = 0
        for i in range(action.operator_index - 1, -1, -1):
            tok = state[i]
            if tok in OPEN_BRACKETS:
                depth -= 1
            elif tok in CLOSE_BRACKETS:
                depth += 1
            elif depth == 0 and tok in prec_map:
                if prec_map[tok] > my_prec:
                    return False

        return True


class NoHigherPrecedenceRight(Policy):
    """
    No higher-precedence operator exists to the RIGHT of this operator.
    Uses the learner's precedence_map.
    """
    category = "precedence"

    def __init__(self):
        super().__init__(
            name="no_higher_prec_right",
            description="No higher-precedence operator to the right"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        if action.action_type != 'evaluate':
            return True

        if action.operator_index is None:
            return True

        prec_map = precedence_map or PRECEDENCE_BODMAS
        my_prec = prec_map.get(action.operator, 0)

        # Check all tokens to the right for higher precedence operators
        depth = 0
        for i in range(action.operator_index + 1, len(state)):
            tok = state[i]
            if tok in OPEN_BRACKETS:
                depth += 1
            elif tok in CLOSE_BRACKETS:
                depth -= 1
            elif depth == 0 and tok in prec_map:
                if prec_map[tok] > my_prec:
                    return False

        return True


# =============================================================================
# CATEGORY 2: DIRECTION POLICIES (mutually exclusive)
# =============================================================================

class LeftmostFirst(Policy):
    """
    Among same-precedence operators, only allow the leftmost one.
    Uses the learner's precedence_map to determine "same precedence".
    """
    category = "direction"

    def __init__(self):
        super().__init__(
            name="leftmost_first",
            description="Among same-precedence operators, pick leftmost"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        if action.action_type != 'evaluate':
            return True

        if action.operator_index is None:
            return True

        prec_map = precedence_map or PRECEDENCE_BODMAS
        my_prec = prec_map.get(action.operator, 0)

        # Get all evaluate actions with same precedence
        same_prec_actions = [
            a for a in get_evaluate_actions(available_actions)
            if prec_map.get(a.operator, 0) == my_prec and a.operator_index is not None
        ]

        if not same_prec_actions:
            return True

        # Find leftmost (minimum index)
        leftmost_idx = min(a.operator_index for a in same_prec_actions)

        return action.operator_index == leftmost_idx


class RightmostFirst(Policy):
    """
    Among same-precedence operators, only allow the rightmost one.
    Uses the learner's precedence_map to determine "same precedence".
    """
    category = "direction"

    def __init__(self):
        super().__init__(
            name="rightmost_first",
            description="Among same-precedence operators, pick rightmost"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        if action.action_type != 'evaluate':
            return True

        if action.operator_index is None:
            return True

        prec_map = precedence_map or PRECEDENCE_BODMAS
        my_prec = prec_map.get(action.operator, 0)

        same_prec_actions = [
            a for a in get_evaluate_actions(available_actions)
            if prec_map.get(a.operator, 0) == my_prec and a.operator_index is not None
        ]

        if not same_prec_actions:
            return True

        rightmost_idx = max(a.operator_index for a in same_prec_actions)

        return action.operator_index == rightmost_idx


class LeftToRightStrict(Policy):
    """
    Strict left-to-right: only allow the leftmost action OVERALL.
    Ignores precedence completely - just picks leftmost.
    """
    category = "direction"

    def __init__(self):
        super().__init__(
            name="left_to_right_strict",
            description="Always pick leftmost operator (ignores precedence)"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        if action.action_type != 'evaluate':
            return True

        if action.operator_index is None:
            return True

        eval_actions = get_evaluate_actions(available_actions)
        eval_actions = [a for a in eval_actions if a.operator_index is not None]

        if not eval_actions:
            return True

        leftmost_idx = min(a.operator_index for a in eval_actions)

        return action.operator_index == leftmost_idx


class RightToLeftStrict(Policy):
    """
    Strict right-to-left: only allow the rightmost action OVERALL.
    Ignores precedence completely.
    """
    category = "direction"

    def __init__(self):
        super().__init__(
            name="right_to_left_strict",
            description="Always pick rightmost operator (ignores precedence)"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        if action.action_type != 'evaluate':
            return True

        if action.operator_index is None:
            return True

        eval_actions = get_evaluate_actions(available_actions)
        eval_actions = [a for a in eval_actions if a.operator_index is not None]

        if not eval_actions:
            return True

        rightmost_idx = max(a.operator_index for a in eval_actions)

        return action.operator_index == rightmost_idx


# =============================================================================
# CATEGORY 3: BRACKET POLICIES (mutually exclusive)
# =============================================================================

class BracketsFirst(Policy):
    """
    Must resolve content inside brackets before operating outside.
    If there are evaluate actions inside brackets, only those are valid.
    """
    category = "bracket"

    def __init__(self):
        super().__init__(
            name="brackets_first",
            description="Must evaluate inside brackets before outside operators"
        )

    def _is_inside_brackets(self, state: Tuple[str, ...], operator_index: int) -> bool:
        """Check if an operator at given index is inside brackets."""
        depth = 0
        for i in range(operator_index):
            if state[i] in OPEN_BRACKETS:
                depth += 1
            elif state[i] in CLOSE_BRACKETS:
                depth -= 1
        return depth > 0

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        if action.action_type == 'drop_brackets':
            return False  # Never allow dropping brackets

        if action.action_type == 'distribute':
            # Distribution is okay if no evaluate inside brackets
            eval_actions = get_evaluate_actions(available_actions)
            has_inside = any(
                a.operator_index is not None and self._is_inside_brackets(state, a.operator_index)
                for a in eval_actions
            )
            return not has_inside

        if action.action_type == 'evaluate':
            if action.operator_index is None:
                return True

            # Check if there are any evaluate actions inside brackets
            eval_actions = get_evaluate_actions(available_actions)
            inside_bracket_actions = [
                a for a in eval_actions
                if a.operator_index is not None and self._is_inside_brackets(state, a.operator_index)
            ]

            if inside_bracket_actions:
                # Only allow if this action is inside brackets
                return self._is_inside_brackets(state, action.operator_index)

            # No bracket content to evaluate, allow this action
            return True

        return True


class BracketsOptional(Policy):
    """
    Brackets don't need to be resolved first - can evaluate or distribute freely.
    Still doesn't allow dropping brackets incorrectly.
    """
    category = "bracket"

    def __init__(self):
        super().__init__(
            name="brackets_optional",
            description="Can evaluate inside or outside brackets, but no dropping"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        # Only restriction: no dropping brackets
        return action.action_type != 'drop_brackets'


class BracketsIgnored(Policy):
    """
    Completely ignores brackets - must drop them before evaluating inside.
    This models a student who doesn't understand brackets at all.
    
    Behavior:
    - Does NOT allow distribute (requires understanding brackets)
    - Does NOT allow evaluate inside brackets (must drop brackets first)
    - DOES allow drop_brackets (the mistake this learner makes)
    - DOES allow evaluate outside brackets
    """
    category = "bracket"

    def __init__(self):
        super().__init__(
            name="brackets_ignored",
            description="Must drop brackets first, cannot evaluate inside them"
        )

    def _is_inside_brackets(self, state: Tuple[str, ...], operator_index: int) -> bool:
        """Check if an operator at given index is inside brackets."""
        depth = 0
        for i in range(operator_index):
            if state[i] in OPEN_BRACKETS:
                depth += 1
            elif state[i] in CLOSE_BRACKETS:
                depth -= 1
        return depth > 0

    def _has_brackets(self, state: Tuple[str, ...]) -> bool:
        """Check if there are any brackets in the state."""
        return any(tok in OPEN_BRACKETS or tok in CLOSE_BRACKETS for tok in state)

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        # Never allow distribute - requires understanding brackets
        if action.action_type == 'distribute':
            return False
        
        # Always allow drop_brackets - this is what a bracket ignorer does
        if action.action_type == 'drop_brackets':
            return True
        
        # For evaluate actions: don't allow if inside brackets
        if action.action_type == 'evaluate':
            if action.operator_index is None:
                return True
            # Block evaluate actions inside brackets - must drop brackets first
            if self._is_inside_brackets(state, action.operator_index):
                return False
            return True
        
        return True


# =============================================================================
# CATEGORY 4: ACTION PREFERENCE POLICIES (optional, can combine)
# =============================================================================

class PreferEvaluate(Policy):
    """
    When both distribute and evaluate inside brackets are available, prefer evaluate.
    """
    category = "action_preference"

    def __init__(self):
        super().__init__(
            name="prefer_evaluate",
            description="Prefer evaluating inside brackets over distributing"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        # If there are evaluate actions available, don't allow distribute
        has_evaluate = any(a.action_type == 'evaluate' for a in available_actions)

        if has_evaluate and action.action_type == 'distribute':
            return False

        return True


class PreferDistribute(Policy):
    """
    When both distribute and evaluate are available, prefer distribute.
    """
    category = "action_preference"

    def __init__(self):
        super().__init__(
            name="prefer_distribute",
            description="Prefer distributing brackets over evaluating inside"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        has_distribute = any(a.action_type == 'distribute' for a in available_actions)

        if has_distribute and action.action_type == 'evaluate':
            return False

        return True


# =============================================================================
# UTILITY POLICIES
# =============================================================================

class AllowAll(Policy):
    """
    Allow all actions (no constraints). Useful as a base.
    """
    category = "utility"

    def __init__(self):
        super().__init__(
            name="allow_all",
            description="Allow all actions (no constraints)"
        )

    def evaluate(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action],
                 precedence_map: Dict[str, int] = None) -> bool:
        return True


# =============================================================================
# POLICY REGISTRY
# =============================================================================

POLICY_REGISTRY = {
    # Category 1: Precedence
    'highest_precedence_first': HighestPrecedenceFirst,
    'no_higher_prec_left': NoHigherPrecedenceLeft,
    'no_higher_prec_right': NoHigherPrecedenceRight,

    # Category 2: Direction
    'leftmost_first': LeftmostFirst,
    'rightmost_first': RightmostFirst,
    'left_to_right_strict': LeftToRightStrict,
    'right_to_left_strict': RightToLeftStrict,

    # Category 3: Bracket handling
    'brackets_first': BracketsFirst,
    'brackets_optional': BracketsOptional,
    'brackets_ignored': BracketsIgnored,

    # Category 4: Action preference
    'prefer_evaluate': PreferEvaluate,
    'prefer_distribute': PreferDistribute,

    # Utility
    'allow_all': AllowAll,
}

# Policy categories for UI organization
POLICY_CATEGORIES = {
    'precedence': {
        'name': 'Precedence Belief',
        'description': 'How operator precedence is determined',
        'policies': ['highest_precedence_first', 'no_higher_prec_left', 'no_higher_prec_right'],
        'exclusive': False,  # Can combine some
    },
    'direction': {
        'name': 'Direction',
        'description': 'Which direction to evaluate same-precedence operators',
        'policies': ['leftmost_first', 'rightmost_first', 'left_to_right_strict', 'right_to_left_strict'],
        'exclusive': True,
    },
    'bracket': {
        'name': 'Bracket Handling',
        'description': 'How to handle brackets',
        'policies': ['brackets_first', 'brackets_optional', 'brackets_ignored'],
        'exclusive': True,
    },
    'action_preference': {
        'name': 'Action Preference',
        'description': 'Preference between evaluate and distribute',
        'policies': ['prefer_evaluate', 'prefer_distribute'],
        'exclusive': True,
    },
}


def get_policy(name: str) -> Policy:
    """Get a policy instance by name."""
    if name not in POLICY_REGISTRY:
        raise ValueError(f"Unknown policy: {name}. Available: {list(POLICY_REGISTRY.keys())}")
    return POLICY_REGISTRY[name]()


def list_policies() -> List[str]:
    """List all available policy names."""
    return list(POLICY_REGISTRY.keys())


def list_policies_by_category() -> Dict[str, List[str]]:
    """List policies organized by category."""
    return {cat: info['policies'] for cat, info in POLICY_CATEGORIES.items()}


def get_precedence_map(name: str) -> Dict[str, int]:
    """Get a precedence map by name."""
    if name not in PRECEDENCE_MAPS:
        raise ValueError(f"Unknown precedence map: {name}. Available: {list(PRECEDENCE_MAPS.keys())}")
    return PRECEDENCE_MAPS[name]


def list_precedence_maps() -> List[str]:
    """List all available precedence map names."""
    return list(PRECEDENCE_MAPS.keys())
