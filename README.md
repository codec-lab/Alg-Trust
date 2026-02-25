# Expression Evaluation Tree Generator

**Explore all possible ways to evaluate arithmetic expressions with interactive visualizations, learner modeling, and reinforcement learning rewards.**

![Python](https://img.shields.io/badge/Python-3.7+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

This tool generates **all possible evaluation paths** for arithmetic expressions, exploring every evaluation order regardless of BODMAS/PEMDAS rules. It includes a **Learner System** that models different types of students—from experts who follow BODMAS perfectly to novices who make common mistakes.

### Key Features

- **Evaluation Tree Visualization**: See all possible ways to evaluate an expression
- **Learner Modeling**: Simulate how different types of students solve expressions
- **Policy System**: Define learner behaviors through composable policy rules
- **Bracket Handling**: Support for distribution, evaluation inside brackets, and common mistakes (bracket dropping)
- **BODMAS Rewards**: Track correct (+1) vs incorrect (-1) operations for RL training

### Example

For the expression `3+2*4`:

| Learner Profile | Behavior | Result | Reasoning |
|----------------|----------|--------|-----------|
| **expert** | `*` first → `+` | **11** | Follows BODMAS correctly |
| **addition_first** | `+` first → `*` | **20** | Believes addition has higher precedence |
| **left_to_right_only** | `+` first → `*` | **20** | Ignores precedence, goes left-to-right |

## Core Components

### 1. Learner System (`learner.py`)

A **Learner** is defined by:
- **Precedence Map**: Their belief about operator ordering (e.g., BODMAS, flat, addition-first)
- **Policies**: Rules that filter valid actions (conjunctively combined)


### 2. Policy System (`policies.py`)

Policies are organized into **categories**:

| Category | Description | Policies |
|----------|-------------|----------|
| **Precedence** | Operator ordering | `highest_precedence_first`, `no_higher_prec_left`, `no_higher_prec_right` |
| **Direction** | Tie-breaking for same precedence | `leftmost_first`, `rightmost_first`, `left_to_right_strict`, `right_to_left_strict` |
| **Bracket Handling** | How to handle brackets | `brackets_first`, `brackets_optional`, `brackets_ignored` |
| **Action Preference** | Evaluate vs distribute | `prefer_evaluate`, `prefer_distribute` |

The conjunction of policies determines valid actions:
```
valid_action = φ₁(s,a,A,P) ∧ φ₂(s,a,A,P) ∧ ... ∧ φₙ(s,a,A,P)
```

### 3. Preset Learner Profiles

| Profile | Precedence | Description |
|---------|------------|-------------|
| `expert` | BODMAS | Follows BODMAS correctly with brackets |
| `bodmas_correct` | BODMAS | Knows BODMAS precedence and left-to-right rule |
| `addition_first` | Addition > Mult | Believes addition comes before multiplication (wrong!) |
| `multiplication_first` | Only * special | Knows multiplication is special, incomplete knowledge |
| `left_to_right_only` | Flat | Strictly left-to-right, ignores precedence |
| `right_to_left` | Flat | Right-to-left, ignores precedence (wrong!) |
| `novice` | Flat | No knowledge - any action is valid |
| `bracket_ignorer` | Flat | Ignores brackets completely, may drop them |
| `distributor` | BODMAS | Knows BODMAS but prefers to distribute |
| `bodmas_wrong_direction` | BODMAS | Knows precedence but goes right-to-left |

### 4. Precedence Maps

| Map | Ordering | Description |
|-----|----------|-------------|
| `bodmas` | `^` > `*/` > `+-` | Standard BODMAS/PEMDAS |
| `addition_first` | `+-` > `^` > `*/` | Addition/subtraction highest (wrong!) |
| `multiplication_first` | `*` > `/^` > `+-` | Only multiplication is special |
| `flat` | All equal | No operator precedence |

## File Structure

```
Alg_Trust_NYU/
├── Core Expression Parsing
│   ├── tokenizer.py           # Parses expressions into tokens
│   ├── graph_builder.py       # Original evaluation tree builder
│   └── graph_builder2.py      # Enhanced builder with bracket distribution
│
├── Learner & Policy System
│   ├── policies.py            # Policy definitions and categories
│   ├── learner.py             # Learner profiles and creation
│   └── learner_integration.py # Integration between learners and graphs
│
├── Visualization
│   ├── visualizer.py          # Original HTML visualization (Plotly)
│   ├── visualizer2.py         # Enhanced visualization
│   ├── visualizer_tabs.py     # Tab-based visualizer
│   └── visualizer_vue.py      # Vue.js interactive explorer
│
├── Entry Points
│   ├── main.py                # Basic expression tree generation
│   └── main2.py               # Advanced with bracket handling
│
├── Tests
│   └── test_policies.py       # Policy system tests
│
└── README.md
```

## Installation

```bash
# Clone the repository
git clone https://github.com/divya603/Alg-Trust.git
cd Alg-Trust

# Install dependencies
pip install -r requirements.txt
```

**Requirements:**
- Python 3.7+
- Plotly (for visualization)
- web browser (for viewing HTML output)

## Usage

### Basic Usage

```bash
# Generate evaluation tree
python main.py "3+2*4"

# With brackets and distribution support
python main2.py "(2+3)*4"

#Learner
python visualizer_tabs.py "4+3-7*4"
```
