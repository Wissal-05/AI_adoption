import json
import pytest
from unittest.mock import MagicMock
from dataclasses import asdict

from adoption_analytics.ai.llm_engine import LLMEngine, AssistantResponse
from adoption_analytics.ai.tool_registry import ToolRegistry, ToolResult


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
        self.last_tools = []
        
    def create(self, model, messages, tools, tool_choice, temperature):
        self.last_messages = messages
        self.last_tools = tools
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
    registry.list_tools.return_value = [
        {"name": "get_usage_kpis", "description": "desc", "parameters": {}},
        {"name": "get_adoption_by_module", "description": "desc", "parameters": {}},
        {"name": "get_adoption_by_campus", "description": "desc", "parameters": {}},
        {"name": "get_top_interactions", "description": "desc", "parameters": {}},
        {"name": "get_data_quality", "description": "desc", "parameters": {}},
        {"name": "get_usage_evolution", "description": "desc", "parameters": {}},
        {"name": "get_organization_usage", "description": "desc", "parameters": {}}
    ]
    # Default successful tool execution
    registry.execute.return_value = ToolResult(
        status="success", tool="test_tool", service="Booking", data={"kpi": 42}, message=""
    )
    return registry


def create_tool_call(id, name, arguments):
    tc = MagicMock()
    tc.id = id
    tc.function.name = name
    tc.function.arguments = json.dumps(arguments) if isinstance(arguments, dict) else arguments
    return tc


def test_missing_api_key(mock_registry, monkeypatch):
    from config.settings import settings
    monkeypatch.setattr(settings, "groq_api_key", None)
    with pytest.raises(ValueError, match="GROQ_API_KEY n'est pas configurée."):
        LLMEngine(mock_registry)


def test_direct_answer(fake_client, mock_registry):
    engine = LLMEngine(mock_registry, client=fake_client)
    fake_client.chat.completions.responses = [
        FakeCompletion(choices=[FakeChoice(FakeMessage(content="Bonjour !"))])
    ]
    
    resp = engine.chat("Salut")
    assert resp.answer == "Bonjour !"
    assert resp.tool_calls == []
    assert not mock_registry.execute.called


def test_tool_calling_flow(fake_client, mock_registry):
    engine = LLMEngine(mock_registry, client=fake_client)
    
    tc = create_tool_call("call_1", "get_usage_kpis", {"service": "Booking"})
    
    fake_client.chat.completions.responses = [
        FakeCompletion(choices=[FakeChoice(FakeMessage(content=None, tool_calls=[tc]))]),
        FakeCompletion(choices=[FakeChoice(FakeMessage(content="Le DAU est de 42."))] )
    ]
    
    resp = engine.chat("Quel est le MAU de Booking ?")
    
    # Assert execution
    mock_registry.execute.assert_called_once_with("get_usage_kpis", service="Booking")
    assert resp.answer == "Le DAU est de 42."
    assert "get_usage_kpis" in resp.tool_calls
    
    # Assert JSON conversion and no dataframes in messages
    last_messages = fake_client.chat.completions.last_messages
    tool_msg = last_messages[-1]
    assert tool_msg["role"] == "tool"
    assert tool_msg["tool_call_id"] == "call_1"
    
    content_dict = json.loads(tool_msg["content"])
    assert content_dict["status"] == "success"
    assert content_dict["data"]["kpi"] == 42


def test_invalid_json_arguments(fake_client, mock_registry):
    engine = LLMEngine(mock_registry, client=fake_client)
    
    tc = create_tool_call("call_1", "get_usage_kpis", "{invalid_json}")
    
    fake_client.chat.completions.responses = [
        FakeCompletion(choices=[FakeChoice(FakeMessage(content=None, tool_calls=[tc]))]),
        FakeCompletion(choices=[FakeChoice(FakeMessage(content="Erreur d'arguments."))] )
    ]
    
    engine.chat("Test")
    
    last_messages = fake_client.chat.completions.last_messages
    tool_msg = last_messages[-1]
    content_dict = json.loads(tool_msg["content"])
    assert content_dict["status"] == "invalid_request"
    assert "Invalid JSON arguments" in content_dict["message"]


