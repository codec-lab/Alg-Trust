"""
Expression Evaluation Tree Generator
Main entry point for generating all possible evaluation paths
"""

from graph_builder import ExpressionGraph
from visualizer import TreeVisualizer
import sys


def main():
    """Main function to generate expression tree"""
    
    print("=" * 70)
    print("EXPRESSION EVALUATION TREE GENERATOR")
    print("=" * 70)
    print()
    print("This tool generates all possible ways to evaluate an expression,")
    print("ignoring BODMAS/PEMDAS rules to explore every evaluation order.")
    print()
    
    # Get expression from user or command line
    if len(sys.argv) > 1:
        expression = sys.argv[1]
    else:
        expression = input("Enter an arithmetic expression (e.g., '2+3*5'): ").strip()
    
    if not expression:
        print("Error: No expression provided")
        return
    
    try:
        # Build the graph
        print(f"\nBuilding evaluation tree for: {expression}")
        print("-" * 70)
        
        graph = ExpressionGraph(expression)
        
        # Print summary
        print(f"[OK] Expression parsed successfully")
        print(f"[OK] Total nodes: {len(graph.nodes)}")
        print(f"[OK] Total edges: {len(graph.edges)}")
        print(f"[OK] Possible final results: {graph.get_final_results()}")

        final_count = sum(1 for n in graph.nodes.values() if n.is_final)
        print(f"[OK] Number of different evaluation paths: {final_count}")
        
        # Generate visualization
        print("\n" + "-" * 70)
        print("Generating interactive visualization...")
        
        visualizer = TreeVisualizer(graph)
        
        # Sanitize filename - replace operators with words
        sanitized = expression.replace('+', 'plus')
        sanitized = sanitized.replace('-', 'minus')
        sanitized = sanitized.replace('*', 'times')
        sanitized = sanitized.replace('/', 'div')
        sanitized = sanitized.replace('^', 'pow')
        sanitized = sanitized.replace(' ', '_')
        
        output_file = f"expression_tree_{sanitized}.html"
        
        visualizer.generate_html(output_file)
        
        print(f"[OK] Visualization saved to: {output_file}")
        print(f"\nOpen '{output_file}' in your browser to view the interactive tree!")
        
        # Print some example paths
        print("\n" + "=" * 70)
        print("SAMPLE EVALUATION PATHS")
        print("=" * 70)
        
        final_nodes = [n for n in graph.nodes.values() if n.is_final]
        
        for i, node in enumerate(final_nodes[:3], 1):  # Show first 3 paths
            print(f"\nPath {i}: Result = {node.result}")
            path = trace_path(graph, node)
            for step, (expr, op) in enumerate(path, 1):
                print(f"  Step {step}: {expr} -> {op}")
        
        if len(final_nodes) > 3:
            print(f"\n... and {len(final_nodes) - 3} more paths")
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()


def trace_path(graph: ExpressionGraph, final_node):
    """Trace path from root to final node"""
    path = []
    current_id = final_node.id
    
    while current_id != graph.root_id:
        # Find edge leading to this node
        edge = next(e for e in graph.edges if e.to_node_id == current_id)
        node = graph.nodes[current_id]
        
        path.append((node.expression, edge.description))
        current_id = edge.from_node_id
    
    # Add root
    root = graph.nodes[graph.root_id]
    path.append((root.expression, "Start"))
    
    return list(reversed(path))


if __name__ == "__main__":
    # Example usage
    if len(sys.argv) == 1:
        print("Example expressions to try:")
        print("  python main.py '2+3*5'")
        print("  python main.py '3+2*4'")
        print("  python main.py '-3+4*2'")
        print("  python main.py '10/2^3'")
        print()
    
    main()