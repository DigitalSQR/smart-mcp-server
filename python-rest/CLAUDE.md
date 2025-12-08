# CLAUDE.md - FHIR MCP Server Implementation Guide

## Overview

This is a Model Context Protocol (MCP) server that enables AI assistants to interact with FHIR R4 healthcare data servers. It provides tools for working with clinical protocols (PlanDefinitions), managing healthcare resources, and querying medical terminology.

## Key Capabilities

### 1. PlanDefinition & CarePlan Workflow

The server supports the complete workflow for clinical protocols:

1. **List PlanDefinitions**: Discover available clinical protocols
2. **Get PlanDefinition Details**: Inspect actions, conditions, and requirements
3. **Apply PlanDefinition**: Generate a CarePlan for a specific patient
4. **Create Supporting Resources**: Create any required resources (Observations, Immunizations, etc.)

### 2. Generic Resource Management

The `fhir_create_resource` tool accepts **raw FHIR JSON**, enabling creation of any valid FHIR R4 resource without being limited to predefined schemas. This is critical for:

- Supporting any resource type the plan definition requires
- Creating Observations with the appropriate codes
- Maintaining flexibility for different implementation guides

### 3. Terminology Services

- **CodeSystem $lookup**: Find display names and properties for codes
- **ValueSet $expand**: Get all codes in a value set
- Search and list CodeSystems and ValueSets

### 4. ImplementationGuide Context

Users can set an ImplementationGuide context to inform the AI about:
- Which profiles to use
- What codes are appropriate
- Dependencies and constraints

## Tool Summary

| Tool | Purpose | Read-Only |
|------|---------|-----------|
| `fhir_list_plan_definitions` | List available clinical protocols | ✅ |
| `fhir_get_plan_definition` | Get protocol details with actions | ✅ |
| `fhir_apply_plan_definition` | Generate CarePlan from protocol | ✅ |
| `fhir_create_resource` | Create any FHIR resource | ❌ |
| `fhir_update_resource` | Update existing resource | ❌ |
| `fhir_get_resource` | Retrieve resource by type/ID | ✅ |
| `fhir_search_resources` | Search resources with params | ✅ |
| `fhir_delete_resource` | Delete a resource | ❌ |
| `fhir_lookup_code` | Look up code in CodeSystem | ✅ |
| `fhir_expand_valueset` | Expand ValueSet to get codes | ✅ |
| `fhir_list_codesystems` | List available CodeSystems | ✅ |
| `fhir_list_valuesets` | List available ValueSets | ✅ |
| `fhir_list_implementation_guides` | List IGs on server | ✅ |
| `fhir_get_implementation_guide` | Get IG details | ✅ |
| `fhir_set_implementation_guide_context` | Set active IG context | ❌ |
| `fhir_get_current_implementation_guide_context` | View current IG | ✅ |
| `fhir_get_server_capability` | Get server capabilities | ✅ |

## Immunization Use Case

For immunization workflows, the typical pattern is:

```
1. User: "Apply the immunization plan for Patient/123"

2. Agent actions:
   a. Call fhir_list_plan_definitions to find immunization protocols
   b. Call fhir_get_plan_definition to understand requirements
   c. Call fhir_apply_plan_definition with subject=Patient/123
   d. Parse the returned CarePlan to understand needed activities
   e. For each activity:
      - If Immunization needed: use fhir_create_resource with Immunization JSON
      - If Observation needed: use fhir_create_resource with Observation JSON
      - Look up appropriate codes using fhir_expand_valueset or fhir_lookup_code

3. Response: Summarize what was created and any pending items
```

## Code Discovery

When creating Observations or other coded resources:

1. **Check ImplementationGuide**: Get context for appropriate code systems
2. **Expand ValueSets**: Find valid codes for specific fields
3. **Lookup Codes**: Get display names and verify codes exist

Example for finding observation codes:
```
1. fhir_list_valuesets with name filter for "observation"
2. fhir_expand_valueset to get codes
3. Select appropriate code based on context
4. fhir_create_resource with properly coded Observation
```

## Creating Resources with Raw JSON

The `fhir_create_resource` tool requires a complete, valid FHIR JSON string. Example:

```json
{
  "resourceType": "Observation",
  "status": "final",
  "category": [{
    "coding": [{
      "system": "http://terminology.hl7.org/CodeSystem/observation-category",
      "code": "vital-signs",
      "display": "Vital Signs"
    }]
  }],
  "code": {
    "coding": [{
      "system": "http://loinc.org",
      "code": "8302-2",
      "display": "Body height"
    }]
  },
  "subject": {
    "reference": "Patient/123"
  },
  "valueQuantity": {
    "value": 170,
    "unit": "cm",
    "system": "http://unitsofmeasure.org",
    "code": "cm"
  }
}
```

## Error Handling

The server provides detailed error messages including:
- FHIR OperationOutcome parsing for server errors
- HTTP status code explanations
- Actionable suggestions for common issues

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `FHIR_SERVER_URL` | `http://localhost:8080/fhir` | FHIR server base URL |

## Best Practices for AI Agents

1. **Always check server capabilities first** when unsure about supported operations
2. **Use ImplementationGuide context** to understand expected profiles and codes
3. **Validate codes exist** before creating resources with coded elements
4. **Parse CarePlan activities** carefully after applying PlanDefinitions
5. **Create resources incrementally** and handle errors gracefully
6. **Use search** to find existing resources before creating duplicates

## FHIR R4 Reference

Key resources for this server:
- [PlanDefinition](https://hl7.org/fhir/R4/plandefinition.html)
- [CarePlan](https://hl7.org/fhir/R4/careplan.html)
- [Observation](https://hl7.org/fhir/R4/observation.html)
- [Immunization](https://hl7.org/fhir/R4/immunization.html)
- [CodeSystem](https://hl7.org/fhir/R4/codesystem.html)
- [ValueSet](https://hl7.org/fhir/R4/valueset.html)
- [ImplementationGuide](https://hl7.org/fhir/R4/implementationguide.html)