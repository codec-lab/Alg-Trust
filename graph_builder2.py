"""
Graph Builder 2 for Expression Evaluation Tree
Handles brackets with multiple approaches including common BODMAS mistakes:
1. Distribution: blindly distribute brackets (correct way)
2. Evaluate Inside: evaluate inside brackets first (correct way)
3. Drop Brackets: just remove brackets without distributing (mistake)
4. Wrong Distribution: treat any operator as + when distributing (mistake)
"""

from tokenizer import tokenize, validate_tokens, OPEN_BRACKETS, CLOSE_BRACKETS, BRACKET_PAIRS
from typing import List, Tuple, Dict, Optional
import uuid
import copy


class Node:
    """Represents a state in the expression evaluation"""

    def __init__(self, tokens: List[str], parent_id: str = None):
        self.id = str(uuid.uuid4())[:8]
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
                 action_type: str, description: str):
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.action_type = action_type  # 'distribute', 'evaluate', 'compute'
        self.description = description

    def __repr__(self):
        return f"Edge({self.action_type}: {self.description})"


def find_bracket_groups(tokens: List[str], outermost_only: bool = True) -> List[Tuple[int, int]]:
    """
    Find bracket groups with their start/end indices.
    Returns list of (start_index, end_index) tuples for matching brackets.

    Args:
        tokens: List of tokens
        outermost_only: If True, only returns outermost brackets.
                        If False, returns ALL brackets including nested ones.
    """
    groups = []

    if outermost_only:
        i = 0
        while i < len(tokens):
            if tokens[i] in OPEN_BRACKETS:
                # Find matching close bracket
                depth = 1
                start = i
                j = i + 1
                while j < len(tokens) and depth > 0:
                    if tokens[j] in OPEN_BRACKETS:
                        depth += 1
                    elif tokens[j] in CLOSE_BRACKETS:
                        depth -= 1
                    j += 1
                end = j - 1
                groups.append((start, end))
                i = end + 1
            else:
                i += 1
    else:
        # Find ALL brackets including nested ones
        stack = []  # Stack of (open_bracket_char, start_index)
        for i, token in enumerate(tokens):
            if token in OPEN_BRACKETS:
                stack.append((token, i))
            elif token in CLOSE_BRACKETS:
                if stack:
                    open_bracket, start = stack.pop()
                    # Check if brackets match
                    if BRACKET_PAIRS.get(open_bracket) == token:
                        groups.append((start, i))
        # Sort by start position for consistent ordering
        groups.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    return groups


def get_bracket_content(tokens: List[str], start: int, end: int) -> List[str]:
    """Get the tokens inside a bracket group (excluding brackets)."""
    return tokens[start + 1:end]


def find_top_level_operators(tokens: List[str]) -> List[Tuple[int, str]]:
    """
    Find operators at the top level (not inside any brackets).
    Returns list of (index, operator) tuples.
    """
    operators = ['+', '-', '*', '/', '^']
    result = []
    depth = 0

    for i, token in enumerate(tokens):
        if token in OPEN_BRACKETS:
            depth += 1
        elif token in CLOSE_BRACKETS:
            depth -= 1
        elif token in operators and depth == 0:
            result.append((i, token))

    return result


def parse_bracket_terms(tokens: List[str], split_all_operators: bool = False) -> List[Tuple[str, List[str]]]:
    """
    Parse tokens inside a bracket into terms with their signs.
    Example: ['2', '+', '3', '-', '4'] -> [('+', ['2']), ('+', ['3']), ('-', ['4'])]
    Handles nested brackets as single terms.

    Args:
        tokens: List of tokens inside the bracket
        split_all_operators: If True, treat ALL operators (including *, /, ^) as term
                            separators. This simulates the WRONG way of distributing
                            where someone treats (3*2)*5 as if it were (3+2)*5.
    """
    if not tokens:
        return []

    terms = []
    current_sign = '+'
    current_term = []
    depth = 0

    # Which operators split terms
    if split_all_operators:
        split_ops = ['+', '-', '*', '/', '^']
    else:
        split_ops = ['+', '-']

    i = 0
    while i < len(tokens):
        token = tokens[i]

        if token in OPEN_BRACKETS:
            depth += 1
            current_term.append(token)
        elif token in CLOSE_BRACKETS:
            depth -= 1
            current_term.append(token)
        elif token in split_ops and depth == 0 and current_term:
            # End of current term
            terms.append((current_sign, current_term))
            # For wrong distribution, always use '+' as the connector
            if split_all_operators:
                current_sign = '+'
            else:
                current_sign = token
            current_term = []
        elif token in ['*', '/', '^'] and depth == 0 and not split_all_operators:
            # These bind tighter, keep in current term (only in correct mode)
            current_term.append(token)
        else:
            current_term.append(token)

        i += 1

    # Don't forget the last term
    if current_term:
        terms.append((current_sign, current_term))

    return terms


