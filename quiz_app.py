"""
Learner Diagnosis Quiz - Streamlit App

Tab 1 – Quiz: hardcoded questions, identify learner from trace/answer.
Tab 2 – Diagnose Any Equation: enter any expression, see mystery learner trace,
         pick which of two described learners produced it.
"""

import streamlit as st
from learner_integration import LearnerGraphWalker
from learner import create_learner, LEARNER_PROFILES
import random


# =============================================================================
# QUIZ TAB — LEARNER LABELS
# =============================================================================

LEARNER_DESCRIPTIONS = {
    'expert': 'Expert - Follows BODMAS correctly (brackets, then */ before +-)',
    'addition_first': 'Addition First - Does +/- before */',
    'multiplication_first': 'Multiplication First - Prioritizes * above all, distributes eagerly',
    'bracket_ignorer': 'Bracket Ignorer - Drops brackets and ignores them',
    'left_to_right_only': 'Left to Right - Ignores precedence, evaluates left to right',
    'right_to_left': 'Right to Left - Ignores precedence, evaluates right to left',
}

LEARNER_SHORT_NAMES = {
    'expert': 'Expert (BODMAS)',
    'addition_first': 'Addition First',
    'multiplication_first': 'Multiplication First',
    'bracket_ignorer': 'Bracket Ignorer',
    'left_to_right_only': 'Left to Right',
    'right_to_left': 'Right to Left',
}


# =============================================================================
# DIAGNOSTIC TAB — PLAIN ENGLISH LABELS
# =============================================================================

# Never pick these as the mystery learner (they get BODMAS right)
DIAG_EXCLUDE = {'expert', 'bodmas_correct'}

# Shown as the binary choice options (what the person knows / gets wrong)
DIAG_LEARNER_DESCRIPTIONS = {
    'addition_first':
        "Does addition and subtraction before multiplication and division",
    'multiplication_first':
        "Treats multiplication as the highest-priority operation; expands brackets with ×",
    'left_to_right_only':
        "Ignores operator precedence — evaluates everything strictly left to right",
    'right_to_left':
        "Ignores operator precedence — evaluates everything strictly right to left",
    'novice':
        "Has no consistent rule — picks operations in no predictable order",
    'bracket_ignorer':
        "Drops brackets entirely, then evaluates left to right",
    'distributor':
        "Knows BODMAS but prefers to expand (distribute) brackets instead of evaluating inside them",
    'bodmas_wrong_direction':
        "Knows multiplication comes before addition, but applies operations right to left",
    'expert':
        "Correctly follows BODMAS: brackets first, then ×÷, then +−, left to right",
    'bodmas_correct':
        "Follows BODMAS (×÷ before +−), evaluates left to right",
}

# Short labels (shown in summary table)
DIAG_LEARNER_LABELS = {
    'addition_first':         'Addition Before ×',
    'multiplication_first':   '× Highest Priority',
    'left_to_right_only':     'Strictly Left→Right',
    'right_to_left':          'Strictly Right→Left',
    'novice':                 'No Consistent Strategy',
    'bracket_ignorer':        'Ignores Brackets',
    'distributor':            'Prefers Distributing',
    'bodmas_wrong_direction':  'BODMAS Right→Left',
    'expert':                 'Expert (BODMAS)',
    'bodmas_correct':         'BODMAS Correct',
}


# =============================================================================
# SHARED HELPERS
# =============================================================================

def display_expr(s: str) -> str:
    """Replace / with ÷ for display."""
    return s.replace('/', '÷')


def has_distributable_brackets(expression: str) -> bool:
    """
    Return True if the expression has a bracket group that contains +/- inside
    AND is adjacent to an operator — i.e. distribution is actually meaningful.
    Mirrors the check in extract_actions_from_tokens.
    """
    from tokenizer import tokenize
    from graph_builder2 import find_distributable_brackets, get_bracket_content
    try:
        tokens = tokenize(expression)
        for dist in find_distributable_brackets(tokens):
            inner = get_bracket_content(tokens, dist['bracket_start'], dist['bracket_end'])
            if any(t in ['+', '-'] for t in inner):
                return True
        return False
    except Exception:
        return False


