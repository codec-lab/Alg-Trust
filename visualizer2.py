"""
Visualizer for Expression Evaluation Tree (Version 2)
Handles distribution vs evaluation with different edge colors
"""

from graph_builder2 import ExpressionGraph2, Node, Edge
from typing import Dict, List, Tuple
import plotly.graph_objects as go


class TreeVisualizer2:
    """Creates interactive tree visualization with distribution support."""

    def __init__(self, graph: ExpressionGraph2):
        self.graph = graph
        self.tree_data = None

    def _build_tree_structure(self) -> Dict:
        """Build hierarchical tree structure from graph."""
        root_node = self.graph.nodes[self.graph.root_id]
        tree = self._node_to_tree(root_node)
        return tree

    def _node_to_tree(self, node: Node) -> Dict:
        """Convert a node and its children to tree structure."""
        children_edges = [e for e in self.graph.edges if e.from_node_id == node.id]

        node_data = {
            "name": node.expression,
            "id": node.id,
            "is_final": node.is_final,
            "result": node.result if node.is_final else None,
            "children": []
        }

        for edge in children_edges:
            child_node = self.graph.nodes[edge.to_node_id]
            child_tree = self._node_to_tree(child_node)

            child_tree["edge_label"] = edge.description
            child_tree["edge_type"] = edge.action_type

            node_data["children"].append(child_tree)

        return node_data

    def _calculate_positions(self, tree_data: Dict, depth: int = 0,
                             pos: Dict = None, x_offset: List = None,
                             parent_pos: Tuple = None) -> Tuple[Dict, List]:
        """Calculate x, y positions for each node in the tree."""
        if pos is None:
            pos = {}
        if x_offset is None:
            x_offset = [0]

        edges = []
        node_id = tree_data["id"]

        if not tree_data["children"]:
            x = x_offset[0]
            x_offset[0] += 1
        else:
            child_positions = []
            for child in tree_data["children"]:
                child_edges = self._calculate_positions(
                    child, depth + 1, pos, x_offset, None
                )[1]
                edges.extend(child_edges)
                child_positions.append(pos[child["id"]][0])

            x = sum(child_positions) / len(child_positions)

        y = -depth
        pos[node_id] = (x, y)

        for child in tree_data["children"]:
            edges.append({
                "from": node_id,
                "to": child["id"],
                "label": child.get("edge_label", ""),
                "type": child.get("edge_type", "evaluate")
            })

        return pos, edges

    def generate_visualization(self, output_file: str = "expression_tree.html"):
        """Generate interactive Plotly visualization."""
        tree_data = self._build_tree_structure()
        positions, edges = self._calculate_positions(tree_data)
        all_nodes = self._flatten_tree(tree_data)

        fig = go.Figure()

        # Add edges with color coding
        for edge in edges:
            from_pos = positions[edge["from"]]
            to_pos = positions[edge["to"]]

            # Color based on action type
            edge_type = edge.get("type", "evaluate")
            if edge_type == 'distribute':
                edge_color = '#9c27b0'  # Purple for distribution
                bg_color = '#f3e5f5'
            else:
                edge_color = '#1976d2'  # Blue for evaluation
                bg_color = '#e3f2fd'

            # Add edge line
            fig.add_trace(go.Scatter(
                x=[from_pos[0], to_pos[0]],
                y=[from_pos[1], to_pos[1]],
                mode='lines',
                line=dict(color=edge_color, width=2),
                hoverinfo='skip',
                showlegend=False
            ))

            # Add edge label
            mid_x = (from_pos[0] + to_pos[0]) / 2
            mid_y = (from_pos[1] + to_pos[1]) / 2

            if edge["label"]:
                # Truncate long labels
                label = edge["label"]
                if len(label) > 30:
                    label = label[:27] + "..."

                type_prefix = "D" if edge_type == 'distribute' else "E"
                fig.add_annotation(
                    x=mid_x,
                    y=mid_y,
                    text=f"[{type_prefix}] {label}",
                    showarrow=False,
                    font=dict(size=9, color='#333'),
                    bgcolor=bg_color,
                    bordercolor=edge_color,
                    borderwidth=1,
                    borderpad=3
                )

        # Separate nodes
        intermediate_nodes = [n for n in all_nodes if not n["is_final"]]
        final_nodes = [n for n in all_nodes if n["is_final"]]

        # Add intermediate nodes
        if intermediate_nodes:
            fig.add_trace(go.Scatter(
                x=[positions[n["id"]][0] for n in intermediate_nodes],
                y=[positions[n["id"]][1] for n in intermediate_nodes],
                mode='markers+text',
                marker=dict(
                    size=15,
                    color='#4a90e2',
                    line=dict(color='#2c5aa0', width=2)
                ),
                text=[n["name"] if len(n["name"]) < 20 else n["name"][:17] + "..."
                      for n in intermediate_nodes],
                textposition='top center',
                textfont=dict(size=10),
                hoverinfo='text',
                hovertext=[f"Expression: {n['name']}" for n in intermediate_nodes],
                name='Intermediate',
                showlegend=True
            ))

        # Add final nodes
        if final_nodes:
            fig.add_trace(go.Scatter(
                x=[positions[n["id"]][0] for n in final_nodes],
                y=[positions[n["id"]][1] for n in final_nodes],
                mode='markers+text',
                marker=dict(
                    size=18,
                    color='#52c41a',
                    line=dict(color='#389e0d', width=2)
                ),
                text=[f"{n['name']}<br><b>= {n['result']}</b>" for n in final_nodes],
                textposition='top center',
                textfont=dict(size=10),
                hoverinfo='text',
                hovertext=[f"Result: {n['result']}" for n in final_nodes],
                name='Final Result',
                showlegend=True
            ))

        # Add legend for edge types
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='lines',
            line=dict(color='#9c27b0', width=3),
            name='[D] Distribute'
        ))
        fig.add_trace(go.Scatter(
            x=[None], y=[None],
            mode='lines',
            line=dict(color='#1976d2', width=3),
            name='[E] Evaluate'
        ))

        # Update layout
        truncated_text = " [TRUNCATED]" if getattr(self.graph, 'truncated', False) else ""
        fig.update_layout(
            title=dict(
                text=f"Expression Tree (Distribution): {self.graph.expression}{truncated_text}<br>"
                     f"<sup>Nodes: {len(self.graph.nodes)} | "
                     f"Results: {len(self.graph.get_final_results())}</sup>",
                x=0.5,
                font=dict(size=16)
            ),
            showlegend=True,
            legend=dict(
                yanchor="top",
                y=0.99,
                xanchor="left",
                x=0.01,
                bgcolor='rgba(255,255,255,0.9)'
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
            paper_bgcolor='#fafafa',
            margin=dict(l=40, r=40, t=80, b=40)
        )

        fig.write_html(output_file)
        print(f"Visualization saved to: {output_file}")
        return output_file

    def _flatten_tree(self, tree_data: Dict) -> List[Dict]:
        """Flatten tree structure into a list of nodes."""
        nodes = [tree_data]
        for child in tree_data.get("children", []):
            nodes.extend(self._flatten_tree(child))
        return nodes

    def generate_html(self, output_file: str = "expression_tree.html"):
        """Alias for generate_visualization."""
        return self.generate_visualization(output_file)


if __name__ == "__main__":
    print("Creating visualization for: (2+3)*5")
    graph = ExpressionGraph2("(2+3)*5")
    visualizer = TreeVisualizer2(graph)
    visualizer.generate_html("test_dist_tree.html")

    print("\nCreating visualization for: (2+3)+4")
    graph2 = ExpressionGraph2("(2+3)+4")
    visualizer2 = TreeVisualizer2(graph2)
    visualizer2.generate_html("test_dist_tree2.html")
