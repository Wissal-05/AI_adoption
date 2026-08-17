import json
import pytest
from unittest.mock import MagicMock
from dataclasses import asdict

from adoption_analytics.ai.llm_engine import LLMEngine, AssistantResponse
from adoption_analytics.ai.tool_registry import ToolRegistry, ToolResult
from adoption_analytics.ai.knowledge_retriever import KnowledgeRetriever

class FakeMessage:
    def __init__(self, content, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls or []

class FakeChoice:
    def __init__(self, message):
        self.message = message

class FakeCompletion:
    def __init__(self, choices):
        self.choices = choices

class FakeCompletions:
    def __init__(self):
        self.responses = []
        self.call_count = 0
        self.last_messages = []
        
    def create(self, model, messages, tools, tool_choice, temperature):
        self.last_messages = messages
        if self.call_count >= len(self.responses):
            raise Exception("No more responses queued")
        response = self.responses[self.call_count]
        self.call_count += 1
        if isinstance(response, Exception):
            raise response
        return response

class FakeChat:
    def __init__(self):
        self.completions = FakeCompletions()

class FakeGroqClient:
    def __init__(self):
        self.chat = FakeChat()

@pytest.fixture
def fake_client():
    return FakeGroqClient()

@pytest.fixture
def mock_registry():
    registry = MagicMock(spec=ToolRegistry)
    # The real registry has 7 tools, we just simulate getting them back.
    registry.list_tools.return_value = [
        {"name": "tool_1", "description": "d1", "parameters": {}},
        {"name": "tool_2", "description": "d2", "parameters": {}},
        {"name": "tool_3", "description": "d3", "parameters": {}},
        {"name": "tool_4", "description": "d4", "parameters": {}},
        {"name": "tool_5", "description": "d5", "parameters": {}},
        {"name": "tool_6", "description": "d6", "parameters": {}},
        {"name": "tool_7", "description": "d7", "parameters": {}}
    ]
    return registry

@pytest.fixture
def mock_retriever():
    ret = MagicMock(spec=KnowledgeRetriever)
    return ret

def test_retriever_absent_still_works(fake_client, mock_registry):
    engine = LLMEngine(mock_registry, client=fake_client)
    fake_client.chat.completions.responses = [
        FakeCompletion([FakeChoice(FakeMessage("No RAG"))])
    ]
    resp = engine.chat("Hello")
    assert resp.answer == "No RAG"
    assert len(resp.knowledge_sources) == 0

def test_mau_question_calls_tool(fake_client, mock_registry, mock_retriever):
    mock_retriever.search.return_value = [
        {"source": "kpi_definitions.md", "section": "MAU", "content": "definition MAU"}
    ]
    engine = LLMEngine(mock_registry, client=fake_client, knowledge_retriever=mock_retriever)
    
    tc = MagicMock()
    tc.function.name = "tool_1"
    tc.function.arguments = "{}"
    tc.id = "call_1"
    
    fake_client.chat.completions.responses = [
        FakeCompletion([FakeChoice(FakeMessage("", [tc]))]),
        FakeCompletion([FakeChoice(FakeMessage("Le MAU est 137"))])
    ]
    mock_registry.execute.return_value = ToolResult(status="success", tool="tool_1", service="", data={})
    
    resp = engine.chat("Quel est le MAU de Booking ?")
    
    # 1. RAG metadata injected
    assert "CONTEXTE DOCUMENTAIRE" in fake_client.chat.completions.last_messages[1]["content"]
    assert "kpi_definitions.md" in fake_client.chat.completions.last_messages[1]["content"]
    
    # 2. Tool called
    assert "tool_1" in resp.tool_calls
    assert len(resp.knowledge_sources) == 1
    
    # 3. No dataframes!
    for msg in fake_client.chat.completions.last_messages:
        assert "DataFrame" not in str(msg)

def test_mau_definition_no_tool(fake_client, mock_registry, mock_retriever):
    mock_retriever.search.return_value = [
        {"source": "kpi_definitions.md", "section": "MAU", "content": "Utilisateurs actifs mensuels."}
    ]
    engine = LLMEngine(mock_registry, client=fake_client, knowledge_retriever=mock_retriever)
    fake_client.chat.completions.responses = [
        FakeCompletion([FakeChoice(FakeMessage("C'est les utilisateurs actifs mensuels."))])
    ]
    
    resp = engine.chat("Que signifie MAU ?")
    assert len(resp.tool_calls) == 0
    assert len(resp.knowledge_sources) == 1

def test_usage_vs_adoption(fake_client, mock_registry, mock_retriever):
    mock_retriever.search.return_value = [
        {"source": "methodology.md", "section": "Adoption", "content": "bla"}
    ]
    engine = LLMEngine(mock_registry, client=fake_client, knowledge_retriever=mock_retriever)
    fake_client.chat.completions.responses = [FakeCompletion([FakeChoice(FakeMessage("Bla"))])]
    resp = engine.chat("Différence usage et adoption ?")
    assert len(resp.knowledge_sources) == 1
    
def test_transport_documentary(fake_client, mock_registry, mock_retriever):
    mock_retriever.search.return_value = [
        {"source": "data_limitations.md", "section": "Booking", "content": "Transport indispo"}
    ]
    engine = LLMEngine(mock_registry, client=fake_client, knowledge_retriever=mock_retriever)
    fake_client.chat.completions.responses = [FakeCompletion([FakeChoice(FakeMessage("indispo"))])]
    resp = engine.chat("Pourquoi Transport n'a pas de taux ?")
    assert len(resp.knowledge_sources) == 1

def test_source_ip_limitation(fake_client, mock_registry, mock_retriever):
    mock_retriever.search.return_value = [
        {"source": "data_limitations.md", "section": "Learning Center", "content": "IP biais"}
    ]
    engine = LLMEngine(mock_registry, client=fake_client, knowledge_retriever=mock_retriever)
    fake_client.chat.completions.responses = [FakeCompletion([FakeChoice(FakeMessage("Biais IP"))])]
    resp = engine.chat("Une adresse IP est un utilisateur ?")
    assert len(resp.knowledge_sources) == 1

def test_no_relevant_knowledge(fake_client, mock_registry, mock_retriever):
    mock_retriever.search.return_value = []
    engine = LLMEngine(mock_registry, client=fake_client, knowledge_retriever=mock_retriever)
    fake_client.chat.completions.responses = [
        FakeCompletion([FakeChoice(FakeMessage("Answer"))])
    ]
    
    engine.chat("Question")
    assert "CONTEXTE DOCUMENTAIRE" not in fake_client.chat.completions.last_messages[1]["content"]

def test_maximum_3_passages_injected(fake_client, mock_registry, mock_retriever):
    mock_retriever.search.return_value = [
        {"source": "a", "section": "a", "content": "a"},
        {"source": "b", "section": "b", "content": "b"},
        {"source": "c", "section": "c", "content": "c"}
    ]
    engine = LLMEngine(mock_registry, client=fake_client, knowledge_retriever=mock_retriever)
    fake_client.chat.completions.responses = [FakeCompletion([FakeChoice(FakeMessage("Ans"))])]
    resp = engine.chat("Q")
    # check that we asked for top 3
    mock_retriever.search.assert_called_with("Q", top_k=3)
    assert len(resp.knowledge_sources) == 3

def test_retriever_error_continues_without_rag(fake_client, mock_registry, mock_retriever):
    mock_retriever.search.side_effect = Exception("Boom")
    engine = LLMEngine(mock_registry, client=fake_client, knowledge_retriever=mock_retriever)
    fake_client.chat.completions.responses = [
        FakeCompletion([FakeChoice(FakeMessage("Still working"))])
    ]
    resp = engine.chat("Question")
    assert resp.answer == "Still working"
    assert len(resp.knowledge_sources) == 0

def test_exactly_7_tools_are_registered(mock_registry):
    engine = LLMEngine(mock_registry)
    assert len(engine._get_groq_tools()) == 7
