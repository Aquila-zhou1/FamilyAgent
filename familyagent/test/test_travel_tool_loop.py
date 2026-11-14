"""Offline regression tests for the actual travel agent tool loop."""

import unittest
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, ToolMessage

from familyagent.func import agent_travel


class WeatherModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        return self

    def _generate(self, messages, *args, **kwargs):
        if self.i == 1:
            assert isinstance(messages[-1], ToolMessage)
            assert messages[-1].tool_call_id == "weather-call"
            assert "18-28" in messages[-1].content
        return super()._generate(messages, *args, **kwargs)


class TravelToolLoopTests(unittest.TestCase):
    def make_agent(self):
        model = WeatherModel(responses=[
            AIMessage(content="", tool_calls=[{
                "name": "get_weather", "args": {"location": "北京"},
                "id": "weather-call", "type": "tool_call",
            }]),
            AIMessage(content="Weather received; itinerary ready."),
        ])
        with patch.object(agent_travel, "get_llm", return_value=model):
            return agent_travel.create_travel_agent()

    def test_invoke_executes_weather_and_returns_final_answer(self):
        with patch.object(agent_travel, "travel_agent", self.make_agent()):
            self.assertEqual(agent_travel.invoke_travel_agent("北京"),
                             "Weather received; itinerary ready.")

    def test_stream_executes_weather_and_only_emits_model_text(self):
        with patch.object(agent_travel, "travel_agent", self.make_agent()):
            self.assertEqual("".join(agent_travel.stream_travel_agent("北京")),
                             "Weather received; itinerary ready.")


if __name__ == "__main__":
    unittest.main()
