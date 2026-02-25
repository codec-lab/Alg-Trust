"""
Learner System for Expression Evaluation

A Learner is defined by:
1. A precedence_map - their belief about operator ordering
2. A set of policies - rules that filter valid actions

The conjunction of policies determines which actions the learner considers valid:
valid_action = φ₁(s,a,A,P) ∧ φ₂(s,a,A,P) ∧ ... ∧ φₙ(s,a,A,P)

Where P is the learner's precedence_map passed to each policy.
"""

from typing import List, Tuple, Set, Dict, Optional
from policies import (
    Policy, Action, POLICY_REGISTRY, get_policy, list_policies,
    get_evaluate_actions, PRECEDENCE_MAPS, PRECEDENCE_BODMAS,
    POLICY_CATEGORIES, list_precedence_maps
)


class Learner:
    """
    A learner with a precedence belief and a set of policies.

    The learner's valid actions are determined by:
    1. Their precedence_map (belief about operator ordering)
    2. The conjunction of their policies (all must return True)
    """

    def __init__(self, name: str, policy_names: List[str],
                 precedence_map: Dict[str, int] = None,
                 precedence_name: str = None,
                 description: str = ""):
        """
        Create a learner with specified policies and precedence belief.

        Args:
            name: Unique identifier for this learner
            policy_names: List of policy names to use (from POLICY_REGISTRY)
            precedence_map: Custom operator precedence dict (optional)
            precedence_name: Name of a preset precedence map (e.g., 'bodmas', 'addition_first')
            description: Human-readable description of this learner
        """
        self.name = name
        self.policy_names = policy_names
        self.description = description
        self.policies: List[Policy] = [get_policy(pn) for pn in policy_names]

        # Set precedence map
        if precedence_map is not None:
            self.precedence_map = precedence_map
            self.precedence_name = "custom"
        elif precedence_name is not None:
            if precedence_name not in PRECEDENCE_MAPS:
                raise ValueError(f"Unknown precedence: {precedence_name}. "
                                 f"Available: {list(PRECEDENCE_MAPS.keys())}")
            self.precedence_map = PRECEDENCE_MAPS[precedence_name]
            self.precedence_name = precedence_name
        else:
            # Default to BODMAS
            self.precedence_map = PRECEDENCE_BODMAS
            self.precedence_name = "bodmas"

    def is_valid(self, state: Tuple[str, ...], action: Action,
                 available_actions: List[Action]) -> bool:
        """
        Check if an action is valid for this learner.

        Returns True only if ALL policies return True (conjunction).
        The learner's precedence_map is passed to each policy.
        """
        return all(
            policy.evaluate(state, action, available_actions, self.precedence_map)
            for policy in self.policies
        )

    def valid_actions(self, state: Tuple[str, ...],
                      available_actions: List[Action]) -> List[Action]:
        """
        Get all valid actions for this learner in the given state.

        Returns actions where the conjunction of all policies is True.
        """
        return [
            action for action in available_actions
            if self.is_valid(state, action, available_actions)
        ]

    def evaluate_all(self, state: Tuple[str, ...], action: Action,
                     available_actions: List[Action]) -> Dict[str, bool]:
        """
        Evaluate all policies for an action and return individual results.

        Useful for debugging/visualization to see which policies pass/fail.
        """
        return {
            policy.name: policy.evaluate(state, action, available_actions, self.precedence_map)
            for policy in self.policies
        }

    def get_config(self) -> Dict:
        """Get the learner's configuration as a dict (for serialization/UI)."""
        return {
            'name': self.name,
            'precedence': self.precedence_name,
            'policies': self.policy_names,
            'description': self.description,
        }

    def __repr__(self):
        return f"Learner({self.name}, prec={self.precedence_name}, policies={self.policy_names})"


# =============================================================================
# PRESET LEARNER PROFILES
# =============================================================================

LEARNER_PROFILES = {
    # Expert: Knows BODMAS perfectly
    "expert": {
        "precedence": "bodmas",
        "policies": [
            "highest_precedence_first",
            "leftmost_first",
            "brackets_first",
            "prefer_evaluate",
        ],
        "description": "Expert learner - follows BODMAS correctly with brackets"
    },

    # Knows precedence and direction (correct)
    "bodmas_correct": {
        "precedence": "bodmas",
        "policies": [
            "highest_precedence_first",
            "leftmost_first",
            "brackets_optional",
        ],
        "description": "Knows BODMAS precedence and left-to-right rule"
    },

    # Addition first (wrong precedence belief)
    "addition_first": {
        "precedence": "addition_first",
        "policies": [
            "highest_precedence_first",
            "leftmost_first",
            "brackets_first",
        ],
        "description": "Believes addition comes before multiplication (wrong!)"
    },

    # Multiplication only (partial knowledge)
    "multiplication_first": {
        "precedence": "multiplication_first",
        "policies": [
            "highest_precedence_first",
            "leftmost_first",
            "brackets_optional",
            "prefer_evaluate",
        ],
        "description": "Knows multiplication is special, but incomplete knowledge"
    },

    # Left-to-right only (ignores all precedence)
    "left_to_right_only": {
        "precedence": "flat",
        "policies": [
            "left_to_right_strict",
            "brackets_optional",
        ],
        "description": "Evaluates strictly left-to-right, ignoring precedence"
    },

    # Right-to-left (wrong direction)
    "right_to_left": {
        "precedence": "flat",
        "policies": [
            "right_to_left_strict",
            "brackets_optional",
        ],
        "description": "Evaluates right-to-left, ignoring precedence (wrong!)"
    },

    # Novice - no constraints at all
    "novice": {
        "precedence": "flat",
        "policies": [
            "allow_all",
        ],
        "description": "No knowledge - any action is considered valid"
    },

    # Bracket ignorer - might drop brackets
    "bracket_ignorer": {
        "precedence": "flat",
        "policies": [
            "left_to_right_strict",
            "brackets_ignored",
        ],
        "description": "Ignores brackets completely, may drop them incorrectly"
    },

    # Prefers distributing
    "distributor": {
        "precedence": "bodmas",
        "policies": [
            "highest_precedence_first",
            "leftmost_first",
            "brackets_optional",
            "prefer_distribute",
        ],
        "description": "Knows BODMAS but prefers to distribute brackets"
    },

    # Knows BODMAS precedence but wrong direction (right-to-left)
    "bodmas_wrong_direction": {
        "precedence": "bodmas",
        "policies": [
            "highest_precedence_first",
            "rightmost_first",
            "brackets_first",
        ],
        "description": "Knows BODMAS precedence but goes right-to-left (wrong!)"
    },
}