def drop_brackets(tokens: List[str], bracket_start: int, bracket_end: int) -> List[str]:
    """
    Simply remove brackets without distributing.
    This simulates the mistake of ignoring brackets entirely.

    Example: (2+3)*5 -> 2+3*5
    """
    # Get content inside brackets
    inner = tokens[bracket_start + 1:bracket_end]

    # Build new token list without the brackets
    result = tokens[:bracket_start] + inner + tokens[bracket_end + 1:]

    return result


def wrong_distribute_bracket(tokens: List[str], bracket_start: int, bracket_end: int,
                              op_side: str, op_index: int, outer_operand: List[str]) -> List[str]:
    """
    Perform WRONG distribution - treat any operator inside as addition.

    For (3*2)*5: returns (3*5+2*5) - WRONG! (treats * as +)
    For (8/2)*3: returns (8*3+2*3) - WRONG! (treats / as +)

    This simulates the mistake where someone distributes over multiplication
    as if it were addition.
    """
    inner_tokens = get_bracket_content(tokens, bracket_start, bracket_end)
    outer_operator = tokens[op_index]

    # Parse inner bracket treating ALL operators as term separators
    terms = parse_bracket_terms(inner_tokens, split_all_operators=True)

    if len(terms) <= 1:
        return None  # No wrong distribution possible with single term

    # Build distributed expression (wrongly, treating all ops as +)
    distributed_inner = []

    for i, (sign, term_tokens) in enumerate(terms):
        if i > 0:
            # Always use + between terms (the wrong part)
            distributed_inner.append('+')

        # Build: term op outer_operand OR outer_operand op term
        if op_side == 'right':
            if len(term_tokens) > 1 or (term_tokens and term_tokens[0] in OPEN_BRACKETS):
                distributed_inner.extend(['('] + term_tokens + [')'])
            else:
                distributed_inner.extend(term_tokens)
            distributed_inner.append(outer_operator)
            distributed_inner.extend(outer_operand)
        else:
            distributed_inner.extend(outer_operand)
            distributed_inner.append(outer_operator)
            if len(term_tokens) > 1 or (term_tokens and term_tokens[0] in OPEN_BRACKETS):
                distributed_inner.extend(['('] + term_tokens + [')'])
            else:
                distributed_inner.extend(term_tokens)

    # Wrap the distributed result in brackets
    distributed = ['('] + distributed_inner + [')']

    # Build final token list (same logic as correct distribution)
    if op_side == 'right':
        before = tokens[:bracket_start]
        after_operand_idx = op_index + 1
        if tokens[after_operand_idx] in OPEN_BRACKETS:
            depth = 1
            j = after_operand_idx + 1
            while j < len(tokens) and depth > 0:
                if tokens[j] in OPEN_BRACKETS:
                    depth += 1
                elif tokens[j] in CLOSE_BRACKETS:
                    depth -= 1
                j += 1
            after = tokens[j:]
        else:
            after = tokens[after_operand_idx + 1:]
        result = before + distributed + after
    else:
        before_operand_idx = op_index - 1
        if tokens[before_operand_idx] in CLOSE_BRACKETS:
            depth = 1
            j = before_operand_idx - 1
            while j >= 0 and depth > 0:
                if tokens[j] in CLOSE_BRACKETS:
                    depth += 1
                elif tokens[j] in OPEN_BRACKETS:
                    depth -= 1
                j -= 1
            before = tokens[:j + 1]
        else:
            before = tokens[:before_operand_idx]
        after = tokens[bracket_end + 1:]
        result = before + distributed + after

    return result