def generate_random_equation():
    """
    Generate a random arithmetic expression that is guaranteed to:
    - Have at least one * and one +/- (so a precedence conflict exists)
    - Parse cleanly (no division, so no messy decimals)
    - Produce a different trace for at least one non-expert learner
    About half the time the expression will include a bracketed sub-expression.
    Returns the expression string, or a safe fallback.
    """
    from tokenizer import tokenize

    for _ in range(60):
        n    = random.randint(3, 5)
        nums = [str(random.randint(1, 9)) for _ in range(n)]
        ops  = [random.choice(['+', '-', '*']) for _ in range(n - 1)]
        if '*' not in ops:
            ops[random.randrange(len(ops))] = '*'
        if not any(o in ('+', '-') for o in ops):
            ops[random.randrange(len(ops))] = random.choice(['+', '-'])

        # ~50% chance of wrapping a sub-expression in brackets
        use_brackets = (n >= 3) and (random.random() < 0.5)

        if use_brackets:
            # Pick how many numbers go inside brackets (2 or 3)
            blen   = random.randint(2, min(3, n - 1))
            bstart = random.randint(0, n - blen)
            bend   = bstart + blen  # exclusive — nums[bstart:bend] are bracketed

            # Ensure the bracket interior contains at least one +/-
            # (makes it interesting for bracket_ignorer and distributor)
            inner_ops = ops[bstart:bend - 1]
            if not any(o in ('+', '-') for o in inner_ops) and inner_ops:
                ops[bstart + random.randrange(len(inner_ops))] = random.choice(['+', '-'])

            # Ensure there's a * adjacent to the bracket so the bracket placement
            # creates a real precedence conflict with the outside
            adj_has_mult = (
                (bstart > 0 and ops[bstart - 1] == '*') or
                (bend < n   and ops[bend - 1]   == '*')
            )
            if not adj_has_mult:
                if bstart > 0:
                    ops[bstart - 1] = '*'
                else:
                    ops[bend - 1] = '*'

            # Build token string with brackets
            parts = []
            for i in range(n):
                if i == bstart:
                    parts.append('(')
                parts.append(nums[i])
                if i == bend - 1:
                    parts.append(')')
                if i < len(ops):
                    parts.append(ops[i])
            expr = ''.join(parts)
        else:
            parts = []
            for i, num in enumerate(nums):
                parts.append(num)
                if i < len(ops):
                    parts.append(ops[i])
            expr = ''.join(parts)

        # Validate tokenisation
        try:
            tokenize(expr)
        except Exception:
            continue

        # Require at least one learner to differ from expert
        try:
            expert_states = [s['state'] for s in get_learner_trace(expr, 'expert')]
            check_learners = ['addition_first', 'left_to_right_only', 'right_to_left']
            if any(c in expr for c in '([{'):
                check_learners.append('bracket_ignorer')
            for name in check_learners:
                try:
                    if [s['state'] for s in get_learner_trace(expr, name)] != expert_states:
                        return expr
                except Exception:
                    continue
        except Exception:
            continue

    return '2+3*4'  # safe fallback


def validate_equation(equation: str) -> str | None:
    """
    Try to tokenise the equation. Returns None if valid, or an error message.
    """
    from tokenizer import tokenize
    try:
        tokens = tokenize(equation.strip())
        if not tokens:
            return "Expression is empty."
        return None
    except Exception as e:
        return f"Invalid expression: {e}"


def get_learner_trace(expression: str, learner_name: str):
    """Get the full trace for a learner solving an expression."""
    learner = create_learner(learner_name)
    walker = LearnerGraphWalker(expression, learner)
    return walker.walk_deterministic()


def walk_with_arithmetic_errors(expression: str, learner_name: str, error_prob: float = 0.25):
    """
    Walk a learner's trace, but with a probability of swapping the operator
    at each evaluate step (e.g. computing a+b instead of a*b).

    The error propagates: a wrong intermediate result becomes the input
    for all subsequent steps, just like a real student's arithmetic slip.

    Returns the same step format as walk_deterministic(), with an extra
    'arithmetic_error' key on steps where a swap occurred.
    """
    from graph_builder2 import perform_operation
    from tokenizer import tokenize
    from learner_integration import extract_actions_from_tokens

    OTHER_OPS = {'+': ['-', '*'], '-': ['+', '*'], '*': ['+', '-'], '/': ['+', '-']}

    learner = create_learner(learner_name)
    walker  = LearnerGraphWalker(expression, learner)
    tokens  = tokenize(expression)
    steps   = []

    while len(tokens) > 1:
        state       = tuple(tokens)
        all_actions = extract_actions_from_tokens(tokens)
        if not all_actions:
            break

        valid_actions = learner.valid_actions(state, all_actions)
        chosen = valid_actions[0] if valid_actions else None

        step = {
            'state':        ''.join(tokens),
            'tokens':       list(tokens),
            'all_actions':  all_actions,
            'valid_actions': valid_actions,
            'chosen_action': chosen,
            'arithmetic_error': False,
        }
        steps.append(step)

        if not chosen:
            break

        # Possibly swap the operator for evaluate actions
        if chosen.action_type == 'evaluate' and random.random() < error_prob:
            swapped_op = random.choice(OTHER_OPS.get(chosen.operator, []))
            try:
                new_tokens = perform_operation(tokens, chosen.operator_index, swapped_op)
                if new_tokens is not None:
                    step['arithmetic_error'] = True
                    step['swapped_op'] = swapped_op  # for explanation display
                    tokens = new_tokens
                    continue
            except Exception:
                pass  # fall through to normal execution

        # Normal execution
        new_tokens = walker._execute_action(list(tokens), chosen)
        if new_tokens is None:
            break
        tokens = new_tokens

    # Final state
    if len(tokens) == 1:
        steps.append({
            'state':        ''.join(tokens),
            'tokens':       list(tokens),
            'all_actions':  [],
            'valid_actions': [],
            'chosen_action': None,
            'arithmetic_error': False,
            'is_final':     True,
            'result':       float(tokens[0]),
        })

    return steps


def format_trace(steps, show_all=True, show_first_n=None, show_last_n=None):
    """Format trace steps for display as a student would write their work."""
    if not steps:
        return "No steps available"

    total_steps = len(steps)

    if show_all:
        visible = list(range(total_steps))
        omit_middle = False
    elif show_first_n is not None:
        visible = list(range(min(show_first_n, total_steps)))
        omit_middle = len(visible) < total_steps
    elif show_last_n is not None:
        start = max(0, total_steps - show_last_n)
        visible = list(range(start, total_steps))
        omit_middle = start > 0
    else:
        visible = list(range(total_steps))
        omit_middle = False

    lines = []

    if show_last_n is not None and omit_middle:
        lines.append("  ...")

    for idx in visible:
        state = steps[idx].get('state', '')
        prefix = "  " if (idx == 0 and show_last_n is None) else "= "
        lines.append(f"{prefix}{state}")

    if show_first_n is not None and omit_middle:
        lines.append("  ...")

    return "\n".join(lines)


