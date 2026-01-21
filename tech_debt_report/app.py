Here is the updated script. I have added a visualize_debt_clusters function using matplotlib.
The Problem with Graph Visualization: If you try to plot an entire codebase, you get a "hairball"—a messy black blob that is impossible to read.
The Solution: This script uses Smart Filtering. It doesn't plot the whole code; it extracts only the "High Debt" clusters (the Magic Values and God Objects and the files that touch them) and plots those subgraphs.
The Visual Codebase Analyzer
New Prerequisites:
pip install networkx matplotlib

The Script (code_debt_visualizer.py):
import ast
import os
import networkx as nx
import matplotlib.pyplot as plt
from collections import defaultdict

# --- 1. THE PARSER (Same as before) ---
class CodeGraphBuilder(ast.NodeVisitor):
    def __init__(self):
        self.graph = nx.DiGraph()
        self.current_file = None
        self.current_scope = None 
        self.literals = defaultdict(int)

    def add_node(self, name, node_type, **attrs):
        self.graph.add_node(name, type=node_type, **attrs)

    def add_edge(self, source, target, relation):
        self.graph.add_edge(source, target, relation=relation)

    def process_directory(self, root_dir):
        print(f"Scanning {root_dir}...")
        for dirpath, _, filenames in os.walk(root_dir):
            for filename in filenames:
                if filename.endswith(".py"):
                    self.process_file(os.path.join(dirpath, filename))

    def process_file(self, filepath):
        self.current_file = filepath
        self.current_scope = filepath
        self.add_node(filepath, "File")
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=filepath)
            self.visit(tree)
        except Exception as e:
            print(f"Skipping {filepath}: {e}")

    def visit_ClassDef(self, node):
        class_name = f"{self.current_file}::{node.name}"
        self.add_node(class_name, "Class", name=node.name)
        self.add_edge(self.current_scope, class_name, "defines")
        prev = self.current_scope
        self.current_scope = class_name
        self.generic_visit(node)
        self.current_scope = prev

    def visit_FunctionDef(self, node):
        func_name = f"{self.current_file}::{node.name}"
        self.add_node(func_name, "Function", name=node.name)
        self.add_edge(self.current_scope, func_name, "defines")
        prev = self.current_scope
        self.current_scope = func_name
        self.generic_visit(node)
        self.current_scope = prev

    def visit_Constant(self, node):
        if isinstance(node.value, str) and len(node.value) > 50: return 
        val_str = str(node.value)
        if val_str in ['0', '1', '-1', '', 'True', 'False', 'None']: return

        val_type = type(node.value).__name__
        # Label formatting: Truncate long strings for the graph label
        label = val_str if len(val_str) < 15 else val_str[:12] + "..."
        literal_id = f"LITERAL:{val_type}:{val_str}"
        
        if not self.graph.has_node(literal_id):
            self.add_node(literal_id, "Literal", value=val_str, label=label)
        
        self.add_edge(self.current_scope, literal_id, "uses")
        self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.add_edge(self.current_file, alias.name, "imports")
    
    def visit_ImportFrom(self, node):
        if node.module:
            self.add_edge(self.current_file, node.module, "imports")

# --- 2. THE VISUALIZER ---