def distribute_bracket(tokens: List[str], bracket_start: int, bracket_end: int,
                       op_side: str, op_index: int, outer_operand: List[str]) -> List[str]:
    """
    Perform distribution on a bracket group.

    For (a + b) * c: returns (a*c + b*c)  <- wrapped in brackets
    For c * (a + b): returns (c*a + c*b)  <- wrapped in brackets
    For (a - b) * c: returns (a*c - b*c)  <- wrapped in brackets
    For (a + b) * c * d: returns (a*c + b*c) * d  <- brackets preserved for chain

    Args:
        tokens: Full token list
        bracket_start, bracket_end: Indices of bracket
        op_side: 'left' or 'right' - which side the outer operator is on
        op_index: Index of the outer operator
        outer_operand: Tokens of the operand being distributed

    Returns:
        New token list with distribution applied, or None if distribution not applicable
    """
    inner_tokens = get_bracket_content(tokens, bracket_start, bracket_end)
    outer_operator = tokens[op_index]

    # Parse inner bracket into terms
    terms = parse_bracket_terms(inner_tokens)

    # Distribution only makes sense with 2+ terms (e.g., a+b, not just a*b)
    # Single term means no + or - at top level, so nothing to distribute over
    if len(terms) <= 1:
        return None

    # Build distributed expression (the inner part that will be wrapped in brackets)
    distributed_inner = []

    for i, (sign, term_tokens) in enumerate(terms):
        if i > 0:
            # Add the sign between terms
            distributed_inner.append(sign)
        elif sign == '-':
            # First term with negative sign
            # We need to handle this - prepend negative
            if term_tokens and term_tokens[0] not in ['+', '-']:
                term_tokens = ['-'] + term_tokens

        # Build: term op outer_operand OR outer_operand op term
        if op_side == 'right':
            # (term) * outer -> term * outer
            if len(term_tokens) > 1 or (term_tokens and term_tokens[0] in OPEN_BRACKETS):
                # Wrap in brackets if complex
                distributed_inner.extend(['('] + term_tokens + [')'])
            else:
                distributed_inner.extend(term_tokens)
            distributed_inner.append(outer_operator)
            distributed_inner.extend(outer_operand)
        else:
            # outer * (term) -> outer * term
            distributed_inner.extend(outer_operand)
            distributed_inner.append(outer_operator)
            if len(term_tokens) > 1 or (term_tokens and term_tokens[0] in OPEN_BRACKETS):
                distributed_inner.extend(['('] + term_tokens + [')'])
            else:
                distributed_inner.extend(term_tokens)

    # Wrap the distributed result in brackets since it contains multiple terms
    distributed = ['('] + distributed_inner + [')']

    # Build final token list
    if op_side == 'right':
        # (bracket) op operand -> distributed
        # tokens before bracket + distributed + tokens after operand
        before = tokens[:bracket_start]
        after_operand_idx = op_index + 1
        # Find end of operand (could be a bracket group or single token)
        if tokens[after_operand_idx] in OPEN_BRACKETS:
            depth = 1
            j = after_operand_idx + 1
            while j < len(tokens) and depth > 0:
                if tokens[j] in OPEN_BRACKETS:
                    depth += 1
                elif tokens[j] in CLOSE_BRACKETS:
                    depth -= 1
                j += 1
            after = tokens[j:]
        else:
            after = tokens[after_operand_idx + 1:]

        result = before + distributed + after
    else:
        # operand op (bracket) -> distributed
        before_operand_idx = op_index - 1
        # Find start of operand
        if tokens[before_operand_idx] in CLOSE_BRACKETS:
            depth = 1
            j = before_operand_idx - 1
            while j >= 0 and depth > 0:
                if tokens[j] in CLOSE_BRACKETS:
                    depth += 1
                elif tokens[j] in OPEN_BRACKETS:
                    depth -= 1
                j -= 1
            before = tokens[:j + 1]
        else:
            before = tokens[:before_operand_idx]

        after = tokens[bracket_end + 1:]
        result = before + distributed + after

    return result