def get_final_answer(steps):
    """Get final answer from steps."""
    if steps and 'result' in steps[-1]:
        result = steps[-1]['result']
        if result == int(result):
            return str(int(result))
        else:
            return f"{result:.4f}".rstrip('0').rstrip('.')
    return "N/A"


# =============================================================================
# DIAGNOSTIC TAB HELPERS
# =============================================================================

def _bracket_depth_at(tokens, index):
    """Bracket nesting depth at the given token index."""
    depth = 0
    for i in range(min(index, len(tokens))):
        if tokens[i] in ('(', '[', '{'):
            depth += 1
        elif tokens[i] in (')', ']', '}'):
            depth -= 1
    return max(depth, 0)


def describe_trace_divergences(steps, expert_walker):
    """
    Compare each chosen action in `steps` against what the expert would do at
    that same state. Returns a plain-English string describing only the
    divergences that *actually occurred* in this trace — nothing generic.
    """
    BODMAS_PREC = {'+': 1, '-': 1, '*': 2, '/': 2, '^': 3}

    # ordered dict so first-seen example is kept; key = category
    found = {}

    def _short(action):
        """Strip 'Compute '/'Distribute ' prefix and replace / with ÷."""
        d = action.description.replace('/', '÷')
        for prefix in ('Compute ', 'Distribute ', 'Drop brackets: '):
            if d.startswith(prefix):
                d = d[len(prefix):]
        return d

    for step in steps[:-1]:
        tokens = step['tokens']
        l = step.get('chosen_action')
        if not l:
            continue

        try:
            valid, _ = expert_walker.get_valid_actions_for_state(list(tokens))
            if not valid:
                continue
            e = valid[0]
        except Exception:
            continue

        # No divergence at this step
        if l.action_type == e.action_type and l.operator_index == e.operator_index:
            continue

        l_str = _short(l)
        e_str = _short(e)
        l_idx = l.operator_index if l.operator_index is not None else 0
        e_idx = e.operator_index if e.operator_index is not None else 0
        l_depth = _bracket_depth_at(tokens, l_idx)
        e_depth = _bracket_depth_at(tokens, e_idx)

        if l.action_type == 'drop_brackets' and 'drop_brackets' not in found:
            found['drop_brackets'] = (
                f"dropped brackets instead of evaluating inside them "
                f"(dropped `{l_str}`)"
            )

        elif l.action_type == 'distribute' and e.action_type != 'distribute' \
                and 'distribute' not in found:
            found['distribute'] = (
                f"expanded brackets by distributing instead of evaluating inside "
                f"(distributed `{l_str}` instead of `{e_str}`)"
            )

        elif l_depth < e_depth and 'skip_brackets' not in found:
            found['skip_brackets'] = (
                f"skipped bracket contents and evaluated outside first "
                f"(chose `{l_str}` instead of `{e_str}`)"
            )

        elif l_depth == e_depth \
                and l.action_type == 'evaluate' and e.action_type == 'evaluate':
            l_prec = BODMAS_PREC.get(l.operator, 0)
            e_prec = BODMAS_PREC.get(e.operator, 0)

            if l_prec < e_prec:
                if l.operator in ('+', '-') and e.operator in ('*', '/') \
                        and 'add_before_mult' not in found:
                    found['add_before_mult'] = (
                        f"did addition/subtraction before multiplication/division "
                        f"(computed `{l_str}` before `{e_str}`)"
                    )
                elif 'wrong_prec' not in found:
                    found['wrong_prec'] = (
                        f"applied operators in the wrong priority order "
                        f"(chose `{l_str}` instead of `{e_str}`)"
                    )

            elif l_prec == e_prec and l_idx != e_idx:
                # If both chose the same associative operator (+/*), order doesn't
                # affect the result — skip flagging this as a divergence.
                if l.operator == e.operator and l.operator in ('+', '*'):
                    pass
                elif l_idx > e_idx and 'right_to_left' not in found:
                    found['right_to_left'] = (
                        f"evaluated right to left instead of left to right "
                        f"(computed `{l_str}` before `{e_str}`)"
                    )
                elif l_idx < e_idx and 'unexpected_order' not in found:
                    found['unexpected_order'] = (
                        f"chose an earlier operation unexpectedly "
                        f"(chose `{l_str}` instead of `{e_str}`)"
                    )

    if not found:
        return "follows the same steps as BODMAS on this expression"

    parts = list(found.values())
    sentence = parts[0].capitalize()
    for p in parts[1:]:
        sentence += f"; also {p}"
    return sentence


def _is_step_wrong(tokens, mystery_action, expert_walker) -> bool:
    """
    Returns True if mystery_action differs from what expert would choose
    at this token state (i.e. this step deviates from BODMAS).

    Exception: if both learner and expert evaluate the same associative operator
    (+ or *) at the same bracket depth, order doesn't affect the result — not wrong.
    """
    try:
        valid, _ = expert_walker.get_valid_actions_for_state(list(tokens))
        if not valid or not mystery_action:
            return True
        expert_action = valid[0]
        # Exact match — definitely not wrong
        if (mystery_action.action_type == expert_action.action_type
                and mystery_action.operator == expert_action.operator
                and mystery_action.operator_index == expert_action.operator_index):
            return False
        # Same associative operator at the same depth → order doesn't matter
        if (mystery_action.action_type == 'evaluate'
                and expert_action.action_type == 'evaluate'
                and mystery_action.operator == expert_action.operator
                and mystery_action.operator in ('+', '*')
                and _bracket_depth_at(tokens, mystery_action.operator_index)
                    == _bracket_depth_at(tokens, expert_action.operator_index)):
            return False
        return True
    except Exception:
        return True


