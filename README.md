# Expression Evaluation Tree Generator

**Explore all possible ways to evaluate arithmetic expressions with interactive visualizations, learner modeling, and reinforcement learning rewards.**


## Overview

This tool generates **all possible evaluation paths** for arithmetic expressions, exploring every evaluation order regardless of BODMAS/PEMDAS rules. It includes a **Learner System** that models different types of students—from experts who follow BODMAS perfectly to novices who make common mistakes.

### Key Features

- **Evaluation Tree Visualization**: See all possible ways to evaluate an expression
- **Learner Modeling**: Simulate how different types of students solve expressions
- **Policy System**: Define learner behaviors through composable policy rules
- **Bracket Handling**: Support for distribution, evaluation inside brackets, and common mistakes (bracket dropping)
- **BODMAS Rewards**: Track correct (+1) vs incorrect (-1) operations for RL training


## Core Components

### 1. Learner System (`learner.py`)

A **Learner** is defined by:
- **Precedence Map**: Their belief about operator ordering (e.g., BODMAS, flat, addition-first)
- **Policies**: Rules that filter valid actions (conjunctively combined)


### 2. Policy System (`policies.py`)

Policies are organized into **categories**

The conjunction of policies determines valid actions:
```
valid_action = φ₁(s,a,A,P) ∧ φ₂(s,a,A,P) ∧ ... ∧ φₙ(s,a,A,P)
```


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
