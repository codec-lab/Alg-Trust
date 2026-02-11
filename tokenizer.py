"""
Tokenizer for arithmetic expressions
Supports: +, -, *, /, ^ operators, negative numbers, and parentheses
"""

import re


def tokenize(expression: str) -> list:
    """
    Tokenize an arithmetic expression into a list of tokens.
    
    Args:
        expression: String like "2+3*5" or "-3+4*2"
    
    Returns:
        List of tokens: ["2", "+", "3", "*", "5"] or ["-3", "+", "4", "*", "2"]
    
    Examples:
        >>> tokenize("2+3*5")
        ['2', '+', '3', '*', '5']
        >>> tokenize("-3+4*2")
        ['-3', '+', '4', '*', '2']
        >>> tokenize("10/2^3")
        ['10', '/', '2', '^', '3']
    """
    # Remove all whitespace
    expression = expression.replace(" ", "")
    
    tokens = []
    i = 0
    
    while i < len(expression):
        # Check if current character is a parenthesis
        if expression[i] in ['(', ')']:
            tokens.append(expression[i])
            i += 1

        # Check if current character is an operator
        elif expression[i] in ['+', '*', '/', '^']:
            tokens.append(expression[i])
            i += 1

        # Handle minus: could be subtraction or negative number
        elif expression[i] == '-':
            # It's a negative number if:
            # 1. It's at the start of expression, OR
            # 2. Previous token is an operator, OR
            # 3. Previous token is an opening parenthesis
            if i == 0 or (tokens and tokens[-1] in ['+', '-', '*', '/', '^', '(']):
                # It's a negative number - read the full number
                j = i + 1
                while j < len(expression) and (expression[j].isdigit() or expression[j] == '.'):
                    j += 1
                tokens.append(expression[i:j])
                i = j
            else:
                # It's a subtraction operator
                tokens.append('-')
                i += 1
        
        # Handle numbers (including decimals)
        elif expression[i].isdigit() or expression[i] == '.':
            j = i
            while j < len(expression) and (expression[j].isdigit() or expression[j] == '.'):
                j += 1
            tokens.append(expression[i:j])
            i = j
        
        else:
            raise ValueError(f"Invalid character in expression: {expression[i]}")
    
    return tokens


def validate_tokens(tokens: list) -> bool:
    """
    Validate that tokens form a valid expression.

    Args:
        tokens: List of tokens

    Returns:
        True if valid, raises ValueError if invalid
    """
    if not tokens:
        raise ValueError("Empty token list")

    operators = ['+', '-', '*', '/', '^']
    paren_depth = 0

    for i, token in enumerate(tokens):
        # Check balanced parentheses
        if token == '(':
            paren_depth += 1
        elif token == ')':
            paren_depth -= 1
            if paren_depth < 0:
                raise ValueError(f"Unmatched closing parenthesis at position {i}")

        # Check for empty parentheses ()
        if token == ')' and i > 0 and tokens[i-1] == '(':
            raise ValueError(f"Empty parentheses at position {i}")

        # Check that operators have valid neighbors
        if token in operators:
            # Operator shouldn't be at start (except minus handled as negative)
            if i == 0:
                raise ValueError(f"Expression cannot start with operator: {token}")
            # Operator shouldn't be at end
            if i == len(tokens) - 1:
                raise ValueError(f"Expression cannot end with operator: {token}")
            # Previous token should be a number or )
            prev = tokens[i-1]
            if prev in operators or prev == '(':
                raise ValueError(f"Operator {token} at position {i} follows invalid token: {prev}")
            # Next token should be a number or (
            next_token = tokens[i+1]
            if next_token in operators or next_token == ')':
                raise ValueError(f"Operator {token} at position {i} precedes invalid token: {next_token}")

    if paren_depth != 0:
        raise ValueError(f"Unmatched opening parenthesis ({paren_depth} unclosed)")

    return True


if __name__ == "__main__":
    # Test cases
    test_expressions = [
        "2+3*5",
        "-3+4*2",
        "10/2^3",
        "5-3*2",
        "2*-3",
        "100+50-25*2/5",
        "(2+3)*5",
        "2*(3+4)",
        "((2+3))",
        "(2+3)*(4+5)",
        "(-3+4)*2",
    ]

    print("Testing tokenizer:")
    print("-" * 50)
    for expr in test_expressions:
        tokens = tokenize(expr)
        validate_tokens(tokens)
        print(f"{expr:20} -> {tokens}")
