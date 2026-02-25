"""
Expression Evaluation Tree Generator (Version 2)
Handles brackets with distribution approach

Two approaches when encountering brackets:
1. Distribute: blindly distribute the bracket (a+b)*c -> a*c + b*c
2. Evaluate Inside: evaluate what's inside the bracket first (original)
"""

from graph_builder2 import ExpressionGraph2
from visualizer_vue import VueTreeVisualizer
import sys


def main():
    """Main function to generate expression tree with distribution."""

    print("=" * 70)
    print("EXPRESSION EVALUATION TREE GENERATOR (v2 - BODMAS Mistakes)")
    print("=" * 70)
    print()
    print("This tool explores ALL possible evaluation paths, including mistakes:")
    print("  [D]    DISTRIBUTE:    (a+b)*c -> (a*c + b*c)  [correct distribution]")
    print("  [DROP] DROP BRACKETS: (a+b)*c -> a+b*c        [ignores brackets]")
    print("  [E]    EVALUATE:      Compute any operation   [in any order]")
    print()

    # Get expression from user or command line
    if len(sys.argv) > 1:
        expression = sys.argv[1]
    else:
        expression = input("Enter an arithmetic expression (e.g., '(2+3)*5'): ").strip()

    if not expression:
        print("Error: No expression provided")
        return

    # Default node limit (can be overridden with second argument)
    max_nodes = 500
    if len(sys.argv) > 2:
        try:
            max_nodes = int(sys.argv[2])
        except:
            pass

    try:
        # Build the graph
        print(f"\nBuilding evaluation tree for: {expression}")
        print(f"(Node limit: {max_nodes})")
        print("-" * 70)

        graph = ExpressionGraph2(expression, max_nodes=max_nodes)

        # Print summary
        print(f"[OK] Expression parsed successfully")
        print(f"[OK] Total nodes: {len(graph.nodes)}")
        print(f"[OK] Total edges: {len(graph.edges)}")
        if graph.truncated:
            print(f"[!]  Graph TRUNCATED at {max_nodes} nodes (use higher limit to see more)")

        # Count edge types
        dist_count = sum(1 for e in graph.edges if e.action_type == 'distribute')
        drop_count = sum(1 for e in graph.edges if e.action_type == 'drop_brackets')
        eval_count = sum(1 for e in graph.edges if e.action_type == 'evaluate')
        print(f"[OK] Distribute: {dist_count}")
        print(f"[OK] Drop brackets: {drop_count}")
        print(f"[OK] Evaluate: {eval_count}")

        print(f"[OK] Possible final results: {graph.get_final_results()}")

        final_count = sum(1 for n in graph.nodes.values() if n.is_final)
        print(f"[OK] Number of different evaluation paths: {final_count}")

        # Note about graph size
        if graph.truncated:
            print(f"\n[NOTE] Graph was truncated. Increase limit with: python main2.py '{expression}' 500")

        # Generate visualization
        print("\n" + "-" * 70)
        print("Generating interactive Vue visualization...")

        visualizer = VueTreeVisualizer(graph)

        # Sanitize filename
        sanitized = expression.replace('+', 'plus')
        sanitized = sanitized.replace('-', 'minus')
        sanitized = sanitized.replace('*', 'times')
        sanitized = sanitized.replace('/', 'div')
        sanitized = sanitized.replace('^', 'pow')
        sanitized = sanitized.replace(' ', '_')
        sanitized = sanitized.replace('(', 'L')
        sanitized = sanitized.replace(')', 'R')
        sanitized = sanitized.replace('{', 'L')
        sanitized = sanitized.replace('}', 'R')
        sanitized = sanitized.replace('[', 'L')
        sanitized = sanitized.replace(']', 'R')

        output_file = f"dist_tree_{sanitized}.html"

        visualizer.generate_html(output_file)

        print(f"[OK] Visualization saved to: {output_file}")
        print(f"\nOpen '{output_file}' in your browser to view the interactive tree!")

        # Print sample paths
        print("\n" + "=" * 70)
        print("SAMPLE EVALUATION PATHS")
        print("=" * 70)

        final_nodes = [n for n in graph.nodes.values() if n.is_final]

        # Sort by result to show different outcomes
        final_nodes.sort(key=lambda n: n.result if n.result else 0)

        for i, node in enumerate(final_nodes[:5], 1):
            print(f"\nPath {i}: Result = {node.result}")
            path = trace_path(graph, node)
            for step, (expr, action) in enumerate(path, 1):
                print(f"  Step {step}: {expr}")
                if action != "Start":
                    print(f"           -> {action}")

        if len(final_nodes) > 5:
            print(f"\n... and {len(final_nodes) - 5} more paths")

    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


def trace_path(graph, final_node):
    """Trace path from root to final node."""
    path = []
    current_id = final_node.id

    while current_id != graph.root_id:
        edge = next(e for e in graph.edges if e.to_node_id == current_id)
        node = graph.nodes[current_id]

        action_desc = f"[{edge.action_type.upper()}] {edge.description}"
        path.append((node.expression, action_desc))
        current_id = edge.from_node_id

    root = graph.nodes[graph.root_id]
    path.append((root.expression, "Start"))

    return list(reversed(path))


if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("Usage: python main2.py '<expression>' [max_nodes]")
        print()
        print("Examples:")
        print("  python main2.py '(2+3)*5'           # Default limit (200 nodes)")
        print("  python main2.py '(2+3)*5' 500       # Higher limit")
        print("  python main2.py '5*(2+3)'")
        print("  python main2.py '(2-3)*4'")
        print("  python main2.py '(2+3)*(4-1)'       # Complex - will truncate")
        print("  python main2.py '(2+3)+4'           # Blind distribution example")
        print()

    main()
