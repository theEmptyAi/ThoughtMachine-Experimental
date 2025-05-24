#!/usr/bin/env python3
import asyncio
import json
import uuid
import sys
import os
import argparse
import websockets
import requests
import signal
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.tree import Tree
from rich.table import Table
from rich import box
from rich.syntax import Syntax
from rich.prompt import Prompt
from rich.live import Live
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgba
import matplotlib
matplotlib.use('TkAgg')  # Use TkAgg backend for displaying plots

# Configure rich console for better output
console = Console()

@dataclass
class Config:
    """Configuration for the Thought Machine CLI client"""
    host: str = "localhost"
    port: int = 8000
    cid: str = ""
    dev_mode: bool = False
    show_dag: bool = False  # Changed to False by default
    history_size: int = 10
    debug: bool = False

class EmptyAIClient:
    """Client for interacting with the Thought Machine server"""
    
    def __init__(self, config: Config):
        self.config = config
        self.base_url = f"http://{config.host}:{config.port}"
        self.ws_url = f"ws://{config.host}:{config.port}/ws"
        self.cid = config.cid or uuid.uuid4().hex[:8]
        self.ws = None
        self.flow_data = None
        self.node_thought: dict[str, str] = {}   # ← track thought for each node
        self.message_history: List[Dict[str, Any]] = []
        self.exit_flag = asyncio.Event()
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, self._handle_exit)
        signal.signal(signal.SIGTERM, self._handle_exit)
        
        console.print(f"[bold blue]ThoughtMetachine Client v1.0[/]")
        console.print(f"[bold]Conversation ID:[/] [green]{self.cid}[/]")
        if config.dev_mode:
            console.print(f"[bold yellow]🛠️  ThoughtMetachine Dev Mode: ON[/]")
    
    def _handle_exit(self, *args):
        """Handle exit signals gracefully"""
        self.exit_flag.set()
        console.print("\n[bold red]Exiting...[/]")
        sys.exit(0)
    
    async def _connect_websocket(self):
        """Establish websocket connection to the server"""
        ws_endpoint = f"{self.ws_url}/{self.cid}"
        console.print(f"[bold yellow]Connecting to WebSocket at:[/] {ws_endpoint}")
        
        # Keep retrying with exponential backoff until we connect or exit
        delay = 1
        while not self.exit_flag.is_set():
            try:
                self.ws = await websockets.connect(
                    ws_endpoint,
                    ping_interval=20,
                    close_timeout=30,
                    open_timeout=30
                )
                console.print(f"[bold green]WebSocket connected successfully[/]")
                return True
            except Exception as e:
                console.print(f"[bold yellow]WebSocket connection failed: {e}. Retrying in {delay}s...[/]")
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)
        return False
    
    async def _send_message(self, text: str):
        """Send a message to the Thought Machine server"""
        try:
            response = requests.post(
                f"{self.base_url}/chat",
                json={"cid": self.cid, "text": text}
            )
            if response.status_code != 200:
                console.print(f"[bold red]Error:[/] Server returned {response.status_code}")
                return False
            return True
        except Exception as e:
            console.print(f"[bold red]Error sending message:[/] {e}")
            return False
    
    def _display_message(self, sender: str, text: str, message_type: str = "content"):
        """Display a message in the console with rich formatting
        
        Args:
            sender: Who sent the message ('user', 'assistant', 'system')
            text: The message content
            message_type: Type of message ('content', 'status', 'debug', 'technical')
        """
        # Add timestamp to message header
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if sender == "user":
            # Enhanced user message panel with gradient background
            from rich.style import Style
            
            panel = Panel(
                text,
                title=f"[bold]You[/] [dim]· {timestamp}[/]",
                title_align="left",
                border_style="#4f46e5", # Indigo border
                style="#818cf8 on #312e81", # Light indigo text on dark indigo background
                expand=False,
                padding=(1, 2),
                box=box.ROUNDED
            )
            console.print(panel)
        elif sender == "system":
            # System messages with different styling based on type
            if message_type == "status":
                # Use a subtle background with no border for status updates
                console.print(f"[dim slate_blue]⎯⎯ {text} ⎯⎯[/]")
            elif message_type == "technical":
                # Use a subtle technical indicator for node events, DAG info, etc.
                console.print(f"[dim steel_blue]• {text}[/]")
            elif message_type == "debug":
                # Debug info less prominent
                console.print(f"[dim grey]ℹ {text}[/]")
            else:
                # Default system messages
                console.print(f"[slate_blue]{text}[/]")
        else:  # assistant
            # Skip system messages like 'task started' in full panel format
            if text.strip() == "🚀 task started" or text.startswith("DAG visualization"):
                console.print(f"[dim slate_blue]{text}[/]")
                return
                
            # Enhanced AI message panel with better styling for content
            try:
                # Parse as markdown for better code formatting and highlights
                md_content = Markdown(text)
                
                # Create a more visually appealing panel with modern styling and gradient background
                panel = Panel(
                    md_content,
                    title=f"[bold]AI[/] [dim]· {timestamp}[/]",
                    title_align="left",
                    border_style="#059669",  # Emerald border
                    style="#34d399 on #064e3b",  # Light emerald text on dark emerald background
                    expand=False,
                    padding=(1, 2),
                    box=box.ROUNDED
                )
                # Add a subtle divider before AI messages
                console.print("", style="dim")
                console.print(panel)
                
                # Add visual separator for better readability
                if self.config.dev_mode:
                    console.print("", style="dim")
            except Exception:
                # Fallback to plain text if markdown parsing fails
                panel = Panel(
                    text,
                    title=f"[bold]AI[/] [dim]· {timestamp}[/]",
                    title_align="left",
                    border_style="#059669",  # Emerald border
                    style="#34d399 on #064e3b",  # Light emerald text on dark emerald background
                    expand=False,
                    padding=(1, 2),
                    box=box.ROUNDED
                )
                console.print(panel)
    
    def _visualize_dag(self, flow_data: Dict[str, Any]):
        """Visualize the directed acyclic graph (DAG) of the task flow"""
        if not flow_data or "nodes" not in flow_data or "start" not in flow_data:
            console.print("[yellow]No valid flow data to visualize[/]")
            return
        
        # Create a directed graph
        G = nx.DiGraph()
        
        # Add nodes and edges
        nodes = flow_data.get("nodes", {})
        start_node = flow_data.get("start")
        
        # Add all nodes first
        for node_id, node_data in nodes.items():
            thought_name = node_data.get("thought", "unknown")
            params = node_data.get("params", {})
            param_str = "\n".join(f"{k}: {v}" for k, v in params.items())
            label = f"{node_id}\n{thought_name}\n{param_str}"
            G.add_node(node_id, label=label, thought=thought_name)
        
        # Add edges
        for node_id, node_data in nodes.items():
            next_node = node_data.get("next")
            if next_node:
                G.add_edge(node_id, next_node)
        
        # Create the plot
        plt.figure(figsize=(10, 7))
        pos = nx.spring_layout(G, seed=42)  # Consistent layout
        
        # Node colors based on thoughts
        node_colors = []
        for node in G.nodes():
            thought = G.nodes[node].get("thought", "")
            if "reply" in thought:
                node_colors.append(to_rgba("green", 0.7))
            elif "dev" in thought:
                node_colors.append(to_rgba("red", 0.7))
            else:
                node_colors.append(to_rgba("blue", 0.7))
        
        # Draw the graph
        nx.draw_networkx_nodes(G, pos, node_size=2000, node_color=node_colors, alpha=0.9)
        nx.draw_networkx_edges(G, pos, edge_color="gray", width=2, arrowsize=20)
        
        # Add labels with wrapped text
        labels = {}
        for node in G.nodes():
            labels[node] = G.nodes[node].get("label", node)
        
        nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, font_weight="bold")
        
        # Highlight the start node
        if start_node in G.nodes():
            nx.draw_networkx_nodes(G, pos, nodelist=[start_node], 
                                 node_size=2200, node_color=to_rgba("orange", 0.9))
        
        plt.title("Thought Machine Task Flow (DAG)", size=16)
        plt.axis("off")
        plt.tight_layout()
        
        # Show the plot
        plt.show(block=False)
        plt.pause(0.1)  # Small pause to render the plot
    
    async def _display_debug_info(self, data: Dict[str, Any]):
        """Display debug information"""
        if not self.config.debug:
            return
            
        stage = data.get("stage")
        if stage == "plan":
            plan = data.get("plan", {})
            console.print("[bold yellow]🗺️  Plan:[/]")
            syntax = Syntax(json.dumps(plan, indent=2), "json", theme="monokai")
            console.print(syntax)
        elif stage == "execute":
            console.print("[bold yellow]🚀 Executing flow...[/]")
        elif stage == "fallback":
            console.print("[bold yellow]💬 Falling back to chat...[/]")
    
    async def _handle_websocket_messages(self):
        """Handle incoming websocket messages"""
        if not self.ws:
            return
        
        # Track if we've got the full response yet
        waiting_for_node_done = False
        current_node_id = None
            
        while not self.exit_flag.is_set():
            try:
                # Longer timeout to prevent frequent wakeups
                message = await asyncio.wait_for(self.ws.recv(), timeout=0.5)
                message_data = json.loads(message)
                topic = message_data.get("topic")
                data = message_data.get("data")
                
                # Debug logging for messages if debug mode is enabled
                if self.config.debug:
                    console.print(f"[dim]Received WebSocket message: {topic}[/]")
                
                if topic == "user":
                    # Add to history
                    self.message_history.append({"sender": "user", "text": data})
            
                elif topic == "assistant":
                    # Display AI message immediately when received
                    if data and isinstance(data, str) and data.strip():
                        # Determine if this is a system message or content
                        if data.strip() == "🚀 task started" or data.startswith("DAG visualization"):
                            self._display_message("system", data, message_type="status")
                        else:
                            self._display_message("assistant", data, message_type="content")
                        # Add to history
                        self.message_history.append({"sender": "assistant", "text": data})
            
                elif topic == "debug":
                    await self._display_debug_info(data)
                    # Store flow data for visualization if available
                    if data.get("stage") == "plan" and data.get("plan") and data["plan"].get("flow"):
                        self.flow_data = data["plan"]["flow"]
                        
                        # Only announce that DAG is available, don't show it automatically
                        if self.config.show_dag:
                            self._display_message("system", "DAG visualization available. Type /dag show to view it.", message_type="status")
                        # We'll only show DAG explicitly when requested with /dag show command
            
                elif topic == "node.start":
                    node_id = data.get("id")
                    thought   = data.get("thought")
                    # remember which thought this node is running
                    self.node_thought[node_id] = thought
                    self._display_message(
                        "system",
                        f"▶ Node {node_id}   (thought: {thought})",
                        message_type="technical"
                    )
                    
                elif topic == "node.done":
                    node_id = data.get("id")
                    out     = data.get("out", {})
                    # lookup the thought name we saved earlier
                    thought   = self.node_thought.get(node_id, "‽")

                    # trace the completion of the node with its thought
                    self._display_message(
                        "system",
                        f"✓ Node {node_id}   (thought: {thought})",
                        message_type="technical"
                    )

                    # If the node yielded its own reply we DON'T print it
                    # here; the server now sends a single 'assistant' event
                    # for that, avoiding duplicate panels.

                    # no need to duplicate the standard assistant event if desired
                    
                    if self.config.debug:
                        self._display_message("system", f"Debug - Node Output:", message_type="debug")
                        console.print(out)
                
                elif topic == "node.log":
                    node_id = data.get("id")
                    thought   = data.get("thought")
                    logs    = data.get("logs", "")
                    self._display_message(
                        "system",
                        f"📄 stdout from {thought} ({node_id}):\n{logs}",
                        message_type="debug"
                    )
                
                elif topic == "task.done":
                    self._display_message("system", "✅ Task completed", message_type="status")
            
            except asyncio.TimeoutError:
                # This is expected, allows checking the exit flag periodically
                await asyncio.sleep(0.1)
                continue
            except websockets.exceptions.ConnectionClosed:
                console.print("[bold red]WebSocket connection closed[/]")
                # keep retrying until the server comes back up or we exit
                while not self.exit_flag.is_set():
                    console.print("[bold yellow]Attempting to reconnect in 5s...[/]")
                    await asyncio.sleep(5)
                    try:
                        self.ws = await asyncio.wait_for(
                            websockets.connect(f"{self.ws_url}/{self.cid}", ping_interval=20, close_timeout=30),
                            timeout=15
                        )
                        console.print("[bold green]Reconnected successfully[/]")
                        break
                    except Exception as e:
                        console.print(f"[bold red]Reconnect failed: {e}[/]")
                continue
            except Exception as e:
                console.print(f"[bold red]Error processing message:[/] {e}")
                await asyncio.sleep(1)  # Avoid tight loop on errors
    
    async def start(self):
        """Start the client"""
        # Try to establish WebSocket connection
        if not await self._connect_websocket():
            console.print("[bold red]Failed to connect to the server. Is it running?[/]")
            return
        
        try:
            # Set up message handler in the background
            message_handler = asyncio.create_task(self._handle_websocket_messages())
            
            # Show a hint about /help command on startup
            console.print("[dim italic]Type /help to see available commands[/]")
        
            # Main input loop
            while not self.exit_flag.is_set():
                text = await asyncio.to_thread(Prompt.ask, "[bold blue]>[/] ")
                # Handle client commands
                if text.strip().lower() == "/help":
                    self._display_help()
                    continue
                elif text.strip().lower() == "/exit" or text.strip().lower() == "/quit":
                    break
                elif text.strip().lower() == "/dev on":
                    self.config.dev_mode = True
                    console.print("[bold green]Developer mode enabled[/]")
                    continue
                elif text.strip().lower() == "/dev off":
                    self.config.dev_mode = False
                    console.print("[bold yellow]Developer mode disabled[/]")
                    continue
                elif text.strip().lower() == "/dag on":
                    self.config.show_dag = True
                    console.print("[bold green]DAG visualization enabled[/]")
                    continue
                elif text.strip().lower() == "/dag off":
                    self.config.show_dag = False
                    console.print("[bold yellow]DAG visualization disabled[/]")
                    continue
                elif text.strip().lower() == "/dag show":
                    if self.flow_data:
                        console.print("[bold green]Showing DAG visualization...[/]")
                        self._visualize_dag(self.flow_data)
                    else:
                        console.print("[bold yellow]No DAG data available. Send a message first.[/]")
                    continue
                elif text.strip().lower() == "/debug on":
                    self.config.debug = True
                    console.print("[bold green]Debug mode enabled[/]")
                    continue
                elif text.strip().lower() == "/debug off":
                    self.config.debug = False
                    console.print("[bold yellow]Debug mode disabled[/]")
                    continue
                elif text.strip().lower() == "/clear":
                    os.system('cls' if os.name == 'nt' else 'clear')
                    continue
                
                # Display user message and send to server
                try:
                    # Display user message
                    self._display_message("user", text)
                    
                    # Send message to server
                    if not await self._send_message(text):
                        console.print("[bold red]Failed to send message[/]")
                        continue
                    
                    # After sending a message, we're now waiting for node.done
                    waiting_for_node_done = True
                except Exception as e:
                    console.print(f"[bold red]Error sending message:[/] {e}")
    
        except Exception as e:
            console.print(f"[bold red]Error:[/] {e}")
        
        finally:
            # Clean up
            message_handler.cancel()
            try:
                await self.ws.close()
            except:
                pass
    
    def _display_help(self):
        """Display help information"""
        table = Table(title="[bold]Thought Machine Client Commands[/]", box=box.ROUNDED, border_style="dim cyan")
        table.add_column("[bold]Command[/]", style="cyan")
        table.add_column("[bold]Description[/]", style="green")
        
        table.add_row("/help", "Show this help message")
        table.add_row("/exit", "Exit the client")
        table.add_row("/quit", "Exit the client (alias)")
        table.add_row("/dev on", "Enable developer mode")
        table.add_row("/dev off", "Disable developer mode")
        table.add_row("/dag on", "Enable DAG visualization")
        table.add_row("/dag off", "Disable DAG visualization")
        table.add_row("/dag show", "Show the current task flow graph")
        table.add_row("/debug on", "Enable debug information")
        table.add_row("/debug off", "Disable debug information")
        table.add_row("/clear", "Clear the terminal")
        
        console.print(table)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Thought Machine CLI Client")
    parser.add_argument(
        "--host", 
        default="localhost",
        help="Host address for the Thought Machine server"
    )
    parser.add_argument(
        "--port", 
        type=int, 
        default=8000,
        help="Port for the Thought Machine server"
    )
    parser.add_argument(
        "--cid", 
        default="",
        help="Conversation ID (leave empty for new conversation)"
    )
    parser.add_argument(
        "--dev", 
        action="store_true",
        help="Start in developer mode"
    )
    parser.add_argument(
        "--no-dag", 
        action="store_true",
        help="Disable DAG visualization"
    )
    parser.add_argument(
        "--debug", 
        action="store_true",
        help="Enable debug information"
    )
    
    return parser.parse_args()

async def main():
    # Parse command line args
    args = parse_args()
    
    # Configure the client
    config = Config(
        host=args.host,
        port=args.port,
        cid=args.cid,
        dev_mode=args.dev,
        show_dag=not args.no_dag,
        debug=args.debug
    )
    
    # Create and start the client
    client = EmptyAIClient(config)
    await client.start()

if __name__ == "__main__":
    asyncio.run(main())
