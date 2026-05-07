import asyncio
import os
import logging
import uvicorn
import traceback
from pathlib import Path
import typing

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.middleware.cors import CORSMiddleware
from huggingface_hub import hf_hub_download
from llama_cpp import Llama, CreateCompletionResponse
import psutil

import nest_asyncio
nest_asyncio.apply()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def log_ram(stage: str):
    """Logs the current RAM usage of the system."""
    mem = psutil.virtual_memory()
    used_gb = mem.used / (1024 ** 3)
    total_gb = mem.total / (1024 ** 3)
    logger.info(f"[RAM REPORT] {stage} | Used: {used_gb:.2f} GB / {total_gb:.2f} GB ({mem.percent}%)")

# 1. Initialize FastMCP with your strict security settings
mcp = FastMCP(
    "Leak-III-Worker",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    )
)

# Global LLM instance placeholder
llm = None

# ==========================================
# ⚙️ THE WORKER TOOL
# ==========================================
@mcp.tool()
def propose_lean_tactic(current_proof_state: str, strategic_directive: str = "") -> str:
    """
    Generates the next logical Lean 4 tactic based on the current proof state.
    
    Args:
        current_proof_state: The exact output from the 'get_current_proof_state' tool.
        strategic_directive: The high-level mathematical strategy to follow (e.g., 'Use induction').
    """
    logger.info(f"Received request for tactic. Strategy: {strategic_directive}")
    
    if llm is None:
        return "Error: DeepSeek Prover model is not loaded."

    prompt = f"""You are an expert Lean 4 mathematician. 
    Given the following proof state, provide the exact Lean 4 tactic(s) to advance or solve the goal.
    Adhere strictly to this mathematical strategy: {strategic_directive}

    ### Current Proof State:
    {current_proof_state}

    ### Lean 4 Tactic(s):
    ```lean4
    """

    log_ram("Before LLM Inference")

    # CPU-bound inference
    raw_response = llm(
        prompt,
        max_tokens=128,
        stop=["```", "###"], 
        temperature=0.2,
        stream=False      
    )

    log_ram("After LLM Inference")

    response = typing.cast(CreateCompletionResponse, raw_response)
    
    tactic_code = response['choices'][0]['text'].strip()
    return tactic_code
#

# ==========================================
# 🚀 SERVER STARTUP
# ==========================================
async def main_serve():
    global llm
    logger.info("Booting DeepSeek Prover Worker...")

    log_ram("Startup - Baseline Memory")
    
    # 1. The Warmup: Download and cache the 4-bit GGUF Model
    logger.info("⏳ Downloading and loading Unsloth 4-bit model into RAM. This may take 1-2 minutes...")
    try:
        model_path = hf_hub_download(
            repo_id="unsloth/DeepSeek-Prover-V2-7B-GGUF",
            filename="DeepSeek-Prover-V2-7B-Q4_K_M.gguf"
        )
        
        log_ram("After File Download (Before Llama Load)")

        # Load into llama.cpp, forcing exactly 2 threads for the free HF CPU tier
        llm = Llama(
            model_path=model_path,
            n_ctx=2048,      
            n_threads=2,     
            verbose=False,
            use_mmap=True
        )
        logger.info("✅ Warmup Complete. DeepSeek-Prover is locked in RAM!")

        log_ram("After Llama.cpp Initialization")
    except Exception as e:
        logger.error(f"❌ Failed to load model: {e}")
        logger.error(traceback.format_exc())
        return

    # 2. Grab the standard Starlette ASGI application
    http_app = mcp.sse_app()
    
    # 3. Add the CORS middleware exactly like Leak-I
    http_app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*", "mcp-protocol-version", "mcp-session-id"], 
        expose_headers=["mcp-session-id"]
    )
    
    # 4. Start Uvicorn programmatically so it shares the CURRENT event loop
    logger.info("Booting up Leak-III ASGI environment on Port 7860...")
    config = uvicorn.Config(
        http_app, 
        host="0.0.0.0", 
        port=7860,
        proxy_headers=True,               
        forwarded_allow_ips="*",
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main_serve())