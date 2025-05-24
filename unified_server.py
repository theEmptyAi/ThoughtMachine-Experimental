#!/usr/bin/env python3
import uuid
import json
import os
import ast
import logging
import asyncio
from typing import Dict, List, Any, Optional

# FastAPI imports
from fastapi import FastAPI, WebSocket, BackgroundTasks, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.websockets import WebSocketDisconnect

# Thought Machine imports
from core.brain import Brain
from core.pubsub import hub

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Thought Machine Unified Server")

# Allow all origins for testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage of Brain instances per conversation
brains: Dict[str, Brain] = {}

# Define the default project path for the sample project
DEFAULT_PROJECT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), 'sample_py_project'))

# ----------------------------------------------------------------------------------
# Python Code Parser Class (from python-code-parser/app.py)
# ----------------------------------------------------------------------------------

class PythonCodeParser:
    """
    Parser for Python code that extracts the structure of imports, classes, and methods.
    """
    
    def __init__(self, project_path):
        self.project_path = project_path
        self.project_structure = {
            "name": os.path.basename(project_path),
            "globals": [],
            "classes": []
        }
    
    def parse_project(self):
        """Parse all Python files in the project directory"""
        for root, _, files in os.walk(self.project_path):
            for file in files:
                if file.endswith('.py'):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, self.project_path)
                    try:
                        self.parse_file(file_path, relative_path)
                    except Exception as e:
                        logger.error(f"Error parsing {file_path}: {str(e)}")
        
        return self.project_structure
    
    def generate_dummy_summary(self, name, object_type):
        """Generate a dummy summary for a class or method for development purposes"""
        if object_type == "class":
            templates = [
                f"A class that implements {name} functionality",
                f"Represents a {name} object in the system",
                f"Container for {name} related operations and data",
                f"Handles all {name} processing in the application",
                f"Provides utilities for working with {name} objects"
            ]
        else:  # method or function
            templates = [
                f"Performs {name} operation on the data",
                f"Handles the {name} process", 
                f"Utility method for {name} functionality",
                f"Implements the {name} algorithm",
                f"Processes input and performs {name} operation"
            ]
        
        # Use the name to deterministically select a summary template
        # This ensures the same name always gets the same summary
        index = sum(ord(c) for c in name) % len(templates)
        return templates[index]
    
    def extract_function_params(self, func_node):
        """Extract function parameters as a formatted string"""
        params = []
        for arg in func_node.args.args:
            if arg.arg != 'self':  # Skip 'self' parameter for methods
                # Check if there's a default value
                params.append(arg.arg)
        
        # Handle *args and **kwargs
        if func_node.args.vararg:
            params.append(f"*{func_node.args.vararg.arg}")
        if func_node.args.kwarg:
            params.append(f"**{func_node.args.kwarg.arg}")
        
        return f"({', '.join(params)})" if params else "()"
    
    def parse_file(self, file_path, relative_path):
        """Parse a single Python file"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        try:
            tree = ast.parse(content)
            
            # Get file-level globals (imports, variables, functions)
            file_globals = {
                "file": relative_path,
                "imports": [],
                "functions": [],
                "variables": [],
                "code": content  # Store the entire file content
            }
            
            # Track classes to avoid duplicates
            classes_in_file = []
            
            for node in ast.iter_child_nodes(tree):
                # Imports
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    import_line = ast.get_source_segment(content, node)
                    if import_line:
                        file_globals["imports"].append(import_line)
                
                # Global functions
                elif isinstance(node, ast.FunctionDef):
                    function_line = node.lineno
                    function_code = ast.get_source_segment(content, node)
                    function_name = node.name
                    docstring = ast.get_docstring(node) or ""
                    
                    # Generate a function ID for linking
                    function_id = f"{relative_path.replace('/', '.').replace('.py', '')}.{function_name}"
                    
                    # Get function parameters
                    params = self.extract_function_params(node)
                    
                    # Generate a summary if no docstring
                    summary = docstring.split('\n')[0] if docstring else self.generate_dummy_summary(function_name, "method")
                    
                    function_info = {
                        "id": function_id,
                        "name": function_name,
                        "line": function_line,
                        "params": params,
                        "code": function_code,
                        "docstring": docstring,
                        "summary": summary,
                        "nested_functions": []
                    }
                    
                    # Extract any nested functions
                    self.extract_nested_functions(node, content, function_id)
                    
                    file_globals["functions"].append(function_info)
                
                # Classes (including their methods)
                elif isinstance(node, ast.ClassDef):
                    class_info = self.extract_class_info(node, content, relative_path)
                    classes_in_file.append(class_info)
            
            # Add the file globals to the project structure
            self.project_structure["globals"].append(file_globals)
            
            # Add all classes from this file to the project structure
            self.project_structure["classes"].extend(classes_in_file)
            
        except Exception as e:
            logger.error(f"Error parsing abstract syntax tree for {file_path}: {str(e)}")
    
    def extract_class_info(self, class_node, source, file_path, parent_class=None):
        """Extract information about a class including methods and nested classes"""
        class_line = class_node.lineno
        class_name = class_node.name
        class_code = ast.get_source_segment(source, class_node)
        docstring = ast.get_docstring(class_node) or ""
        
        # Generate a class ID for linking
        base_id = f"{file_path.replace('/', '.').replace('.py', '')}"
        if parent_class:
            class_id = f"{parent_class}.{class_name}"
        else:
            class_id = f"{base_id}.{class_name}"
        
        # Get inheritance information
        bases = []
        for base in class_node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                # Handle module.Class inheritance
                attr_source = ast.get_source_segment(source, base)
                if attr_source:
                    bases.append(attr_source)
        
        # Generate a summary if no docstring
        summary = docstring.split('\n')[0] if docstring else self.generate_dummy_summary(class_name, "class")
        
        class_info = {
            "id": class_id,
            "name": class_name,
            "line": class_line,
            "file": file_path,
            "bases": bases,
            "docstring": docstring,
            "summary": summary,
            "code": class_code,
            "methods": [],
            "nested_classes": []
        }
        
        # Process all child nodes (methods and nested classes)
        for node in ast.iter_child_nodes(class_node):
            # Methods
            if isinstance(node, ast.FunctionDef):
                method_line = node.lineno
                method_code = ast.get_source_segment(source, node)
                method_name = node.name
                method_docstring = ast.get_docstring(node) or ""
                
                # Generate a method ID for linking
                method_id = f"{class_id}.{method_name}"
                
                # Get method parameters
                params = self.extract_function_params(node)
                
                # Generate a summary if no docstring
                method_summary = method_docstring.split('\n')[0] if method_docstring else self.generate_dummy_summary(method_name, "method")
                
                method_info = {
                    "id": method_id,
                    "name": method_name,
                    "line": method_line,
                    "params": params,
                    "code": method_code,
                    "docstring": method_docstring,
                    "summary": method_summary,
                    "nested_functions": []
                }
                
                # Extract any nested functions
                self.extract_nested_functions(node, source, method_id)
                
                class_info["methods"].append(method_info)
            
            # Nested classes
            elif isinstance(node, ast.ClassDef):
                nested_class = self.extract_class_info(node, source, file_path, class_id)
                class_info["nested_classes"].append(nested_class)
        
        return class_info
    
    def extract_nested_functions(self, func_node, source, parent_id):
        """Extract nested functions from a method"""
        nested_functions = []
        
        for node in ast.iter_child_nodes(func_node):
            if isinstance(node, ast.FunctionDef):
                nested_func_line = node.lineno
                nested_func_code = ast.get_source_segment(source, node)
                nested_func_name = node.name
                nested_func_docstring = ast.get_docstring(node) or ""
                
                # Generate a function ID for linking
                nested_func_id = f"{parent_id}.{nested_func_name}"
                
                # Get function parameters
                params = self.extract_function_params(node)
                
                # Generate a summary if no docstring
                summary = nested_func_docstring.split('\n')[0] if nested_func_docstring else self.generate_dummy_summary(nested_func_name, "method")
                
                nested_func_info = {
                    "id": nested_func_id,
                    "name": nested_func_name,
                    "line": nested_func_line,
                    "params": params,
                    "code": nested_func_code,
                    "docstring": nested_func_docstring,
                    "summary": summary,
                    "nested_functions": []  # Could go deeper if needed
                }
                
                nested_functions.append(nested_func_info)
        
        return nested_functions

# ----------------------------------------------------------------------------------
# Thought Machine API Endpoints (from api.py)
# ----------------------------------------------------------------------------------

# Monkey patch the Executor.run method to explicitly emit replies
from core.executor import Executor

_original_run = Executor.run

async def _patched_run(self):
    conv = self.state.get("__conv")   # may be None in tests
    node  = self.flow["start"]
    nodes = self.flow["nodes"]

    # Wrap the pub method to intercept 'assistant' messages
    original_pub = self.pub
    async def pub_wrapper(topic, data):
        # Intercept every node.done
        if topic == "node.done":
            out = data.get("out", {})
            cid = self.state.get("__cid", "default")

            # (1) If the node has a textual reply → emit one assistant
            #     event so the client can show its normal panel.
            if isinstance(out.get("reply"), str):
                await hub.queue(cid).put({"topic": "assistant",
                                          "data": out["reply"]})

            # (2) If the node returned *other* data but no reply →
            #     convert it to friendly text via result_to_reply.
            elif out:
                try:
                    formatted = await self.factory.run(
                        "result_to_reply",
                        self.state,
                        data=out,
                        goal=self.state.get("goal", "")
                    )
                    await hub.queue(cid).put({"topic": "assistant",
                                              "data": formatted.get("reply", "")})
                except Exception as e:
                    # 3) Absolute fallback – plain JSON dump.
                    import json
                    await hub.queue(cid).put(
                        {"topic": "assistant",
                         "data": "Raw result:\n```json\n" +
                                 json.dumps(out, indent=2, ensure_ascii=False) +
                                 "\n```"})
        # Forward the original node.* event in every case
        await original_pub(topic, data)
    
    self.pub = pub_wrapper
    
    while node:
        spec = nodes[node]                        # {thought, params, next}
        await self.pub("node.start", {"id": node, "thought": spec["thought"]})
        out = await self.factory.run(spec["thought"], self.state, **spec.get("params", {}))
        self.state.update(out)
        if conv and "reply" in out and isinstance(out["reply"], str):
            conv.add("assistant", out["reply"])
            # Don't emit the reply here as we already do it in pub_wrapper
        await self.pub("node.done", {"id": node, "out": out})
        node = spec.get("next")

# Apply the monkey patch
Executor.run = _patched_run

async def _handle_and_emit(cid: str, text: str):
    """Run Brain.handle and push its textual reply (if any) to the hub."""
    brain = brains.setdefault(cid, Brain())
    
    # Use try-except to handle any errors in the brain processing
    try:
        logger.info(f"Processing message from {cid}: {text}")
        reply = await brain.handle(cid, text)
        logger.info(f"Brain reply for {cid}: {reply}")
        
        if reply:
            q = hub.queue(cid)
            # Make sure to properly format and send the assistant message
            await q.put({"topic": "assistant", "data": reply})
            logger.info(f"Sent assistant message to {cid}")
            
            # Only send task.done for immediate replies (not for async tasks)
            if not reply.startswith("🚀"):
                await q.put({"topic": "task.done", "data": {}})
                logger.info(f"Sent task.done for {cid} (immediate reply)")
    except Exception as e:
        logger.error(f"Error processing message for {cid}: {str(e)}")
        # Notify the client of the error
        q = hub.queue(cid)
        await q.put({"topic": "assistant", "data": f"Error processing your request: {str(e)}"})


@app.post("/chat")
async def chat(body: dict, bt: BackgroundTasks):
    cid = body.get("cid") or uuid.uuid4().hex
    text = body["text"]
    # publish user message event
    await hub.queue(cid).put({"topic": "user", "data": text})
    # handle asynchronously and emit reply when done
    bt.add_task(_handle_and_emit, cid, text)
    return {"cid": cid}

@app.websocket("/ws/{cid}")
async def websocket_endpoint(ws: WebSocket, cid: str):
    logger.info(f"WebSocket connection requested for conversation: {cid}")
    await ws.accept()
    logger.info(f"WebSocket connection accepted for conversation: {cid}")
    q = hub.queue(cid)
    try:
        # Send initial connection confirmation
        await ws.send_text(json.dumps({"topic": "system", "data": "Connected to Thought Machine"}))
        logger.info(f"Sent initial connection message to client: {cid}")
        
        while True:
            ev = await q.get()
            logger.info(f"Sending event to client {cid}: {ev['topic']}")
            await ws.send_text(json.dumps(ev, default=str, ensure_ascii=False))
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for conversation: {cid}")
    except Exception as e:
        logger.error(f"Error in WebSocket handling for {cid}: {str(e)}")
    finally:
        logger.info(f"WebSocket connection closed for conversation: {cid}")

# ----------------------------------------------------------------------------------
# Python Code Parser API Endpoints (from python-code-parser/app.py)
# ----------------------------------------------------------------------------------

@app.get("/api/parse")
async def parse_project(project_path: Optional[str] = Query(None)):
    """
    API endpoint to parse a Python project
    Query parameters:
        - project_path: The absolute path to the project directory (optional, defaults to sample_py_project)
    Returns:
        JSON structure of the project's Python code
    """
    path = project_path or DEFAULT_PROJECT_PATH
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"Project path '{path}' does not exist")
    
    try:
        parser = PythonCodeParser(path)
        project_structure = parser.parse_project()
        return project_structure
    except Exception as e:
        logger.exception("Error parsing project")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/projects")
async def list_projects(directory: Optional[str] = Query(None)):
    """
    API endpoint to list available projects in a directory
    Query parameters:
        - directory: The directory to look for projects
    Returns:
        List of project names and paths
    """
    dir_path = directory or os.getcwd()
    
    if not os.path.exists(dir_path):
        raise HTTPException(status_code=404, detail=f"Directory '{dir_path}' does not exist")
    
    try:
        projects = []
        for item in os.listdir(dir_path):
            item_path = os.path.join(dir_path, item)
            if os.path.isdir(item_path):
                # Check if it's a Python project by looking for .py files
                has_py_files = False
                for root, _, files in os.walk(item_path):
                    if any(file.endswith('.py') for file in files):
                        has_py_files = True
                        break
                
                if has_py_files:
                    projects.append({
                        "name": item,
                        "path": item_path
                    })
        
        return projects
    except Exception as e:
        logger.exception("Error listing projects")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/", response_class=HTMLResponse)
async def home():
    """Simple home page with usage instructions"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Thought Machine Unified Server</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                max-width: 900px; 
                margin: 0 auto; 
                padding: 30px; 
                background-color: #0f172a;
                color: #e2e8f0; 
            }
            h1, h2, h3 { 
                color: #f1f5f9; 
                border-bottom: 1px solid #334155;
                padding-bottom: 10px;
            }
            h1 { 
                font-size: 2.5em; 
                background: linear-gradient(to right, #4f46e5, #10b981);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 40px;
            }
            .section {
                background-color: rgba(30, 41, 59, 0.8);
                border-radius: 10px;
                padding: 20px;
                margin-bottom: 30px;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }
            .endpoints {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
            }
            .endpoint { 
                background-color: rgba(15, 23, 42, 0.8);
                border-radius: 8px;
                padding: 15px; 
                margin-bottom: 15px; 
                border-left: 4px solid #4f46e5;
            }
            .endpoint.parser {
                border-left: 4px solid #10b981;
            }
            pre { 
                background-color: #1e293b; 
                padding: 12px; 
                border-radius: 5px; 
                overflow: auto;
                color: #94a3b8;
            }
            code {
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 0.9em;
            }
            .tag {
                display: inline-block;
                padding: 2px 8px;
                margin-right: 5px;
                border-radius: 4px;
                font-size: 0.8em;
                font-weight: bold;
            }
            .tag.get {
                background-color: #3b82f6;
                color: white;
            }
            .tag.post {
                background-color: #22c55e;
                color: white;
            }
            .tag.ws {
                background-color: #8b5cf6;
                color: white;
            }
        </style>
    </head>
    <body>
        <h1>Thought Machine Unified Server</h1>
        
        <div class="section">
            <h2>Overview</h2>
            <p>This server combines two functionalities:</p>
            <ol>
                <li><strong>Thought Machine Server</strong> - Provides chat and brain functionalities</li>
                <li><strong>Python Code Parser</strong> - Parses Python projects and returns their structure</li>
            </ol>
            <p>Both servers now run on the same port for easier integration with clients.</p>
        </div>
        
        <div class="section">
            <h2>API Endpoints</h2>
            <div class="endpoints">
                <div>
                    <h3>Thought Machine Server</h3>
                    <div class="endpoint">
                        <span class="tag post">POST</span> <code>/chat</code>
                        <p>Send a chat message to the Thought Machine brain</p>
                        <p><strong>Body:</strong></p>
                        <pre>{
  "cid": "conversation_id", // optional
  "text": "Your message here"
}</pre>
                    </div>
                    
                    <div class="endpoint">
                        <span class="tag ws">WS</span> <code>/ws/{cid}</code>
                        <p>WebSocket connection for real-time updates</p>
                        <p>Connect to this endpoint to receive events from the Thought Machine brain.</p>
                    </div>
                </div>
                
                <div>
                    <h3>Python Code Parser</h3>
                    <div class="endpoint parser">
                        <span class="tag get">GET</span> <code>/api/parse</code>
                        <p>Parse a Python project and get its structure</p>
                        <p><strong>Query Parameters:</strong></p>
                        <ul>
                            <li><code>project_path</code> - Path to the project (optional)</li>
                        </ul>
                    </div>
                    
                    <div class="endpoint parser">
                        <span class="tag get">GET</span> <code>/api/projects</code>
                        <p>List available Python projects</p>
                        <p><strong>Query Parameters:</strong></p>
                        <ul>
                            <li><code>directory</code> - Directory to search (optional)</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="section">
            <h2>Using with CLI Client</h2>
            <p>Run the <code>cli_client.py</code> script to connect to this server:</p>
            <pre>python cli_client.py --host localhost --port 8000</pre>
        </div>
    </body>
    </html>
    """

# ----------------------------------------------------------------------------------
# Main execution
# ----------------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "unified_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        # watch these dirs (you can add others)
        reload_dirs=[".", "thoughts", "core", "profiles"],
        # include .py, .json, and .txt files too
        reload_includes=["*.py", "*.json", "*.txt"],
        # ignore generated or heavy folders
        reload_excludes=[
            "conversations/*",
            "**/__pycache__/*"
        ],
        # give a small pause on reload so clients get time to reconnect
        reload_delay=0.5,
    )
