"""
Visualizer for Expression Evaluation Tree
Generates interactive visualization using Plotly
"""

from graph_builder import ExpressionGraph, Node, Edge
from typing import Dict, List, Tuple
import plotly.graph_objects as go


class TreeVisualizer:
    """Creates interactive tree visualization"""
    
    def __init__(self, graph: ExpressionGraph):
        self.graph = graph
        self.tree_data = None
    
    def _build_tree_structure(self) -> Dict:
        """
        Build hierarchical tree structure from graph.
        Uses BFS to organize nodes by levels.
        """
        # Start from root
        root_node = self.graph.nodes[self.graph.root_id]
        
        # Build tree recursively
        tree = self._node_to_tree(root_node)
        
        return tree
    
    def _node_to_tree(self, node: Node) -> Dict:
        """
        Convert a node and its children to tree structure.

        Args:
            node: Current node

        Returns:
            Dict with node data and children
        """
        # Find all edges from this node
        children_edges = [e for e in self.graph.edges if e.from_node_id == node.id]

        # Build node data
        node_data = {
            "name": node.expression,
            "id": node.id,
            "is_final": node.is_final,
            "result": node.result if node.is_final else None,
            "cumulative_reward": node.cumulative_reward,
            "children": []
        }

        # Recursively build children
        for edge in children_edges:
            child_node = self.graph.nodes[edge.to_node_id]
            child_tree = self._node_to_tree(child_node)

            # Add edge information with reward (operator, position)
            child_tree["edge_label"] = f"'{edge.operator}',{edge.operation_index}"
            child_tree["edge_reward"] = edge.reward

            node_data["children"].append(child_tree)

        return node_data
    
    def _calculate_positions(self, tree_data: Dict, depth: int = 0,
                               pos: Dict = None, x_offset: List = None,
                               parent_pos: Tuple = None) -> Tuple[Dict, List]:
        """
        Calculate x, y positions for each node in the tree.
        Uses a simple algorithm to space nodes horizontally at each level.

        Returns:
            Tuple of (positions dict, edges list)
        """
        if pos is None:
            pos = {}
        if x_offset is None:
            x_offset = [0]  # Mutable to track horizontal position

        edges = []

        # Calculate position for current node
        node_id = tree_data["id"]

        # If leaf node, assign next x position
        if not tree_data["children"]:
            x = x_offset[0]
            x_offset[0] += 1
        else:
            # Process children first
            child_positions = []
            for child in tree_data["children"]:
                child_edges = self._calculate_positions(
                    child, depth + 1, pos, x_offset, None
                )[1]
                edges.extend(child_edges)
                child_positions.append(pos[child["id"]][0])

            # Parent x is average of children x positions
            x = sum(child_positions) / len(child_positions)

        y = -depth  # Negative so tree grows downward
        pos[node_id] = (x, y)

        # Create edges to children
        for child in tree_data["children"]:
            edges.append({
                "from": node_id,
                "to": child["id"],
                "label": child.get("edge_label", ""),
                "reward": child.get("edge_reward", 0)
            })

        return pos, edges

    def generate_visualization(self, output_file: str = "expression_tree.html"):
        """
        Generate interactive Plotly visualization.

        Args:
            output_file: Path to save HTML file
        """
        # Build tree structure
        tree_data = self._build_tree_structure()

        # Calculate positions
        positions, edges = self._calculate_positions(tree_data)

        # Flatten tree to get all nodes
        all_nodes = self._flatten_tree(tree_data)

        # Create figure
        fig = go.Figure()

        # Add edges (lines connecting nodes)
        for edge in edges:
            from_pos = positions[edge["from"]]
            to_pos = positions[edge["to"]]

            # Color edge based on reward
            reward = edge.get("reward", 0)
            if reward > 0:
                edge_color = '#52c41a'  # Green for correct action
            else:
                edge_color = '#ff4d4f'  # Red for wrong action

            # Add edge line
            fig.add_trace(go.Scatter(
                x=[from_pos[0], to_pos[0]],
                y=[from_pos[1], to_pos[1]],
                mode='lines',
                line=dict(color=edge_color, width=3),
                hoverinfo='skip',
                showlegend=False
            ))

            # Add edge label with reward
            mid_x = (from_pos[0] + to_pos[0]) / 2
            mid_y = (from_pos[1] + to_pos[1]) / 2

            # Format reward with sign
            reward_str = f"+{reward}" if reward > 0 else str(reward)
            reward_color = '#52c41a' if reward > 0 else '#ff4d4f'

            if edge["label"]:
                fig.add_annotation(
                    x=mid_x,
                    y=mid_y,
                    text=f"{edge['label']}<br><b style='color:{reward_color}'>[{reward_str}]</b>",
                    showarrow=False,
                    font=dict(size=11, color='#333'),
                    bgcolor='#fffbe6' if reward > 0 else '#fff1f0',
                    bordercolor=reward_color,
                    borderwidth=2,
                    borderpad=4
                )

        # Separate nodes into intermediate and final
        intermediate_nodes = [n for n in all_nodes if not n["is_final"]]
        final_nodes = [n for n in all_nodes if n["is_final"]]

        # Add intermediate nodes (blue)
        if intermediate_nodes:
            fig.add_trace(go.Scatter(
                x=[positions[n["id"]][0] for n in intermediate_nodes],
                y=[positions[n["id"]][1] for n in intermediate_nodes],
                mode='markers+text',
                marker=dict(
                    size=20,
                    color='#4a90e2',
                    line=dict(color='#2c5aa0', width=2)
                ),
                text=[n["name"] for n in intermediate_nodes],
                textposition='top center',
                textfont=dict(size=12),
                hoverinfo='text',
                hovertext=[f"Expression: {n['name']}" for n in intermediate_nodes],
                name='Intermediate Node',
                showlegend=True
            ))

        # Add final nodes (green)
        if final_nodes:
            # Create labels with cumulative reward
            def format_final_label(n):
                reward = n.get('cumulative_reward', 0)
                reward_str = f"+{reward}" if reward > 0 else str(reward)
                return f"{n['name']}<br><b>Result: {n['result']}</b><br><b>Σ Reward: {reward_str}</b>"

            def format_hover(n):
                reward = n.get('cumulative_reward', 0)
                reward_str = f"+{reward}" if reward > 0 else str(reward)
                return f"Expression: {n['name']}\nResult: {n['result']}\nTotal Reward: {reward_str}"

            fig.add_trace(go.Scatter(
                x=[positions[n["id"]][0] for n in final_nodes],
                y=[positions[n["id"]][1] for n in final_nodes],
                mode='markers+text',
                marker=dict(
                    size=20,
                    color='#52c41a',
                    line=dict(color='#389e0d', width=2)
                ),
                text=[format_final_label(n) for n in final_nodes],
                textposition='top center',
                textfont=dict(size=12),
                hoverinfo='text',
                hovertext=[format_hover(n) for n in final_nodes],
                name='Final Result',
                showlegend=True
            ))

        # Update layout
        fig.update_layout(
            title=dict(
                text=f"Expression Evaluation Tree: {self.graph.expression}<br>"
                     f"<sup>Total Nodes: {len(self.graph.nodes)} | "
                     f"Final Results: {', '.join(map(str, self.graph.get_final_results()))}</sup>",
                x=0.5,
                font=dict(size=18)
            ),
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(255,255,255,0.8)'
            ),
            hovermode='closest',
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                title=''
            ),
            yaxis=dict(
                showgrid=False,
                zeroline=False,
                showticklabels=False,
                title=''
            ),
            plot_bgcolor='white',
            paper_bgcolor='#f5f5f5',
            margin=dict(l=40, r=40, t=80, b=40)
        )

        # Save to HTML
        fig.write_html(output_file)
        print(f"Visualization saved to: {output_file}")
        return output_file

    def _flatten_tree(self, tree_data: Dict) -> List[Dict]:
        """Flatten tree structure into a list of nodes."""
        nodes = [tree_data]
        for child in tree_data.get("children", []):
            nodes.extend(self._flatten_tree(child))
        return nodes

    # Keep generate_html as an alias for backward compatibility
    def generate_html(self, output_file: str = "expression_tree.html"):
        """Alias for generate_visualization for backward compatibility."""
        return self.generate_visualization(output_file)


if __name__ == "__main__":
    # Test visualization
    print("Creating visualization for: 3+2*4")
    graph = ExpressionGraph("3+2*4")
    visualizer = TreeVisualizer(graph)
    visualizer.generate_html("test_tree.html")
    
    print("\nCreating visualization for: 2+3*5")
    graph2 = ExpressionGraph("2+3*5")
    visualizer2 = TreeVisualizer(graph2)
    visualizer2.generate_html("test_tree2.html")
