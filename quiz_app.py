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


def get_learner_trace(expression: str, learner_name: str):
    """Get the full trace for a learner solving an expression."""
    learner = create_learner(learner_name)
    walker = LearnerGraphWalker(expression, learner)
    return walker.walk_deterministic()


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
                if l_idx > e_idx and 'right_to_left' not in found:
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
    """
    try:
        valid, _ = expert_walker.get_valid_actions_for_state(list(tokens))
        if not valid or not mystery_action:
            return True
        expert_action = valid[0]
        return not (
            mystery_action.action_type == expert_action.action_type
            and mystery_action.operator == expert_action.operator
            and mystery_action.operator_index == expert_action.operator_index
        )
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


def generate_questions():
    return [
        # Full trace (5)
        {'expression': '2+3*4',      'correct_learner': 'addition_first',    'format': FORMAT_FULL_TRACE,
         'options': ['expert', 'addition_first', 'right_to_left']},
        {'expression': '2*3+4*5',    'correct_learner': 'left_to_right_only','format': FORMAT_FULL_TRACE,
         'options': ['expert', 'addition_first', 'left_to_right_only', 'right_to_left']},
        {'expression': '10-2-3',     'correct_learner': 'right_to_left',     'format': FORMAT_FULL_TRACE,
         'options': ['expert', 'right_to_left']},
        {'expression': '5+2*(3+1)',  'correct_learner': 'bracket_ignorer',   'format': FORMAT_FULL_TRACE,
         'options': ['expert', 'addition_first', 'bracket_ignorer']},
        {'expression': '12/3+4*2',   'correct_learner': 'expert',            'format': FORMAT_FULL_TRACE,
         'options': ['expert', 'addition_first', 'left_to_right_only', 'right_to_left']},
        # Answer only (5)
        {'expression': '12-3+4',     'correct_learner': 'right_to_left',     'format': FORMAT_ANSWER_ONLY,
         'options': ['expert', 'right_to_left']},
        {'expression': '20-4*3+2',   'correct_learner': 'addition_first',    'format': FORMAT_ANSWER_ONLY,
         'options': ['expert', 'addition_first', 'left_to_right_only', 'right_to_left']},
        {'expression': '8/4*2',      'correct_learner': 'multiplication_first','format': FORMAT_ANSWER_ONLY,
         'options': ['expert', 'multiplication_first']},
        {'expression': '4*(2+3)',     'correct_learner': 'bracket_ignorer',   'format': FORMAT_ANSWER_ONLY,
         'options': ['expert', 'bracket_ignorer']},
        {'expression': '15-3*2+4',   'correct_learner': 'left_to_right_only','format': FORMAT_ANSWER_ONLY,
         'options': ['expert', 'addition_first', 'left_to_right_only', 'right_to_left']},
        # Partial start (3)
        {'expression': '10+2*3-4',   'correct_learner': 'expert',            'format': FORMAT_PARTIAL_START,
         'options': ['expert', 'addition_first', 'left_to_right_only']},
        {'expression': '3+6/2*4',    'correct_learner': 'multiplication_first','format': FORMAT_PARTIAL_START,
         'options': ['expert', 'addition_first', 'multiplication_first']},
        {'expression': '2*(3+4)-5',  'correct_learner': 'addition_first',    'format': FORMAT_PARTIAL_START,
         'options': ['expert', 'addition_first', 'bracket_ignorer']},
        # Partial end (2)
        {'expression': '10/2/5',     'correct_learner': 'right_to_left',     'format': FORMAT_PARTIAL_END,
         'options': ['expert', 'right_to_left']},
        {'expression': '20/4/2',     'correct_learner': 'right_to_left',     'format': FORMAT_PARTIAL_END,
         'options': ['expert', 'right_to_left']},
    ]


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
    expression    = q['expression']
    correct_learner = q['correct_learner']
    q_format      = q['format']
    options       = q['options']

    steps = get_learner_trace(expression, correct_learner)
    final_answer = get_final_answer(steps)

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
    st.markdown("**Which learner type is this?**")

    if f'shuffled_options_{current_q}' not in st.session_state:
        shuffled = options.copy()
        random.shuffle(shuffled)
        st.session_state[f'shuffled_options_{current_q}'] = shuffled

    shuffled_options = st.session_state[f'shuffled_options_{current_q}']

    selected = st.radio(
        "Select your answer:",
        shuffled_options,
        format_func=lambda x: LEARNER_SHORT_NAMES.get(x, x),
        key=f"radio_{current_q}",
        disabled=st.session_state.revealed,
    )
    st.session_state.selected_answer = selected

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("Reveal Answer", disabled=st.session_state.revealed):
            st.session_state.revealed = True
            if selected == correct_learner and not st.session_state.answered[current_q]:
                st.session_state.score += 1
            st.session_state.answered[current_q] = True
            st.rerun()
    with col3:
        if current_q < total_q - 1:
            if st.button("Next Question ->"):
                st.session_state.current_q += 1
                st.session_state.revealed = False
                st.session_state.selected_answer = None
                st.rerun()
        else:
            if st.button("See Results"):
                st.session_state.current_q += 1
                st.rerun()

    if st.session_state.revealed:
        st.markdown("---")
        if selected == correct_learner:
            st.success(f"Correct! This is the **{LEARNER_SHORT_NAMES[correct_learner]}** learner.")
        else:
            st.error(f"Incorrect. This is the **{LEARNER_SHORT_NAMES[correct_learner]}** learner.")
        with st.expander("See full trace and explanation", expanded=True):
            st.markdown(f"**Learner:** {LEARNER_DESCRIPTIONS[correct_learner]}")
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

    equation_input = st.text_input(
        "Equation:",
        placeholder="e.g.  3 + 4 * 2   or   5 + 2*(3+1)",
        key="diag_eq_input",
    )

    if st.button("Run", key="diag_run_btn"):
        if not equation_input.strip():
            st.warning("Please enter an equation first.")
            return
        # Reset diagnostic state whenever a new equation is submitted
        for k in list(st.session_state.keys()):
            if k.startswith("diag_"):
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
        mystery_ans = all_results[mystery]["answer"]

        # Foil: prefer a different final answer
        foils_diff = [k for k in candidates if k != mystery and all_results[k]["answer"] != mystery_ans]
        foils_same = [k for k in candidates if k != mystery]
        foil = random.choice(foils_diff) if foils_diff else random.choice(foils_same)

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
    desc_map = st.session_state.diag_desc_map

    trace_rows = _build_trace_rows(mystery_steps, expert_walker)

    if trace_rows:
        lines = [display_expr(trace_rows[0][0])]  # always show starting state
        for curr_state, action_desc, next_state, wrong in trace_rows:
            lines.append("  ↓")
            if wrong:
                lines.append("  ████████████████████")
            else:
                lines.append(display_expr(next_state))
        # If the last step was blacked out, still show the final answer with an arrow
        if trace_rows and trace_rows[-1][3]:
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