def create_learner(profile_name: str) -> Learner:
    """
    Create a learner from a preset profile.

    Args:
        profile_name: Name of profile from LEARNER_PROFILES

    Returns:
        Learner instance
    """
    if profile_name not in LEARNER_PROFILES:
        available = list(LEARNER_PROFILES.keys())
        raise ValueError(f"Unknown profile: {profile_name}. Available: {available}")

    profile = LEARNER_PROFILES[profile_name]
    return Learner(
        name=profile_name,
        policy_names=profile["policies"],
        precedence_name=profile["precedence"],
        description=profile["description"]
    )


def create_custom_learner(name: str, policy_names: List[str],
                           precedence_name: str = "bodmas",
                           description: str = "") -> Learner:
    """
    Create a custom learner with specific policies and precedence.

    Args:
        name: Unique name for the learner
        policy_names: List of policy names to use
        precedence_name: Name of precedence map to use
        description: Optional description

    Returns:
        Learner instance
    """
    return Learner(
        name=name,
        policy_names=policy_names,
        precedence_name=precedence_name,
        description=description
    )


def list_learner_profiles() -> List[str]:
    """List all available learner profile names."""
    return list(LEARNER_PROFILES.keys())


def describe_profile(profile_name: str) -> str:
    """Get description of a learner profile."""
    if profile_name not in LEARNER_PROFILES:
        raise ValueError(f"Unknown profile: {profile_name}")
    return LEARNER_PROFILES[profile_name]["description"]


def get_profile_config(profile_name: str) -> Dict:
    """Get full configuration of a learner profile."""
    if profile_name not in LEARNER_PROFILES:
        raise ValueError(f"Unknown profile: {profile_name}")
    return LEARNER_PROFILES[profile_name]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def compare_learners(state: Tuple[str, ...], available_actions: List[Action],
                     learner_names: List[str] = None) -> Dict[str, List[Action]]:
    """
    Compare what actions different learners would take.

    Args:
        state: Current expression state (tuple of tokens)
        available_actions: All available actions
        learner_names: List of learner profile names (default: all)

    Returns:
        Dict mapping learner name to their valid actions
    """
    if learner_names is None:
        learner_names = list_learner_profiles()

    results = {}
    for name in learner_names:
        learner = create_learner(name)
        results[name] = learner.valid_actions(state, available_actions)

    return results


def print_learner_comparison(state: Tuple[str, ...], available_actions: List[Action],
                              learner_names: List[str] = None):
    """
    Print a formatted comparison of learner behaviors.
    """
    comparison = compare_learners(state, available_actions, learner_names)

    print(f"\nState: {''.join(state)}")
    print(f"Available actions: {[str(a) for a in available_actions]}")
    print("\nLearner Valid Actions:")
    print("-" * 80)

    for name, valid in comparison.items():
        learner = create_learner(name)
        valid_str = [str(a) for a in valid]
        print(f"{name:25} | prec={learner.precedence_name:15} | {valid_str}")
        print(f"{'':25} | ({learner.description})")
        print("-" * 80)


def get_learner_builder_options() -> Dict:
    """
    Get all options for building a custom learner (for UI).

    Returns:
        Dict with precedence_maps and policy_categories
    """
    return {
        'precedence_maps': {
            name: {
                'operators': prec_map,
                'description': _get_precedence_description(name)
            }
            for name, prec_map in PRECEDENCE_MAPS.items()
        },
        'policy_categories': POLICY_CATEGORIES,
        'preset_profiles': {
            name: profile
            for name, profile in LEARNER_PROFILES.items()
        }
    }


def _get_precedence_description(name: str) -> str:
    """Get a human-readable description of a precedence map."""
    descriptions = {
        'bodmas': "Standard BODMAS: ^ > */ > +-",
        'addition_first': "Addition first (wrong): +- > ^ > */",
        'multiplication_first': "Only * is special: * > /^ > +-",
        'flat': "All operators equal (no precedence)",
    }
    return descriptions.get(name, "Custom precedence")