def find_distributable_brackets(tokens: List[str], include_nested: bool = True) -> List[Dict]:
    """
    Find all bracket groups that can be distributed.
    Returns list of dicts with distribution info.

    Args:
        tokens: List of tokens
        include_nested: If True, also find nested brackets (not just outermost)
    """
    distributable = []
    bracket_groups = find_bracket_groups(tokens, outermost_only=not include_nested)

    for start, end in bracket_groups:
        # Check for operator on the right
        if end + 1 < len(tokens) and tokens[end + 1] in ['+', '-', '*', '/', '^']:
            op_index = end + 1
            operator = tokens[op_index]

            # Get the operand after the operator
            if op_index + 1 < len(tokens):
                operand_start = op_index + 1
                if tokens[operand_start] in OPEN_BRACKETS:
                    # Operand is a bracket group
                    depth = 1
                    j = operand_start + 1
                    while j < len(tokens) and depth > 0:
                        if tokens[j] in OPEN_BRACKETS:
                            depth += 1
                        elif tokens[j] in CLOSE_BRACKETS:
                            depth -= 1
                        j += 1
                    operand = tokens[operand_start:j]
                else:
                    operand = [tokens[operand_start]]

                # Check if distribution is valid
                # For division: X/(a+b) can't distribute, but (a+b)/X can
                if operator == '/' and tokens[operand_start] in OPEN_BRACKETS:
                    # This is (a+b)/(c+d) - tricky, skip for now
                    pass
                else:
                    distributable.append({
                        'bracket_start': start,
                        'bracket_end': end,
                        'op_side': 'right',
                        'op_index': op_index,
                        'operator': operator,
                        'operand': operand
                    })

        # Check for operator on the left
        if start > 0 and tokens[start - 1] in ['+', '-', '*', '/', '^']:
            op_index = start - 1
            operator = tokens[op_index]

            # Get the operand before the operator
            if op_index > 0:
                operand_end = op_index - 1
                if tokens[operand_end] in CLOSE_BRACKETS:
                    # Operand is a bracket group
                    depth = 1
                    j = operand_end - 1
                    while j >= 0 and depth > 0:
                        if tokens[j] in CLOSE_BRACKETS:
                            depth += 1
                        elif tokens[j] in OPEN_BRACKETS:
                            depth -= 1
                        j -= 1
                    operand = tokens[j + 1:operand_end + 1]
                else:
                    operand = [tokens[operand_end]]

                # For division: a/(b+c) can't distribute
                if operator == '/':
                    continue

                distributable.append({
                    'bracket_start': start,
                    'bracket_end': end,
                    'op_side': 'left',
                    'op_index': op_index,
                    'operator': operator,
                    'operand': operand
                })

    return distributable


def find_evaluatable_operations(tokens: List[str]) -> List[Tuple[int, str]]:
    """
    Find operations that can be evaluated (number op number, no brackets adjacent).
    This is the original approach from graph_builder.py.
    """
    operations = []
    operators = ['+', '-', '*', '/', '^']
    all_brackets = OPEN_BRACKETS + CLOSE_BRACKETS

    for i, token in enumerate(tokens):
        if token in operators:
            left = tokens[i - 1]
            right = tokens[i + 1]
            if left not in all_brackets and right not in all_brackets:
                operations.append((i, token))

    return operations


def perform_operation(tokens: List[str], op_index: int, operator: str) -> List[str]:
    """Perform a single arithmetic operation and return new tokens."""
    left = float(tokens[op_index - 1])
    right = float(tokens[op_index + 1])

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

    # Format result nicely
    if result == int(result):
        result_str = str(int(result))
    else:
        result_str = str(result)

    new_tokens = tokens[:op_index - 1] + [result_str] + tokens[op_index + 2:]
    return simplify_brackets(new_tokens)


def simplify_brackets(tokens: List[str]) -> List[str]:
    """Remove brackets that contain only a single number."""
    all_brackets = OPEN_BRACKETS + CLOSE_BRACKETS
    operators = ['+', '-', '*', '/', '^']

    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(tokens) - 2:
            if (tokens[i] in OPEN_BRACKETS and
                tokens[i + 1] not in all_brackets + operators and
                tokens[i + 2] == BRACKET_PAIRS.get(tokens[i])):
                tokens = tokens[:i] + [tokens[i + 1]] + tokens[i + 3:]
                changed = True
            else:
                i += 1
    return tokens


def is_only_addition_bracket(tokens: List[str], start: int, end: int) -> bool:
    """Check if bracket contains only additions (no other operators)."""
    inner = get_bracket_content(tokens, start, end)
    for token in inner:
        if token in ['-', '*', '/', '^']:
            return False
        if token in OPEN_BRACKETS:
            return False  # Has nested brackets
    return True


