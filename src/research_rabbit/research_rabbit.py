import json

from typing_extensions import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langchain_ollama import ChatOllama
from langgraph.graph import START, END, StateGraph

from research_rabbit.configuration import Configuration
from research_rabbit.utils import deduplicate_and_format_sources, tavily_search, format_sources
from research_rabbit.state import SummaryState, SummaryStateInput, SummaryStateOutput
from research_rabbit.prompts import query_writer_instructions, summarizer_instructions, reflection_instructions

# Model Factory
def get_llm(config: RunnableConfig, json_mode: bool = False):
    configurable = Configuration.from_runnable_config(config)
    provider = (configurable.llm_provider or "ollama").lower()
    
    import os
    if configurable.openai_api_key:
        os.environ["OPENAI_API_KEY"] = configurable.openai_api_key
    if configurable.gemini_api_key:
        os.environ["GEMINI_API_KEY"] = configurable.gemini_api_key
    if configurable.tavily_api_key:
        os.environ["TAVILY_API_KEY"] = configurable.tavily_api_key
        
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        model = configurable.model_name or "gemini-1.5-flash"
        if json_mode:
            return ChatGoogleGenerativeAI(model=model, temperature=0, response_mime_type="application/json")
        return ChatGoogleGenerativeAI(model=model, temperature=0)
    elif provider == "openai":
        from langchain_openai import ChatOpenAI
        model = configurable.model_name or "gpt-4o-mini"
        if json_mode:
            return ChatOpenAI(model=model, temperature=0, model_kwargs={"response_format": {"type": "json_object"}})
        return ChatOpenAI(model=model, temperature=0)
    else:  # ollama or default
        from langchain_ollama import ChatOllama
        model = configurable.model_name or configurable.local_llm or "llama3.2"
        if json_mode:
            return ChatOllama(model=model, temperature=0, format="json")
        return ChatOllama(model=model, temperature=0)

# Nodes   
def generate_query(state: SummaryState, config: RunnableConfig):
    """ Generate a query for web search """
    
    # Format the prompt
    query_writer_instructions_formatted = query_writer_instructions.format(research_topic=state.research_topic)

    # Generate a query with dynamic LLM
    llm_json_mode = get_llm(config, json_mode=True)
    result = llm_json_mode.invoke(
        [SystemMessage(content=query_writer_instructions_formatted),
        HumanMessage(content=f"Generate a query for web search:")]
    )   
    query = json.loads(result.content)
    
    return {"search_query": query['query']}

def web_research(state: SummaryState, config: RunnableConfig):
    """ Gather information from the web """
    
    # Set Tavily API key from config if present
    configurable = Configuration.from_runnable_config(config)
    import os
    if configurable.tavily_api_key:
        os.environ["TAVILY_API_KEY"] = configurable.tavily_api_key

    # Search the web
    search_results = tavily_search(state.search_query, include_raw_content=True, max_results=1)
    
    # Format the sources
    search_str = deduplicate_and_format_sources(search_results, max_tokens_per_source=1000)
    return {"sources_gathered": [format_sources(search_results)], "research_loop_count": state.research_loop_count + 1, "web_research_results": [search_str]}

def summarize_sources(state: SummaryState, config: RunnableConfig):
    """ Summarize the gathered sources """
    
    # Existing summary
    existing_summary = state.running_summary

    # Most recent web research
    most_recent_web_research = state.web_research_results[-1]

    # Build the human message
    if existing_summary:
        human_message_content = (
            f"Extend the existing summary: {existing_summary}\n\n"
            f"Include new search results: {most_recent_web_research} "
            f"That addresses the following topic: {state.research_topic}"
        )
    else:
        human_message_content = (
            f"Generate a summary of these search results: {most_recent_web_research} "
            f"That addresses the following topic: {state.research_topic}"
        )

    # Run the dynamic LLM
    llm = get_llm(config, json_mode=False)
    result = llm.invoke(
        [SystemMessage(content=summarizer_instructions),
        HumanMessage(content=human_message_content)]
    )

    running_summary = result.content
    return {"running_summary": running_summary}

def reflect_on_summary(state: SummaryState, config: RunnableConfig):
    """ Reflect on the summary and generate a follow-up query """

    # Generate a query with dynamic LLM
    llm_json_mode = get_llm(config, json_mode=True)
    result = llm_json_mode.invoke(
        [SystemMessage(content=reflection_instructions.format(research_topic=state.research_topic)),
        HumanMessage(content=f"Identify a knowledge gap and generate a follow-up web search query based on our existing knowledge: {state.running_summary}")]
    )   
    follow_up_query = json.loads(result.content)

    # Overwrite the search query
    return {"search_query": follow_up_query['follow_up_query']}

def finalize_summary(state: SummaryState):
    """ Finalize the summary """
    
    # Format all accumulated sources into a single bulleted list
    all_sources = "\n".join(source for source in state.sources_gathered)
    state.running_summary = f"## Summary\n\n{state.running_summary}\n\n ### Sources:\n{all_sources}"
    return {"running_summary": state.running_summary}

def route_research(state: SummaryState, config: RunnableConfig) -> Literal["finalize_summary", "web_research"]:
    """ Route the research based on the follow-up query """

    configurable = Configuration.from_runnable_config(config)
    if state.research_loop_count <= configurable.max_web_research_loops:
        return "web_research"
    else:
        return "finalize_summary" 
    
# Add nodes and edges 
builder = StateGraph(SummaryState, input=SummaryStateInput, output=SummaryStateOutput, config_schema=Configuration)
builder.add_node("generate_query", generate_query)
builder.add_node("web_research", web_research)
builder.add_node("summarize_sources", summarize_sources)
builder.add_node("reflect_on_summary", reflect_on_summary)
builder.add_node("finalize_summary", finalize_summary)

# Add edges
builder.add_edge(START, "generate_query")
builder.add_edge("generate_query", "web_research")
builder.add_edge("web_research", "summarize_sources")
builder.add_edge("summarize_sources", "reflect_on_summary")
builder.add_conditional_edges("reflect_on_summary", route_research)
builder.add_edge("finalize_summary", END)

graph = builder.compile()