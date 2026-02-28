JSON_SCHEMA = {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.local/orchestrator/changeProposal.hunks.schema.json",
  "type": "object",
  "required": ["status", "commit_message", "hunks", "commands"],
  "additionalProperties": False,
  "properties": {
    "status": { "type": "string", "enum": ["complete", "need_more_info"] },
    "commit_message": { "type": "string" },
    "hunks": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": False,
        "required": ["hunk_id", "path", "old_start", "old_len", "new_start", "new_len", "lines"],
        "properties": {
          "hunk_id": { "type": "string" },
          "path": { "type": "string" },
          "old_start": { "type": "integer" },
          "old_len": { "type": "integer" },
          "new_start": { "type": "integer" },
          "new_len": { "type": "integer" },
          "lines": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "commands": { "type": "array", "items": { "type": "string" } }
  }
}
