// Generated from contracts/protocol-v1.json; run python3 -m scripts.generate_protocol_contract.
export const protocolContract = {
  "title": "ProblemForger protocol v1 closed contract",
  "x-contract-version": 1,
  "x-frame-max-bytes": 4194304,
  "x-page-max-records": 100,
  "x-operations": {
    "create_run": {
      "params": "CreateRunParams",
      "result": "RunResult"
    },
    "get_run": {
      "params": "GetRunParams",
      "result": "GetRunResult"
    },
    "get_graph": {
      "params": "GetGraphParams",
      "result": "GraphResult"
    },
    "propose_mutation": {
      "params": "ProposeMutationParams",
      "result": "ProposalResult"
    },
    "get_proposal": {
      "params": "GetProposalParams",
      "result": "ProposalResult"
    },
    "get_audit_timeline": {
      "params": "GetAuditTimelineParams",
      "result": "AuditTimelineResult"
    }
  },
  "x-proposal-states": {
    "PENDING": {
      "terminal": false,
      "reason_code": "null",
      "resulting_graph_version": "null",
      "graph_effect": "none",
      "kind": "lifecycle"
    },
    "ABANDONED": {
      "terminal": true,
      "reason_code": "identifier",
      "resulting_graph_version": "null",
      "graph_effect": "none",
      "kind": "lifecycle"
    },
    "COMMIT": {
      "terminal": true,
      "reason_code": "nullable_identifier",
      "resulting_graph_version": "positive_integer",
      "graph_effect": "advance",
      "kind": "governance"
    },
    "REJECT": {
      "terminal": true,
      "reason_code": "identifier",
      "resulting_graph_version": "integer",
      "graph_effect": "preserve",
      "kind": "governance"
    },
    "RETRY": {
      "terminal": true,
      "reason_code": "identifier",
      "resulting_graph_version": "integer",
      "graph_effect": "preserve",
      "kind": "governance"
    },
    "ESCALATE": {
      "terminal": true,
      "reason_code": "identifier",
      "resulting_graph_version": "integer",
      "graph_effect": "preserve",
      "kind": "governance"
    },
    "CONFLICT": {
      "terminal": true,
      "reason_code": "identifier",
      "resulting_graph_version": "integer",
      "graph_effect": "differ",
      "kind": "governance"
    }
  },
  "x-proposal-transitions": {
    "ABSENT": [
      "PENDING"
    ],
    "PENDING": [
      "ABANDONED",
      "COMMIT",
      "REJECT",
      "RETRY",
      "ESCALATE",
      "CONFLICT"
    ],
    "ABANDONED": [],
    "COMMIT": [],
    "REJECT": [],
    "RETRY": [],
    "ESCALATE": [],
    "CONFLICT": []
  },
  "$defs": {
    "Identifier": {
      "type": "string",
      "pattern": "[^\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]",
      "x-max-utf8-bytes": 256
    },
    "NullableIdentifier": {
      "type": [
        "string",
        "null"
      ],
      "pattern": "[^\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]",
      "x-max-utf8-bytes": 256
    },
    "NonEmptyString": {
      "type": "string",
      "pattern": "[^\\u0009-\\u000d\\u001c-\\u0020\\u0085\\u00a0\\u1680\\u2000-\\u200a\\u2028\\u2029\\u202f\\u205f\\u3000\\ufeff]"
    },
    "SafeInteger": {
      "type": "integer",
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "NullableInteger": {
      "type": [
        "integer",
        "null"
      ],
      "minimum": 0,
      "maximum": 9007199254740991
    },
    "PositiveInteger": {
      "type": "integer",
      "minimum": 1,
      "maximum": 9007199254740991
    },
    "Limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100
    },
    "ProtocolVersion": {
      "type": "integer",
      "minimum": 1,
      "maximum": 9007199254740991,
      "const": 1,
      "x-const-error-code": "UNSUPPORTED_PROTOCOL_VERSION"
    },
    "RequestVersion": {
      "type": "integer",
      "minimum": 1,
      "maximum": 9007199254740991,
      "const": 1
    },
    "JsonObject": {
      "type": "object"
    },
    "MetadataHash": {
      "type": "string",
      "pattern": "^sha256:problemforger-run-metadata-v2:[0-9a-f]{64}(?![\\s\\S])",
      "x-canonical-hash": {
        "algorithm": "sha256",
        "prefix": "sha256:problemforger-run-metadata-v2:",
        "domain_separator": "problemforger.run-metadata.v2\u0000",
        "canonicalization": "run-metadata-json-v2"
      }
    },
    "RequestHash": {
      "type": "string",
      "pattern": "^sha256:problemforger-request-v1:[0-9a-f]{64}(?![\\s\\S])"
    },
    "RunMetadata": {
      "type": "object",
      "properties": {
        "metadata_schema_version": {
          "$ref": "#/$defs/RequestVersion"
        },
        "data": {
          "$ref": "#/$defs/JsonObject"
        }
      },
      "required": [
        "metadata_schema_version",
        "data"
      ],
      "additionalProperties": false,
      "x-size-canonicalization": "run-metadata-json-v2",
      "x-max-canonical-bytes": 1048576
    },
    "CreateRunParams": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "run_metadata": {
          "$ref": "#/$defs/RunMetadata"
        }
      },
      "required": [
        "run_id",
        "run_metadata"
      ],
      "additionalProperties": false
    },
    "GetRunParams": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        }
      },
      "required": [
        "run_id"
      ],
      "additionalProperties": false
    },
    "GetGraphParams": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "limit": {
          "$ref": "#/$defs/Limit"
        },
        "selection": {
          "$ref": "#/$defs/JsonObject"
        },
        "after_cursor": {
          "$ref": "#/$defs/Identifier"
        }
      },
      "required": [
        "run_id",
        "limit"
      ],
      "additionalProperties": false
    },
    "ProposeMutationParams": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "proposal_id": {
          "$ref": "#/$defs/Identifier"
        },
        "request_schema_version": {
          "$ref": "#/$defs/RequestVersion"
        },
        "expected_graph_version": {
          "$ref": "#/$defs/SafeInteger"
        },
        "operations": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/JsonObject"
          }
        },
        "evidence": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/JsonObject"
          }
        }
      },
      "required": [
        "run_id",
        "proposal_id",
        "request_schema_version",
        "expected_graph_version",
        "operations",
        "evidence"
      ],
      "additionalProperties": false,
      "x-size-fields": [
        "request_schema_version",
        "expected_graph_version",
        "operations",
        "evidence"
      ],
      "x-max-canonical-bytes": 1048576
    },
    "GetProposalParams": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "proposal_id": {
          "$ref": "#/$defs/Identifier"
        }
      },
      "required": [
        "run_id",
        "proposal_id"
      ],
      "additionalProperties": false
    },
    "GetAuditTimelineParams": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "limit": {
          "$ref": "#/$defs/Limit",
          "x-error-code": "INVALID_LIMIT"
        },
        "after_journal_position": {
          "$ref": "#/$defs/SafeInteger"
        }
      },
      "required": [
        "run_id",
        "limit"
      ],
      "additionalProperties": false
    },
    "Request": {
      "type": "object",
      "properties": {
        "protocol_schema_version": {
          "$ref": "#/$defs/ProtocolVersion"
        },
        "request_id": {
          "$ref": "#/$defs/Identifier"
        },
        "operation": {
          "type": "string",
          "enum": [
            "create_run",
            "get_run",
            "get_graph",
            "propose_mutation",
            "get_proposal",
            "get_audit_timeline"
          ]
        },
        "params": {
          "$ref": "#/$defs/JsonObject"
        }
      },
      "required": [
        "protocol_schema_version",
        "request_id",
        "operation",
        "params"
      ],
      "additionalProperties": false
    },
    "SuccessResponse": {
      "type": "object",
      "properties": {
        "protocol_schema_version": {
          "$ref": "#/$defs/ProtocolVersion"
        },
        "request_id": {
          "$ref": "#/$defs/Identifier"
        },
        "operation": {
          "type": "string",
          "enum": [
            "create_run",
            "get_run",
            "get_graph",
            "propose_mutation",
            "get_proposal",
            "get_audit_timeline"
          ]
        },
        "result": {
          "$ref": "#/$defs/JsonObject"
        }
      },
      "required": [
        "protocol_schema_version",
        "request_id",
        "operation",
        "result"
      ],
      "additionalProperties": false
    },
    "RunResult": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "run_metadata": {
          "$ref": "#/$defs/RunMetadata"
        },
        "metadata_hash": {
          "$ref": "#/$defs/MetadataHash"
        },
        "graph_version": {
          "$ref": "#/$defs/SafeInteger"
        },
        "last_journal_position": {
          "$ref": "#/$defs/SafeInteger"
        },
        "created": {
          "type": "boolean"
        }
      },
      "required": [
        "run_id",
        "run_metadata",
        "metadata_hash",
        "graph_version",
        "last_journal_position",
        "created"
      ],
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "created": {
                "const": true
              }
            }
          },
          "then": {
            "properties": {
              "graph_version": {
                "const": 0
              },
              "last_journal_position": {
                "const": 0
              }
            }
          }
        }
      ],
      "x-version-position": [
        "graph_version",
        "last_journal_position"
      ]
    },
    "GetRunResult": {
      "allOf": [
        {
          "$ref": "#/$defs/RunResult"
        },
        {
          "properties": {
            "created": {
              "const": false
            }
          }
        }
      ]
    },
    "GraphResult": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "graph_schema_version": {
          "$ref": "#/$defs/PositiveInteger"
        },
        "graph_version": {
          "$ref": "#/$defs/SafeInteger"
        },
        "nodes": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/JsonObject"
          }
        },
        "edges": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/JsonObject"
          }
        },
        "next_cursor": {
          "$ref": "#/$defs/NullableIdentifier"
        },
        "has_more": {
          "type": "boolean"
        }
      },
      "required": [
        "run_id",
        "graph_schema_version",
        "graph_version",
        "nodes",
        "edges",
        "next_cursor",
        "has_more"
      ],
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "has_more": {
                "const": true
              }
            }
          },
          "then": {
            "properties": {
              "next_cursor": {
                "$ref": "#/$defs/Identifier"
              }
            }
          }
        }
      ]
    },
    "ProposalResult": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "proposal_id": {
          "$ref": "#/$defs/Identifier"
        },
        "status": {
          "type": "string",
          "enum": [
            "PENDING",
            "ABANDONED",
            "COMMIT",
            "REJECT",
            "RETRY",
            "ESCALATE",
            "CONFLICT"
          ]
        },
        "request_hash": {
          "$ref": "#/$defs/RequestHash"
        },
        "reason_code": {
          "$ref": "#/$defs/NullableIdentifier"
        },
        "resulting_graph_version": {
          "$ref": "#/$defs/NullableInteger"
        },
        "journal_position": {
          "$ref": "#/$defs/PositiveInteger"
        }
      },
      "required": [
        "run_id",
        "proposal_id",
        "status",
        "request_hash",
        "reason_code",
        "resulting_graph_version",
        "journal_position"
      ],
      "additionalProperties": false,
      "x-version-position": [
        "resulting_graph_version",
        "journal_position"
      ],
      "allOf": [
        {
          "if": {
            "properties": {
              "status": {
                "const": "PENDING"
              }
            }
          },
          "then": {
            "properties": {
              "reason_code": {
                "type": "null"
              },
              "resulting_graph_version": {
                "type": "null"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "status": {
                "const": "ABANDONED"
              }
            }
          },
          "then": {
            "properties": {
              "reason_code": {
                "$ref": "#/$defs/Identifier"
              },
              "resulting_graph_version": {
                "type": "null"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "status": {
                "const": "COMMIT"
              }
            }
          },
          "then": {
            "properties": {
              "reason_code": {
                "$ref": "#/$defs/NullableIdentifier"
              },
              "resulting_graph_version": {
                "$ref": "#/$defs/PositiveInteger"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "status": {
                "const": "REJECT"
              }
            }
          },
          "then": {
            "properties": {
              "reason_code": {
                "$ref": "#/$defs/Identifier"
              },
              "resulting_graph_version": {
                "$ref": "#/$defs/SafeInteger"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "status": {
                "const": "RETRY"
              }
            }
          },
          "then": {
            "properties": {
              "reason_code": {
                "$ref": "#/$defs/Identifier"
              },
              "resulting_graph_version": {
                "$ref": "#/$defs/SafeInteger"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "status": {
                "const": "ESCALATE"
              }
            }
          },
          "then": {
            "properties": {
              "reason_code": {
                "$ref": "#/$defs/Identifier"
              },
              "resulting_graph_version": {
                "$ref": "#/$defs/SafeInteger"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "status": {
                "const": "CONFLICT"
              }
            }
          },
          "then": {
            "properties": {
              "reason_code": {
                "$ref": "#/$defs/Identifier"
              },
              "resulting_graph_version": {
                "$ref": "#/$defs/SafeInteger"
              }
            }
          }
        }
      ]
    },
    "AuditRecord": {
      "type": "object",
      "properties": {
        "journal_position": {
          "$ref": "#/$defs/PositiveInteger"
        },
        "record_type": {
          "$ref": "#/$defs/Identifier",
          "enum": [
            "proposal_receipt",
            "non_terminal_audit",
            "mutation_decision",
            "proposal_abandoned",
            "graph_changed"
          ]
        },
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "proposal_id": {
          "$ref": "#/$defs/Identifier"
        },
        "lifecycle_state": {
          "type": "string",
          "enum": [
            "PENDING",
            "ABANDONED"
          ]
        },
        "outcome": {
          "type": "string",
          "enum": [
            "COMMIT",
            "REJECT",
            "RETRY",
            "ESCALATE",
            "CONFLICT"
          ]
        },
        "reason_code": {
          "$ref": "#/$defs/Identifier"
        },
        "graph_version": {
          "$ref": "#/$defs/SafeInteger"
        }
      },
      "required": [
        "journal_position",
        "record_type",
        "run_id"
      ],
      "additionalProperties": false,
      "oneOf": [
        {
          "type": "object",
          "properties": {
            "journal_position": {
              "$ref": "#/$defs/PositiveInteger"
            },
            "record_type": {
              "const": "proposal_receipt"
            },
            "run_id": {
              "$ref": "#/$defs/Identifier"
            },
            "proposal_id": {
              "$ref": "#/$defs/Identifier"
            },
            "lifecycle_state": {
              "const": "PENDING"
            }
          },
          "required": [
            "journal_position",
            "record_type",
            "run_id",
            "proposal_id",
            "lifecycle_state"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "journal_position": {
              "$ref": "#/$defs/PositiveInteger"
            },
            "record_type": {
              "const": "non_terminal_audit"
            },
            "run_id": {
              "$ref": "#/$defs/Identifier"
            },
            "proposal_id": {
              "$ref": "#/$defs/Identifier"
            }
          },
          "required": [
            "journal_position",
            "record_type",
            "run_id"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "journal_position": {
              "$ref": "#/$defs/PositiveInteger"
            },
            "record_type": {
              "const": "mutation_decision"
            },
            "run_id": {
              "$ref": "#/$defs/Identifier"
            },
            "proposal_id": {
              "$ref": "#/$defs/Identifier"
            },
            "outcome": {
              "enum": [
                "COMMIT",
                "REJECT",
                "RETRY",
                "ESCALATE",
                "CONFLICT"
              ]
            },
            "reason_code": {
              "$ref": "#/$defs/Identifier"
            },
            "graph_version": {
              "$ref": "#/$defs/SafeInteger"
            }
          },
          "required": [
            "journal_position",
            "record_type",
            "run_id",
            "proposal_id",
            "outcome",
            "graph_version"
          ],
          "additionalProperties": false,
          "allOf": [
            {
              "if": {
                "properties": {
                  "outcome": {
                    "enum": [
                      "REJECT",
                      "RETRY",
                      "ESCALATE",
                      "CONFLICT"
                    ]
                  }
                }
              },
              "then": {
                "properties": {
                  "reason_code": {
                    "$ref": "#/$defs/Identifier"
                  }
                },
                "required": [
                  "reason_code"
                ]
              }
            },
            {
              "if": {
                "properties": {
                  "outcome": {
                    "const": "COMMIT"
                  }
                }
              },
              "then": {
                "properties": {
                  "graph_version": {
                    "$ref": "#/$defs/PositiveInteger"
                  }
                }
              }
            }
          ]
        },
        {
          "type": "object",
          "properties": {
            "journal_position": {
              "$ref": "#/$defs/PositiveInteger"
            },
            "record_type": {
              "const": "proposal_abandoned"
            },
            "run_id": {
              "$ref": "#/$defs/Identifier"
            },
            "proposal_id": {
              "$ref": "#/$defs/Identifier"
            },
            "lifecycle_state": {
              "const": "ABANDONED"
            },
            "reason_code": {
              "$ref": "#/$defs/Identifier"
            }
          },
          "required": [
            "journal_position",
            "record_type",
            "run_id",
            "proposal_id",
            "lifecycle_state",
            "reason_code"
          ],
          "additionalProperties": false
        },
        {
          "type": "object",
          "properties": {
            "journal_position": {
              "$ref": "#/$defs/PositiveInteger"
            },
            "record_type": {
              "const": "graph_changed"
            },
            "run_id": {
              "$ref": "#/$defs/Identifier"
            },
            "proposal_id": {
              "$ref": "#/$defs/Identifier"
            },
            "graph_version": {
              "$ref": "#/$defs/PositiveInteger"
            }
          },
          "required": [
            "journal_position",
            "record_type",
            "run_id",
            "proposal_id",
            "graph_version"
          ],
          "additionalProperties": false
        }
      ],
      "x-version-position": [
        "graph_version",
        "journal_position"
      ]
    },
    "AuditTimelineResult": {
      "type": "object",
      "properties": {
        "run_id": {
          "$ref": "#/$defs/Identifier"
        },
        "records": {
          "type": "array",
          "items": {
            "$ref": "#/$defs/AuditRecord"
          },
          "maxItems": 100,
          "x-error-code": "INVALID_LIMIT"
        },
        "next_after_journal_position": {
          "$ref": "#/$defs/SafeInteger"
        },
        "has_more": {
          "type": "boolean"
        }
      },
      "required": [
        "run_id",
        "records",
        "next_after_journal_position",
        "has_more"
      ],
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "records": {
                "maxItems": 0
              }
            }
          },
          "then": {
            "properties": {
              "has_more": {
                "const": false
              }
            }
          }
        }
      ]
    },
    "Error": {
      "type": "object",
      "properties": {
        "code": {
          "type": "string",
          "enum": [
            "PROTOCOL_ERROR",
            "UNSUPPORTED_PROTOCOL_VERSION",
            "UNAUTHORIZED",
            "NOT_FOUND",
            "RUN_METADATA_CONFLICT",
            "IDEMPOTENCY_CONFLICT",
            "INVALID_LIMIT",
            "PAYLOAD_TOO_LARGE",
            "STORE_IN_USE"
          ]
        },
        "message": {
          "$ref": "#/$defs/NonEmptyString"
        }
      },
      "required": [
        "code",
        "message"
      ],
      "additionalProperties": false
    },
    "ErrorResponse": {
      "type": "object",
      "properties": {
        "protocol_schema_version": {
          "$ref": "#/$defs/ProtocolVersion"
        },
        "request_id": {
          "$ref": "#/$defs/NullableIdentifier"
        },
        "error": {
          "$ref": "#/$defs/Error"
        }
      },
      "required": [
        "protocol_schema_version",
        "request_id",
        "error"
      ],
      "additionalProperties": false,
      "allOf": [
        {
          "if": {
            "properties": {
              "error": {
                "properties": {
                  "code": {
                    "const": "PROTOCOL_ERROR"
                  }
                }
              }
            }
          },
          "then": {
            "properties": {
              "request_id": {
                "$ref": "#/$defs/NullableIdentifier"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "error": {
                "properties": {
                  "code": {
                    "const": "UNSUPPORTED_PROTOCOL_VERSION"
                  }
                }
              }
            }
          },
          "then": {
            "properties": {
              "request_id": {
                "$ref": "#/$defs/NullableIdentifier"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "error": {
                "properties": {
                  "code": {
                    "const": "UNAUTHORIZED"
                  }
                }
              }
            }
          },
          "then": {
            "properties": {
              "request_id": {
                "$ref": "#/$defs/Identifier"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "error": {
                "properties": {
                  "code": {
                    "const": "NOT_FOUND"
                  }
                }
              }
            }
          },
          "then": {
            "properties": {
              "request_id": {
                "$ref": "#/$defs/Identifier"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "error": {
                "properties": {
                  "code": {
                    "const": "RUN_METADATA_CONFLICT"
                  }
                }
              }
            }
          },
          "then": {
            "properties": {
              "request_id": {
                "$ref": "#/$defs/Identifier"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "error": {
                "properties": {
                  "code": {
                    "const": "IDEMPOTENCY_CONFLICT"
                  }
                }
              }
            }
          },
          "then": {
            "properties": {
              "request_id": {
                "$ref": "#/$defs/Identifier"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "error": {
                "properties": {
                  "code": {
                    "const": "INVALID_LIMIT"
                  }
                }
              }
            }
          },
          "then": {
            "properties": {
              "request_id": {
                "$ref": "#/$defs/Identifier"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "error": {
                "properties": {
                  "code": {
                    "const": "PAYLOAD_TOO_LARGE"
                  }
                }
              }
            }
          },
          "then": {
            "properties": {
              "request_id": {
                "$ref": "#/$defs/NullableIdentifier"
              }
            }
          }
        },
        {
          "if": {
            "properties": {
              "error": {
                "properties": {
                  "code": {
                    "const": "STORE_IN_USE"
                  }
                }
              }
            }
          },
          "then": {
            "properties": {
              "request_id": {
                "type": "null"
              }
            }
          }
        }
      ]
    }
  },
  "x-errors": {
    "PROTOCOL_ERROR": "nullable_identifier",
    "UNSUPPORTED_PROTOCOL_VERSION": "nullable_identifier",
    "UNAUTHORIZED": "identifier",
    "NOT_FOUND": "identifier",
    "RUN_METADATA_CONFLICT": "identifier",
    "IDEMPOTENCY_CONFLICT": "identifier",
    "INVALID_LIMIT": "identifier",
    "PAYLOAD_TOO_LARGE": "nullable_identifier",
    "STORE_IN_USE": "null"
  }
} as const;
