"""
RAG Multi-Agent Workflow for Enhanced RnD Assistant
"""
from typing import Dict, Any

from langgraph.graph import StateGraph, END, START

from database.milvus_manager import milvus_manager
from agents.query_classifier_agent import EnhancedQueryClassifierAgent
from agents.search_agent import EnhancedSearchAgent
from agents.smart_product_search_agent import SmartProductSearchAgent
from agents.benchmark_agent import BenchmarkAgent
from agents.market_gap_agent import MarketGapAgent
from agents.verify_idea_agent import VerifyIdeaAgent
from agents.audience_volume_agent import AudienceVolumeAgent
from agents.response_generator_agent import EnhancedResponseGeneratorAgent
from utils.helpers import AgentState, create_initial_state


class RAGMultiAgentWorkflow:
    """Enhanced RAG Multi-Agent Workflow Orchestrator"""

    def __init__(self):
        # Initialize Milvus connection
        milvus_manager.connect()

        # Initialize agents
        self.classifier_agent = EnhancedQueryClassifierAgent()
        self.search_agent = EnhancedSearchAgent()
        self.smart_search_agent = SmartProductSearchAgent()
        self.benchmark_agent = BenchmarkAgent()
        self.market_gap_agent = MarketGapAgent()
        self.verify_idea_agent = VerifyIdeaAgent()
        self.audience_volume_agent = AudienceVolumeAgent()
        self.response_generator = EnhancedResponseGeneratorAgent()

        # Build workflow
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)

        # Add nodes
        workflow.add_node("classify_query", self._classify_query)
        workflow.add_node("search_products", self._search_products)
        workflow.add_node("smart_search", self._smart_search)
        workflow.add_node("benchmark_analysis", self._benchmark_analysis)
        workflow.add_node("market_gap_analysis", self._market_gap_analysis)
        workflow.add_node("verify_idea_analysis", self._verify_idea_analysis)
        workflow.add_node("audience_volume_analysis", self._audience_volume_analysis)
        workflow.add_node("generate_response", self._generate_response)

        # Define workflow edges
        workflow.add_edge(START, "classify_query")

        # Conditional routing after classification
        workflow.add_conditional_edges(
            "classify_query",
            self._route_after_classification,
            {
                "smart_search": "smart_search",
                "other": "search_products"
            }
        )

        # Smart search goes directly to response
        workflow.add_edge("smart_search", "generate_response")

        # Traditional search routing
        workflow.add_conditional_edges(
            "search_products",
            self._route_to_analysis,
            {
                "benchmark": "benchmark_analysis",
                "market_gap": "market_gap_analysis",
                "verify_idea": "verify_idea_analysis",
                "audience_volume": "audience_volume_analysis"
            }
        )

        # All analysis nodes go to response generation
        workflow.add_edge("benchmark_analysis", "generate_response")
        workflow.add_edge("market_gap_analysis", "generate_response")
        workflow.add_edge("verify_idea_analysis", "generate_response")
        workflow.add_edge("audience_volume_analysis", "generate_response")
        workflow.add_edge("generate_response", END)

        return workflow.compile()

    def _route_after_classification(self, state: AgentState) -> str:
        """Route after query classification"""
        if state["query_type"] == "smart_search":
            return "smart_search"
        else:
            return "other"

    def _route_to_analysis(self, state: AgentState) -> str:
        """Route to appropriate analysis based on query type"""
        return state["query_type"]

    # Node functions
    async def _classify_query(self, state: AgentState) -> AgentState:
        """Classify the query"""
        return await self.classifier_agent.process(state)

    async def _search_products(self, state: AgentState) -> AgentState:
        """Search for products"""
        return await self.search_agent.process(state)

    async def _smart_search(self, state: AgentState) -> AgentState:
        """Execute smart search"""
        return await self.smart_search_agent.process(state)

    async def _benchmark_analysis(self, state: AgentState) -> AgentState:
        """Perform benchmark analysis"""
        return await self.benchmark_agent.process(state)

    async def _market_gap_analysis(self, state: AgentState) -> AgentState:
        """Perform market gap analysis"""
        return await self.market_gap_agent.process(state)

    async def _verify_idea_analysis(self, state: AgentState) -> AgentState:
        """Perform idea verification analysis"""
        return await self.verify_idea_agent.process(state)

    async def _audience_volume_analysis(self, state: AgentState) -> AgentState:
        """Perform audience volume analysis"""
        return await self.audience_volume_agent.process(state)

    async def _generate_response(self, state: AgentState) -> AgentState:
        """Generate final response"""
        return await self.response_generator.process(state)

    async def process_query(self, query: str, input_image: str = None) -> str:
        """Process a user query through the workflow"""
        initial_state = create_initial_state(query, input_image)

        try:
            final_state = await self.workflow.ainvoke(initial_state)
            return final_state["final_answer"]
        except Exception as e:
            return f"❌ Lỗi xử lý: {str(e)}"

    def get_workflow_graph(self):
        """Get the workflow graph for visualization"""
        return self.workflow

    async def process_query_with_state(self, query: str, input_image: str = None) -> Dict[str, Any]:
        """Process query and return full state for debugging"""
        initial_state = create_initial_state(query, input_image)

        try:
            final_state = await self.workflow.ainvoke(initial_state)
            return final_state
        except Exception as e:
            return {
                "error": str(e),
                "final_answer": f"❌ Lỗi xử lý: {str(e)}"
            }