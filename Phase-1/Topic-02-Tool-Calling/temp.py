import json

sample_text = '{\"order_id\":\"B2200\"}'

print(json.loads(sample_text)['order_id'])

resp = {
  "id": "gen-1793819681-6xvuHdOcptgKJiv9FNXi",
  "choices": [
    {
      "finish_reason": "tool_calls",
      "index": 0,
      "logprobs": None,
      "message": {
        "content": None,
        "refusal": None,
        "role": "assistant",
        "annotations": None,
        "audio": None,
        "function_call": None,
        "tool_calls": [
          {
            "id": "call_k6Vbm5I5I6g4cslLCefghhFM",
            "function": {
              "arguments": "{\"order_id\":\"B2200\"}",
              "name": "get_order_status"
            },
            "type": "function",
            "index": 0
          }
        ],
        "reasoning": None
      },
      "native_finish_reason": "tool_calls"
    }
  ],
  "created": 1793819681,
  "model": "openai/gpt-4o-mini",
  "object": "chat.completion",
  "metadata": None,
  "moderation": None,
  "service_tier": "default",
  "system_fingerprint": "fp_d3b38c8dc1",
  "usage": {
    "completion_tokens": 18,
    "prompt_tokens": 76,
    "total_tokens": 94,
    "completion_tokens_details": {
      "accepted_prediction_tokens": None,
      "audio_tokens": 0,
      "reasoning_tokens": 0,
      "rejected_prediction_tokens": None,
      "text_tokens": None,
      "image_tokens": 0
    },
    "prompt_tokens_details": {
      "audio_tokens": 0,
      "cache_write_tokens": 0,
      "cached_tokens": 0,
      "image_tokens": None,
      "text_tokens": None,
      "video_tokens": 0
    },
    "cost": 2.22e-05,
    "is_byok": False,
    "cost_details": {
      "upstream_inference_cost": 2.22e-05,
      "upstream_inference_prompt_cost": 1.14e-05,
      "upstream_inference_completions_cost": 1.08e-05
    }
  },
  "provider": "OpenAI"
}

print(resp['choices'][0]['finish_reason'])