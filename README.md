# Expression Evaluation Tree Generator

**Explore all possible ways to evaluate arithmetic expressions with interactive visualizations and reinforcement learning rewards.**

![Python](https://img.shields.io/badge/Python-3.7+-blue)
![License](https://img.shields.io/badge/License-MIT-green)

## Overview

This tool generates **all possible evaluation paths** for arithmetic expressions, ignoring traditional BODMAS/PEMDAS rules to explore every evaluation order. It creates an interactive tree diagram showing:

- 🌳 All possible intermediate states  
- ✅ Correct operations (following BODMAS) highlighted in **green** with `+1` reward
- ❌ Incorrect operations highlighted in **red** with `-1` reward
- 📊 Cumulative rewards for each evaluation path
- 🎯 Final results from different evaluation paths

### Example

For the expression `3+2*4`:

| Path | Order | Calculation | Result | Total Reward |
|------|-------|-------------|--------|--------------|
| Path 1 | `*` first (BODMAS correct) | `3+(2*4)` = `3+8` | **11** | +2 |
| Path 2 | `+` first (incorrect) | `(3+2)*4` = `5*4` | **20** | -2 |

The tool visualizes both paths, showing which follow BODMAS rules through color-coded edges and rewards!

## Features

✅ **Operators**: `+`, `-`, `*`, `/`, `^` (power)  
✅ **Parentheses**: Full support for nested parentheses like `(2+3)*(4+5)`  
✅ **Negative numbers**: Handles expressions like `-3+4*2`  
✅ **BODMAS/PEMDAS rewards**: +1 for correct operations, -1 for incorrect  
✅ **Dependency-aware**: Understands when operations are independent (can be done in parallel)  
✅ **Interactive HTML visualization** with Plotly  
✅ **Cumulative reward tracking** for each path  

## File Structure

```
Alg_Trust_NYU/
├── tokenizer.py        # Parses expressions into tokens
├── graph_builder.py    # Builds the evaluation tree with rewards
├── visualizer.py       # Generates interactive HTML visualization
├── main.py             # Main entry point
└── README.md           # This file
```

## Installation

```bash
# Clone the repository
git clone https://github.com/divya603/Alg-Trust.git
cd Alg-Trust

# Install dependencies
pip install plotly
```

**Requirements:**
- Python 3.7+
- Plotly (for visualization)
- Modern web browser (for viewing HTML output)

## Usage

### Basic Usage

```bash
python main.py "3+2*4"
```

### Interactive Mode

```bash
python main.py
# Enter expression when prompted
```

### More Examples

```bash
# Simple expression
python main.py "2+3*5"

# With negative numbers
python main.py "-3+4*2"

# With parentheses
python main.py "(2+3)*5"

# Nested parentheses
python main.py "(2+3)*(4+5)"

# Complex expression
python main.py "2+3*4-5"
```

## Output

The program generates:

1. **Console output** with statistics:
   - Total nodes and edges
   - All possible final results
   - Sample evaluation paths

2. **Interactive HTML file** with:
   - Tree diagram showing all paths
   - **Blue nodes** = intermediate expressions
   - **Green nodes** = final results with cumulative rewards
   - **Green edges** = correct BODMAS operation (+1)
   - **Red edges** = incorrect operation (-1)

## How BODMAS Rewards Work

### Operator Priority
| Operator | Priority |
|----------|----------|
| `^` | 3 (highest) |
| `*`, `/` | 2 |
| `+`, `-` | 1 (lowest) |

### Reward Logic

1. **Within same parenthesis depth**: Higher priority operators must be done first
2. **Deeper parentheses first**: Operations inside `()` have higher effective priority
3. **Left-to-right for chains**: Adjacent operators with same priority → leftmost first
4. **Independent operations**: Non-adjacent same-priority ops can be done in any order

### Example: `2+3*4-5`

```
Available: ['+' at 1, '*' at 3, '-' at 5]

Correct choice: '*' at 3 (highest priority) → +1 reward
Wrong choices: '+' or '-' (lower priority) → -1 reward
```

## Understanding the Visualization

### Nodes
- **Blue circles**: Intermediate expression states
- **Green circles**: Final results with cumulative reward shown

### Edges
- **Green lines**: Correct BODMAS operations `[+1]`
- **Red lines**: Incorrect operations `[-1]`
- **Labels**: Show `'operator',position` and reward

### Interpreting Cumulative Rewards
- **Maximum possible reward**: Always following BODMAS = best path
- **Negative total reward**: Made more wrong choices than right
- **Zero reward**: Equal right and wrong choices

## Algorithm Details

### Graph Building
- Uses **Breadth-First Search (BFS)** to explore all paths
- At each state, finds all available operations
- Creates branches for each possible operation
- Assigns rewards based on BODMAS correctness

### Complexity
- **Time**: O(n!) where n = number of operations
- **Space**: O(n!) for storing all paths

### Why So Many Paths?

| Operations | Possible Paths |
|------------|---------------|
| 2 | 2 |
| 3 | 6 |
| 4 | 24 |
| 5 | 120 |

## Example Console Output

```
======================================================================
EXPRESSION EVALUATION TREE GENERATOR
======================================================================

Building evaluation tree for: 3+2*4
----------------------------------------------------------------------
[OK] Expression parsed successfully
[OK] Total nodes: 5
[OK] Total edges: 4
[OK] Possible final results: [11.0, 20.0]
[OK] Number of different evaluation paths: 2

----------------------------------------------------------------------
SAMPLE EVALUATION PATHS
======================================================================

Path 1: Result = 11.0
  Step 1: 3+2*4 -> Start
  Step 2: 3+8.0 -> Performed '*' at position 3
  Step 3: 11.0 -> Performed '+' at position 1

Path 2: Result = 20.0
  Step 1: 3+2*4 -> Start
  Step 2: 5.0*4 -> Performed '+' at position 1
  Step 3: 20.0 -> Performed '*' at position 1
```

## Use Cases

- **Education**: Teaching BODMAS/PEMDAS rules by showing consequences of wrong order
- **Reinforcement Learning**: Training agents to learn operator precedence
- **Algorithm Visualization**: Understanding expression parsing and evaluation
- **Research**: Studying how humans evaluate expressions

## Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests

## License

MIT License - Free to use for educational and research purposes.

## Author

Created for exploring algorithmic trust and expression evaluation at NYU.
