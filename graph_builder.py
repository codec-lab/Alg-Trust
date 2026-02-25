"""
Graph Builder for Expression Evaluation Tree
Generates all possible ways to evaluate an arithmetic expression
"""

from tokenizer import tokenize, validate_tokens, OPEN_BRACKETS, CLOSE_BRACKETS, BRACKET_PAIRS
from typing import List, Tuple, Dict
import uuid


class Node:
    """Represents a state in the expression evaluation"""

    def __init__(self, tokens: List[str], parent_id: str = None):
        self.id = str(uuid.uuid4())[:8]  # Short unique ID
        self.tokens = tokens
        self.expression = ''.join(tokens)
        self.is_final = len(tokens) == 1
        self.result = float(tokens[0]) if self.is_final else None
        self.parent_id = parent_id

    def __repr__(self):
        return f"Node({self.expression}, final={self.is_final})"


class Edge:
    """Represents an operation performed between two nodes"""

    def __init__(self, from_node_id: str, to_node_id: str,
                 operation_index: int, operator: str):
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.operation_index = operation_index
        self.operator = operator
        self.description = f"Performed '{operator}' at position {operation_index}"

    def __repr__(self):
        return f"Edge({self.operation_index}, '{self.operator}')"


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

        # Create root node
        root = Node(tokens)
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

            # For each available operation, create a new branch
            for op_index, operator in available_ops:
                # Perform the operation
                new_tokens = self._perform_operation(
                    current_node.tokens, op_index, operator
                )

                # Create new node
                new_node = Node(new_tokens, parent_id=current_node.id)
                self.nodes[new_node.id] = new_node

                # Create edge
                edge = Edge(current_node.id, new_node.id, op_index, operator)
                self.edges.append(edge)

                # Add to queue for further exploration
                queue.append(new_node)
    
    def _find_available_operations(self, tokens: List[str]) -> List[Tuple[int, str]]:
        """
        Find all operator positions that can be performed.
        An operator is available only if both adjacent tokens are numbers
        (not brackets).

        Args:
            tokens: List of tokens

        Returns:
            List of (index, operator) tuples
        """
        operations = []
        operators = ['+', '-', '*', '/', '^']
        all_brackets = OPEN_BRACKETS + CLOSE_BRACKETS

        for i, token in enumerate(tokens):
            if token in operators:
                # Check that left operand is a number (not a bracket)
                left = tokens[i - 1]
                # Check that right operand is a number (not a bracket)
                right = tokens[i + 1]

                # Both must be numbers (not any bracket type)
                if left not in all_brackets and right not in all_brackets:
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

        # Simplify any bracket(number) patterns like (5), {5}, [5]
        new_tokens = self._simplify_brackets(new_tokens)

        return new_tokens

    def _simplify_brackets(self, tokens: List[str]) -> List[str]:
        """
        Remove brackets that contain only a single number.
        Pattern: open_bracket, number, matching_close_bracket -> number
        Works for all bracket types: (), {}, []

        Args:
            tokens: List of tokens

        Returns:
            Simplified token list
        """
        all_brackets = OPEN_BRACKETS + CLOSE_BRACKETS
        operators = ['+', '-', '*', '/', '^']

        changed = True
        while changed:
            changed = False
            i = 0
            while i < len(tokens) - 2:
                # Look for pattern: open_bracket, number, matching_close_bracket
                if (tokens[i] in OPEN_BRACKETS and
                    tokens[i + 1] not in all_brackets + operators and
                    tokens[i + 2] == BRACKET_PAIRS[tokens[i]]):
                    # Remove the brackets, keep the number
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

    print("\n" + "=" * 60)
    print("Test 8: Curly braces {2+3}*5")
    print("=" * 60)
    graph8 = ExpressionGraph("{2+3}*5")
    graph8.print_summary()

    print("\n" + "=" * 60)
    print("Test 9: Square brackets [2+3]*5")
    print("=" * 60)
    graph9 = ExpressionGraph("[2+3]*5")
    graph9.print_summary()

    print("\n" + "=" * 60)
    print("Test 10: Mixed brackets {[2+3]}*5")
    print("=" * 60)
    graph10 = ExpressionGraph("{[2+3]}*5")
    graph10.print_summary()

    print("\n" + "=" * 60)
    print("Test 11: Nested brackets 2+{3*[1+2]}")
    print("=" * 60)
    graph11 = ExpressionGraph("2+{3*[1+2]}")
    graph11.print_summary()
