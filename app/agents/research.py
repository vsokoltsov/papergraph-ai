"""Research agent public interface."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from opentelemetry import trace

from app.agents.models import AgentEvent
from app.agents.protocols import PaperGraphRepository, PapersServiceClient, PaperVectorRepository
from app.agents.research_graph import build_research_graph
from app.agents.research_tools import log_agent_event, rerank_documents, rewrite_search_query
from app.agents.utils import (
    create_research_tools,
    default_research_system_prompt,
    format_agent_event,
    record_agent_tokens,
)
from app.metrics import track_agent_run

tracer = trace.get_tracer(__name__)


@dataclass
class ResearchAgent:
    """LangGraph-backed academic paper research agent."""

    tools: Sequence[BaseTool]
    model_name: str
    api_key: str
    emit_event: Callable[[AgentEvent], None] | None = None
    system_prompt: str | None = None
    events: list[AgentEvent] = field(default_factory=list)

    @track_agent_run
    @tracer.start_as_current_span("agent.run")
    async def run(self, question: str) -> str:
        """Run the research workflow for a user question.

        Args:
            question: User research question.

        Returns:
            Final answer generated from retrieved evidence.
        """

        self._emit({"type": "run_start", "input": {"question": question}})
        llm = ChatOpenAI(
            model=self.model_name,
            api_key=self.api_key,
            temperature=0,
        )
        workflow = build_research_graph(
            tools=self.tools,
            llm=llm,
            system_prompt=self.system_prompt or default_research_system_prompt(),
        )

        result = await workflow.ainvoke({"question": question})
        messages = result["messages"]
        answer = result["answer"]
        record_agent_tokens(
            messages=messages,
            question=question,
            answer=answer,
            model_name=self.model_name,
        )
        self._emit({"type": "run_end", "output": {"answer": answer}})
        return answer

    def _emit(self, event: AgentEvent) -> None:
        """Emit one structured agent event.

        Args:
            event: Event to record and optionally stream.
        """

        self.events.append(event)
        log_agent_event(event)
        if self.emit_event:
            self.emit_event(event)


__all__ = [
    "AgentEvent",
    "PaperGraphRepository",
    "PaperVectorRepository",
    "PapersServiceClient",
    "ResearchAgent",
    "build_research_graph",
    "create_research_tools",
    "default_research_system_prompt",
    "format_agent_event",
    "record_agent_tokens",
    "rerank_documents",
    "rewrite_search_query",
]
