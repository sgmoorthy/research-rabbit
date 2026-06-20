import os
import uuid
import json
import asyncio
import traceback
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Research Rabbit UI")

# Allow CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "reports")
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(BASE_DIR)), "config.json")

# Ensure directories exist
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)

# In-memory storage for active tasks
# Maps task_id -> {"topic": str, "queue": asyncio.Queue, "status": str, "result": dict}
active_tasks = {}

class SettingsModel(BaseModel):
    llm_provider: str
    local_llm: str
    model_name: str
    openai_api_key: str
    gemini_api_key: str
    tavily_api_key: str
    max_loops: int

class ResearchRequest(BaseModel):
    research_topic: str
    max_loops: Optional[int] = None
    llm_provider: Optional[str] = None
    model_name: Optional[str] = None
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    tavily_api_key: Optional[str] = None

# Helper functions for settings
def load_saved_settings():
    settings = {
        "llm_provider": os.environ.get("LLM_PROVIDER", "ollama"),
        "local_llm": os.environ.get("LOCAL_LLM", "llama3.2"),
        "model_name": os.environ.get("MODEL_NAME", ""),
        "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
        "gemini_api_key": os.environ.get("GEMINI_API_KEY", ""),
        "tavily_api_key": os.environ.get("TAVILY_API_KEY", ""),
        "max_loops": int(os.environ.get("MAX_WEB_RESEARCH_LOOPS", "3"))
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                settings.update(saved)
        except Exception:
            pass
    return settings

def save_settings(settings: dict):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error saving settings: {e}")

# Settings API
@app.get("/api/settings")
def get_settings():
    return load_saved_settings()

@app.post("/api/settings")
def update_settings(settings: SettingsModel):
    save_settings(settings.model_dump())
    return {"status": "success", "message": "Settings updated successfully"}

# Reports API (History)
@app.get("/api/reports")
def list_reports():
    reports = []
    if os.path.exists(REPORTS_DIR):
        for filename in os.listdir(REPORTS_DIR):
            if filename.endswith(".json"):
                path = os.path.join(REPORTS_DIR, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        reports.append({
                            "id": data.get("id"),
                            "topic": data.get("topic"),
                            "timestamp": data.get("timestamp"),
                            "loop_count": data.get("loop_count", 0),
                            "llm_provider": data.get("llm_provider")
                        })
                except Exception:
                    pass
    # Sort reports by timestamp descending
    reports.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
    return reports

@app.get("/api/reports/{report_id}")
def get_report(report_id: str):
    path = os.path.join(REPORTS_DIR, f"{report_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read report: {str(e)}")

@app.delete("/api/reports/{report_id}")
def delete_report(report_id: str):
    path = os.path.join(REPORTS_DIR, f"{report_id}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Report not found")
    try:
        os.remove(path)
        return {"status": "success", "message": "Report deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete report: {str(e)}")

# Background research task
async def run_research_agent(task_id: str, request: ResearchRequest):
    queue = active_tasks[task_id]["queue"]
    
    # Merge request overrides with stored settings
    saved = load_saved_settings()
    llm_provider = request.llm_provider or saved["llm_provider"]
    local_llm = saved["local_llm"]
    model_name = request.model_name or saved["model_name"]
    openai_api_key = request.openai_api_key or saved["openai_api_key"]
    gemini_api_key = request.gemini_api_key or saved["gemini_api_key"]
    tavily_api_key = request.tavily_api_key or saved["tavily_api_key"]
    max_loops = request.max_loops if request.max_loops is not None else saved["max_loops"]
    
    config_dict = {
        "max_web_research_loops": max_loops,
        "local_llm": local_llm,
        "llm_provider": llm_provider,
        "model_name": model_name,
        "openai_api_key": openai_api_key,
        "gemini_api_key": gemini_api_key,
        "tavily_api_key": tavily_api_key
    }
    
    try:
        from research_rabbit.research_rabbit import graph
        from langchain_core.runnables import RunnableConfig
        
        config = RunnableConfig(configurable=config_dict)
        initial_state = {"research_topic": request.research_topic}
        
        # Stream graph outputs
        async for event in graph.astream(initial_state, config=config):
            # event is a dictionary, e.g. {'generate_query': {'search_query': '...'}}
            # Send step output to the stream queue
            node_name = list(event.keys())[0]
            node_data = event[node_name]
            
            await queue.put({
                "type": "step",
                "node": node_name,
                "data": node_data
            })
            
        # Get final state by compiling output
        # Let's inspect what is currently in state
        final_state = await graph.aget_state(config)
        final_values = final_state.values
        
        running_summary = final_values.get("running_summary", "")
        sources_gathered = final_values.get("sources_gathered", [])
        loop_count = final_values.get("research_loop_count", 0)
        
        # Save report
        report_data = {
            "id": task_id,
            "topic": request.research_topic,
            "timestamp": datetime.now().isoformat(),
            "summary": running_summary,
            "sources": sources_gathered,
            "loop_count": loop_count,
            "llm_provider": llm_provider,
            "model_name": model_name or (local_llm if llm_provider == "ollama" else ""),
            "config": {
                "max_loops": max_loops,
                "llm_provider": llm_provider,
                "model_name": model_name
            }
        }
        
        report_path = os.path.join(REPORTS_DIR, f"{task_id}.json")
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=4)
            
        active_tasks[task_id]["status"] = "completed"
        active_tasks[task_id]["result"] = report_data
        
        await queue.put({
            "type": "done",
            "report_id": task_id,
            "data": report_data
        })
        
    except Exception as e:
        traceback_str = traceback.format_exc()
        print(f"Error executing agent: {e}\n{traceback_str}")
        active_tasks[task_id]["status"] = "failed"
        
        await queue.put({
            "type": "error",
            "message": str(e),
            "traceback": traceback_str
        })
    finally:
        # Sentinel to close stream
        await queue.put(None)

# Research Start API
@app.post("/api/research")
async def start_research(request: ResearchRequest, background_tasks: BackgroundTasks):
    if not request.research_topic.strip():
        raise HTTPException(status_code=400, detail="Research topic cannot be empty")
        
    task_id = str(uuid.uuid4())
    active_tasks[task_id] = {
        "topic": request.research_topic,
        "queue": asyncio.Queue(),
        "status": "running",
        "result": None
    }
    
    background_tasks.add_task(run_research_agent, task_id, request)
    return {"task_id": task_id}

# SSE stream endpoint
@app.get("/api/stream/{task_id}")
async def stream_task(task_id: str):
    if task_id not in active_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
        
    async def sse_generator():
        queue = active_tasks[task_id]["queue"]
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        except asyncio.CancelledError:
            print(f"Streaming client disconnected for task {task_id}")
            
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

# Serve index.html
@app.get("/")
async def read_index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Web UI is initialized. Please create static files."}

# Mount static folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("research_rabbit.gui:app", host="127.0.0.1", port=8000, reload=True)
