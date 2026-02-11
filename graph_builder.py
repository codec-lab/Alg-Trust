"""
Graph Builder for Expression Evaluation Tree
Generates all possible ways to evaluate an arithmetic expression
"""

from tokenizer import tokenize, validate_tokens
from typing import List, Tuple, Dict
import uuid


class Node:
    """Represents a state in the expression evaluation"""

    def __init__(self, tokens: List[str], parent_id: str = None, cumulative_reward: int = 0):
        self.id = str(uuid.uuid4())[:8]  # Short unique ID
        self.tokens = tokens
        self.expression = ''.join(tokens)
        self.is_final = len(tokens) == 1
        self.result = float(tokens[0]) if self.is_final else None
        self.parent_id = parent_id
        self.cumulative_reward = cumulative_reward  # Sum of rewards from root to this node

    def __repr__(self):
        return f"Node({self.expression}, final={self.is_final}, reward={self.cumulative_reward})"


class Edge:
    """Represents an operation performed between two nodes"""

    def __init__(self, from_node_id: str, to_node_id: str,
                 operation_index: int, operator: str, reward: int = 0):
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.operation_index = operation_index
        self.operator = operator
        self.reward = reward  # +1 for correct action, -1 for wrong action
        self.description = f"Performed '{operator}' at position {operation_index}"

    def __repr__(self):
        return f"Edge({self.operation_index}, '{self.operator}', reward={self.reward})"


# BODMAS operator priorities (higher number = higher priority)
OPERATOR_PRIORITY = {
    '+': 1,
    '-': 1,
    '*': 2,
    '/': 2,
    '^': 3
}


def get_parenthesis_depth(tokens: List[str], op_index: int) -> int:
    """
    Calculate the parenthesis depth at a given operator position.

    Args:
        tokens: List of tokens
        op_index: Index of the operator

    Returns:
        Depth (number of unclosed open parentheses before this position)
    """
    depth = 0
    for i in range(op_index):
        if tokens[i] == '(':
            depth += 1
        elif tokens[i] == ')':
            depth -= 1
    return depth


def get_operation_priority(op: Tuple[int, str], tokens: List[str] = None) -> Tuple[int, int]:
    """
    Get the effective priority of an operation as (depth, operator_priority).

    Args:
        op: (index, operator) tuple
        tokens: List of tokens

    Returns:
        Tuple of (parenthesis_depth, operator_priority)
    """
    op_index, operator = op
    depth = get_parenthesis_depth(tokens, op_index) if tokens else 0
    priority = OPERATOR_PRIORITY.get(operator, 0)
    return (depth, priority)


def get_correct_operations(available_ops: List[Tuple[int, str]], tokens: List[str] = None) -> List[Tuple[int, str]]:
    """
    Determine ALL correct operations based on dependency-aware BODMAS rules.

    Operations at different parenthesis depths are considered independent scopes.
    Within each depth level, operations with the highest operator priority are correct.
    Adjacent operations (sharing operands) form chains - only leftmost in chain is correct.

    Rules:
    1. Group operations by parenthesis depth
    2. Within each depth, find the highest operator priority
    3. Among highest priority ops, check for adjacency (indices differ by 2)
    4. Adjacent ops form chains - only leftmost in each chain is correct
    5. Non-adjacent ops are independent - all are correct

    Args:
        available_ops: List of (index, operator) tuples
        tokens: List of tokens (needed to calculate parenthesis depth)

    Returns:
        List of all correct (index, operator) tuples
    """
    if not available_ops:
        return []

    # Calculate priority for each operation: (depth, operator_priority)
    op_priorities = [(op, get_operation_priority(op, tokens)) for op in available_ops]

    # Group operations by depth
    depth_groups = {}
    for op, (depth, op_priority) in op_priorities:
        if depth not in depth_groups:
            depth_groups[depth] = []
        depth_groups[depth].append((op, op_priority))

    # For each depth, find operations with the highest operator priority
    # Then apply left-to-right rule for adjacent (chained) operations
    correct_ops = []
    for depth, ops_at_depth in depth_groups.items():
        max_priority_at_depth = max(priority for _, priority in ops_at_depth)

        # Get all ops with max priority at this depth
        max_priority_ops = [(op, priority) for op, priority in ops_at_depth
                           if priority == max_priority_at_depth]

        # Sort by index (left to right)
        max_priority_ops.sort(key=lambda x: x[0][0])

        # Find chains of adjacent operations (indices differ by 2 = share operand)
        # For each chain, only the leftmost is correct
        prev_index = None
        for op, priority in max_priority_ops:
            op_index = op[0]
            if prev_index is None or op_index != prev_index + 2:
                # Start of new chain or isolated operation - include it
                correct_ops.append(op)
            # else: part of existing chain, skip (only leftmost is correct)
            prev_index = op_index

    return correct_ops