def is_same_operator_expression(tokens: List[str]) -> Tuple[bool, Optional[str]]:
    """
    Check if the entire expression contains only one type of operator.
    Example: ['2', '+', '3', '+', '1'] -> (True, '+')
    Example: ['2', '*', '3', '*', '4'] -> (True, '*')
    Example: ['2', '+', '3', '*', '4'] -> (False, None)

    Returns (is_same_op, operator)
    """
    all_brackets = OPEN_BRACKETS + CLOSE_BRACKETS
    operators = ['+', '-', '*', '/', '^']
    found_operator = None

    for token in tokens:
        if token in all_brackets:
            return (False, None)  # Has brackets
        if token in operators:
            if found_operator is None:
                found_operator = token
            elif token != found_operator:
                return (False, None)  # Mixed operators

    return (True, found_operator) if found_operator else (False, None)


def compute_same_operator_result(tokens: List[str], operator: str) -> str:
    """
    Compute the result of a same-operator expression (left-to-right).
    """
    numbers = [float(t) for t in tokens if t != operator]

    if not numbers:
        return tokens[0] if tokens else '0'

    result = numbers[0]
    for num in numbers[1:]:
        if operator == '+':
            result += num
        elif operator == '-':
            result -= num
        elif operator == '*':
            result *= num
        elif operator == '/':
            if num == 0:
                raise ValueError("Division by zero")
            result /= num
        elif operator == '^':
            result = result ** num

    if result == int(result):
        return str(int(result))
    return str(result)


