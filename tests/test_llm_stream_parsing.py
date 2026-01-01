import json
import unittest
from unittest.mock import MagicMock, patch
from api.llm_client import generate_page_burst

class TestLLMStreamParsing(unittest.TestCase):
    def setUp(self):
        # Mock env vars to allow "live" logic without real keys
        self.env_patcher = patch.dict("os.environ", {
            "GEMINI_API_KEY": "fake_key",
            "GEMINI_GENERATION_MODEL": "gemini-1.5-flash",
        })
        self.env_patcher.start()

    def tearDown(self):
        self.env_patcher.stop()

    @patch("requests.post")
    def test_parses_pretty_printed_stream(self, mock_post):
        """Verify the buffer handles multi-line JSON fragments correctly."""
        # Wrap content in valid Gemini response structure
        def make_chunk(text_fragment):
            return json.dumps({
                "candidates": [{
                    "content": {
                        "parts": [{"text": text_fragment}]
                    }
                }]
            }).encode('utf-8') + b'\n'

        # The LLM is generating a JSON array of sites.
        # We split the Gemini RESPONSE JSON into multiple chunks,
        # AND the text content inside is also split.
        
        # Scenario: 
        # API sends Byte chunks.
        # Chunk 1: '{\n  "candidates": ... text: "[\n"'
        # Chunk 2: '... text: "  {\n    \"kind\": ..."'
        
        # But wait, generate_page_burst iterates requests.iter_lines().
        # It expects each LINE to be a valid JSON object matching the Gemini schema.
        # The TEXT inside that object might be a fragment of the final JSON.
        
        chunk1 = make_chunk('[\n  {\n    "kind": "full_page_html",\n')
        chunk2 = make_chunk('    "html": "<div>Content 1</div>"\n  },\n')
        chunk3 = make_chunk('  {\n    "kind": "full_page_html",\n')
        chunk4 = make_chunk('    "html": "<div>Content 2</div>"\n  }\n]')

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [chunk1, chunk2, chunk3, chunk4]
        mock_post.return_value = mock_response

        # Execute
        results = list(generate_page_burst("brief", 123))

        # Asserts
        self.assertEqual(len(results), 2, "Should parse 2 objects")
        self.assertEqual(results[0]["html"], "<div>Content 1</div>")
        self.assertEqual(results[1]["html"], "<div>Content 2</div>")

    @patch("requests.post")
    def test_parses_split_tokens(self, mock_post):
        """Verify the buffer handles JSON tokens split across chunks."""
        def make_chunk(text_fragment):
             return json.dumps({
                "candidates": [{
                    "content": {
                        "parts": [{"text": text_fragment}]
                    }
                }]
            }).encode('utf-8') + b'\n'

        # Split "html" key and value across Gemini response chunks
        # Chunk 1 text: '[{"kind": "full_page_html", "ht'
        # Chunk 2 text: 'ml": "<div>Sp'
        # Chunk 3 text: 'lit</div>"}]'
        
        chunks = [
            make_chunk('[{"kind": "full_page_html", "ht'),
            make_chunk('ml": "<div>Sp'),
            make_chunk('lit</div>"}]')
        ]

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = chunks
        mock_post.return_value = mock_response

        results = list(generate_page_burst("brief", 123))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["html"], "<div>Split</div>")

    @patch("requests.post")
    def test_handles_empty_stream_gracefully(self, mock_post):
        """Verify it yields an error if stream yields no objects."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [] # Empty stream
        mock_post.return_value = mock_response

        results = list(generate_page_burst("brief", 123))

        self.assertEqual(len(results), 1)
        self.assertIn("error", results[0])
        self.assertIn("No valid JSON objects", results[0]["error"])

    @patch("requests.post")
    def test_ignores_invalid_json_garbage(self, mock_post):
        """Verify it survives non-JSON garbage in the stream."""
        def make_chunk(text):
             return json.dumps({
                "candidates": [{"content": {"parts": [{"text": text}]}}]
            }).encode('utf-8') + b'\n'
            
        chunks = [
            b'data: {"invalid": json}\n', # Garbage line in stream
            make_chunk('{"kind": "full_page_html", "html": "Valid"}') # Valid line
        ]
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = chunks
        mock_post.return_value = mock_response

        results = list(generate_page_burst("brief", 123))

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["html"], "Valid")

if __name__ == "__main__":
    unittest.main()
