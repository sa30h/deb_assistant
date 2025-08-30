# import os
# import logging
# from typing import Optional
# from fastapi import FastAPI, HTTPException
# from fastapi.middleware.cors import CORSMiddleware
# from pydantic import BaseModel
# from dotenv import load_dotenv
# from database_qa import DatabaseQA
# import uvicorn

# # Load environment variables
# load_dotenv()

# # Configure logging
# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger(__name__)

# # FastAPI app
# app = FastAPI(
#     title="Database Q&A API",
#     description="Natural language database querying system",
#     version="1.0.0"
# )

# # Add CORS middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Initialize the QA system
# qa_system = None

# @app.on_event("startup")
# async def startup_event():
#     """Initialize the QA system on startup."""
#     global qa_system
#     try:
#         qa_system = DatabaseQA()
#         logger.info("Database Q&A system initialized successfully")
#     except Exception as e:
#         logger.error(f"Failed to initialize QA system: {e}")
#         raise

# # Request/Response models
# class QuestionRequest(BaseModel):
#     question: str
#     use_human_approval: Optional[bool] = None  # Override default from env

# class QuestionResponse(BaseModel):
#     question: str
#     query: str
#     result: str
#     answer: str
#     status: str

# class HealthResponse(BaseModel):
#     status: str
#     database_connected: bool
#     available_tables: list

# @app.get("/health", response_model=HealthResponse)
# async def health_check():
#     """Health check endpoint."""
#     try:
#         tables = qa_system.get_available_tables()
#         return HealthResponse(
#             status="healthy",
#             database_connected=True,
#             available_tables=tables
#         )
#     except Exception as e:
#         logger.error(f"Health check failed: {e}")
#         return HealthResponse(
#             status="unhealthy",
#             database_connected=False,
#             available_tables=[]
#         )

# @app.post("/ask", response_model=QuestionResponse)
# async def ask_question(request: QuestionRequest):
#     """Ask a question to the database."""
#     if not qa_system:
#         raise HTTPException(status_code=500, detail="QA system not initialized")
    
#     try:
#         # Use the human approval setting from request or fallback to env default
#         use_approval = request.use_human_approval
#         if use_approval is None:
#             use_approval = os.getenv("HUMAN_INTERVENTION", "false").lower() == "true"
        
#         result = qa_system.ask_question(request.question, use_human_approval=use_approval)
        
#         return QuestionResponse(
#             question=request.question,
#             query=result["query"],
#             result=result["result"],
#             answer=result["answer"],
#             status="success"
#         )
#     except Exception as e:
#         logger.error(f"Error processing question: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/tables")
# async def get_tables():
#     """Get available database tables."""
#     if not qa_system:
#         raise HTTPException(status_code=500, detail="QA system not initialized")
    
#     try:
#         tables = qa_system.get_available_tables()
#         return {"tables": tables}
#     except Exception as e:
#         logger.error(f"Error getting tables: {e}")
#         raise HTTPException(status_code=500, detail=str(e))

# @app.get("/schema/{table_name}")
# async def get_table_schema(table_name: str):
#     """Get schema for a specific table."""
#     if not qa_system:
#         raise HTTPException(status_code=500, detail="QA system not initialized")
    
#     try:
#         schema = qa_system.get_table_schema(table_name)
#         return {"table": table_name, "schema": schema}
#     except Exception as e:
#         logger.error(f"Error getting schema for {table_name}: {e}")
#         raise HTTPException(status_code=404, detail=f"Table {table_name} not found or error: {str(e)}")

# if __name__ == "__main__":
#     port = int(os.getenv("PORT", "8000"))
#     host = os.getenv("HOST", "0.0.0.0")
    
#     uvicorn.run(
#         "app:app",
#         host=host,
#         port=port,
#         reload=os.getenv("DEBUG", "false").lower() == "true"
#     )

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
import uvicorn

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the QA system
qa_system = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application lifespan events."""
    global qa_system
    try:
        # Import here to avoid circular imports
        from database_qa import DatabaseQA
        qa_system = DatabaseQA()
        logger.info("Database Q&A system initialized successfully")
        yield
    except Exception as e:
        logger.error(f"Failed to initialize QA system: {e}")
        raise
    finally:
        # Cleanup code here if needed
        pass

# FastAPI app with lifespan handler
app = FastAPI(
    title="Database Q&A API",
    description="Natural language database querying system",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response models
class QuestionRequest(BaseModel):
    question: str
    use_human_approval: Optional[bool] = None  # Override default from env

class QuestionResponse(BaseModel):
    question: str
    query: str
    result: str
    answer: str
    status: str

class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    available_tables: list

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    try:
        tables = qa_system.get_available_tables()
        return HealthResponse(
            status="healthy",
            database_connected=True,
            available_tables=tables
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            database_connected=False,
            available_tables=[]
        )

@app.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """Ask a question to the database."""
    if not qa_system:
        raise HTTPException(status_code=500, detail="QA system not initialized")
    
    try:
        # Use the human approval setting from request or fallback to env default
        use_approval = request.use_human_approval
        if use_approval is None:
            use_approval = os.getenv("HUMAN_INTERVENTION", "false").lower() == "true"
        
        result = qa_system.ask_question(request.question, use_human_approval=use_approval)
        
        return QuestionResponse(
            question=request.question,
            query=result["query"],
            result=result["result"],
            answer=result["answer"],
            status="success"
        )
    except Exception as e:
        logger.error(f"Error processing question: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tables")
async def get_tables():
    """Get available database tables."""
    if not qa_system:
        raise HTTPException(status_code=500, detail="QA system not initialized")
    
    try:
        tables = qa_system.get_available_tables()
        return {"tables": tables}
    except Exception as e:
        logger.error(f"Error getting tables: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/schema/{table_name}")
async def get_table_schema(table_name: str):
    """Get schema for a specific table."""
    if not qa_system:
        raise HTTPException(status_code=500, detail="QA system not initialized")
    
    try:
        schema = qa_system.get_table_schema(table_name)
        return {"table": table_name, "schema": schema}
    except Exception as e:
        logger.error(f"Error getting schema for {table_name}: {e}")
        raise HTTPException(status_code=404, detail=f"Table {table_name} not found or error: {str(e)}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    
    uvicorn.run(
        "app:app",
        host=host,
        port=port,
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )