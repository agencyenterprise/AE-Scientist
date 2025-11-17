import asyncio

from langfuse.langchain import CallbackHandler
from langgraph.graph.state import RunnableConfig

from aigraph import agent_step_1


async def main() -> None:
    state = agent_step_1.State(idea="Minimal hello world")
    context = agent_step_1.Context(model="gpt-4o-mini", temperature=0.0)
    config = RunnableConfig(callbacks=[CallbackHandler()])

    graph = agent_step_1.build()
    response = await graph.ainvoke(state, config=config, context=context)
    print(response)


if __name__ == "__main__":
    asyncio.run(main())
