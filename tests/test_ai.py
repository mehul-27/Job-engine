from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import MagicMock, patch

from career_os.ai import GroqProvider, create_provider, extract_json
from career_os.prompts import (
    cover_letter,
    opportunity_analysis,
    resume_tailor,
    PROMPT_VERSION,
)


class GroqProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_client = MagicMock()

    def test_chat_returns_content(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from Groq"
        mock_response.model = "llama3-70b-8192"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 5
        self.mock_client.chat.completions.create.return_value = mock_response

        provider = GroqProvider(api_key="test-key")
        provider._client = self.mock_client

        result = provider.chat(system="Be helpful", user="Say hi")

        self.assertEqual("Hello from Groq", result.content)
        self.assertEqual("llama3-70b-8192", result.model)
        self.assertIsNotNone(result.latency_ms)
        self.assertEqual(10, result.input_tokens)
        self.assertEqual(5, result.output_tokens)

    def test_chat_json_mode(self) -> None:
        payload = json.dumps({"answer": 42})
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = payload
        mock_response.model = "llama3-70b-8192"
        mock_response.usage = None
        self.mock_client.chat.completions.create.return_value = mock_response

        provider = GroqProvider(api_key="test-key")
        provider._client = self.mock_client
        result = provider.chat(system="JSON only", user="Return answer", json_mode=True)

        self.assertEqual(payload, result.content)
        _, call_kwargs = self.mock_client.chat.completions.create.call_args
        self.assertEqual({"type": "json_object"}, call_kwargs["response_format"])

    def test_chat_passes_messages(self) -> None:
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = ""
        mock_response.model = "m"
        mock_response.usage = None
        self.mock_client.chat.completions.create.return_value = mock_response

        provider = GroqProvider(api_key="test-key", model="mixtral-8x7b-32768")
        provider._client = self.mock_client
        provider.chat(system="Sys", user="User msg")

        _, call_kwargs = self.mock_client.chat.completions.create.call_args
        self.assertEqual("mixtral-8x7b-32768", call_kwargs["model"])
        self.assertEqual("Sys", call_kwargs["messages"][0]["content"])
        self.assertEqual("User msg", call_kwargs["messages"][1]["content"])
        self.assertEqual(0.3, call_kwargs["temperature"])


class CreateProviderTests(unittest.TestCase):
    def test_raises_when_no_api_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError) as ctx:
                create_provider()
        self.assertIn("GROQ_API_KEY", str(ctx.exception))

    def test_creates_provider_with_env(self) -> None:
        with patch.dict(os.environ, {"GROQ_API_KEY": "sk-test", "GROQ_MODEL": "llama-3.1-8b"}):
            provider = create_provider()
        self.assertIsInstance(provider, GroqProvider)


class ExtractJsonTests(unittest.TestCase):
    def test_extracts_top_level_json(self) -> None:
        text = "Here is the result:\n{\"key\": \"value\"}\nDone."
        self.assertEqual({"key": "value"}, extract_json(text))

    def test_extracts_nested_json(self) -> None:
        text = '{"a": {"b": [1, 2]}}'
        self.assertEqual({"a": {"b": [1, 2]}}, extract_json(text))


class PromptVersionTests(unittest.TestCase):
    def test_version_defined(self) -> None:
        self.assertTrue(PROMPT_VERSION.startswith("1."))


class ResumeTailorPromptTests(unittest.TestCase):
    def test_returns_system_and_user(self) -> None:
        sys, user = resume_tailor(
            job_title="Software Engineer",
            job_description="Python, Go, distributed systems",
            master_resume_text="Worked at Google on Kubernetes",
            knowledge_items="Built a distributed cache (project)",
        )
        self.assertIn("resume", sys.lower())
        self.assertIn("Software Engineer", user)
        self.assertIn("Kubernetes", user)
        self.assertIn("distributed cache", user)


class OpportunityAnalysisPromptTests(unittest.TestCase):
    def test_requests_json_analysis(self) -> None:
        sys, user = opportunity_analysis(
            job_title="Backend Intern",
            company="Acme",
            job_description="Python APIs",
            user_skills="Python, FastAPI",
        )
        self.assertIn("Backend Intern", user)
        self.assertIn("required_skills", sys)


class CoverLetterPromptTests(unittest.TestCase):
    def test_returns_plain_text_request(self) -> None:
        sys, user = cover_letter(
            job_title="Engineer",
            company="Co",
            job_description="Build things",
            tailored_resume_text="Built things",
            user_profile="Name: John",
        )
        self.assertIn("Engineer", user)
        self.assertIn("cover letter", sys.lower())


if __name__ == "__main__":
    unittest.main()
