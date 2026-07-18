from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.eval.llm.ground_truth.models import GeneratedQuestion, GeneratedQuestions, SourceDocument


class LangChainGroundTruthGenerator:
    """LLM-backed ground-truth generator using LangChain structured output.

    Args:
        model_name: OpenAI chat model name.
        api_key: OpenAI API key.
    """

    def __init__(self, model_name: str, api_key: str) -> None:
        llm = ChatOpenAI(model=model_name, api_key=api_key, temperature=0)
        self.generator = llm.with_structured_output(GeneratedQuestions)

    async def generate(
        self,
        document: SourceDocument,
        questions_per_document: int,
    ) -> list[GeneratedQuestion]:
        """Generate questions and answers from one source document.

        Args:
            document: Source paper or graph record.
            questions_per_document: Number of question-answer pairs to generate.

        Returns:
            Generated ground-truth examples.
        """

        response = await self.generator.ainvoke(
            [
                SystemMessage(content=ground_truth_instructions()),
                HumanMessage(content=ground_truth_prompt(document, questions_per_document)),
            ]
        )

        match response:
            case GeneratedQuestions():
                return response.questions
            case dict():
                return GeneratedQuestions.model_validate(response).questions
            case _:
                raise TypeError(f"Unexpected generator response type: {type(response)}")


def ground_truth_instructions() -> str:
    """Return instructions for generating LLM evaluation ground truth.

    Returns:
        System prompt for the ground-truth generation model.
    """

    return """
You generate evaluation datasets for an academic-paper research assistant.

Generate questions that a user could realistically ask after ingesting the provided paper
for a project about knowledge-graph-enhanced retrieval augmented generation with LLMs.
Generate answers using only the provided title and abstract.

Rules:
- Do not invent facts that are not in the source document.
- Prefer questions about knowledge graphs, graph-based retrieval, retrieval augmented
  generation, LLM factuality, provenance, domain adaptation, evaluation methods,
  and research limitations.
- If the paper uses the acronym RAG for something other than retrieval augmented
  generation, do not generate questions about it.
- Questions should test semantic understanding, not exact title lookup.
- Answers should be concise but complete enough to serve as ground truth.
- Include important paper-specific details when they are available.
- Do not mention that the answer was generated from an abstract.
""".strip()


def ground_truth_prompt(document: SourceDocument, questions_per_document: int) -> str:
    """Build the user prompt for one source document.

    Args:
        document: Source document to generate ground truth from.
        questions_per_document: Number of examples to request.

    Returns:
        Prompt text for the generation model.
    """

    return f"""
Generate {questions_per_document} evaluation question-answer pairs.

Document:
{document.document}

Title:
{document.title}

Abstract:
{document.abstract}
""".strip()