def test_tool_not_available_and_invalid_request(fake_client, mock_registry):
    engine = LLMEngine(mock_registry, client=fake_client)
    
    mock_registry.execute.return_value = ToolResult(
        status="not_available", tool="get_usage_kpis", service="Booking", data={}, message="Not here"
    )
    
    tc = create_tool_call("call_1", "get_usage_kpis", {"service": "Booking"})
    
    fake_client.chat.completions.responses = [
        FakeCompletion(choices=[FakeChoice(FakeMessage(content=None, tool_calls=[tc]))]),
        FakeCompletion(choices=[FakeChoice(FakeMessage(content="Non disponible."))] )
    ]
    
    engine.chat("Test")
    last_messages = fake_client.chat.completions.last_messages
    content_dict = json.loads(last_messages[-1]["content"])
    assert content_dict["status"] == "not_available"
    assert content_dict["message"] == "Not here"


def test_max_rounds_reached(fake_client, mock_registry):
    engine = LLMEngine(mock_registry, client=fake_client)
    
    tc = create_tool_call("call_1", "get_usage_kpis", {"service": "Booking"})
    
    # 3 responses that all return tool calls
    fake_client.chat.completions.responses = [
        FakeCompletion(choices=[FakeChoice(FakeMessage(content=None, tool_calls=[tc]))]),
        FakeCompletion(choices=[FakeChoice(FakeMessage(content=None, tool_calls=[tc]))]),
        FakeCompletion(choices=[FakeChoice(FakeMessage(content=None, tool_calls=[tc]))]),
        FakeCompletion(choices=[FakeChoice(FakeMessage(content="Should not be reached."))] )
    ]
    
    resp = engine.chat("Test", max_rounds=3)
    assert resp.error == "Max tool rounds reached"
    assert len(resp.tool_calls) == 3


def test_parallel_tool_calls(fake_client, mock_registry):
    engine = LLMEngine(mock_registry, client=fake_client)
    
    tc1 = create_tool_call("call_1", "get_usage_kpis", {"service": "Booking"})
    tc2 = create_tool_call("call_2", "get_data_quality", {"service": "Booking"})
    
    fake_client.chat.completions.responses = [
        FakeCompletion(choices=[FakeChoice(FakeMessage(content=None, tool_calls=[tc1, tc2]))]),
        FakeCompletion(choices=[FakeChoice(FakeMessage(content="Réponse finale."))] )
    ]
    
    resp = engine.chat("Test")
    assert resp.tool_calls == ["get_usage_kpis", "get_data_quality"]
    assert mock_registry.execute.call_count == 2
    
    
def test_all_7_tools_routing(fake_client, mock_registry):
    engine = LLMEngine(mock_registry, client=fake_client)
    
    tools_to_test = [
        "get_usage_kpis",
        "get_adoption_by_module",
        "get_adoption_by_campus",
        "get_top_interactions",
        "get_data_quality",
        "get_usage_evolution",
        "get_organization_usage"
    ]
    
    calls = [create_tool_call(f"call_{i}", tool, {"service": "Booking"}) for i, tool in enumerate(tools_to_test)]
    
    fake_client.chat.completions.responses = [
        FakeCompletion(choices=[FakeChoice(FakeMessage(content=None, tool_calls=calls))]),
        FakeCompletion(choices=[FakeChoice(FakeMessage(content="Done."))] )
    ]
    
    engine.chat("Test all routing")
    
    # Assert all 7 tools were routed correctly
    assert mock_registry.execute.call_count == 7
    executed_tools = [call.args[0] for call in mock_registry.execute.call_args_list]
    assert executed_tools == tools_to_test
    
    
def test_no_dataframes_in_tools_schemas(fake_client, mock_registry):
    engine = LLMEngine(mock_registry, client=fake_client)
    tools = engine._get_groq_tools()
    
    for tool in tools:
        assert "dataframe" not in str(tool).lower()
        assert "series" not in str(tool["function"]["parameters"]).lower() # Or at least no raw pandas objects
        # We ensure they are pure JSON schemas
        json.dumps(tool)