def _build_trace_rows(mystery_steps, expert_walker):
    """
    Returns a list of tuples:
        (current_state: str, action_desc: str | None, next_state: str, is_wrong: bool)
    action_desc is None for wrong steps (should be blacked out).
    """
    rows = []
    for i, step in enumerate(mystery_steps[:-1]):
        tokens = step.get('tokens', [])
        chosen = step.get('chosen_action')
        current_state = step['state']
        next_state = mystery_steps[i + 1]['state']
        wrong = _is_step_wrong(tokens, chosen, expert_walker)
        action_desc = None if wrong else (chosen.description if chosen else None)
        rows.append((current_state, action_desc, next_state, wrong))
    return rows


# =============================================================================
# QUIZ TAB — QUESTIONS
# =============================================================================

FORMAT_FULL_TRACE    = "full_trace"
FORMAT_ANSWER_ONLY   = "answer_only"
FORMAT_PARTIAL_START = "partial_start"
FORMAT_PARTIAL_END   = "partial_end"


ALL_QUIZ_OPTIONS = [
    'expert', 'addition_first', 'multiplication_first',
    'bracket_ignorer', 'left_to_right_only', 'right_to_left',
]


def generate_questions():
    return [
        # Full trace (5)
        {'expression': '2+3*4',      'correct_learner': 'addition_first',     'format': FORMAT_FULL_TRACE},
        {'expression': '2*3+4*5',    'correct_learner': 'left_to_right_only', 'format': FORMAT_FULL_TRACE},
        {'expression': '10-2-3',     'correct_learner': 'right_to_left',      'format': FORMAT_FULL_TRACE},
        {'expression': '5+2*(3+1)',  'correct_learner': 'bracket_ignorer',    'format': FORMAT_FULL_TRACE},
        {'expression': '12/3+4*2',   'correct_learner': 'expert',             'format': FORMAT_FULL_TRACE},
        # Answer only (5)
        {'expression': '12-3+4',     'correct_learner': 'right_to_left',      'format': FORMAT_ANSWER_ONLY},
        {'expression': '20-4*3+2',   'correct_learner': 'addition_first',     'format': FORMAT_ANSWER_ONLY},
        {'expression': '8/4*2',      'correct_learner': 'multiplication_first','format': FORMAT_ANSWER_ONLY},
        {'expression': '4*(2+3)',     'correct_learner': 'bracket_ignorer',    'format': FORMAT_ANSWER_ONLY},
        {'expression': '15-3*2+4',   'correct_learner': 'left_to_right_only', 'format': FORMAT_ANSWER_ONLY},
        # Partial start (3)
        {'expression': '10+2*3-4',   'correct_learner': 'expert',             'format': FORMAT_PARTIAL_START},
        {'expression': '3+6/2*4',    'correct_learner': 'multiplication_first','format': FORMAT_PARTIAL_START},
        {'expression': '2*(3+4)-5',  'correct_learner': 'addition_first',     'format': FORMAT_PARTIAL_START},
        # Partial end (2)
        {'expression': '10/2/5',     'correct_learner': 'right_to_left',      'format': FORMAT_PARTIAL_END},
        {'expression': '20/4/2',     'correct_learner': 'right_to_left',      'format': FORMAT_PARTIAL_END},
    ]


def get_correct_learners(question):
    """
    Dynamically compute which learners in ALL_QUIZ_OPTIONS produce the same
    visible output as the shown trace — so multiple learners can be correct
    if they are indistinguishable given the information shown.
    """
    expr    = question['expression']
    source  = question['correct_learner']
    fmt     = question['format']

    ref_steps  = get_learner_trace(expr, source)
    ref_states = [s['state'] for s in ref_steps]
    ref_answer = get_final_answer(ref_steps)

    correct = []
    for name in ALL_QUIZ_OPTIONS:
        try:
            s      = get_learner_trace(expr, name)
            states = [x['state'] for x in s]
            answer = get_final_answer(s)
        except Exception:
            continue

        if fmt == FORMAT_FULL_TRACE:
            match = (states == ref_states)
        elif fmt == FORMAT_ANSWER_ONLY:
            match = (answer == ref_answer)
        elif fmt == FORMAT_PARTIAL_START:
            match = (states[:2] == ref_states[:2] and answer == ref_answer)
        elif fmt == FORMAT_PARTIAL_END:
            match = (states[-2:] == ref_states[-2:])
        else:
            match = False

        if match:
            correct.append(name)

    return correct


# =============================================================================
# QUIZ TAB RENDERER
# =============================================================================

