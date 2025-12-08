#!/usr/bin/env python3
"""
FHIR MCP Server - A Model Context Protocol server for interacting with FHIR R4 servers.

This server provides tools to work with PlanDefinitions, apply care plans,
create FHIR resources, and query terminology (CodeSystems, ValueSets).
"""

import os
import sys
import json
import logging
from typing import Optional, Dict, Any
from enum import Enum
import httpx
from pydantic import BaseModel, Field, ConfigDict
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("fhir-mcp-server")

# Initialize MCP server
mcp = FastMCP("fhir_mcp")

# Configuration
FHIR_SERVER_URL = os.environ.get("FHIR_SERVER_URL", "http://localhost:8080/fhir")
DEFAULT_TIMEOUT = 60.0

# Store the current ImplementationGuide context
_implementation_guide_context: Dict[str, Any] = {}


# === Enums ===
class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# === Pydantic Input Models ===
class ListPlanDefinitionsInput(BaseModel):
    """Input for listing PlanDefinitions."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    status: str = Field(default="", description="Filter by status (draft, active, retired, unknown)")
    title: str = Field(default="", description="Filter by title (partial match)")
    count: str = Field(default="100", description="Maximum number of results to return")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format: markdown or json")


class GetPlanDefinitionInput(BaseModel):
    """Input for getting a specific PlanDefinition."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    plan_definition_id: str = Field(..., description="The ID of the PlanDefinition to retrieve", min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format: markdown or json")


class ApplyPlanDefinitionInput(BaseModel):
    """Input for applying a PlanDefinition to generate a CarePlan."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    plan_definition_id: str = Field(..., description="The ID of the PlanDefinition to apply", min_length=1)
    subject: str = Field(..., description="Reference to the subject (e.g., Patient/123)", min_length=1)
    encounter: str = Field(default="", description="Reference to the encounter (e.g., Encounter/456)")
    practitioner: str = Field(default="", description="Reference to the practitioner (e.g., Practitioner/789)")
    organization: str = Field(default="", description="Reference to the organization (e.g., Organization/abc)")


class CreateResourceInput(BaseModel):
    """Input for creating a FHIR resource using raw JSON."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    resource_json: str = Field(..., description="The complete FHIR resource as a JSON string", min_length=2)


class UpdateResourceInput(BaseModel):
    """Input for updating a FHIR resource using raw JSON."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    resource_type: str = Field(..., description="The FHIR resource type (e.g., Patient, Observation)", min_length=1)
    resource_id: str = Field(..., description="The ID of the resource to update", min_length=1)
    resource_json: str = Field(..., description="The complete FHIR resource as a JSON string", min_length=2)


class GetResourceInput(BaseModel):
    """Input for retrieving a FHIR resource."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    resource_type: str = Field(..., description="The FHIR resource type (e.g., Patient, Observation)", min_length=1)
    resource_id: str = Field(..., description="The ID of the resource to retrieve", min_length=1)
    response_format: ResponseFormat = Field(default=ResponseFormat.JSON, description="Output format: markdown or json")


class SearchResourceInput(BaseModel):
    """Input for searching FHIR resources."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    resource_type: str = Field(..., description="The FHIR resource type to search (e.g., Patient, Observation)", min_length=1)
    search_params: str = Field(default="", description="URL-encoded search parameters (e.g., 'name=John&birthdate=1990-01-01')")
    count: str = Field(default="50", description="Maximum number of results to return")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format: markdown or json")


class LookupCodeInput(BaseModel):
    """Input for looking up a code in a CodeSystem."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    system: str = Field(..., description="The CodeSystem URL (e.g., http://loinc.org)", min_length=1)
    code: str = Field(..., description="The code to look up", min_length=1)
    version: str = Field(default="", description="Optional CodeSystem version")


class ExpandValueSetInput(BaseModel):
    """Input for expanding a ValueSet."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    valueset_url: str = Field(default="", description="The canonical URL of the ValueSet to expand")
    valueset_id: str = Field(default="", description="The ID of the ValueSet to expand (alternative to URL)")
    filter: str = Field(default="", description="Text filter to apply to the expansion")
    count: str = Field(default="100", description="Maximum number of codes to return")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format: markdown or json")


class ListCodeSystemsInput(BaseModel):
    """Input for listing available CodeSystems."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    name: str = Field(default="", description="Filter by name (partial match)")
    url: str = Field(default="", description="Filter by URL (partial match)")
    count: str = Field(default="50", description="Maximum number of results to return")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format: markdown or json")


class ListValueSetsInput(BaseModel):
    """Input for listing available ValueSets."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    name: str = Field(default="", description="Filter by name (partial match)")
    url: str = Field(default="", description="Filter by URL (partial match)")
    count: str = Field(default="50", description="Maximum number of results to return")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format: markdown or json")


class SetImplementationGuideInput(BaseModel):
    """Input for setting the current ImplementationGuide context."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    implementation_guide_id: str = Field(default="", description="The ID of the ImplementationGuide resource")
    implementation_guide_url: str = Field(default="", description="The canonical URL of the ImplementationGuide (alternative to ID)")


class GetImplementationGuideInput(BaseModel):
    """Input for retrieving an ImplementationGuide."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    implementation_guide_id: str = Field(default="", description="The ID of the ImplementationGuide to retrieve")
    implementation_guide_url: str = Field(default="", description="The canonical URL of the ImplementationGuide (alternative to ID)")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format: markdown or json")


class ListImplementationGuidesInput(BaseModel):
    """Input for listing available ImplementationGuides."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    name: str = Field(default="", description="Filter by name (partial match)")
    count: str = Field(default="50", description="Maximum number of results to return")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN, description="Output format: markdown or json")


