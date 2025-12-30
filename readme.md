# FHIR MCP Server

A Model Context Protocol (MCP) server that provides comprehensive FHIR R4 operations including PlanDefinition $apply, resource management, terminology services, and Questionnaire/StructureMap transformation via Matchbox.

## Purpose

This MCP server provides a secure interface for AI assistants to interact with FHIR R4 servers, enabling clinical decision support workflows through PlanDefinitions, resource creation/management, terminology lookups, and structured data capture via Questionnaires.

## Features

### ImplementationGuide Context Management
- **`fhir_set_implementation_guide_context`** - Set the IG context for resource validation
- **`fhir_get_current_implementation_guide_context`** - Get the currently set IG context
- **`fhir_get_implementation_guide`** - Retrieve full IG details by ID or URL
- **`fhir_list_implementation_guides`** - List available IGs on the server

### PlanDefinition Operations
- **`fhir_list_plan_definitions`** - List available PlanDefinitions with filters
- **`fhir_get_plan_definition`** - Get full PlanDefinition details including actions
- **`fhir_apply_plan_definition`** - Execute $apply to generate a CarePlan

### Generic Resource Operations
- **`fhir_get_resource`** - Retrieve any FHIR resource by type and ID
- **`fhir_search_resources`** - Search resources with FHIR search parameters
- **`fhir_create_resource`** - Create any FHIR resource using raw JSON
- **`fhir_update_resource`** - Update an existing resource
- **`fhir_delete_resource`** - Delete a resource

### Terminology Services
- **`fhir_list_valuesets`** - List available ValueSets
- **`fhir_expand_valueset`** - Expand a ValueSet to get all codes
- **`fhir_list_codesystems`** - List available CodeSystems
- **`fhir_lookup_code`** - Look up a code's display and properties

### Questionnaire Operations
- **`fhir_get_questionnaire`** - Retrieve a Questionnaire for data capture
- **`fhir_list_questionnaires`** - List available Questionnaires
- **`fhir_transform_questionnaire_response`** - Transform via StructureMap on Matchbox

### Server Information
- **`fhir_get_server_capability`** - Get the server's CapabilityStatement

## Prerequisites

- Docker Desktop with MCP Toolkit enabled
- Docker MCP CLI plugin (`docker mcp` command)
- FHIR R4 server running (default: http://localhost:8080/fhir)
- Matchbox server for StructureMap transforms (default: http://localhost:8081/matchboxv3/fhir)

## Configuration

Environment variables:
- `FHIR_SERVER_URL` - Base URL of the FHIR server (default: http://localhost:8080/fhir)
- `MATCHBOX_SERVER_URL` - Base URL of Matchbox server (default: http://localhost:8081/matchboxv3/fhir)

## Installation

See the step-by-step instructions provided with the files.

## Usage Examples

In Claude Desktop, you can ask:

### ImplementationGuide Context
- "Set the implementation guide context to the WHO SMART Guidelines IG"
- "What implementation guide are we currently using?"
- "List all available implementation guides"

### PlanDefinition Workflows
- "List all active plan definitions"
- "Show me the details of the diabetes screening plan definition"
- "Apply the immunization plan definition to Patient/123"
- "What actions are defined in PlanDefinition/anc-contact?"

### Resource Management
- "Create a new Patient resource with name John Smith, born 1980-01-15"
- "Search for all Observations for Patient/123"
- "Get the Condition with ID abc123"
- "Delete the Observation with ID temp-obs-1"

### Terminology
- "List ValueSets related to pregnancy"
- "Expand the administrative gender ValueSet"
- "Look up LOINC code 8867-4"
- "What codes are in the observation category CodeSystem?"

### Questionnaire Workflow
- "Get the ANC registration questionnaire"
- "List all active questionnaires"
- "Transform this QuestionnaireResponse using the ANC StructureMap"

## Architecture

```
Claude Desktop → MCP Gateway → FHIR MCP Server → FHIR Server (localhost:8080)
                                       ↓
                               Matchbox Server (localhost:8081)
                               (for StructureMap transforms)
```

## Workflow: Using Questionnaires to Create Resources

1. **Get the Questionnaire**: Use `fhir_get_questionnaire` to retrieve the questionnaire structure
2. **Ask Questions**: The agent asks the user each question based on the Questionnaire items
3. **Build QuestionnaireResponse**: The agent constructs the QuestionnaireResponse JSON
4. **Transform**: Use `fhir_transform_questionnaire_response` to convert to FHIR resources via Matchbox
5. **Create Resources**: The transformed Bundle can be processed to create individual resources

## Workflow: Applying PlanDefinitions

1. **Set Context**: Use `fhir_set_implementation_guide_context` to set the IG
2. **Find PlanDefinition**: Use `fhir_list_plan_definitions` to find available plans
3. **Review Requirements**: Use `fhir_get_plan_definition` to see what data is needed
4. **Prepare Data**: Create required resources (Patient, Observations, etc.)
5. **Apply**: Use `fhir_apply_plan_definition` to generate the CarePlan
6. **Process**: The agent processes the returned CarePlan activities

## Development

### Local Testing

```bash
# Set environment variables for testing
export FHIR_SERVER_URL="http://localhost:8080/fhir"
export MATCHBOX_SERVER_URL="http://localhost:8081/matchboxv3/fhir"

# Run directly
python fhir_server.py

# Test MCP protocol
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | python fhir_server.py
```

### Adding New Tools

1. Add the function to `fhir_server.py`
2. Decorate with `@mcp.tool()`
3. Use SINGLE-LINE docstrings only
4. Use empty string defaults for parameters
5. Update the catalog entry with the new tool name
6. Rebuild the Docker image

## Troubleshooting

### Tools Not Appearing
- Verify Docker image built successfully
- Check catalog and registry files
- Ensure Claude Desktop config includes custom catalog
- Restart Claude Desktop

### FHIR Server Connection Errors
- Verify FHIR server is running and accessible
- Check the FHIR_SERVER_URL environment variable
- Test with: `curl http://localhost:8080/fhir/metadata`

### Matchbox Transform Errors
- Verify Matchbox server is running
- Check that the StructureMap exists and is valid
- Ensure QuestionnaireResponse references the correct Questionnaire

### Validation Errors
- Set the ImplementationGuide context before creating resources
- Check that resources conform to the expected profiles
- Review the OperationOutcome details in error messages

## Security Considerations

- No authentication configured by default (suitable for local development)
- For production, configure FHIR server authentication
- Running as non-root user in Docker
- Sensitive data never logged

## FHIR Resources

- FHIR R4 Specification: https://hl7.org/fhir/R4/
- PlanDefinition: https://hl7.org/fhir/R4/plandefinition.html
- $apply Operation: https://hl7.org/fhir/R4/plandefinition-operation-apply.html
- Questionnaire: https://hl7.org/fhir/R4/questionnaire.html
- StructureMap: https://hl7.org/fhir/R4/structuremap.html

## License

MIT License