class ExpressionGraph2:
    """Builds evaluation graph with distribution and evaluate-inside branches."""

    def __init__(self, expression: str, max_nodes: int = None):
        self.expression = expression
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.root_id = None
        self.max_nodes = max_nodes
        self.truncated = False  # True if we hit the node limit
        # Track nodes that came from wrong distribution (don't wrong-distribute them again)
        self.wrong_dist_nodes = set()

        self._build_graph()

    def _build_graph(self):
        """Build the complete graph using BFS."""
        tokens = tokenize(self.expression)
        validate_tokens(tokens)

        root = Node(tokens)
        self.root_id = root.id
        self.nodes[root.id] = root

        # Track seen expressions to avoid duplicates
        self.seen_expressions = {root.expression: root.id}

        queue = [root]

        while queue:
            # Check node limit
            if self.max_nodes and len(self.nodes) >= self.max_nodes:
                self.truncated = True
                break

            current_node = queue.pop(0)

            if current_node.is_final:
                continue

            # Check if this is a same-operator expression (e.g., 2+3+4 or 2*3*4)
            # If so, just compute the result in one step
            is_same_op, operator = is_same_operator_expression(current_node.tokens)
            if is_same_op and operator:
                try:
                    result = compute_same_operator_result(current_node.tokens, operator)
                    new_tokens = [result]
                    new_expr = ''.join(new_tokens)

                    # Check if we've seen this expression before
                    if new_expr in self.seen_expressions:
                        existing_id = self.seen_expressions[new_expr]
                        desc = f"Compute all '{operator}' operations"
                        edge = Edge(current_node.id, existing_id, 'evaluate', desc)
                        self.edges.append(edge)
                    else:
                        new_node = Node(new_tokens, parent_id=current_node.id)
                        self.nodes[new_node.id] = new_node
                        self.seen_expressions[new_expr] = new_node.id

                        desc = f"Compute all '{operator}' operations"
                        edge = Edge(current_node.id, new_node.id, 'evaluate', desc)
                        self.edges.append(edge)

                        queue.append(new_node)
                    continue
                except:
                    pass  # Fall through to normal processing

            actions = self._find_all_actions(current_node.tokens)

            for action in actions:
                try:
                    new_tokens = action['result_tokens']
                    new_expr = ''.join(new_tokens)

                    # Check if we've seen this expression before
                    if new_expr in self.seen_expressions:
                        existing_id = self.seen_expressions[new_expr]
                        edge = Edge(current_node.id, existing_id,
                                   action['type'], action['description'])
                        self.edges.append(edge)
                    else:
                        new_node = Node(new_tokens, parent_id=current_node.id)
                        self.nodes[new_node.id] = new_node
                        self.seen_expressions[new_expr] = new_node.id

                        edge = Edge(current_node.id, new_node.id,
                                   action['type'], action['description'])
                        self.edges.append(edge)

                        queue.append(new_node)

                except Exception as e:
                    # Skip invalid operations
                    pass

    def _find_all_actions(self, tokens: List[str], allow_wrong_distribute: bool = True) -> List[Dict]:
        """Find all possible actions from current state."""
        actions = []
        seen_results = set()  # Avoid duplicate actions that produce same result

        def add_action(action_type: str, description: str, result_tokens: List[str]):
            """Helper to add action if result is unique."""
            result_key = ''.join(result_tokens)
            if result_key not in seen_results:
                seen_results.add(result_key)
                actions.append({
                    'type': action_type,
                    'description': description,
                    'result_tokens': result_tokens
                })

        # 1. Find distributable brackets (including nested ones)
        distributable = find_distributable_brackets(tokens, include_nested=True)
        for dist in distributable:
            inner = ''.join(get_bracket_content(tokens,
                                                dist['bracket_start'],
                                                dist['bracket_end']))
            operand_str = ''.join(dist['operand'])

            # 1a. Correct distribution (only if 2+ terms inside bracket)
            try:
                result = distribute_bracket(
                    tokens,
                    dist['bracket_start'],
                    dist['bracket_end'],
                    dist['op_side'],
                    dist['op_index'],
                    dist['operand']
                )
                if result:  # None if only single term (distribution not applicable)
                    result = simplify_brackets(result)
                    add_action('distribute',
                              f"Distribute ({inner}) {dist['operator']} {operand_str}",
                              result)
            except:
                pass

            # 1b. WRONG distribution - DISABLED for now (causes exponential growth)
            # TODO: Re-enable with proper limits if needed
            # if allow_wrong_distribute:
            #     try:
            #         result = wrong_distribute_bracket(...)
            #     except:
            #         pass

        # 2. Drop brackets (just remove them without distributing)
        all_brackets = find_bracket_groups(tokens, outermost_only=False)
        for start, end in all_brackets:
            try:
                inner = ''.join(get_bracket_content(tokens, start, end))
                result = drop_brackets(tokens, start, end)
                result = simplify_brackets(result)
                add_action('drop_brackets',
                          f"Drop brackets: ({inner})",
                          result)
            except:
                pass

        # 3. Find evaluatable operations (original approach)
        operations = find_evaluatable_operations(tokens)
        for op_index, operator in operations:
            try:
                result = perform_operation(tokens, op_index, operator)
                left = tokens[op_index - 1]
                right = tokens[op_index + 1]
                add_action('evaluate',
                          f"Compute {left} {operator} {right}",
                          result)
            except:
                pass

        return actions

    def get_final_results(self) -> List[float]:
        """Get all possible final results."""
        return sorted(set(
            node.result for node in self.nodes.values()
            if node.is_final
        ))

    def print_summary(self):
        """Print a summary of the graph."""
        print(f"Expression: {self.expression}")
        print(f"Total nodes: {len(self.nodes)}")
        print(f"Total edges: {len(self.edges)}")
        if self.truncated:
            print(f"[TRUNCATED] Graph limited to {self.max_nodes} nodes")
        print(f"Final results: {self.get_final_results()}")

        final_count = sum(1 for n in self.nodes.values() if n.is_final)
        print(f"Final nodes: {final_count}")

        # Count action types
        dist_count = sum(1 for e in self.edges if e.action_type == 'distribute')
        drop_count = sum(1 for e in self.edges if e.action_type == 'drop_brackets')
        eval_count = sum(1 for e in self.edges if e.action_type == 'evaluate')
        print(f"Distribute edges: {dist_count}")
        print(f"Drop brackets edges: {drop_count}")
        print(f"Evaluate edges: {eval_count}")


if __name__ == "__main__":
    print("=" * 60)
    print("Test 1: Simple (2+3)*5")
    print("=" * 60)
    graph1 = ExpressionGraph2("(2+3)*5")
    graph1.print_summary()

    print("\n" + "=" * 60)
    print("Test 2: 5*(2+3)")
    print("=" * 60)
    graph2 = ExpressionGraph2("5*(2+3)")
    graph2.print_summary()

    print("\n" + "=" * 60)
    print("Test 3: (2-3)*4")
    print("=" * 60)
    graph3 = ExpressionGraph2("(2-3)*4")
    graph3.print_summary()

    print("\n" + "=" * 60)
    print("Test 4: (2+3)*(4-1)")
    print("=" * 60)
    graph4 = ExpressionGraph2("(2+3)*(4-1)")
    graph4.print_summary()

    print("\n" + "=" * 60)
    print("Test 5: (2+3)+4 (blind distribution)")
    print("=" * 60)
    graph5 = ExpressionGraph2("(2+3)+4")
    graph5.print_summary()
