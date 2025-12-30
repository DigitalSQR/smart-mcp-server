#!/usr/bin/env python3
"""Simple FHIR MCP Server - Provides FHIR R4 operations including PlanDefinition apply, resource management, and terminology services."""
import os
import sys
import json
import logging
import httpx
from mcp.server.fastmcp import FastMCP
from enum import Enum

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("fhir-server")

# Initialize MCP server
mcp = FastMCP("fhir")

# Configuration
FHIR_SERVER_URL = os.environ.get("FHIR_SERVER_URL", "http://localhost:8080/fhir")
MATCHBOX_SERVER_URL = os.environ.get("MATCHBOX_SERVER_URL", "http://localhost:8081/matchboxv3/fhir")

# Session state for ImplementationGuide context
_current_ig_context = {"id": "", "url": "", "name": ""}


class ResponseFormat(Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# === UTILITY FUNCTIONS ===

def format_resource_summary(resource: dict, format_type: str = "markdown") -> str:
    """Format a FHIR resource for display."""
    if format_type == "json":
        return json.dumps(resource, indent=2)
    
    resource_type = resource.get("resourceType", "Unknown")
    resource_id = resource.get("id", "N/A")
    
    lines = [f"**{resource_type}** (ID: {resource_id})"]
    
    if "name" in resource:
        name = resource["name"]
        if isinstance(name, list):
            name = name[0] if name else {}
        if isinstance(name, dict):
            given = " ".join(name.get("given", []))
            family = name.get("family", "")
            lines.append(f"- Name: {given} {family}".strip())
        else:
            lines.append(f"- Name: {name}")
    
    if "title" in resource:
        lines.append(f"- Title: {resource['title']}")
    
    if "status" in resource:
        lines.append(f"- Status: {resource['status']}")
    
    if "description" in resource:
        desc = resource["description"]
        if len(desc) > 200:
            desc = desc[:200] + "..."
        lines.append(f"- Description: {desc}")
    
    return "\n".join(lines)


def format_bundle_summary(bundle: dict, format_type: str = "markdown") -> str:
    """Format a FHIR Bundle for display."""
    if format_type == "json":
        return json.dumps(bundle, indent=2)
    
    total = bundle.get("total", len(bundle.get("entry", [])))
    entries = bundle.get("entry", [])
    
    lines = [f"📊 **Search Results** (Total: {total})", ""]
    
    for i, entry in enumerate(entries[:20], 1):
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType", "Unknown")
        resource_id = resource.get("id", "N/A")
        
        title = resource.get("title", resource.get("name", ""))
        if isinstance(title, list):
            title = title[0] if title else ""
        if isinstance(title, dict):
            given = " ".join(title.get("given", []))
            family = title.get("family", "")
            title = f"{given} {family}".strip()
        
        if title:
            lines.append(f"{i}. **{resource_type}/{resource_id}** - {title}")
        else:
            lines.append(f"{i}. **{resource_type}/{resource_id}**")
    
    if len(entries) > 20:
        lines.append(f"\n... and {len(entries) - 20} more results")
    
    return "\n".join(lines)


def extract_target_structure_map(questionnaire: dict) -> str:
    """Extract targetStructureMap URL from Questionnaire extensions."""
    extensions = questionnaire.get("extension", [])
    for ext in extensions:
        if ext.get("url") == "http://hl7.org/fhir/uv/sdc/StructureDefinition/sdc-questionnaire-targetStructureMap":
            return ext.get("valueCanonical", "")
    return ""


async def make_fhir_request(method: str, url: str, data: dict = None, params: dict = None, server: str = "fhir") -> dict:
    """Make a request to the FHIR server."""
    base_url = FHIR_SERVER_URL if server == "fhir" else MATCHBOX_SERVER_URL
    full_url = f"{base_url}/{url}" if not url.startswith("http") else url
    
    headers = {
        "Content-Type": "application/fhir+json",
        "Accept": "application/fhir+json"
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        if method == "GET":
            response = await client.get(full_url, headers=headers, params=params)
        elif method == "POST":
            response = await client.post(full_url, headers=headers, json=data, params=params)
        elif method == "PUT":
            response = await client.put(full_url, headers=headers, json=data)
        elif method == "DELETE":
            response = await client.delete(full_url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        
        if response.status_code == 204:
            return {"status": "success", "message": "Resource deleted"}
        
        return response.json()


# === IMPLEMENTATION GUIDE CONTEXT TOOLS ===

@mcp.tool()
async def fhir_set_implementation_guide_context(implementation_guide_id: str = "", implementation_guide_url: str = "") -> str:
    """Set the current ImplementationGuide context for subsequent operations."""
    global _current_ig_context
    
    if not implementation_guide_id.strip() and not implementation_guide_url.strip():
        return "❌ Error: Either implementation_guide_id or implementation_guide_url is required"
    
    try:
        if implementation_guide_id.strip():
            ig = await make_fhir_request("GET", f"ImplementationGuide/{implementation_guide_id}")
        else:
            bundle = await make_fhir_request("GET", "ImplementationGuide", params={"url": implementation_guide_url})
            entries = bundle.get("entry", [])
            if not entries:
                return f"❌ Error: No ImplementationGuide found with URL: {implementation_guide_url}"
            ig = entries[0].get("resource", {})
        
        _current_ig_context = {
            "id": ig.get("id", ""),
            "url": ig.get("url", ""),
            "name": ig.get("name", ig.get("title", ""))
        }
        
        return f"✅ ImplementationGuide context set:\n- ID: {_current_ig_context['id']}\n- Name: {_current_ig_context['name']}\n- URL: {_current_ig_context['url']}"
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error setting IG context: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_get_current_implementation_guide_context() -> str:
    """Get the currently set ImplementationGuide context."""
    if not _current_ig_context.get("id"):
        return "ℹ️ No ImplementationGuide context is currently set. Use fhir_set_implementation_guide_context to set one."
    
    return f"📋 Current ImplementationGuide Context:\n- ID: {_current_ig_context['id']}\n- Name: {_current_ig_context['name']}\n- URL: {_current_ig_context['url']}"


@mcp.tool()
async def fhir_get_implementation_guide(implementation_guide_id: str = "", implementation_guide_url: str = "", response_format: str = "markdown") -> str:
    """Retrieve an ImplementationGuide by ID or URL."""
    if not implementation_guide_id.strip() and not implementation_guide_url.strip():
        return "❌ Error: Either implementation_guide_id or implementation_guide_url is required"
    
    try:
        if implementation_guide_id.strip():
            ig = await make_fhir_request("GET", f"ImplementationGuide/{implementation_guide_id}")
        else:
            bundle = await make_fhir_request("GET", "ImplementationGuide", params={"url": implementation_guide_url})
            entries = bundle.get("entry", [])
            if not entries:
                return f"❌ Error: No ImplementationGuide found with URL: {implementation_guide_url}"
            ig = entries[0].get("resource", {})
        
        if response_format == "json":
            return json.dumps(ig, indent=2)
        
        lines = [f"📘 **ImplementationGuide**: {ig.get('title', ig.get('name', 'Unknown'))}"]
        lines.append(f"- ID: {ig.get('id', 'N/A')}")
        lines.append(f"- URL: {ig.get('url', 'N/A')}")
        lines.append(f"- Version: {ig.get('version', 'N/A')}")
        lines.append(f"- Status: {ig.get('status', 'N/A')}")
        
        if ig.get("description"):
            lines.append(f"\n**Description**: {ig['description'][:500]}...")
        
        definition = ig.get("definition", {})
        resources = definition.get("resource", [])
        if resources:
            lines.append(f"\n**Resources** ({len(resources)} total):")
            for res in resources[:10]:
                ref = res.get("reference", {}).get("reference", "Unknown")
                name = res.get("name", ref)
                lines.append(f"  - {name} ({ref})")
            if len(resources) > 10:
                lines.append(f"  ... and {len(resources) - 10} more")
        
        return "\n".join(lines)
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error getting IG: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_list_implementation_guides(name: str = "", count: str = "50", response_format: str = "markdown") -> str:
    """List available ImplementationGuide resources from the FHIR server."""
    try:
        params = {"_count": count}
        if name.strip():
            params["name:contains"] = name
        
        bundle = await make_fhir_request("GET", "ImplementationGuide", params=params)
        
        if response_format == "json":
            return json.dumps(bundle, indent=2)
        
        return format_bundle_summary(bundle, "markdown")
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error listing IGs: {e}")
        return f"❌ Error: {str(e)}"


# === PLAN DEFINITION TOOLS ===

@mcp.tool()
async def fhir_list_plan_definitions(status: str = "", title: str = "", count: str = "100", response_format: str = "markdown") -> str:
    """List available PlanDefinition resources from the FHIR server with optional filters."""
    try:
        params = {"_count": count}
        if status.strip():
            params["status"] = status
        if title.strip():
            params["title:contains"] = title
        
        bundle = await make_fhir_request("GET", "PlanDefinition", params=params)
        
        if response_format == "json":
            return json.dumps(bundle, indent=2)
        
        return format_bundle_summary(bundle, "markdown")
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error listing PlanDefinitions: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_get_plan_definition(plan_definition_id: str, response_format: str = "markdown") -> str:
    """Retrieve a specific PlanDefinition by ID with full details including actions."""
    if not plan_definition_id.strip():
        return "❌ Error: plan_definition_id is required"
    
    try:
        pd = await make_fhir_request("GET", f"PlanDefinition/{plan_definition_id}")
        
        if response_format == "json":
            return json.dumps(pd, indent=2)
        
        lines = [f"📋 **PlanDefinition**: {pd.get('title', pd.get('name', 'Unknown'))}"]
        lines.append(f"- ID: {pd.get('id', 'N/A')}")
        lines.append(f"- URL: {pd.get('url', 'N/A')}")
        lines.append(f"- Version: {pd.get('version', 'N/A')}")
        lines.append(f"- Status: {pd.get('status', 'N/A')}")
        
        if pd.get("description"):
            lines.append(f"\n**Description**: {pd['description']}")
        
        actions = pd.get("action", [])
        if actions:
            lines.append(f"\n**Actions** ({len(actions)}):")
            for i, action in enumerate(actions, 1):
                title = action.get("title", action.get("description", f"Action {i}"))
                lines.append(f"  {i}. {title}")
                
                if action.get("input"):
                    lines.append(f"     Inputs: {len(action['input'])} data requirements")
                if action.get("output"):
                    lines.append(f"     Outputs: {len(action['output'])} data requirements")
                if action.get("definitionCanonical"):
                    lines.append(f"     Definition: {action['definitionCanonical']}")
        
        return "\n".join(lines)
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error getting PlanDefinition: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_apply_plan_definition(plan_definition_id: str, subject: str, encounter: str = "", practitioner: str = "", organization: str = "") -> str:
    """Apply a PlanDefinition to generate a CarePlan for a specific subject."""
    if not plan_definition_id.strip():
        return "❌ Error: plan_definition_id is required"
    if not subject.strip():
        return "❌ Error: subject is required (e.g., Patient/123)"
    
    try:
        params = {"subject": subject}
        if encounter.strip():
            params["encounter"] = encounter
        if practitioner.strip():
            params["practitioner"] = practitioner
        if organization.strip():
            params["organization"] = organization
        
        result = await make_fhir_request("POST", f"PlanDefinition/{plan_definition_id}/$apply", params=params)
        
        return json.dumps(result, indent=2)
    
    except httpx.HTTPStatusError as e:
        error_text = e.response.text
        try:
            error_json = json.loads(error_text)
            if error_json.get("resourceType") == "OperationOutcome":
                issues = error_json.get("issue", [])
                error_messages = [issue.get("diagnostics", issue.get("details", {}).get("text", "Unknown error")) for issue in issues]
                return f"❌ Operation Error:\n" + "\n".join(f"- {msg}" for msg in error_messages)
        except json.JSONDecodeError:
            pass
        return f"❌ HTTP Error: {e.response.status_code} - {error_text}"
    except Exception as e:
        logger.error(f"Error applying PlanDefinition: {e}")
        return f"❌ Error: {str(e)}"


# === GENERIC RESOURCE TOOLS ===

@mcp.tool()
async def fhir_get_resource(resource_type: str, resource_id: str, response_format: str = "json") -> str:
    """Retrieve a FHIR resource by type and ID."""
    if not resource_type.strip():
        return "❌ Error: resource_type is required"
    if not resource_id.strip():
        return "❌ Error: resource_id is required"
    
    try:
        resource = await make_fhir_request("GET", f"{resource_type}/{resource_id}")
        
        if response_format == "json":
            return json.dumps(resource, indent=2)
        
        return format_resource_summary(resource, "markdown")
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error getting resource: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_search_resources(resource_type: str, search_params: str = "", count: str = "50", response_format: str = "markdown") -> str:
    """Search for FHIR resources of a specific type with optional search parameters."""
    if not resource_type.strip():
        return "❌ Error: resource_type is required"
    
    try:
        params = {"_count": count}
        if search_params.strip():
            for param in search_params.split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value
        
        bundle = await make_fhir_request("GET", resource_type, params=params)
        
        if response_format == "json":
            return json.dumps(bundle, indent=2)
        
        return format_bundle_summary(bundle, "markdown")
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error searching resources: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_create_resource(resource_json: str) -> str:
    """Create a new FHIR resource using raw JSON. Supports any valid FHIR R4 resource type."""
    if not resource_json.strip():
        return "❌ Error: resource_json is required"
    
    try:
        resource = json.loads(resource_json)
    except json.JSONDecodeError as e:
        return f"❌ Error: Invalid JSON - {str(e)}"
    
    resource_type = resource.get("resourceType")
    if not resource_type:
        return "❌ Error: resourceType is required in the FHIR resource"
    
    try:
        params = {}
        if _current_ig_context.get("url"):
            params["profile"] = _current_ig_context["url"]
        
        result = await make_fhir_request("POST", resource_type, data=resource, params=params if params else None)
        
        created_id = result.get("id", "Unknown")
        return f"✅ Created {resource_type}/{created_id}\n\n{json.dumps(result, indent=2)}"
    
    except httpx.HTTPStatusError as e:
        error_text = e.response.text
        try:
            error_json = json.loads(error_text)
            if error_json.get("resourceType") == "OperationOutcome":
                issues = error_json.get("issue", [])
                error_messages = []
                for issue in issues:
                    severity = issue.get("severity", "error")
                    msg = issue.get("diagnostics", issue.get("details", {}).get("text", "Unknown error"))
                    location = issue.get("location", [])
                    loc_str = f" at {', '.join(location)}" if location else ""
                    error_messages.append(f"[{severity}] {msg}{loc_str}")
                return f"❌ Validation Error:\n" + "\n".join(f"- {msg}" for msg in error_messages)
        except json.JSONDecodeError:
            pass
        return f"❌ HTTP Error: {e.response.status_code} - {error_text}"
    except Exception as e:
        logger.error(f"Error creating resource: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_update_resource(resource_type: str, resource_id: str, resource_json: str) -> str:
    """Update an existing FHIR resource using raw JSON."""
    if not resource_type.strip():
        return "❌ Error: resource_type is required"
    if not resource_id.strip():
        return "❌ Error: resource_id is required"
    if not resource_json.strip():
        return "❌ Error: resource_json is required"
    
    try:
        resource = json.loads(resource_json)
    except json.JSONDecodeError as e:
        return f"❌ Error: Invalid JSON - {str(e)}"
    
    resource["id"] = resource_id
    if resource.get("resourceType") != resource_type:
        resource["resourceType"] = resource_type
    
    try:
        result = await make_fhir_request("PUT", f"{resource_type}/{resource_id}", data=resource)
        return f"✅ Updated {resource_type}/{resource_id}\n\n{json.dumps(result, indent=2)}"
    
    except httpx.HTTPStatusError as e:
        error_text = e.response.text
        try:
            error_json = json.loads(error_text)
            if error_json.get("resourceType") == "OperationOutcome":
                issues = error_json.get("issue", [])
                error_messages = [issue.get("diagnostics", "Unknown error") for issue in issues]
                return f"❌ Validation Error:\n" + "\n".join(f"- {msg}" for msg in error_messages)
        except json.JSONDecodeError:
            pass
        return f"❌ HTTP Error: {e.response.status_code} - {error_text}"
    except Exception as e:
        logger.error(f"Error updating resource: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_delete_resource(resource_type: str, resource_id: str) -> str:
    """Delete a FHIR resource by type and ID."""
    if not resource_type.strip():
        return "❌ Error: resource_type is required"
    if not resource_id.strip():
        return "❌ Error: resource_id is required"
    
    try:
        await make_fhir_request("DELETE", f"{resource_type}/{resource_id}")
        return f"✅ Deleted {resource_type}/{resource_id}"
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error deleting resource: {e}")
        return f"❌ Error: {str(e)}"


# === TERMINOLOGY TOOLS ===

@mcp.tool()
async def fhir_list_valuesets(name: str = "", url: str = "", count: str = "50", response_format: str = "markdown") -> str:
    """List available ValueSet resources from the FHIR server."""
    try:
        params = {"_count": count}
        if name.strip():
            params["name:contains"] = name
        if url.strip():
            params["url:contains"] = url
        
        bundle = await make_fhir_request("GET", "ValueSet", params=params)
        
        if response_format == "json":
            return json.dumps(bundle, indent=2)
        
        return format_bundle_summary(bundle, "markdown")
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error listing ValueSets: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_expand_valueset(valueset_id: str = "", valueset_url: str = "", filter: str = "", count: str = "100", response_format: str = "markdown") -> str:
    """Expand a ValueSet to retrieve all codes it contains."""
    if not valueset_id.strip() and not valueset_url.strip():
        return "❌ Error: Either valueset_id or valueset_url is required"
    
    try:
        if valueset_id.strip():
            params = {"_count": count}
            if filter.strip():
                params["filter"] = filter
            result = await make_fhir_request("GET", f"ValueSet/{valueset_id}/$expand", params=params)
        else:
            params = {"url": valueset_url, "count": count}
            if filter.strip():
                params["filter"] = filter
            result = await make_fhir_request("GET", "ValueSet/$expand", params=params)
        
        if response_format == "json":
            return json.dumps(result, indent=2)
        
        expansion = result.get("expansion", {})
        contains = expansion.get("contains", [])
        
        lines = [f"📋 **ValueSet Expansion**: {result.get('name', result.get('title', 'Unknown'))}"]
        lines.append(f"- Total codes: {expansion.get('total', len(contains))}")
        lines.append("")
        lines.append("**Codes:**")
        
        for code_entry in contains[:50]:
            system = code_entry.get("system", "")
            code = code_entry.get("code", "")
            display = code_entry.get("display", "")
            lines.append(f"- `{code}` - {display}")
            if system:
                lines.append(f"  System: {system}")
        
        if len(contains) > 50:
            lines.append(f"\n... and {len(contains) - 50} more codes")
        
        return "\n".join(lines)
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error expanding ValueSet: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_list_codesystems(name: str = "", url: str = "", count: str = "50", response_format: str = "markdown") -> str:
    """List available CodeSystem resources from the FHIR server."""
    try:
        params = {"_count": count}
        if name.strip():
            params["name:contains"] = name
        if url.strip():
            params["url:contains"] = url
        
        bundle = await make_fhir_request("GET", "CodeSystem", params=params)
        
        if response_format == "json":
            return json.dumps(bundle, indent=2)
        
        return format_bundle_summary(bundle, "markdown")
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error listing CodeSystems: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_lookup_code(system: str, code: str, version: str = "") -> str:
    """Look up a code in a CodeSystem to get its display name and properties."""
    if not system.strip():
        return "❌ Error: system is required"
    if not code.strip():
        return "❌ Error: code is required"
    
    try:
        params = {"system": system, "code": code}
        if version.strip():
            params["version"] = version
        
        result = await make_fhir_request("GET", "CodeSystem/$lookup", params=params)
        
        parameters = result.get("parameter", [])
        
        lines = [f"🔍 **Code Lookup**: {code}"]
        lines.append(f"- System: {system}")
        
        for param in parameters:
            name = param.get("name", "")
            value = param.get("valueString", param.get("valueCode", param.get("valueBoolean", param.get("valueDateTime", ""))))
            if name and value:
                lines.append(f"- {name}: {value}")
        
        return "\n".join(lines)
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error looking up code: {e}")
        return f"❌ Error: {str(e)}"


# === QUESTIONNAIRE TOOLS ===

@mcp.tool()
async def fhir_get_questionnaire(questionnaire_id: str = "", questionnaire_url: str = "", response_format: str = "json") -> str:
    """Retrieve a Questionnaire by ID or canonical URL for the agent to ask questions."""
    if not questionnaire_id.strip() and not questionnaire_url.strip():
        return "❌ Error: Either questionnaire_id or questionnaire_url is required"
    
    try:
        if questionnaire_id.strip():
            questionnaire = await make_fhir_request("GET", f"Questionnaire/{questionnaire_id}")
        else:
            bundle = await make_fhir_request("GET", "Questionnaire", params={"url": questionnaire_url})
            entries = bundle.get("entry", [])
            if not entries:
                return f"❌ Error: No Questionnaire found with URL: {questionnaire_url}"
            questionnaire = entries[0].get("resource", {})
        
        if response_format == "json":
            return json.dumps(questionnaire, indent=2)
        
        lines = [f"📝 **Questionnaire**: {questionnaire.get('title', questionnaire.get('name', 'Unknown'))}"]
        lines.append(f"- ID: {questionnaire.get('id', 'N/A')}")
        lines.append(f"- URL: {questionnaire.get('url', 'N/A')}")
        lines.append(f"- Status: {questionnaire.get('status', 'N/A')}")
        
        target_map = extract_target_structure_map(questionnaire)
        if target_map:
            lines.append(f"- Target StructureMap: {target_map}")
        
        items = questionnaire.get("item", [])
        if items:
            lines.append(f"\n**Items** ({len(items)}):")
            for item in items:
                link_id = item.get("linkId", "")
                text = item.get("text", "")
                item_type = item.get("type", "")
                required = "Required" if item.get("required") else "Optional"
                lines.append(f"  - [{link_id}] {text} ({item_type}, {required})")
        
        return "\n".join(lines)
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error getting Questionnaire: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_list_questionnaires(title: str = "", status: str = "", count: str = "50", response_format: str = "markdown") -> str:
    """List available Questionnaire resources from the FHIR server."""
    try:
        params = {"_count": count}
        if title.strip():
            params["title:contains"] = title
        if status.strip():
            params["status"] = status
        
        bundle = await make_fhir_request("GET", "Questionnaire", params=params)
        
        if response_format == "json":
            return json.dumps(bundle, indent=2)
        
        return format_bundle_summary(bundle, "markdown")
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error listing Questionnaires: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def fhir_transform_questionnaire_response(questionnaire_response_json: str, structure_map_url: str = "") -> str:
    """Transform a QuestionnaireResponse using StructureMap on Matchbox server to create FHIR resources."""
    if not questionnaire_response_json.strip():
        return "❌ Error: questionnaire_response_json is required"
    
    try:
        qr = json.loads(questionnaire_response_json)
    except json.JSONDecodeError as e:
        return f"❌ Error: Invalid JSON - {str(e)}"
    
    if qr.get("resourceType") != "QuestionnaireResponse":
        return "❌ Error: Resource must be a QuestionnaireResponse"
    
    try:
        map_url = structure_map_url.strip()
        
        if not map_url:
            questionnaire_url = qr.get("questionnaire", "")
            if questionnaire_url:
                if "/" in questionnaire_url and not questionnaire_url.startswith("http"):
                    q_id = questionnaire_url.split("/")[-1]
                    questionnaire = await make_fhir_request("GET", f"Questionnaire/{q_id}")
                else:
                    bundle = await make_fhir_request("GET", "Questionnaire", params={"url": questionnaire_url})
                    entries = bundle.get("entry", [])
                    if entries:
                        questionnaire = entries[0].get("resource", {})
                    else:
                        return f"❌ Error: Could not find Questionnaire: {questionnaire_url}"
                
                map_url = extract_target_structure_map(questionnaire)
        
        if not map_url:
            return "❌ Error: No StructureMap URL found. Please provide structure_map_url or ensure Questionnaire has targetStructureMap extension."
        
        result = await make_fhir_request(
            "POST",
            f"StructureMap/$transform?source={map_url}",
            data=qr,
            server="matchbox"
        )
        
        return f"✅ Transform successful!\n\n{json.dumps(result, indent=2)}"
    
    except httpx.HTTPStatusError as e:
        error_text = e.response.text
        try:
            error_json = json.loads(error_text)
            if error_json.get("resourceType") == "OperationOutcome":
                issues = error_json.get("issue", [])
                error_messages = [issue.get("diagnostics", "Unknown error") for issue in issues]
                return f"❌ Transform Error:\n" + "\n".join(f"- {msg}" for msg in error_messages)
        except json.JSONDecodeError:
            pass
        return f"❌ HTTP Error: {e.response.status_code} - {error_text}"
    except Exception as e:
        logger.error(f"Error transforming QuestionnaireResponse: {e}")
        return f"❌ Error: {str(e)}"


# === SERVER CAPABILITY ===

@mcp.tool()
async def fhir_get_server_capability() -> str:
    """Get the FHIR server's CapabilityStatement to understand supported resources and operations."""
    try:
        capability = await make_fhir_request("GET", "metadata")
        
        lines = [f"🏥 **FHIR Server Capability Statement**"]
        lines.append(f"- FHIR Version: {capability.get('fhirVersion', 'Unknown')}")
        lines.append(f"- Software: {capability.get('software', {}).get('name', 'Unknown')}")
        lines.append(f"- Status: {capability.get('status', 'Unknown')}")
        
        rest = capability.get("rest", [])
        if rest:
            server_rest = rest[0]
            resources = server_rest.get("resource", [])
            
            lines.append(f"\n**Supported Resources** ({len(resources)}):")
            for res in resources[:30]:
                res_type = res.get("type", "Unknown")
                interactions = [i.get("code", "") for i in res.get("interaction", [])]
                operations = [o.get("name", "") for o in res.get("operation", [])]
                
                lines.append(f"- **{res_type}**")
                if interactions:
                    lines.append(f"  Interactions: {', '.join(interactions)}")
                if operations:
                    lines.append(f"  Operations: {', '.join(operations)}")
            
            if len(resources) > 30:
                lines.append(f"\n... and {len(resources) - 30} more resources")
        
        return "\n".join(lines)
    
    except httpx.HTTPStatusError as e:
        return f"❌ HTTP Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error getting capability: {e}")
        return f"❌ Error: {str(e)}"


# === SERVER STARTUP ===

if __name__ == "__main__":
    logger.info("Starting FHIR MCP server...")
    logger.info(f"FHIR Server URL: {FHIR_SERVER_URL}")
    logger.info(f"Matchbox Server URL: {MATCHBOX_SERVER_URL}")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)