class DeleteResourceInput(BaseModel):
    """Input for deleting a FHIR resource."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)
    
    resource_type: str = Field(..., description="The FHIR resource type (e.g., Patient, Observation)", min_length=1)
    resource_id: str = Field(..., description="The ID of the resource to delete", min_length=1)


# === Utility Functions ===
async def _make_fhir_request(
    endpoint: str,
    method: str = "GET",
    json_data: dict = None,
    params: dict = None,
    headers: dict = None
) -> dict:
    """Make an HTTP request to the FHIR server."""
    url = f"{FHIR_SERVER_URL}/{endpoint}"
    
    default_headers = {
        "Accept": "application/fhir+json",
        "Content-Type": "application/fhir+json"
    }
    if headers:
        default_headers.update(headers)
    
    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=method,
            url=url,
            json=json_data,
            params=params,
            headers=default_headers,
            timeout=DEFAULT_TIMEOUT
        )
        response.raise_for_status()
        
        if response.status_code == 204:
            return {"status": "success", "message": "Resource deleted successfully"}
        
        return response.json()


def _handle_fhir_error(e: Exception) -> str:
    """Format FHIR-specific error messages."""
    if isinstance(e, httpx.HTTPStatusError):
        status_code = e.response.status_code
        try:
            error_body = e.response.json()
            if error_body.get("resourceType") == "OperationOutcome":
                issues = error_body.get("issue", [])
                error_msgs = []
                for issue in issues:
                    severity = issue.get("severity", "error")
                    msg = issue.get("diagnostics", issue.get("details", {}).get("text", "Unknown error"))
                    error_msgs.append(f"[{severity}] {msg}")
                return f"❌ FHIR Error ({status_code}):\n" + "\n".join(error_msgs)
        except Exception:
            pass
        
        if status_code == 404:
            return "❌ Error: Resource not found. Please verify the resource type and ID."
        elif status_code == 400:
            return f"❌ Error: Bad request. Check your input parameters.\nDetails: {e.response.text[:500]}"
        elif status_code == 422:
            return f"❌ Error: Unprocessable entity. The resource failed validation.\nDetails: {e.response.text[:500]}"
        elif status_code == 409:
            return "❌ Error: Conflict. The resource may already exist or there's a version conflict."
        return f"❌ Error: FHIR server returned status {status_code}\nDetails: {e.response.text[:500]}"
    
    elif isinstance(e, httpx.TimeoutException):
        return "❌ Error: Request timed out. The FHIR server may be slow or unavailable."
    elif isinstance(e, httpx.ConnectError):
        return f"❌ Error: Could not connect to FHIR server at {FHIR_SERVER_URL}. Please verify the server is running."
    
    return f"❌ Error: Unexpected error - {type(e).__name__}: {str(e)}"


def _format_plan_definition(pd: dict, include_actions: bool = True) -> str:
    """Format a PlanDefinition for markdown display."""
    lines = []
    lines.append(f"## {pd.get('title', pd.get('name', 'Untitled'))}")
    lines.append(f"**ID**: {pd.get('id', 'N/A')}")
    lines.append(f"**Status**: {pd.get('status', 'N/A')}")
    
    if pd.get('url'):
        lines.append(f"**URL**: {pd.get('url')}")
    if pd.get('version'):
        lines.append(f"**Version**: {pd.get('version')}")
    if pd.get('description'):
        lines.append(f"**Description**: {pd.get('description')}")
    if pd.get('publisher'):
        lines.append(f"**Publisher**: {pd.get('publisher')}")
    
    # Goals
    goals = pd.get('goal', [])
    if goals:
        lines.append("\n### Goals")
        for goal in goals:
            desc = goal.get('description', {})
            text = desc.get('text', 'No description')
            lines.append(f"- {text}")
    
    # Actions
    if include_actions:
        actions = pd.get('action', [])
        if actions:
            lines.append("\n### Actions")
            _format_actions(actions, lines, indent=0)
    
    lines.append("")
    return "\n".join(lines)


def _format_actions(actions: list, lines: list, indent: int = 0) -> None:
    """Recursively format PlanDefinition actions."""
    prefix = "  " * indent
    for i, action in enumerate(actions):
        title = action.get('title', action.get('description', f'Action {i+1}'))
        lines.append(f"{prefix}- **{title}**")
        
        if action.get('description') and action.get('title'):
            lines.append(f"{prefix}  Description: {action.get('description')}")
        
        # Definition reference
        if action.get('definitionCanonical'):
            lines.append(f"{prefix}  Definition: {action.get('definitionCanonical')}")
        
        # Timing
        timing = action.get('timingTiming', action.get('timingDateTime', action.get('timingPeriod')))
        if timing:
            lines.append(f"{prefix}  Timing: {json.dumps(timing)}")
        
        # Required behavior
        if action.get('requiredBehavior'):
            lines.append(f"{prefix}  Required: {action.get('requiredBehavior')}")
        
        # Conditions
        conditions = action.get('condition', [])
        for cond in conditions:
            kind = cond.get('kind', 'unknown')
            expr = cond.get('expression', {})
            lines.append(f"{prefix}  Condition ({kind}): {expr.get('expression', 'N/A')}")
        
        # Inputs/Outputs
        inputs = action.get('input', [])
        if inputs:
            lines.append(f"{prefix}  Inputs: {', '.join([i.get('type', 'unknown') for i in inputs])}")
        
        outputs = action.get('output', [])
        if outputs:
            lines.append(f"{prefix}  Outputs: {', '.join([o.get('type', 'unknown') for o in outputs])}")
        
        # Nested actions
        sub_actions = action.get('action', [])
        if sub_actions:
            _format_actions(sub_actions, lines, indent + 1)


def _format_bundle_entry(entry: dict) -> str:
    """Format a bundle entry for display."""
    resource = entry.get('resource', {})
    resource_type = resource.get('resourceType', 'Unknown')
    resource_id = resource.get('id', 'N/A')
    
    lines = [f"### {resource_type}/{resource_id}"]
    
    # Common fields
    if resource.get('status'):
        lines.append(f"**Status**: {resource.get('status')}")
    if resource.get('intent'):
        lines.append(f"**Intent**: {resource.get('intent')}")
    
    # Subject
    subject = resource.get('subject', {})
    if subject.get('reference'):
        lines.append(f"**Subject**: {subject.get('reference')}")
    
    return "\n".join(lines)


# === MCP Tools ===

@mcp.tool(
    name="fhir_list_plan_definitions",
    annotations={
        "title": "List FHIR PlanDefinitions",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_list_plan_definitions(params: ListPlanDefinitionsInput) -> str:
    """List available PlanDefinition resources from the FHIR server with optional filters."""
    logger.info(f"Listing PlanDefinitions with filters: status={params.status}, title={params.title}")
    
    try:
        search_params = {"_count": params.count}
        if params.status.strip():
            search_params["status"] = params.status.strip()
        if params.title.strip():
            search_params["title:contains"] = params.title.strip()
        
        result = await _make_fhir_request("PlanDefinition", params=search_params)
        
        entries = result.get("entry", [])
        total = result.get("total", len(entries))
        
        if not entries:
            return "📋 No PlanDefinitions found matching the specified criteria."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2)
        
        lines = [f"# PlanDefinitions ({len(entries)} of {total})", ""]
        for entry in entries:
            pd = entry.get("resource", {})
            lines.append(_format_plan_definition(pd, include_actions=False))
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_get_plan_definition",
    annotations={
        "title": "Get FHIR PlanDefinition",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_get_plan_definition(params: GetPlanDefinitionInput) -> str:
    """Retrieve a specific PlanDefinition by ID with full details including actions."""
    logger.info(f"Getting PlanDefinition: {params.plan_definition_id}")
    
    try:
        result = await _make_fhir_request(f"PlanDefinition/{params.plan_definition_id}")
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2)
        
        return _format_plan_definition(result, include_actions=True)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_apply_plan_definition",
    annotations={
        "title": "Apply PlanDefinition",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_apply_plan_definition(params: ApplyPlanDefinitionInput) -> str:
    """Apply a PlanDefinition to generate a CarePlan for a specific subject."""
    logger.info(f"Applying PlanDefinition {params.plan_definition_id} to subject {params.subject}")
    
    try:
        # Build the $apply operation URL with parameters
        apply_params = {"subject": params.subject}
        
        if params.encounter.strip():
            apply_params["encounter"] = params.encounter.strip()
        if params.practitioner.strip():
            apply_params["practitioner"] = params.practitioner.strip()
        if params.organization.strip():
            apply_params["organization"] = params.organization.strip()
        
        result = await _make_fhir_request(
            f"PlanDefinition/{params.plan_definition_id}/$apply",
            method="GET",
            params=apply_params
        )
        
        # The result could be a CarePlan, RequestGroup, or Bundle depending on server implementation
        resource_type = result.get("resourceType", "Unknown")
        
        lines = [f"# CarePlan Generated from PlanDefinition/{params.plan_definition_id}", ""]
        lines.append(f"**Resource Type**: {resource_type}")
        
        if resource_type == "Bundle":
            entries = result.get("entry", [])
            lines.append(f"**Total Resources**: {len(entries)}")
            lines.append("\n## Resources in Bundle\n")
            for entry in entries:
                lines.append(_format_bundle_entry(entry))
                lines.append("")
            lines.append("\n## Full Bundle (JSON)\n")
            lines.append("```json")
            lines.append(json.dumps(result, indent=2))
            lines.append("```")
        elif resource_type == "CarePlan":
            lines.append(f"**ID**: {result.get('id', 'N/A')}")
            lines.append(f"**Status**: {result.get('status', 'N/A')}")
            lines.append(f"**Intent**: {result.get('intent', 'N/A')}")
            
            subject = result.get('subject', {})
            lines.append(f"**Subject**: {subject.get('reference', 'N/A')}")
            
            # Activities
            activities = result.get('activity', [])
            if activities:
                lines.append("\n## Activities\n")
                for activity in activities:
                    ref = activity.get('reference', {})
                    detail = activity.get('detail', {})
                    if ref.get('reference'):
                        lines.append(f"- Reference: {ref.get('reference')}")
                    if detail:
                        lines.append(f"  - Status: {detail.get('status', 'N/A')}")
                        if detail.get('description'):
                            lines.append(f"  - Description: {detail.get('description')}")
            
            lines.append("\n## Full CarePlan (JSON)\n")
            lines.append("```json")
            lines.append(json.dumps(result, indent=2))
            lines.append("```")
        else:
            lines.append("\n## Full Response (JSON)\n")
            lines.append("```json")
            lines.append(json.dumps(result, indent=2))
            lines.append("```")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_create_resource",
    annotations={
        "title": "Create FHIR Resource",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def fhir_create_resource(params: CreateResourceInput) -> str:
    """Create a new FHIR resource using raw JSON. Supports any valid FHIR R4 resource type."""
    logger.info("Creating new FHIR resource")
    
    try:
        resource = json.loads(params.resource_json)
        resource_type = resource.get("resourceType")
        
        if not resource_type:
            return "❌ Error: The resource JSON must include a 'resourceType' field."
        
        result = await _make_fhir_request(
            resource_type,
            method="POST",
            json_data=resource
        )
        
        created_id = result.get("id", "N/A")
        return f"✅ Successfully created {resource_type}/{created_id}\n\n```json\n{json.dumps(result, indent=2)}\n```"
        
    except json.JSONDecodeError as e:
        return f"❌ Error: Invalid JSON - {str(e)}"
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_update_resource",
    annotations={
        "title": "Update FHIR Resource",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_update_resource(params: UpdateResourceInput) -> str:
    """Update an existing FHIR resource using raw JSON."""
    logger.info(f"Updating resource: {params.resource_type}/{params.resource_id}")
    
    try:
        resource = json.loads(params.resource_json)
        
        # Ensure resource type matches
        if resource.get("resourceType") and resource.get("resourceType") != params.resource_type:
            return f"❌ Error: Resource type in JSON ({resource.get('resourceType')}) doesn't match specified type ({params.resource_type})"
        
        # Ensure ID is set
        resource["id"] = params.resource_id
        resource["resourceType"] = params.resource_type
        
        result = await _make_fhir_request(
            f"{params.resource_type}/{params.resource_id}",
            method="PUT",
            json_data=resource
        )
        
        return f"✅ Successfully updated {params.resource_type}/{params.resource_id}\n\n```json\n{json.dumps(result, indent=2)}\n```"
        
    except json.JSONDecodeError as e:
        return f"❌ Error: Invalid JSON - {str(e)}"
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_get_resource",
    annotations={
        "title": "Get FHIR Resource",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_get_resource(params: GetResourceInput) -> str:
    """Retrieve a FHIR resource by type and ID."""
    logger.info(f"Getting resource: {params.resource_type}/{params.resource_id}")
    
    try:
        result = await _make_fhir_request(f"{params.resource_type}/{params.resource_id}")
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2)
        
        # Basic markdown formatting
        lines = [f"# {params.resource_type}/{params.resource_id}", ""]
        
        for key, value in result.items():
            if key in ["resourceType", "id", "meta"]:
                continue
            if isinstance(value, dict):
                lines.append(f"**{key}**: {json.dumps(value)}")
            elif isinstance(value, list):
                lines.append(f"**{key}**: {len(value)} items")
            else:
                lines.append(f"**{key}**: {value}")
        
        lines.append("\n## Full Resource (JSON)\n")
        lines.append("```json")
        lines.append(json.dumps(result, indent=2))
        lines.append("```")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_search_resources",
    annotations={
        "title": "Search FHIR Resources",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_search_resources(params: SearchResourceInput) -> str:
    """Search for FHIR resources of a specific type with optional search parameters."""
    logger.info(f"Searching {params.resource_type} with params: {params.search_params}")
    
    try:
        # Parse search params from URL-encoded string
        search_params = {"_count": params.count}
        if params.search_params.strip():
            for param in params.search_params.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    search_params[key] = value
        
        result = await _make_fhir_request(params.resource_type, params=search_params)
        
        entries = result.get("entry", [])
        total = result.get("total", len(entries))
        
        if not entries:
            return f"📋 No {params.resource_type} resources found matching the criteria."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2)
        
        lines = [f"# {params.resource_type} Search Results ({len(entries)} of {total})", ""]
        
        for entry in entries:
            resource = entry.get("resource", {})
            resource_id = resource.get("id", "N/A")
            lines.append(f"## {params.resource_type}/{resource_id}")
            
            # Show key fields based on common resource types
            if params.resource_type == "Patient":
                name = resource.get("name", [{}])[0] if resource.get("name") else {}
                family = name.get("family", "")
                given = " ".join(name.get("given", []))
                lines.append(f"**Name**: {given} {family}")
                lines.append(f"**Gender**: {resource.get('gender', 'N/A')}")
                lines.append(f"**Birth Date**: {resource.get('birthDate', 'N/A')}")
            elif params.resource_type == "Observation":
                code = resource.get("code", {}).get("coding", [{}])[0] if resource.get("code") else {}
                lines.append(f"**Code**: {code.get('display', code.get('code', 'N/A'))}")
                lines.append(f"**Status**: {resource.get('status', 'N/A')}")
                value = resource.get("valueQuantity", resource.get("valueString", resource.get("valueCodeableConcept")))
                if value:
                    lines.append(f"**Value**: {json.dumps(value)}")
            else:
                # Generic display for other types
                if resource.get("status"):
                    lines.append(f"**Status**: {resource.get('status')}")
                if resource.get("name"):
                    lines.append(f"**Name**: {resource.get('name')}")
            
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_delete_resource",
    annotations={
        "title": "Delete FHIR Resource",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_delete_resource(params: DeleteResourceInput) -> str:
    """Delete a FHIR resource by type and ID."""
    logger.info(f"Deleting resource: {params.resource_type}/{params.resource_id}")
    
    try:
        await _make_fhir_request(
            f"{params.resource_type}/{params.resource_id}",
            method="DELETE"
        )
        
        return f"✅ Successfully deleted {params.resource_type}/{params.resource_id}"
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_lookup_code",
    annotations={
        "title": "Lookup Code in CodeSystem",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_lookup_code(params: LookupCodeInput) -> str:
    """Look up a code in a CodeSystem to get its display name and properties."""
    logger.info(f"Looking up code {params.code} in system {params.system}")
    
    try:
        lookup_params = {
            "system": params.system,
            "code": params.code
        }
        if params.version.strip():
            lookup_params["version"] = params.version.strip()
        
        result = await _make_fhir_request("CodeSystem/$lookup", params=lookup_params)
        
        # Parse Parameters response
        parameters = result.get("parameter", [])
        
        lines = [f"# Code Lookup: {params.code}", ""]
        lines.append(f"**System**: {params.system}")
        
        for param in parameters:
            name = param.get("name", "")
            value = param.get("valueString", param.get("valueCode", param.get("valueBoolean", param.get("valueCoding"))))
            if value is not None:
                lines.append(f"**{name}**: {value}")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_expand_valueset",
    annotations={
        "title": "Expand ValueSet",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_expand_valueset(params: ExpandValueSetInput) -> str:
    """Expand a ValueSet to retrieve all codes it contains."""
    logger.info(f"Expanding ValueSet: url={params.valueset_url}, id={params.valueset_id}")
    
    try:
        if params.valueset_id.strip():
            endpoint = f"ValueSet/{params.valueset_id.strip()}/$expand"
            expand_params = {}
        elif params.valueset_url.strip():
            endpoint = "ValueSet/$expand"
            expand_params = {"url": params.valueset_url.strip()}
        else:
            return "❌ Error: You must provide either a ValueSet ID or URL."
        
        expand_params["count"] = params.count
        if params.filter.strip():
            expand_params["filter"] = params.filter.strip()
        
        result = await _make_fhir_request(endpoint, params=expand_params)
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2)
        
        expansion = result.get("expansion", {})
        contains = expansion.get("contains", [])
        total = expansion.get("total", len(contains))
        
        lines = [f"# ValueSet Expansion", ""]
        lines.append(f"**Name**: {result.get('name', result.get('title', 'N/A'))}")
        lines.append(f"**URL**: {result.get('url', 'N/A')}")
        lines.append(f"**Total Codes**: {total}")
        lines.append("")
        lines.append("## Codes")
        lines.append("")
        
        for item in contains:
            system = item.get("system", "")
            code = item.get("code", "")
            display = item.get("display", "")
            lines.append(f"- **{code}**: {display}")
            lines.append(f"  System: {system}")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_list_codesystems",
    annotations={
        "title": "List CodeSystems",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_list_codesystems(params: ListCodeSystemsInput) -> str:
    """List available CodeSystem resources from the FHIR server."""
    logger.info(f"Listing CodeSystems: name={params.name}, url={params.url}")
    
    try:
        search_params = {"_count": params.count}
        if params.name.strip():
            search_params["name:contains"] = params.name.strip()
        if params.url.strip():
            search_params["url:contains"] = params.url.strip()
        
        result = await _make_fhir_request("CodeSystem", params=search_params)
        
        entries = result.get("entry", [])
        total = result.get("total", len(entries))
        
        if not entries:
            return "📋 No CodeSystems found matching the criteria."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2)
        
        lines = [f"# CodeSystems ({len(entries)} of {total})", ""]
        
        for entry in entries:
            cs = entry.get("resource", {})
            lines.append(f"## {cs.get('name', cs.get('title', 'Untitled'))}")
            lines.append(f"**ID**: {cs.get('id', 'N/A')}")
            lines.append(f"**URL**: {cs.get('url', 'N/A')}")
            lines.append(f"**Version**: {cs.get('version', 'N/A')}")
            lines.append(f"**Status**: {cs.get('status', 'N/A')}")
            if cs.get('description'):
                lines.append(f"**Description**: {cs.get('description')[:200]}...")
            concept_count = len(cs.get('concept', []))
            if concept_count > 0:
                lines.append(f"**Concept Count**: {concept_count}")
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_list_valuesets",
    annotations={
        "title": "List ValueSets",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_list_valuesets(params: ListValueSetsInput) -> str:
    """List available ValueSet resources from the FHIR server."""
    logger.info(f"Listing ValueSets: name={params.name}, url={params.url}")
    
    try:
        search_params = {"_count": params.count}
        if params.name.strip():
            search_params["name:contains"] = params.name.strip()
        if params.url.strip():
            search_params["url:contains"] = params.url.strip()
        
        result = await _make_fhir_request("ValueSet", params=search_params)
        
        entries = result.get("entry", [])
        total = result.get("total", len(entries))
        
        if not entries:
            return "📋 No ValueSets found matching the criteria."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2)
        
        lines = [f"# ValueSets ({len(entries)} of {total})", ""]
        
        for entry in entries:
            vs = entry.get("resource", {})
            lines.append(f"## {vs.get('name', vs.get('title', 'Untitled'))}")
            lines.append(f"**ID**: {vs.get('id', 'N/A')}")
            lines.append(f"**URL**: {vs.get('url', 'N/A')}")
            lines.append(f"**Version**: {vs.get('version', 'N/A')}")
            lines.append(f"**Status**: {vs.get('status', 'N/A')}")
            if vs.get('description'):
                lines.append(f"**Description**: {vs.get('description')[:200]}...")
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_list_implementation_guides",
    annotations={
        "title": "List ImplementationGuides",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_list_implementation_guides(params: ListImplementationGuidesInput) -> str:
    """List available ImplementationGuide resources from the FHIR server."""
    logger.info(f"Listing ImplementationGuides: name={params.name}")
    
    try:
        search_params = {"_count": params.count}
        if params.name.strip():
            search_params["name:contains"] = params.name.strip()
        
        result = await _make_fhir_request("ImplementationGuide", params=search_params)
        
        entries = result.get("entry", [])
        total = result.get("total", len(entries))
        
        if not entries:
            return "📋 No ImplementationGuides found."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2)
        
        lines = [f"# ImplementationGuides ({len(entries)} of {total})", ""]
        
        for entry in entries:
            ig = entry.get("resource", {})
            lines.append(f"## {ig.get('name', ig.get('title', 'Untitled'))}")
            lines.append(f"**ID**: {ig.get('id', 'N/A')}")
            lines.append(f"**URL**: {ig.get('url', 'N/A')}")
            lines.append(f"**Version**: {ig.get('version', 'N/A')}")
            lines.append(f"**Status**: {ig.get('status', 'N/A')}")
            lines.append(f"**FHIR Version**: {ig.get('fhirVersion', ['N/A'])}")
            if ig.get('description'):
                lines.append(f"**Description**: {ig.get('description')[:200]}...")
            lines.append("")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_get_implementation_guide",
    annotations={
        "title": "Get ImplementationGuide",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_get_implementation_guide(params: GetImplementationGuideInput) -> str:
    """Retrieve an ImplementationGuide by ID or URL."""
    logger.info(f"Getting ImplementationGuide: id={params.implementation_guide_id}, url={params.implementation_guide_url}")
    
    try:
        if params.implementation_guide_id.strip():
            result = await _make_fhir_request(f"ImplementationGuide/{params.implementation_guide_id.strip()}")
        elif params.implementation_guide_url.strip():
            search_result = await _make_fhir_request("ImplementationGuide", params={"url": params.implementation_guide_url.strip()})
            entries = search_result.get("entry", [])
            if not entries:
                return f"❌ Error: No ImplementationGuide found with URL: {params.implementation_guide_url}"
            result = entries[0].get("resource", {})
        else:
            return "❌ Error: You must provide either an ImplementationGuide ID or URL."
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(result, indent=2)
        
        lines = [f"# ImplementationGuide: {result.get('name', result.get('title', 'Untitled'))}", ""]
        lines.append(f"**ID**: {result.get('id', 'N/A')}")
        lines.append(f"**URL**: {result.get('url', 'N/A')}")
        lines.append(f"**Version**: {result.get('version', 'N/A')}")
        lines.append(f"**Status**: {result.get('status', 'N/A')}")
        lines.append(f"**FHIR Version**: {result.get('fhirVersion', ['N/A'])}")
        lines.append(f"**Package ID**: {result.get('packageId', 'N/A')}")
        
        if result.get('description'):
            lines.append(f"\n**Description**: {result.get('description')}")
        
        # Dependencies
        depends_on = result.get('dependsOn', [])
        if depends_on:
            lines.append("\n## Dependencies")
            for dep in depends_on:
                lines.append(f"- {dep.get('uri', 'N/A')} (version: {dep.get('version', 'N/A')})")
        
        # Global profiles
        globals_list = result.get('global', [])
        if globals_list:
            lines.append("\n## Global Profiles")
            for g in globals_list:
                lines.append(f"- Type: {g.get('type', 'N/A')}, Profile: {g.get('profile', 'N/A')}")
        
        # Definition resources
        definition = result.get('definition', {})
        resources = definition.get('resource', [])
        if resources:
            lines.append(f"\n## Resources ({len(resources)} total)")
            for res in resources[:20]:  # Limit display
                ref = res.get('reference', {})
                lines.append(f"- {ref.get('reference', 'N/A')}: {res.get('name', 'N/A')}")
            if len(resources) > 20:
                lines.append(f"... and {len(resources) - 20} more")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_set_implementation_guide_context",
    annotations={
        "title": "Set ImplementationGuide Context",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_set_implementation_guide_context(params: SetImplementationGuideInput) -> str:
    """Set the current ImplementationGuide context for subsequent operations."""
    global _implementation_guide_context
    logger.info(f"Setting ImplementationGuide context: id={params.implementation_guide_id}, url={params.implementation_guide_url}")
    
    try:
        if params.implementation_guide_id.strip():
            result = await _make_fhir_request(f"ImplementationGuide/{params.implementation_guide_id.strip()}")
        elif params.implementation_guide_url.strip():
            search_result = await _make_fhir_request("ImplementationGuide", params={"url": params.implementation_guide_url.strip()})
            entries = search_result.get("entry", [])
            if not entries:
                return f"❌ Error: No ImplementationGuide found with URL: {params.implementation_guide_url}"
            result = entries[0].get("resource", {})
        else:
            # Clear context
            _implementation_guide_context = {}
            return "✅ ImplementationGuide context cleared."
        
        _implementation_guide_context = result
        
        ig_name = result.get('name', result.get('title', 'Untitled'))
        ig_id = result.get('id', 'N/A')
        ig_url = result.get('url', 'N/A')
        
        return f"✅ ImplementationGuide context set to:\n- **Name**: {ig_name}\n- **ID**: {ig_id}\n- **URL**: {ig_url}"
        
    except Exception as e:
        return _handle_fhir_error(e)


@mcp.tool(
    name="fhir_get_current_implementation_guide_context",
    annotations={
        "title": "Get Current ImplementationGuide Context",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def fhir_get_current_implementation_guide_context() -> str:
    """Get the currently set ImplementationGuide context."""
    global _implementation_guide_context
    
    if not _implementation_guide_context:
        return "📋 No ImplementationGuide context is currently set. Use fhir_set_implementation_guide_context to set one."
    
    ig = _implementation_guide_context
    lines = [f"# Current ImplementationGuide Context", ""]
    lines.append(f"**Name**: {ig.get('name', ig.get('title', 'Untitled'))}")
    lines.append(f"**ID**: {ig.get('id', 'N/A')}")
    lines.append(f"**URL**: {ig.get('url', 'N/A')}")
    lines.append(f"**Version**: {ig.get('version', 'N/A')}")
    lines.append(f"**FHIR Version**: {ig.get('fhirVersion', ['N/A'])}")
    
    return "\n".join(lines)


@mcp.tool(
    name="fhir_get_server_capability",
    annotations={
        "title": "Get FHIR Server Capability Statement",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def fhir_get_server_capability() -> str:
    """Get the FHIR server's CapabilityStatement to understand supported resources and operations."""
    logger.info("Getting server capability statement")
    
    try:
        result = await _make_fhir_request("metadata")
        
        lines = [f"# FHIR Server Capability Statement", ""]
        lines.append(f"**FHIR Version**: {result.get('fhirVersion', 'N/A')}")
        lines.append(f"**Software**: {result.get('software', {}).get('name', 'N/A')} {result.get('software', {}).get('version', '')}")
        lines.append(f"**Status**: {result.get('status', 'N/A')}")
        
        # REST capabilities
        rest = result.get('rest', [{}])[0] if result.get('rest') else {}
        mode = rest.get('mode', 'N/A')
        lines.append(f"**Mode**: {mode}")
        
        # Supported resources
        resources = rest.get('resource', [])
        lines.append(f"\n## Supported Resources ({len(resources)})")
        
        for res in resources:
            res_type = res.get('type', 'Unknown')
            interactions = [i.get('code', '') for i in res.get('interaction', [])]
            search_params = [p.get('name', '') for p in res.get('searchParam', [])]
            
            lines.append(f"\n### {res_type}")
            lines.append(f"**Interactions**: {', '.join(interactions)}")
            if search_params:
                lines.append(f"**Search Parameters**: {', '.join(search_params[:10])}")
                if len(search_params) > 10:
                    lines.append(f"  ... and {len(search_params) - 10} more")
        
        # Operations
        operations = rest.get('operation', [])
        if operations:
            lines.append(f"\n## Operations ({len(operations)})")
            for op in operations:
                lines.append(f"- {op.get('name', 'N/A')}: {op.get('definition', 'N/A')}")
        
        return "\n".join(lines)
        
    except Exception as e:
        return _handle_fhir_error(e)


# === Server Startup ===
if __name__ == "__main__":
    logger.info(f"Starting FHIR MCP server... FHIR Server URL: {FHIR_SERVER_URL}")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)