def visualize_debt_clusters(builder):
    g = builder.graph
    print("Generating visualization for trouble spots...")
    
    # FILTER 1: Find Magic Values (Literals with > 2 incoming edges)
    magic_nodes = [n for n, d in g.nodes(data=True) 
                   if d.get('type') == 'Literal' and g.in_degree(n) > 2]

    # FILTER 2: Find God Objects (Files/Classes with degree > 10)
    # Adjust threshold based on your codebase size
    god_nodes = [n for n, d in g.nodes(data=True) 
                 if d.get('type') in ['File', 'Class'] and g.degree(n) > 10]

    trouble_nodes = set(magic_nodes + god_nodes)
    
    if not trouble_nodes:
        print("No significant trouble spots found to visualize.")
        return

    # Create a subgraph of ONLY trouble nodes and their immediate neighbors
    # This prevents the "Hairball" effect
    nodes_to_draw = set(trouble_nodes)
    for node in trouble_nodes:
        nodes_to_draw.update(g.predecessors(node)) # Who uses the debt?
        nodes_to_draw.update(g.successors(node))   # What does the debt use?
    
    subgraph = g.subgraph(nodes_to_draw)
    
    # --- LAYOUT & STYLING ---
    plt.figure(figsize=(15, 10))
    pos = nx.spring_layout(subgraph, k=0.5, iterations=50) # k regulates distance

    # Color Map
    color_map = []
    size_map = []
    labels = {}
    
    for node in subgraph.nodes():
        node_type = subgraph.nodes[node].get('type', 'Unknown')
        
        # LABELS: Only label the interesting nodes to reduce clutter
        if node in trouble_nodes:
            # Use the 'label' attr for literals, or the node name (filename) for others
            if node_type == 'Literal':
                labels[node] = subgraph.nodes[node].get('label')
            else:
                # Truncate file paths for readability
                labels[node] = node.split(os.sep)[-1]

        # COLORS & SIZES
        if node in magic_nodes:
            color_map.append('#ff4d4d') # RED for Magic Values
            size_map.append(1500)
        elif node in god_nodes:
            color_map.append('#ff9f43') # ORANGE for God Objects
            size_map.append(2000)
        elif node_type == 'File':
            color_map.append('#54a0ff') # BLUE for Files
            size_map.append(300)
        elif node_type == 'Function':
            color_map.append('#1dd1a1') # GREEN for Functions
            size_map.append(200)
        else:
            color_map.append('#c8d6e5') # GREY for others
            size_map.append(100)

    # DRAW
    nx.draw_networkx_nodes(subgraph, pos, node_color=color_map, node_size=size_map, alpha=0.9)
    nx.draw_networkx_edges(subgraph, pos, edge_color='#576574', arrows=True, alpha=0.5)
    nx.draw_networkx_labels(subgraph, pos, labels=labels, font_size=8, font_weight="bold")

    # Legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#ff4d4d', markersize=10, label='Magic Value (Start here!)'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#ff9f43', markersize=10, label='God Object (Complex)'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#54a0ff', markersize=10, label='File'),
        Line2D([0], [0], marker='o', color='w', markerfacecolor='#1dd1a1', markersize=10, label='Function'),
    ]
    plt.legend(handles=legend_elements, loc='upper right')
    
    plt.title("Technical Debt Hotspots: Magic Values & Highly Coupled Objects")
    plt.axis('off')
    plt.tight_layout()
    plt.show()

# --- MAIN ---
if __name__ == "__main__":
    # CHANGE THIS to your codebase directory
    target_directory = "." 
    
    builder = CodeGraphBuilder()
    builder.process_directory(target_directory)
    
    # Run the text report (optional, from previous step)
    # generate_tech_debt_report(builder) 
    
    # Run the visualization
    visualize_debt_clusters(builder)

How to interpret the visual Map
When the window pops up, you will see clusters. Look for the Hub and Spoke patterns:
 * Red Dots (Magic Values):
   * You will see a big Red Dot (e.g., labeled "admin" or 8080) in the center.
   * Surrounding it will be many small Green or Blue dots (Functions/Files) pointing arrows at it.
   * Action: This visually proves that "admin" is hardcoded in 15 different places. Refactor this to a constant immediately.
 * Orange Dots (God Objects):
   * You will see a large Orange Dot (e.g., utils.py or DataManager).
   * It will look like a "star," connected to almost everything else in the cluster.
   * Action: This file is doing too much. Identify the clusters of nodes connected to it and see if you can split them into utils_date.py, utils_string.py, etc.
Tweaking the thresholds
Inside visualize_debt_clusters, look for these lines:
 * if g.in_degree(n) > 2: Change 2 to 5 if you only want to see severe repetition.
 * if g.degree(n) > 10: Change 10 to 20 if you have a massive codebase and the graph is still too crowded.