class ExpressionGraph:
    """Builds and stores the complete evaluation graph"""
    
    def __init__(self, expression: str):
        self.expression = expression
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.root_id = None
        
        # Build the graph
        self._build_graph()
    
    def _build_graph(self):
        """Build the complete graph using BFS"""
        tokens = tokenize(self.expression)
        validate_tokens(tokens)

        # Create root node (starts with 0 cumulative reward)
        root = Node(tokens, cumulative_reward=0)
        self.root_id = root.id
        self.nodes[root.id] = root

        # BFS queue
        queue = [root]

        while queue:
            current_node = queue.pop(0)

            # Skip if this is a final node
            if current_node.is_final:
                continue

            # Find all available operations
            available_ops = self._find_available_operations(current_node.tokens)

            # Determine ALL correct operations (BODMAS + parentheses)
            correct_ops = get_correct_operations(available_ops, current_node.tokens)

            # For each available operation, create a new branch
            for op_index, operator in available_ops:
                # Calculate reward: +1 if this is a correct operation, -1 otherwise
                if (op_index, operator) in correct_ops:
                    reward = 1
                else:
                    reward = -1

                # Perform the operation
                new_tokens = self._perform_operation(
                    current_node.tokens, op_index, operator
                )

                # Create new node with cumulative reward
                new_cumulative = current_node.cumulative_reward + reward
                new_node = Node(new_tokens, parent_id=current_node.id,
                               cumulative_reward=new_cumulative)
                self.nodes[new_node.id] = new_node

                # Create edge with reward
                edge = Edge(current_node.id, new_node.id, op_index, operator, reward)
                self.edges.append(edge)

                # Add to queue for further exploration
                queue.append(new_node)
    
    def _find_available_operations(self, tokens: List[str]) -> List[Tuple[int, str]]:
        """
        Find all operator positions that can be performed.
        An operator is available only if both adjacent tokens are numbers
        (not parentheses).

        Args:
            tokens: List of tokens

        Returns:
            List of (index, operator) tuples
        """
        operations = []
        operators = ['+', '-', '*', '/', '^']

        for i, token in enumerate(tokens):
            if token in operators:
                # Check that left operand is a number (not a parenthesis)
                left = tokens[i - 1]
                # Check that right operand is a number (not a parenthesis)
                right = tokens[i + 1]

                # Both must be numbers (not ( or ))
                if left not in ['(', ')'] and right not in ['(', ')']:
                    operations.append((i, token))

        return operations
    
    def _perform_operation(self, tokens: List[str], op_index: int, 
                          operator: str) -> List[str]:
        """
        Perform an operation and return new token list.
        
        Args:
            tokens: Current token list
            op_index: Index of the operator
            operator: The operator symbol
        
        Returns:
            New token list with operation performed
        """
        # Get operands
        left = float(tokens[op_index - 1])
        right = float(tokens[op_index + 1])
        
        # Perform operation
        if operator == '+':
            result = left + right
        elif operator == '-':
            result = left - right
        elif operator == '*':
            result = left * right
        elif operator == '/':
            if right == 0:
                raise ValueError("Division by zero")
            result = left / right
        elif operator == '^':
            result = left ** right
        else:
            raise ValueError(f"Unknown operator: {operator}")
        
        # Create new token list
        new_tokens = (
            tokens[:op_index-1] +  # Everything before left operand
            [str(result)] +         # The result
            tokens[op_index+2:]     # Everything after right operand
        )

        # Simplify any (number) patterns
        new_tokens = self._simplify_parentheses(new_tokens)

        return new_tokens

    def _simplify_parentheses(self, tokens: List[str]) -> List[str]:
        """
        Remove parentheses that contain only a single number.
        Pattern: '(', number, ')' -> number

        Args:
            tokens: List of tokens

        Returns:
            Simplified token list
        """
        changed = True
        while changed:
            changed = False
            i = 0
            while i < len(tokens) - 2:
                # Look for pattern: '(', number, ')'
                if (tokens[i] == '(' and
                    tokens[i + 2] == ')' and
                    tokens[i + 1] not in ['(', ')', '+', '-', '*', '/', '^']):
                    # Remove the parentheses, keep the number
                    tokens = tokens[:i] + [tokens[i + 1]] + tokens[i + 3:]
                    changed = True
                else:
                    i += 1
        return tokens
    
    def get_final_results(self) -> List[float]:
        """Get all possible final results"""
        return sorted(set(
            node.result for node in self.nodes.values() 
            if node.is_final
        ))
    
    def print_summary(self):
        """Print a summary of the graph"""
        print(f"Expression: {self.expression}")
        print(f"Total nodes: {len(self.nodes)}")
        print(f"Total edges: {len(self.edges)}")
        print(f"Final results: {self.get_final_results()}")
        
        # Count nodes at each depth
        final_count = sum(1 for n in self.nodes.values() if n.is_final)
        print(f"Final nodes: {final_count}")


if __name__ == "__main__":
    # Test with simple expression
    print("=" * 60)
    print("Test 1: Simple expression")
    print("=" * 60)
    graph1 = ExpressionGraph("2+3*5")
    graph1.print_summary()

    print("\n" + "=" * 60)
    print("Test 2: Expression from your example")
    print("=" * 60)
    graph2 = ExpressionGraph("3+2*4")
    graph2.print_summary()

    print("\n" + "=" * 60)
    print("Test 3: With negative number")
    print("=" * 60)
    graph3 = ExpressionGraph("-3+4*2")
    graph3.print_summary()

    print("\n" + "=" * 60)
    print("Test 4: Longer expression")
    print("=" * 60)
    graph4 = ExpressionGraph("2+3*4-5")
    graph4.print_summary()

    print("\n" + "=" * 60)
    print("Test 5: With parentheses (2+3)*5")
    print("=" * 60)
    graph5 = ExpressionGraph("(2+3)*5")
    graph5.print_summary()

    print("\n" + "=" * 60)
    print("Test 6: With parentheses 2*(3+4)")
    print("=" * 60)
    graph6 = ExpressionGraph("2*(3+4)")
    graph6.print_summary()

    print("\n" + "=" * 60)
    print("Test 7: Multiple parentheses (2+3)*(4+5)")
    print("=" * 60)
    graph7 = ExpressionGraph("(2+3)*(4+5)")
    graph7.print_summary()
