import pytest
import json
import base64
from unittest.mock import patch, AsyncMock, MagicMock, call

from pdfse import llm as pdfse_llm


def test_encode_image_to_base64():
    input_bytes = b"test_bytes"
    expected_base64 = base64.b64encode(input_bytes).decode("utf-8")
    expected_string = f"data:image/png;base64,{expected_base64}"
    assert pdfse_llm._encode_image_to_base64(input_bytes) == expected_string


def test_get_system_prompt_text_mode():
    prompt = pdfse_llm.get_system_prompt(image_mode=False)
    assert pdfse_llm._TEXT_MODE_CONTEXT in prompt
    assert pdfse_llm._IMAGE_MODE_CONTEXT not in prompt
    assert pdfse_llm._TEXT_MODE_EXAMPLE in prompt
    assert pdfse_llm._COMMON_PROMPT_HEADER in prompt
    assert pdfse_llm._COMMON_PROMPT_FOOTER in prompt


def test_get_system_prompt_image_mode():
    prompt = pdfse_llm.get_system_prompt(image_mode=True)
    assert pdfse_llm._IMAGE_MODE_CONTEXT in prompt
    assert pdfse_llm._TEXT_MODE_CONTEXT not in prompt
    assert pdfse_llm._IMAGE_MODE_EXAMPLE in prompt
    assert pdfse_llm._COMMON_PROMPT_HEADER in prompt
    assert pdfse_llm._COMMON_PROMPT_FOOTER in prompt


@pytest.fixture
def mock_openai_client():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()

    mock_create = AsyncMock(return_value=mock_response)

    mock_client = MagicMock()
    mock_client.chat = MagicMock()
    mock_client.chat.completions = MagicMock()
    mock_client.chat.completions.create = mock_create

    return mock_client, mock_create, mock_response


@pytest.mark.asyncio
async def test_fetch_heuristic_text_mode(mock_openai_client):
    mock_client, mock_create, mock_response = mock_openai_client

    expected_heuristic = {"field_name": "value"}
    mock_response.choices[0].message.content = json.dumps(expected_heuristic)

    test_schema = {"name": "Test Name"}
    test_samples = ["Sample text 1", "Sample text 2"]

    with patch("pdfse.llm.get_client", return_value=mock_client):
        result = await pdfse_llm.fetch_heuristic(
            test_schema, test_samples, image_mode=False
        )

    assert result == expected_heuristic

    mock_create.assert_called_once()
    call_args = mock_create.call_args[1]

    assert call_args["model"] == "gpt-5-mini"
    assert call_args["response_format"] == {"type": "json_object"}

    messages = call_args["messages"]
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"

    user_content = messages[1]["content"]
    assert isinstance(user_content, list)
    assert len(user_content) == 3

    assert user_content[0]["type"] == "text"
    assert json.dumps(test_schema, indent=2, ensure_ascii=False) in user_content[0]["text"]

    assert user_content[1]["type"] == "text"
    assert "SAMPLE 1" in user_content[1]["text"]
    assert test_samples[0] in user_content[1]["text"]

    assert user_content[2]["type"] == "text"
    assert "SAMPLE 2" in user_content[2]["text"]
    assert test_samples[1] in user_content[2]["text"]


@pytest.mark.asyncio
async def test_fetch_heuristic_image_mode(mock_openai_client):
    mock_client, mock_create, mock_response = mock_openai_client

    expected_heuristic = {"image_field": "image_value"}
    mock_response.choices[0].message.content = json.dumps(expected_heuristic)

    test_schema = {"photo_id": "Photo ID"}
    test_samples = [b"image_bytes_1", b"image_bytes_2"]
    mock_base64_string = "data:image/png;base64,mocked_base64"

    with patch("pdfse.llm.get_client", return_value=mock_client), \
         patch("pdfse.llm._encode_image_to_base64", return_value=mock_base64_string) as mock_encode:

        result = await pdfse_llm.fetch_heuristic(
            test_schema, test_samples, image_mode=True
        )

    assert result == expected_heuristic

    assert mock_encode.call_count == 2
    mock_encode.assert_has_calls([
        call(b"image_bytes_1"),
        call(b"image_bytes_2")
    ])

    mock_create.assert_called_once()
    call_args = mock_create.call_args[1]
    messages = call_args["messages"]
    user_content = messages[1]["content"]

    assert isinstance(user_content, list)
    assert len(user_content) == 3

    assert user_content[0]["type"] == "text"
    assert json.dumps(test_schema, indent=2, ensure_ascii=False) in user_content[0]["text"]

    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"] == mock_base64_string
    assert user_content[1]["image_url"]["detail"] == "high"

    assert user_content[2]["type"] == "image_url"
    assert user_content[2]["image_url"]["url"] == mock_base64_string


@pytest.mark.asyncio
async def test_fetch_heuristic_empty_response(mock_openai_client):
    mock_client, mock_create, mock_response = mock_openai_client

    mock_response.choices[0].message.content = ""

    test_schema = {"name": "Test Name"}
    test_samples = ["Sample text 1"]

    with patch("pdfse.llm.get_client", return_value=mock_client):
        with pytest.raises(ValueError, match="LLM response was empty"):
            await pdfse_llm.fetch_heuristic(
                test_schema, test_samples, image_mode=False
            )

@pytest.mark.asyncio
async def test_fetch_heuristic_no_response_content(mock_openai_client):
    mock_client, mock_create, mock_response = mock_openai_client

    mock_response.choices[0].message.content = None

    test_schema = {"name": "Test Name"}
    test_samples = ["Sample text 1"]

    with patch("pdfse.llm.get_client", return_value=mock_client):
        with pytest.raises(ValueError, match="LLM response was empty"):
            await pdfse_llm.fetch_heuristic(
                test_schema, test_samples, image_mode=False
            )
