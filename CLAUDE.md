# CLAUDE.md - FHIR MCP Server Implementation Guide

This document provides guidance for AI agents using the FHIR MCP Server.

## Overview

This MCP server enables interaction with FHIR R4 servers for clinical decision support workflows. It supports PlanDefinition execution, resource management, terminology services, and Questionnaire-based data capture with StructureMap transformation.

## Key Concepts

### ImplementationGuide Context
Before creating resources, set the ImplementationGuide context to enable profile validation:
```
fhir_set_implementation_guide_context(implementation_guide_id="my-ig-id")
```

### PlanDefinition Workflow
1. List available PlanDefinitions
2. Get PlanDefinition details to understand required inputs
3. Ensure required resources exist (Patient, Observations, etc.)
4. Apply the PlanDefinition to generate a CarePlan
5. Process the CarePlan activities

### Questionnaire Workflow
1. Get the Questionnaire structure
2. Ask the user each question based on Questionnaire items
3. Construct a QuestionnaireResponse JSON
4. Transform via Matchbox to create FHIR resources
5. Save the transformed resources to the FHIR server

## Tool Reference

### Context Management
- `fhir_set_implementation_guide_context` - Set IG for validation
- `fhir_get_current_implementation_guide_context` - Check current IG
- `fhir_get_implementation_guide` - Get IG details
- `fhir_list_implementation_guides` - List available IGs

### PlanDefinition
- `fhir_list_plan_definitions` - List with optional status/title filters
- `fhir_get_plan_definition` - Get full details including actions
- `fhir_apply_plan_definition` - Execute $apply operation

### Resources
- `fhir_get_resource` - Get by type and ID
- `fhir_search_resources` - Search with FHIR parameters
- `fhir_create_resource` - Create using raw JSON
- `fhir_update_resource` - Update existing resource
- `fhir_delete_resource` - Delete resource

### Terminology
- `fhir_list_valuesets` - List ValueSets
- `fhir_expand_valueset` - Get codes in a ValueSet
- `fhir_list_codesystems` - List CodeSystems
- `fhir_lookup_code` - Look up code display/properties

### Questionnaire
- `fhir_get_questionnaire` - Get questionnaire structure
- `fhir_list_questionnaires` - List available questionnaires
- `fhir_transform_questionnaire_response` - Transform via StructureMap

### Server
- `fhir_get_server_capability` - Get CapabilityStatement

## Creating Resources

Always use `fhir_create_resource` with complete FHIR JSON:

```json
{
  "resourceType": "Patient",
  "name": [{"family": "Smith", "given": ["John"]}],
  "birthDate": "1980-01-15",
  "gender": "male"
}
```

For Observations, look up appropriate codes first:
```
fhir_expand_valueset(valueset_url="http://hl7.org/fhir/ValueSet/observation-codes")
fhir_lookup_code(system="http://loinc.org", code="8867-4")
```

## QuestionnaireResponse Structure

When building a QuestionnaireResponse:

```json
{
  "resourceType": "QuestionnaireResponse",
  "questionnaire": "Questionnaire/my-questionnaire",
  "status": "completed",
  "subject": {"reference": "Patient/123"},
  "item": [
    {
      "linkId": "question-1",
      "answer": [{"valueString": "User's answer"}]
    },
    {
      "linkId": "question-2",
      "answer": [{"valueDate": "2024-01-15"}]
    }
  ]
}
```

## Error Handling

The server returns structured error messages:
- `❌ Error:` - General errors
- `❌ HTTP Error:` - FHIR server HTTP errors
- `❌ Validation Error:` - Resource validation failures
- `❌ Operation Error:` - FHIR operation failures
- `❌ Transform Error:` - StructureMap transformation failures

Always check for OperationOutcome details in error responses.

## Best Practices

1. **Always set IG context** before creating profiled resources
2. **Use terminology tools** to find correct codes
3. **Validate Questionnaire items** before building responses
4. **Check PlanDefinition inputs** before applying
5. **Use response_format="json"** when you need to process data programmatically
6. **Use response_format="markdown"** for human-readable summaries

## Environment Configuration

- `FHIR_SERVER_URL` - Main FHIR server (default: http://localhost:8080/fhir)
- `MATCHBOX_SERVER_URL` - Matchbox for transforms (default: http://localhost:8081/matchboxv3/fhir)