def run_quiz_tab():
    st.markdown("**Goal:** Identify which type of learner solved the expression based on their work.")

    with st.expander("Click to see learner profiles", expanded=False):
        st.markdown("""
| Learner | Belief | Example: `2+3*4` |
|---------|--------|------------------|
| **Expert** | Correct BODMAS (×÷ before +−) | `2+12` → `14` |
| **Addition First** | Does +− before ×÷ | `5*4` → `20` |
| **Multiplication First** | × always first, even before ÷ | `8/4*2` → `8/8` → `1` |
| **Bracket Ignorer** | Drops brackets completely | `4*(2+3)` → `11` |
| **Left to Right** | No precedence, just L→R | `5*4` → `20` |
| **Right to Left** | No precedence, just R→L | `10-4+2` → `4` |
        """)

    st.markdown("---")

    if 'questions' not in st.session_state:
        questions = generate_questions()
        random.shuffle(questions)
        st.session_state.questions = questions
        st.session_state.current_q = 0
        st.session_state.revealed = False
        st.session_state.selected_answer = None
        st.session_state.score = 0
        st.session_state.answered = [False] * len(questions)

    questions = st.session_state.questions
    current_q = st.session_state.current_q
    total_q = len(questions)

    # Show final results screen
    if current_q >= total_q:
        st.balloons()
        st.markdown("## Quiz Complete!")
        st.markdown(f"### Your Score: {st.session_state.score} / {total_q}")
        percentage = (st.session_state.score / total_q) * 100
        if percentage >= 80:
            st.success("Excellent! You have a great understanding of learner misconceptions!")
        elif percentage >= 60:
            st.info("Good job! You can identify most learner types.")
        else:
            st.warning("Keep practicing! It takes time to recognise patterns in learner behaviour.")
        if st.button("Restart Quiz"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        return

    st.progress(current_q / total_q)
    st.markdown(f"**Question {current_q + 1} of {total_q}**")

    q = questions[current_q]
    expression      = q['expression']
    correct_learner = q['correct_learner']
    q_format        = q['format']

    steps        = get_learner_trace(expression, correct_learner)
    final_answer = get_final_answer(steps)

    # Compute (and cache) which options are correct for this question
    if f'correct_learners_{current_q}' not in st.session_state:
        st.session_state[f'correct_learners_{current_q}'] = get_correct_learners(q)
    correct_learners = st.session_state[f'correct_learners_{current_q}']

    # Shuffle options once
    if f'shuffled_options_{current_q}' not in st.session_state:
        shuffled = ALL_QUIZ_OPTIONS.copy()
        random.shuffle(shuffled)
        st.session_state[f'shuffled_options_{current_q}'] = shuffled
    shuffled_options = st.session_state[f'shuffled_options_{current_q}']

    st.markdown(f"### Expression: `{display_expr(expression)}`")
    st.markdown("---")

    if q_format == FORMAT_FULL_TRACE:
        st.markdown("**Full trace of student's work:**")
        st.code(display_expr(format_trace(steps, show_all=True)), language=None)
    elif q_format == FORMAT_ANSWER_ONLY:
        st.markdown("**Student's final answer:**")
        st.markdown(f"## {display_expr(final_answer)}")
    elif q_format == FORMAT_PARTIAL_START:
        st.markdown("**First steps of student's work:**")
        st.code(display_expr(format_trace(steps, show_all=False, show_first_n=2)), language=None)
        st.markdown(f"**Final answer:** {display_expr(final_answer)}")
    elif q_format == FORMAT_PARTIAL_END:
        st.markdown("**Last steps of student's work:**")
        st.code(display_expr(format_trace(steps, show_all=False, show_last_n=2)), language=None)

    st.markdown("---")
    st.markdown("**Which learner type(s) could this be? Select all that apply.**")

    selected = st.multiselect(
        "Select your answer(s):",
        shuffled_options,
        format_func=lambda x: LEARNER_SHORT_NAMES.get(x, x),
        key=f"multi_{current_q}",
        disabled=st.session_state.revealed,
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("Reveal Answer", disabled=st.session_state.revealed):
            st.session_state.revealed = True
            if not st.session_state.answered[current_q]:
                if set(selected) == set(correct_learners):
                    st.session_state.score += 1
            st.session_state.answered[current_q] = True
            st.rerun()
    with col3:
        if current_q < total_q - 1:
            if st.button("Next Question ->"):
                st.session_state.current_q += 1
                st.session_state.revealed = False
                st.rerun()
        else:
            if st.button("See Results"):
                st.session_state.current_q += 1
                st.rerun()

    if st.session_state.revealed:
        st.markdown("---")
        correct_names = [LEARNER_SHORT_NAMES.get(l, l) for l in correct_learners]
        if set(selected) == set(correct_learners):
            st.success(f"Correct! Valid answer(s): **{', '.join(correct_names)}**")
        else:
            selected_names = [LEARNER_SHORT_NAMES.get(s, s) for s in selected] if selected else ['(nothing)']
            st.error(
                f"Not quite. You selected: **{', '.join(selected_names)}**. "
                f"Valid answer(s): **{', '.join(correct_names)}**"
            )
            if len(correct_learners) > 1:
                st.info(
                    f"Note: {len(correct_learners)} learners produce the same "
                    f"{'trace' if q_format == FORMAT_FULL_TRACE else 'visible output'} "
                    f"for this expression — all are valid."
                )
        with st.expander("See full trace and explanation", expanded=True):
            for name in correct_learners:
                st.markdown(f"**{LEARNER_SHORT_NAMES.get(name, name)}:** {LEARNER_DESCRIPTIONS.get(name, '')}")
            st.markdown("**Complete trace:**")
            st.code(display_expr(format_trace(steps, show_all=True)), language=None)

    st.markdown("---")
    cols = st.columns(total_q)
    for i, col in enumerate(cols):
        with col:
            label = f"{i+1}"
            if st.session_state.answered[i]:
                label = f"[{i+1}]"
            if i == current_q:
                st.markdown(f"**{label}**")
            else:
                if st.button(label, key=f"nav_{i}"):
                    st.session_state.current_q = i
                    st.session_state.revealed = st.session_state.answered[i]
                    st.rerun()


# =============================================================================
# DIAGNOSTIC TAB RENDERER
# =============================================================================

def run_diagnostic_tab():
    st.markdown("Enter any arithmetic expression. A randomly chosen learner's trace will be shown — figure out which of the two described learners produced it.")

    # If Random was clicked, pre-fill the text box with the generated equation
    if "diag_eq_prefill" in st.session_state:
        st.session_state["diag_eq_input"] = st.session_state.pop("diag_eq_prefill")

    col_input, col_btn = st.columns([4, 1])
    with col_input:
        equation_input = st.text_input(
            "Equation:",
            placeholder="e.g.  3 + 4 * 2   or   5 + 2*(3+1)",
            key="diag_eq_input",
        )
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Random", key="diag_random_btn"):
            rand_eq = generate_random_equation()
            # Clear all diag state, then pre-fill and auto-run with the new equation
            for k in list(st.session_state.keys()):
                if k.startswith("diag_"):
                    del st.session_state[k]
            st.session_state.diag_eq_prefill = rand_eq
            st.session_state.diag_eq = rand_eq
            st.session_state.diag_ready = True
            st.rerun()

    arith_errors = st.checkbox(
        "Include arithmetic mistakes (learner occasionally swaps the operator)",
        key="diag_arith_errors",
    )

    if st.button("Run", key="diag_run_btn"):
        if not equation_input.strip():
            st.warning("Please enter an equation first.")
            return
        err = validate_equation(equation_input.strip())
        if err:
            st.error(err)
            return
        # Reset diagnostic state whenever a new equation is submitted
        for k in list(st.session_state.keys()):
            if k.startswith("diag_") and k != "diag_arith_errors":
                del st.session_state[k]
        st.session_state.diag_eq = equation_input.strip()
        st.session_state.diag_ready = True
        st.rerun()

    if not st.session_state.get("diag_ready"):
        return

    equation = st.session_state.diag_eq
    st.markdown(f"**Expression:** `{display_expr(equation)}`")
    st.markdown("---")

    # ── Run all learners once, then cache ──────────────────────────────────
    if "diag_results" not in st.session_state:
        all_results = {}
        for name in LEARNER_PROFILES:
            try:
                steps = get_learner_trace(equation, name)
                all_results[name] = {"steps": steps, "answer": get_final_answer(steps)}
            except Exception:
                all_results[name] = {"steps": [], "answer": "Error"}

        # Pick mystery learner (exclude expert/bodmas_correct, exclude errors)
        candidates = [
            k for k in LEARNER_PROFILES
            if k not in DIAG_EXCLUDE and all_results[k]["answer"] != "Error"
        ]
        if not candidates:
            st.error("Could not generate valid traces for this equation. Try a different one.")
            return

        # Prefer a learner whose trace (sequence of states) differs from expert's.
        # A different answer guarantees a different trace, but two learners can also
        # take different paths and still land on the same answer — both are fine.
        # Only fall back to same-trace learners if no alternative exists.
        expert_states = [s["state"] for s in all_results["expert"]["steps"]]
        def _trace_differs(name):
            return [s["state"] for s in all_results[name]["steps"]] != expert_states
        candidates_diff = [k for k in candidates if _trace_differs(k)]

        has_dist = has_distributable_brackets(equation)
        has_any_brackets = any(c in equation for c in '([{')

        # distributor only makes sense when brackets with +/- inside exist to expand.
        if not has_dist:
            candidates_diff = [k for k in candidates_diff if k != 'distributor']

        # multiplication_first only shows its defining behaviour when:
        #   - there are no brackets (so * ops are directly evaluatable), OR
        #   - there are distributable brackets (where prefer_distribute_mult fires).
        # With brackets containing only * or /, it falls back to leftmost depth-0 op
        # (ignoring its own precedence belief), producing a misleading trace.
        if has_any_brackets and not has_dist:
            candidates_diff = [k for k in candidates_diff if k != 'multiplication_first']

        # bracket_ignorer only shows its defining behaviour when brackets exist.
        # Without brackets it is identical to left_to_right_only — the "ignores
        # brackets" characteristic is completely invisible.
        if not has_any_brackets:
            candidates_diff = [k for k in candidates_diff if k != 'bracket_ignorer']

        mystery = random.choice(candidates_diff) if candidates_diff else random.choice(candidates)
        mystery_states = [s["state"] for s in all_results[mystery]["steps"]]

        # Build the foil pool with the same guards applied (so the foil's defining
        # behaviour is also visible in this expression).
        foil_pool = [k for k in candidates if k != mystery]
        if not has_dist:
            foil_pool = [k for k in foil_pool if k != 'distributor']
        if has_any_brackets and not has_dist:
            foil_pool = [k for k in foil_pool if k != 'multiplication_first']
        if not has_any_brackets:
            foil_pool = [k for k in foil_pool if k != 'bracket_ignorer']
        if not foil_pool:
            foil_pool = [k for k in candidates if k != mystery]

        # Prefer a foil whose trace differs from the mystery learner's trace.
        # (A learner who reaches the same answer via a different path is still a
        # valid, diagnostically interesting foil — don't filter by answer.)
        def _differs_from_mystery(name):
            return [s["state"] for s in all_results[name]["steps"]] != mystery_states

        foils_diff_trace = [k for k in foil_pool if _differs_from_mystery(k)]
        foil_candidates  = foils_diff_trace if foils_diff_trace else foil_pool

        # Among trace-different foils, prefer ones with a different description
        # so the binary choice presents two visually distinct behaviours.
        expert_walker_tmp = LearnerGraphWalker(equation, create_learner("expert"))
        mystery_desc = describe_trace_divergences(all_results[mystery]["steps"], expert_walker_tmp)
        foils_diff_desc = [
            k for k in foil_candidates
            if describe_trace_divergences(all_results[k]["steps"], expert_walker_tmp) != mystery_desc
        ]
        foil = random.choice(foils_diff_desc) if foils_diff_desc else random.choice(foil_candidates)

        options = [mystery, foil]
        random.shuffle(options)

        st.session_state.diag_results = all_results
        st.session_state.diag_mystery = mystery
        st.session_state.diag_foil = foil
        st.session_state.diag_options = options

    results = st.session_state.diag_results
    mystery = st.session_state.diag_mystery
    foil    = st.session_state.diag_foil
    options = st.session_state.diag_options

    # Use arithmetic-error trace if the checkbox is on, otherwise the clean trace
    if st.session_state.get("diag_arith_errors"):
        mystery_steps = walk_with_arithmetic_errors(equation, mystery)
    else:
        mystery_steps = results[mystery]["steps"]

    # ── Answer summary table ───────────────────────────────────────────────
    st.markdown("#### All Learner Answers")
    answer_map: dict = {}
    for name, data in results.items():
        ans = data["answer"]
        answer_map.setdefault(ans, []).append(name)

    md = "| Answer | Learners |\n|--------|----------|\n"
    for ans in sorted(answer_map.keys()):
        label_list = ", ".join(DIAG_LEARNER_LABELS.get(n, n) for n in answer_map[ans])
        md += f"| **{ans}** | {label_list} |\n"
    st.markdown(md)

    st.markdown("---")

    # ── Mystery trace with wrong steps blacked out ─────────────────────────
    st.markdown("#### Mystery Learner's Trace")
    st.markdown(
        "Steps that differ from correct BODMAS are blacked out — "
        "the intermediate result is hidden and the next visible state appears directly."
    )

    expert_learner = create_learner("expert")
    expert_walker  = LearnerGraphWalker(equation, expert_learner)

    # Compute expression-specific descriptions once and cache them
    if "diag_desc_map" not in st.session_state:
        st.session_state.diag_desc_map = {
            mystery: describe_trace_divergences(results[mystery]["steps"], expert_walker),
            foil:    describe_trace_divergences(results[foil]["steps"],    expert_walker),
        }
    desc_map = dict(st.session_state.diag_desc_map)  # shallow copy so we can augment

    # If arithmetic errors are on and the mystery trace has any swapped operators,
    # append a note to the mystery learner's description
    if st.session_state.get("diag_arith_errors"):
        if any(s.get("arithmetic_error") for s in mystery_steps):
            desc_map[mystery] = desc_map[mystery] + "; also has made an arithmetic mistake — swapped an operator"

    trace_rows = _build_trace_rows(mystery_steps, expert_walker)

    if trace_rows:
        lines = [display_expr(trace_rows[0][0])]  # always show starting state
        for i, (curr_state, action_desc, next_state, wrong) in enumerate(trace_rows):
            arith_err = mystery_steps[i].get("arithmetic_error", False)
            lines.append("  ↓")
            if wrong or arith_err:
                lines.append("  ████████████████████")
            else:
                lines.append(display_expr(next_state))
        # If the last step was blacked out, still show the final answer
        if trace_rows and (trace_rows[-1][3] or mystery_steps[len(trace_rows)-1].get("arithmetic_error")):
            lines.append("  ↓")
            lines.append(display_expr(mystery_steps[-1]["state"]))
        st.code("\n".join(lines), language=None)
    else:
        # Already a single token — nothing to trace
        if mystery_steps:
            st.code(display_expr(mystery_steps[0]["state"]), language=None)

    st.markdown("---")

    # ── Binary choice ──────────────────────────────────────────────────────
    st.markdown("#### Who is this learner?")

    if not st.session_state.get("diag_answered"):
        selected = st.radio(
            "Select your answer:",
            options,
            format_func=lambda x: desc_map.get(x, x),
            key="diag_radio",
        )
        if st.button("Submit Answer", key="diag_submit"):
            st.session_state.diag_selected = selected
            st.session_state.diag_answered = True
            st.rerun()

    else:
        selected = st.session_state.diag_selected
        st.radio(
            "Select your answer:",
            options,
            format_func=lambda x: desc_map.get(x, x),
            index=options.index(selected),
            key="diag_radio_dis",
            disabled=True,
        )

        st.markdown("---")
        if selected == mystery:
            st.success(f"Correct! The mystery learner: **{DIAG_LEARNER_LABELS[mystery]}**")
        else:
            st.error(f"Incorrect. The mystery learner was: **{DIAG_LEARNER_LABELS[mystery]}**")

        with st.expander("Full explanation", expanded=True):
            st.markdown(f"**What the mystery learner did on this expression:** {desc_map[mystery]}")
            st.markdown(f"**What the foil learner does on this expression:** {desc_map[foil]}")
            st.markdown(f"**Mystery learner's answer:** {results[mystery]['answer']}")
            st.markdown(f"**Foil learner's answer:** {results[foil]['answer']}")

            st.markdown("**Full trace (no redaction):**")
            if mystery_steps:
                full_lines = [display_expr(mystery_steps[0]["state"])]
                for i, step in enumerate(mystery_steps[:-1]):
                    chosen = step.get("chosen_action")
                    next_state = mystery_steps[i + 1]["state"]
                    full_lines.append(f"  ↓  {chosen.description if chosen else '?'}")
                    full_lines.append(display_expr(next_state))
                st.code("\n".join(full_lines), language=None)


# =============================================================================
# LEARNER WALKTHROUGH TAB
# =============================================================================

def run_walkthrough_tab():
    st.markdown(
        "Choose a learner and an expression to see exactly which actions are "
        "considered at each step, which are filtered out by the learner's policies, "
        "and which one gets chosen."
    )

    col1, col2 = st.columns([3, 2])
    with col1:
        equation = st.text_input("Equation:", placeholder="e.g. 2+3*4", key="walk_eq")
    with col2:
        learner_name = st.selectbox(
            "Learner:",
            list(LEARNER_PROFILES.keys()),
            key="walk_learner",
            format_func=lambda x: DIAG_LEARNER_LABELS.get(x, x),
        )

    if st.button("Run", key="walk_run"):
        for k in list(st.session_state.keys()):
            if k.startswith("walk_res_"):
                del st.session_state[k]
        st.session_state.walk_res_eq      = equation.strip()
        st.session_state.walk_res_learner = learner_name
        st.session_state.walk_ready       = True
        st.rerun()

    if not st.session_state.get("walk_ready"):
        return

    equation     = st.session_state.walk_res_eq
    learner_name = st.session_state.walk_res_learner

    try:
        learner = create_learner(learner_name)
        walker  = LearnerGraphWalker(equation, learner)
        steps   = walker.walk_deterministic()
    except Exception as e:
        st.error(f"Could not parse expression: {e}")
        return

    st.markdown(
        f"**Expression:** `{display_expr(equation)}`  "
        f"**Learner:** {DIAG_LEARNER_LABELS.get(learner_name, learner_name)}"
    )
    st.markdown(f"*{DIAG_LEARNER_DESCRIPTIONS.get(learner_name, '')}*")
    st.markdown("---")

    def _akey(a):
        return (a.action_type, a.operator_index)

    for i, step in enumerate(steps[:-1]):
        st.markdown(f"**Step {i + 1}**")
        st.code(display_expr(step["state"]), language=None)

        all_actions   = step["all_actions"]
        valid_keys    = {_akey(a) for a in step["valid_actions"]}
        chosen        = step["chosen_action"]
        chosen_key    = _akey(chosen) if chosen else None

        if all_actions:
            md = "| Action | Type | |\n|--------|------|---|\n"
            for a in all_actions:
                key      = _akey(a)
                is_valid = key in valid_keys
                is_chosen= key == chosen_key
                desc     = display_expr(a.description)
                if is_chosen:
                    status = "✅ **chosen**"
                elif is_valid:
                    status = "✅ valid"
                else:
                    status = "❌ blocked"
                md += f"| {desc} | `{a.action_type}` | {status} |\n"
            st.markdown(md)
        else:
            st.markdown("_No actions available — learner is stuck._")

        if i < len(steps) - 2:
            st.markdown(f"↓ → `{display_expr(steps[i + 1]['state'])}`")
        st.markdown("")

    final = steps[-1]
    st.markdown("---")
    st.markdown(f"**Final answer: `{display_expr(final['state'])}` = {get_final_answer(steps)}**")


# =============================================================================
# EXPRESSION TREE TAB
# =============================================================================

def run_tree_tab():
    st.markdown(
        "Shows every possible evaluation path for an expression as an interactive tree. "
        "Blue edges = evaluate, purple = distribute, orange = drop brackets."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        equation = st.text_input("Equation:", placeholder="e.g. (2+3)*4", key="tree_eq")
    with col2:
        max_nodes = st.number_input(
            "Max nodes:", min_value=50, max_value=2000, value=300, step=50, key="tree_max"
        )

    if st.button("Generate Tree", key="tree_run"):
        for k in list(st.session_state.keys()):
            if k.startswith("tree_res_"):
                del st.session_state[k]
        st.session_state.tree_res_eq   = equation.strip()
        st.session_state.tree_res_max  = int(max_nodes)
        st.session_state.tree_ready    = True
        st.rerun()

    if not st.session_state.get("tree_ready"):
        return

    equation  = st.session_state.tree_res_eq
    max_nodes = st.session_state.tree_res_max

    try:
        from graph_builder2 import ExpressionGraph2
        from visualizer_vue import VueTreeVisualizer

        graph = ExpressionGraph2(equation, max_nodes=max_nodes)
        viz   = VueTreeVisualizer(graph)

        html_content = viz._generate_html_template(
            tree_data     = viz._build_tree_data(),
            expression    = graph.expression,
            total_nodes   = len(graph.nodes),
            total_edges   = len(graph.edges),
            final_results = graph.get_final_results(),
            dist_edges    = sum(1 for e in graph.edges if e.action_type == "distribute"),
            drop_edges    = sum(1 for e in graph.edges if e.action_type == "drop_brackets"),
            eval_edges    = sum(1 for e in graph.edges if e.action_type == "evaluate"),
            truncated     = getattr(graph, "truncated", False),
        )

        if getattr(graph, "truncated", False):
            st.warning(
                f"Graph was truncated at {max_nodes} nodes. "
                "Increase Max nodes for a fuller picture."
            )

        import streamlit.components.v1 as components
        components.html(html_content, height=750, scrolling=True)

    except Exception as e:
        st.error(f"Could not build tree: {e}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    st.set_page_config(
        page_title="Learner Diagnosis",
        page_icon="?",
        layout="wide",
    )
    st.title("Learner Diagnosis")

    tab1, tab2, tab3, tab4 = st.tabs([
        "Quiz",
        "Diagnose Any Equation",
        "Learner Walkthrough",
        "Expression Tree",
    ])

    with tab1:
        run_quiz_tab()

    with tab2:
        run_diagnostic_tab()

    with tab3:
        run_walkthrough_tab()

    with tab4:
        run_tree_tab()


if __name__ == "__main__":
    main()
