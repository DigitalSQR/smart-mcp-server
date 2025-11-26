# CLAUDE.md - FHIR PlanDefinition MCP Server

## Overview

This MCP server provides FHIR R4 PlanDefinition capabilities to Claude. It connects to a FHIR server and enables listing and applying PlanDefinitions.

## Tools Available

### list_plan_definitions
Lists PlanDefinition resources from the FHIR server.

**Parameters:**
- `status` (optional): Filter by status (draft, active, retired, unknown)
- `name` (optional): Filter by name (partial match)
- `count` (optional): Maximum results to return (default: 20)

**Example usage:**
- List all: `list_plan_definitions()`
- Filter by status: `list_plan_definitions(status="active")`
- Search by name: `list_plan_definitions(name="diabetes")`

### apply_plan_definition
Applies a PlanDefinition to a subject using the FHIR $apply operation.

**Parameters:**
- `plan_definition_id` (required): The ID of the PlanDefinition to apply
- `subject` (required): Reference to the subject (e.g., "Patient/123" or just "123")

**Example usage:**
- `apply_plan_definition(plan_definition_id="example", subject="Patient/123")`
- `apply_plan_definition(plan_definition_id="diabetes-mgmt", subject="456")`

## FHIR R4 Context

### PlanDefinition Resource
A PlanDefinition represents a pre-defined group of actions to be taken in particular circumstances. Common use cases include:
- Order sets
- Clinical protocols
- Care pathways
- Decision support rules

### $apply Operation
The $apply operation instantiates a PlanDefinition for a specific context (subject). In FHIR R4, it typically returns:
- A CarePlan with activities
- Contained resources (ServiceRequest, MedicationRequest, etc.)

## Configuration

The server connects to: `http://localhost:8080/fhir` by default.

To change the FHIR server URL, set the `FHIR_BASE_URL` environment variable.

## Error Handling

The server handles:
- Connection errors (FHIR server unavailable)
- HTTP errors (4xx, 5xx responses)
- FHIR OperationOutcome responses
- Missing required parameters

## Best Practices for Claude

1. **Always list first**: Before applying a PlanDefinition, list available ones to get valid IDs
2. **Verify subjects exist**: The subject (Patient, etc.) must exist on the FHIR server
3. **Check status**: Only "active" PlanDefinitions are typically meant for production use
4. **Review results**: The $apply result shows what actions would be taken - review before actual implementation