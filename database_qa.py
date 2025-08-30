import os
from typing import Dict, List
from typing_extensions import TypedDict, Annotated
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools.sql_database.tool import QuerySQLDatabaseTool
from langgraph.graph import START, StateGraph
from langgraph.checkpoint.memory import MemorySaver
from langchain.chat_models import init_chat_model
import logging

logger = logging.getLogger(__name__)

class State(TypedDict):
    question: str
    query: str
    result: str
    answer: str

class QueryOutput(TypedDict):
    """Generated SQL query."""
    query: Annotated[str, ..., "Syntactically valid SQL query."]

class DatabaseQA:
    def __init__(self):
        """Initialize the Database Q&A system."""
        self.db = self._setup_database()
        self.llm = self._setup_llm()
        self.graphs = self._setup_graphs()
        
    def _setup_database(self) -> SQLDatabase:
        """Setup database connection from environment variables."""
        db_type = os.getenv("DB_TYPE", "postgresql")
        
        if db_type.lower() == "postgresql":
            postgres_uri = (
                f"postgresql://{os.getenv('POSTGRES_USER')}:"
                f"{os.getenv('POSTGRES_PASSWORD')}@"
                f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
                f"{os.getenv('POSTGRES_PORT', '5432')}/"
                f"{os.getenv('POSTGRES_DB')}"
            )
            connection_string = postgres_uri
        else:
            # Add support for other databases as needed
            raise ValueError(f"Unsupported database type: {db_type}")
        
        try:
            db = SQLDatabase.from_uri(connection_string)
            logger.info(f"Connected to {db_type} database")
            logger.info(f"Available tables: {db.get_usable_table_names()}")
            return db
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise
    
    def _setup_llm(self):
        """Setup LLM from environment variables."""
        llm_provider = os.getenv("LLM_PROVIDER", "google_genai")
        llm_model = os.getenv("LLM_MODEL", "gemini-2.5-flash")
        
        try:
            if llm_provider == "google_genai":
                if not os.getenv("GOOGLE_API_KEY"):
                    raise ValueError("GOOGLE_API_KEY not found in environment variables")
                llm = init_chat_model(llm_model, model_provider=llm_provider)
            else:
                # Add support for other LLM providers as needed
                raise ValueError(f"Unsupported LLM provider: {llm_provider}")
            
            logger.info(f"Initialized {llm_provider} LLM with model {llm_model}")
            return llm
        except Exception as e:
            logger.error(f"Failed to initialize LLM: {e}")
            raise
    
    def _setup_graphs(self) -> Dict:
        """Setup LangGraph workflows."""
        # Query generation prompt
        system_message = """
        Given an input question, create a syntactically correct {dialect} query to
        run to help find the answer. Unless the user specifies in his question a
        specific number of examples they wish to obtain, always limit your query to
        at most {top_k} results. You can order the results by a relevant column to
        return the most interesting examples in the database.

        Never query for all the columns from a specific table, only ask for a the
        few relevant columns given the question.

        Pay attention to use only the column names that you can see in the schema
        description. Be careful to not query for columns that do not exist. Also,
        pay attention to which column is in which table.

        Only use the following tables:
        {table_info}
        """

        user_prompt = "Question: {input}"
        self.query_prompt_template = ChatPromptTemplate(
            [("system", system_message), ("user", user_prompt)]
        )
        
        # Build the graph
        graph_builder = StateGraph(State).add_sequence(
            [self._write_query, self._execute_query, self._generate_answer]
        )
        graph_builder.add_edge(START, "_write_query")

        # Create both versions of the graph
        basic_graph = graph_builder.compile()
        
        # Graph with memory for human-in-the-loop
        memory = MemorySaver()
        approval_graph = graph_builder.compile(
            checkpointer=memory, 
            interrupt_before=["_execute_query"]
        )
        
        return {
            "basic": basic_graph,
            "approval": approval_graph,
            "memory": memory
        }
    
    def _write_query(self, state: State) -> Dict:
        """Generate SQL query to fetch information."""
        max_results = int(os.getenv("MAX_QUERY_RESULTS", "10"))
        
        prompt = self.query_prompt_template.invoke({
            "dialect": self.db.dialect,
            "top_k": max_results,
            "table_info": self.db.get_table_info(),
            "input": state["question"],
        })
        
        structured_llm = self.llm.with_structured_output(QueryOutput)
        result = structured_llm.invoke(prompt)
        return {"query": result["query"]}

    def _execute_query(self, state: State) -> Dict:
        """Execute SQL query."""
        execute_query_tool = QuerySQLDatabaseTool(db=self.db)
        return {"result": execute_query_tool.invoke(state["query"])}

    def _generate_answer(self, state: State) -> Dict:
        """Answer question using retrieved information as context."""
        prompt = (
            "Given the following user question, corresponding SQL query, "
            "and SQL result, answer the user question.\n\n"
            f"Question: {state['question']}\n"
            f"SQL Query: {state['query']}\n"
            f"SQL Result: {state['result']}"
        )
        response = self.llm.invoke(prompt)
        return {"answer": response.content}
    
    def ask_question(self, question: str, use_human_approval: bool = None) -> Dict:
        """
        Ask a question to the database.
        
        Args:
            question: The natural language question
            use_human_approval: Whether to require human approval before executing queries
                               If None, uses environment variable HUMAN_INTERVENTION
        
        Returns:
            Dict with query, result, and answer
        """
        if use_human_approval is None:
            use_human_approval = os.getenv("HUMAN_INTERVENTION", "false").lower() == "true"
        
        if use_human_approval:
            return self._ask_with_approval(question)
        else:
            return self._ask_direct(question)
    
    def _ask_direct(self, question: str) -> Dict:
        """Ask question with direct execution."""
        result = {"query": "", "result": "", "answer": ""}
        
        for step in self.graphs["basic"].stream(
            {"question": question}, 
            stream_mode="updates"
        ):
            if "_write_query" in step:
                result["query"] = step["_write_query"]["query"]
            elif "_execute_query" in step:
                result["result"] = step["_execute_query"]["result"]
            elif "_generate_answer" in step:
                result["answer"] = step["_generate_answer"]["answer"]
        
        return result
    
    def _ask_with_approval(self, question: str) -> Dict:
        """Ask question with human approval step."""
        config = {"configurable": {"thread_id": str(hash(question))}}
        result = {"query": "", "result": "", "answer": ""}
        
        # First phase - generate query and wait for approval
        for step in self.graphs["approval"].stream(
            {"question": question},
            config,
            stream_mode="updates",
        ):
            if "_write_query" in step:
                result["query"] = step["_write_query"]["query"]
                break
        
        # In a production API, human approval would be handled differently
        # For now, we'll auto-approve or you can implement a separate approval endpoint
        auto_approve = os.getenv("AUTO_APPROVE_QUERIES", "true").lower() == "true"
        
        if auto_approve:
            # Continue execution
            for step in self.graphs["approval"].stream(None, config, stream_mode="updates"):
                if "_execute_query" in step:
                    result["result"] = step["_execute_query"]["result"]
                elif "_generate_answer" in step:
                    result["answer"] = step["_generate_answer"]["answer"]
        else:
            # In production, you'd implement a separate approval mechanism
            result["answer"] = "Query generated but requires human approval to execute."
        
        return result
    
    def get_available_tables(self) -> List[str]:
        """Get list of available database tables."""
        return self.db.get_usable_table_names()
    
    def get_table_schema(self, table_name: str) -> str:
        """Get schema information for a specific table."""
        try:
            return self.db.get_table_info([table_name])
        except Exception as e:
            raise ValueError(f"Error getting schema for table {table_name}: {e}")
    
    def test_connection(self) -> Dict:
        """Test database connection."""
        try:
            version = self.db.run("SELECT version();")
            return {
                "connected": True,
                "dialect": self.db.dialect,
                "version": version,
                "tables": self.get_available_tables()
            }
        except Exception as e:
            return {
                "connected": False,
                "error": str(e)
            }