"""
Learner Diagnosis Quiz - Streamlit App

A quiz interface to test if observers can identify learner misconceptions
based on their work (full trace, partial trace, or just answer).
"""

import streamlit as st
from learner_integration import LearnerGraphWalker
from learner import create_learner, LEARNER_PROFILES
import random

# =============================================================================
# LEARNER DESCRIPTIONS (for display)
# =============================================================================

LEARNER_DESCRIPTIONS = {
    'expert': 'Expert - Follows BODMAS correctly (brackets, then */ before +-)',
    'addition_first': 'Addition First - Does +/- before */',
    'multiplication_first': 'Multiplication First - Prioritizes * above all, distributes eagerly',
    'bracket_ignorer': 'Bracket Ignorer - Drops brackets and ignores them',
    'left_to_right_only': 'Left to Right - Ignores precedence, evaluates left to right',
    'right_to_left': 'Right to Left - Ignores precedence, evaluates right to left',
}

# Short names for options
LEARNER_SHORT_NAMES = {
    'expert': 'Expert (BODMAS)',
    'addition_first': 'Addition First',
    'multiplication_first': 'Multiplication First',
    'bracket_ignorer': 'Bracket Ignorer',
    'left_to_right_only': 'Left to Right',
    'right_to_left': 'Right to Left',
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_learner_trace(expression: str, learner_name: str):
    """Get the full trace for a learner solving an expression."""
    learner = create_learner(learner_name)
    walker = LearnerGraphWalker(expression, learner)
    steps = walker.walk_deterministic()
    return steps


def format_trace(steps, show_all=True, show_first_n=None, show_last_n=None):
    """Format trace steps for display."""
    if not steps:
        return "No steps available"

    lines = []
    total_steps = len(steps)

    for i, step in enumerate(steps):
        show_step = False

        if show_all:
            show_step = True
        elif show_first_n is not None and i < show_first_n:
            show_step = True
        elif show_last_n is not None and i >= total_steps - show_last_n:
            show_step = True

        if show_step:
            state = step.get('state', '')
            if step.get('is_final'):
                lines.append(f"Step {i+1}: {state} (FINAL)")
            elif step.get('chosen_action'):
                action = step['chosen_action']
                lines.append(f"Step {i+1}: {state}")
                lines.append(f"        -> {action.description}")
            else:
                lines.append(f"Step {i+1}: {state}")
        elif not show_step and (i == show_first_n if show_first_n else False):
            lines.append("        ...")
            lines.append("        (steps hidden)")
            lines.append("        ...")

    return "\n".join(lines)


def get_final_answer(steps):
    """Get final answer from steps."""
    if steps and 'result' in steps[-1]:
        result = steps[-1]['result']
        # Format nicely
        if result == int(result):
            return str(int(result))
        else:
            return f"{result:.4f}".rstrip('0').rstrip('.')
    return "N/A"


# =============================================================================
# QUIZ QUESTIONS (HARDCODED)
# =============================================================================

# Question format types
FORMAT_FULL_TRACE = "full_trace"
FORMAT_ANSWER_ONLY = "answer_only"
FORMAT_PARTIAL_START = "partial_start"  # Show first 2 steps
FORMAT_PARTIAL_END = "partial_end"      # Show last 2 steps

def generate_questions():
    """Generate the 15 quiz questions."""
    questions = [
        # FORMAT: (expression, correct_learner, question_format, options)
        # Options are learners that give DIFFERENT answers

        # Full trace questions (5)
        {
            'expression': '2+3*4',
            'correct_learner': 'addition_first',
            'format': FORMAT_FULL_TRACE,
            'options': ['expert', 'addition_first', 'right_to_left'],
        },
        {
            'expression': '2*3+4*5',
            'correct_learner': 'left_to_right_only',
            'format': FORMAT_FULL_TRACE,
            'options': ['expert', 'addition_first', 'left_to_right_only', 'right_to_left'],
        },
        {
            'expression': '10-2-3',
            'correct_learner': 'right_to_left',
            'format': FORMAT_FULL_TRACE,
            'options': ['expert', 'right_to_left'],
        },
        {
            'expression': '5+2*(3+1)',
            'correct_learner': 'bracket_ignorer',
            'format': FORMAT_FULL_TRACE,
            'options': ['expert', 'addition_first', 'bracket_ignorer'],
        },
        {
            'expression': '12/3+4*2',
            'correct_learner': 'expert',
            'format': FORMAT_FULL_TRACE,
            'options': ['expert', 'addition_first', 'left_to_right_only', 'right_to_left'],
        },

        # Answer only questions (5)
        {
            'expression': '12-3+4',
            'correct_learner': 'right_to_left',
            'format': FORMAT_ANSWER_ONLY,
            'options': ['expert', 'right_to_left'],
        },
        {
            'expression': '20-4*3+2',
            'correct_learner': 'addition_first',
            'format': FORMAT_ANSWER_ONLY,
            'options': ['expert', 'addition_first', 'left_to_right_only', 'right_to_left'],
        },
        {
            'expression': '8/4*2',
            'correct_learner': 'multiplication_first',
            'format': FORMAT_ANSWER_ONLY,
            'options': ['expert', 'multiplication_first'],
        },
        {
            'expression': '4*(2+3)',
            'correct_learner': 'bracket_ignorer',
            'format': FORMAT_ANSWER_ONLY,
            'options': ['expert', 'bracket_ignorer'],
        },
        {
            'expression': '15-3*2+4',
            'correct_learner': 'left_to_right_only',
            'format': FORMAT_ANSWER_ONLY,
            'options': ['expert', 'addition_first', 'left_to_right_only', 'right_to_left'],
        },

        # Partial trace - first steps shown (3)
        {
            'expression': '10+2*3-4',
            'correct_learner': 'expert',
            'format': FORMAT_PARTIAL_START,
            'options': ['expert', 'addition_first', 'left_to_right_only'],
        },
        {
            'expression': '3+6/2*4',
            'correct_learner': 'multiplication_first',
            'format': FORMAT_PARTIAL_START,
            'options': ['expert', 'addition_first', 'multiplication_first'],
        },
        {
            'expression': '2*(3+4)-5',
            'correct_learner': 'addition_first',
            'format': FORMAT_PARTIAL_START,
            'options': ['expert', 'addition_first', 'bracket_ignorer'],
        },

        # Partial trace - last steps shown (2)
        {
            'expression': '10/2/5',
            'correct_learner': 'right_to_left',
            'format': FORMAT_PARTIAL_END,
            'options': ['expert', 'right_to_left'],
        },
        {
            'expression': '20/4/2',
            'correct_learner': 'right_to_left',
            'format': FORMAT_PARTIAL_END,
            'options': ['expert', 'right_to_left'],
        },
    ]

    return questions


# =============================================================================
# STREAMLIT APP
# =============================================================================

def main():
    st.set_page_config(
        page_title="Learner Diagnosis Quiz",
        page_icon="?",
        layout="centered"
    )

    st.title("Learner Diagnosis Quiz")
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

    # Initialize session state
    if 'questions' not in st.session_state:
        questions = generate_questions()
        random.shuffle(questions)  # Randomize order
        st.session_state.questions = questions
        st.session_state.current_q = 0
        st.session_state.revealed = False
        st.session_state.selected_answer = None
        st.session_state.score = 0
        st.session_state.answered = [False] * len(questions)

    questions = st.session_state.questions
    current_q = st.session_state.current_q
    total_q = len(questions)

    # Progress bar
    st.progress((current_q) / total_q)
    st.markdown(f"**Question {current_q + 1} of {total_q}**")

    # Get current question
    q = questions[current_q]
    expression = q['expression']
    correct_learner = q['correct_learner']
    q_format = q['format']
    options = q['options']

    # Get trace for the correct learner
    steps = get_learner_trace(expression, correct_learner)
    final_answer = get_final_answer(steps)

    # Display the expression
    st.markdown(f"### Expression: `{expression}`")

    # Display format-specific content
    st.markdown("---")

    if q_format == FORMAT_FULL_TRACE:
        st.markdown("**Full trace of student's work:**")
        st.code(format_trace(steps, show_all=True), language=None)

    elif q_format == FORMAT_ANSWER_ONLY:
        st.markdown("**Student's final answer:**")
        st.markdown(f"## {final_answer}")

    elif q_format == FORMAT_PARTIAL_START:
        st.markdown("**First steps of student's work:**")
        st.code(format_trace(steps, show_all=False, show_first_n=2), language=None)
        st.markdown(f"**Final answer:** {final_answer}")

    elif q_format == FORMAT_PARTIAL_END:
        st.markdown("**Last steps of student's work:**")
        st.code(format_trace(steps, show_all=False, show_last_n=2), language=None)

    st.markdown("---")

    # Multiple choice options
    st.markdown("**Which learner type is this?**")

    # Shuffle options for display (but keep track)
    if f'shuffled_options_{current_q}' not in st.session_state:
        shuffled = options.copy()
        random.shuffle(shuffled)
        st.session_state[f'shuffled_options_{current_q}'] = shuffled

    shuffled_options = st.session_state[f'shuffled_options_{current_q}']

    # Radio buttons for selection
    selected = st.radio(
        "Select your answer:",
        shuffled_options,
        format_func=lambda x: LEARNER_SHORT_NAMES.get(x, x),
        key=f"radio_{current_q}",
        disabled=st.session_state.revealed
    )
    st.session_state.selected_answer = selected

    # Buttons row
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

    # Show result if revealed
    if st.session_state.revealed:
        st.markdown("---")

        if selected == correct_learner:
            st.success(f"Correct! This is the **{LEARNER_SHORT_NAMES[correct_learner]}** learner.")
        else:
            st.error(f"Incorrect. This is the **{LEARNER_SHORT_NAMES[correct_learner]}** learner.")

        # Show full explanation
        with st.expander("See full trace and explanation", expanded=True):
            st.markdown(f"**Learner:** {LEARNER_DESCRIPTIONS[correct_learner]}")
            st.markdown("**Complete trace:**")
            st.code(format_trace(steps, show_all=True), language=None)

    # Navigation at bottom
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

    # Show final results
    if current_q >= total_q:
        st.balloons()
        st.markdown("---")
        st.markdown("## Quiz Complete!")
        st.markdown(f"### Your Score: {st.session_state.score} / {total_q}")

        percentage = (st.session_state.score / total_q) * 100
        if percentage >= 80:
            st.success("Excellent! You have a great understanding of learner misconceptions!")
        elif percentage >= 60:
            st.info("Good job! You can identify most learner types.")
        else:
            st.warning("Keep practicing! It takes time to recognize patterns in learner behavior.")

        if st.button("Restart Quiz"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()


if __name__ == "__main__":
    main()
