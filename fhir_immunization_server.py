#!/usr/bin/env python3
"""
FHIR Immunization MCP Server - WHO SMART Immunizations PlanDefinition support with $apply operation.
"""
import os
import sys
import logging
import json
from datetime import datetime, timezone
import httpx
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger("fhir-immunization-server")

# Initialize MCP server
mcp = FastMCP("fhir-immunization")

# Configuration
FHIR_BASE_URL = os.environ.get("FHIR_BASE_URL", "http://localhost:8080/fhir")


def get_fhir_client():
    """Create httpx client with FHIR headers."""
    return httpx.AsyncClient(
        base_url=FHIR_BASE_URL,
        headers={
            "Content-Type": "application/fhir+json",
            "Accept": "application/fhir+json"
        },
        timeout=30.0
    )


def format_resource_summary(resource: dict) -> str:
    """Format a FHIR resource summary for display."""
    resource_type = resource.get("resourceType", "Unknown")
    resource_id = resource.get("id", "N/A")
    
    if resource_type == "PlanDefinition":
        title = resource.get("title", resource.get("name", "Untitled"))
        status = resource.get("status", "unknown")
        description = resource.get("description", "No description")[:200]
        return f"📋 {title} (ID: {resource_id})\n   Status: {status}\n   Description: {description}..."
    elif resource_type == "CarePlan":
        status = resource.get("status", "unknown")
        intent = resource.get("intent", "unknown")
        activities = len(resource.get("activity", []))
        return f"📝 CarePlan (ID: {resource_id})\n   Status: {status}, Intent: {intent}\n   Activities: {activities}"
    elif resource_type == "Patient":
        name = "Unknown"
        if resource.get("name"):
            name_obj = resource["name"][0]
            given = " ".join(name_obj.get("given", []))
            family = name_obj.get("family", "")
            name = f"{given} {family}".strip()
        birth_date = resource.get("birthDate", "Unknown")
        return f"👤 {name} (ID: {resource_id})\n   Birth Date: {birth_date}"
    elif resource_type == "Immunization":
        vaccine = resource.get("vaccineCode", {}).get("text", "Unknown vaccine")
        status = resource.get("status", "unknown")
        occurrence = resource.get("occurrenceDateTime", "Unknown date")
        return f"💉 {vaccine} (ID: {resource_id})\n   Status: {status}, Date: {occurrence}"
    elif resource_type == "Observation":
        code_text = resource.get("code", {}).get("text", "Unknown observation")
        status = resource.get("status", "unknown")
        value = resource.get("valueString", resource.get("valueQuantity", {}).get("value", "N/A"))
        return f"🔬 {code_text} (ID: {resource_id})\n   Status: {status}, Value: {value}"
    else:
        return f"📄 {resource_type} (ID: {resource_id})"


def format_bundle_entries(bundle: dict) -> str:
    """Format bundle entries for display."""
    entries = bundle.get("entry", [])
    if not entries:
        return "No entries found"
    
    result = []
    for entry in entries:
        resource = entry.get("resource", {})
        result.append(format_resource_summary(resource))
    return "\n\n".join(result)


@mcp.tool()
async def list_plan_definitions(status: str = "", title: str = "") -> str:
    """List available PlanDefinitions from the FHIR server with optional status and title filters."""
    logger.info(f"Listing PlanDefinitions with status={status}, title={title}")
    
    try:
        async with get_fhir_client() as client:
            params = {"_count": "100"}
            if status.strip():
                params["status"] = status.strip()
            if title.strip():
                params["title:contains"] = title.strip()
            
            response = await client.get("/PlanDefinition", params=params)
            response.raise_for_status()
            bundle = response.json()
            
            total = bundle.get("total", len(bundle.get("entry", [])))
            entries = bundle.get("entry", [])
            
            if not entries:
                return "📋 No PlanDefinitions found matching the criteria."
            
            result = f"📋 Found {total} PlanDefinition(s):\n\n"
            for entry in entries:
                resource = entry.get("resource", {})
                pd_id = resource.get("id", "N/A")
                title_val = resource.get("title", resource.get("name", "Untitled"))
                status_val = resource.get("status", "unknown")
                url = resource.get("url", "N/A")
                description = resource.get("description", "No description")[:150]
                
                result += f"• **{title_val}**\n"
                result += f"  ID: {pd_id}\n"
                result += f"  URL: {url}\n"
                result += f"  Status: {status_val}\n"
                result += f"  Description: {description}...\n\n"
            
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error listing PlanDefinitions: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_plan_definition(plan_definition_id: str = "") -> str:
    """Get detailed information about a specific PlanDefinition including required inputs and actions."""
    logger.info(f"Getting PlanDefinition: {plan_definition_id}")
    
    if not plan_definition_id.strip():
        return "❌ Error: plan_definition_id is required"
    
    try:
        async with get_fhir_client() as client:
            response = await client.get(f"/PlanDefinition/{plan_definition_id.strip()}")
            response.raise_for_status()
            pd = response.json()
            
            result = f"📋 **PlanDefinition: {pd.get('title', pd.get('name', 'Untitled'))}**\n\n"
            result += f"**ID:** {pd.get('id')}\n"
            result += f"**URL:** {pd.get('url', 'N/A')}\n"
            result += f"**Version:** {pd.get('version', 'N/A')}\n"
            result += f"**Status:** {pd.get('status', 'unknown')}\n"
            result += f"**Description:** {pd.get('description', 'No description')}\n\n"
            
            # List libraries (CQL logic)
            libraries = pd.get("library", [])
            if libraries:
                result += "**📚 Libraries:**\n"
                for lib in libraries:
                    result += f"  • {lib}\n"
                result += "\n"
            
            # List goals
            goals = pd.get("goal", [])
            if goals:
                result += "**🎯 Goals:**\n"
                for goal in goals:
                    desc = goal.get("description", {}).get("text", "No description")
                    result += f"  • {desc}\n"
                result += "\n"
            
            # List actions
            actions = pd.get("action", [])
            if actions:
                result += "**⚡ Actions:**\n"
                result += format_actions(actions, indent=2)
            
            # Subject type
            subject = pd.get("subjectCodeableConcept", {}).get("coding", [])
            if subject:
                result += "\n**👥 Subject Type:** "
                result += ", ".join([c.get("display", c.get("code", "Unknown")) for c in subject])
                result += "\n"
            
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error getting PlanDefinition: {e}")
        return f"❌ Error: {str(e)}"


def format_actions(actions: list, indent: int = 0) -> str:
    """Recursively format action hierarchy."""
    result = ""
    prefix = " " * indent
    
    for action in actions:
        title = action.get("title", action.get("description", "Untitled action"))
        result += f"{prefix}• **{title}**\n"
        
        description = action.get("description")
        if description:
            result += f"{prefix}  Description: {description[:100]}...\n"
        
        # Condition/applicability
        conditions = action.get("condition", [])
        for cond in conditions:
            kind = cond.get("kind", "unknown")
            expr = cond.get("expression", {}).get("expression", "N/A")
            result += f"{prefix}  Condition ({kind}): {expr}\n"
        
        # Definition reference
        definition = action.get("definitionCanonical", action.get("definitionUri"))
        if definition:
            result += f"{prefix}  Definition: {definition}\n"
        
        # Input data requirements
        inputs = action.get("input", [])
        if inputs:
            result += f"{prefix}  📥 Inputs:\n"
            for inp in inputs:
                inp_type = inp.get("type", "Unknown")
                profile = inp.get("profile", [])
                result += f"{prefix}    - {inp_type}"
                if profile:
                    result += f" ({', '.join(profile)})"
                result += "\n"
        
        # Output data
        outputs = action.get("output", [])
        if outputs:
            result += f"{prefix}  📤 Outputs:\n"
            for out in outputs:
                out_type = out.get("type", "Unknown")
                result += f"{prefix}    - {out_type}\n"
        
        # Nested actions
        nested_actions = action.get("action", [])
        if nested_actions:
            result += format_actions(nested_actions, indent + 4)
    
    return result


@mcp.tool()
async def apply_plan_definition(plan_definition_id: str = "", subject: str = "", encounter: str = "", practitioner: str = "") -> str:
    """Apply a PlanDefinition to a patient using the $apply operation and return the resulting CarePlan."""
    logger.info(f"Applying PlanDefinition {plan_definition_id} to subject {subject}")
    
    if not plan_definition_id.strip():
        return "❌ Error: plan_definition_id is required"
    if not subject.strip():
        return "❌ Error: subject (Patient reference like 'Patient/123') is required"
    
    try:
        async with get_fhir_client() as client:
            params = {"subject": subject.strip()}
            if encounter.strip():
                params["encounter"] = encounter.strip()
            if practitioner.strip():
                params["practitioner"] = practitioner.strip()
            
            response = await client.get(
                f"/PlanDefinition/{plan_definition_id.strip()}/$apply",
                params=params
            )
            response.raise_for_status()
            result_data = response.json()
            
            resource_type = result_data.get("resourceType", "Unknown")
            
            if resource_type == "CarePlan":
                return format_careplan_result(result_data)
            elif resource_type == "Bundle":
                return format_bundle_apply_result(result_data)
            elif resource_type == "RequestGroup":
                return format_request_group_result(result_data)
            else:
                return f"✅ Apply operation returned:\n\n```json\n{json.dumps(result_data, indent=2)}\n```"
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error during $apply: {e}")
        error_body = e.response.text
        return f"❌ FHIR Server Error: {e.response.status_code}\n\nDetails: {error_body}"
    except Exception as e:
        logger.error(f"Error applying PlanDefinition: {e}")
        return f"❌ Error: {str(e)}"


def format_careplan_result(careplan: dict) -> str:
    """Format CarePlan result from $apply operation."""
    result = "✅ **CarePlan Generated Successfully**\n\n"
    result += f"**ID:** {careplan.get('id', 'N/A')}\n"
    result += f"**Status:** {careplan.get('status', 'unknown')}\n"
    result += f"**Intent:** {careplan.get('intent', 'unknown')}\n"
    
    # Subject
    subject = careplan.get("subject", {})
    result += f"**Subject:** {subject.get('reference', 'N/A')}\n"
    
    # Period
    period = careplan.get("period", {})
    if period:
        result += f"**Period:** {period.get('start', 'N/A')} to {period.get('end', 'N/A')}\n"
    
    # Activities
    activities = careplan.get("activity", [])
    if activities:
        result += f"\n**📋 Activities ({len(activities)}):**\n"
        for i, activity in enumerate(activities, 1):
            detail = activity.get("detail", {})
            reference = activity.get("reference", {})
            
            if detail:
                kind = detail.get("kind", "Unknown")
                code = detail.get("code", {}).get("text", detail.get("code", {}).get("coding", [{}])[0].get("display", "Unknown"))
                status = detail.get("status", "unknown")
                scheduled = detail.get("scheduledTiming", detail.get("scheduledPeriod", detail.get("scheduledString", {})))
                
                result += f"\n  **{i}. {code}**\n"
                result += f"     Kind: {kind}\n"
                result += f"     Status: {status}\n"
                if scheduled:
                    result += f"     Scheduled: {json.dumps(scheduled)}\n"
                
                # Product reference (vaccine)
                product = detail.get("productCodeableConcept", {})
                if product:
                    product_text = product.get("text", product.get("coding", [{}])[0].get("display", "N/A"))
                    result += f"     Product: {product_text}\n"
            
            if reference:
                result += f"     Reference: {reference.get('reference', 'N/A')}\n"
    
    # Contained resources
    contained = careplan.get("contained", [])
    if contained:
        result += f"\n**📦 Contained Resources ({len(contained)}):**\n"
        for res in contained:
            result += f"  • {res.get('resourceType', 'Unknown')} (ID: {res.get('id', 'N/A')})\n"
    
    result += f"\n**📄 Full CarePlan JSON:**\n```json\n{json.dumps(careplan, indent=2)}\n```"
    return result


def format_bundle_apply_result(bundle: dict) -> str:
    """Format Bundle result from $apply operation (R5 style)."""
    result = "✅ **Apply Operation Result (Bundle)**\n\n"
    result += f"**Type:** {bundle.get('type', 'unknown')}\n"
    
    entries = bundle.get("entry", [])
    result += f"**Entries:** {len(entries)}\n\n"
    
    for i, entry in enumerate(entries, 1):
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType", "Unknown")
        resource_id = resource.get("id", "N/A")
        
        result += f"**{i}. {resource_type}** (ID: {resource_id})\n"
        
        if resource_type == "RequestGroup":
            result += format_request_group_summary(resource)
        elif resource_type == "CarePlan":
            result += f"   Status: {resource.get('status', 'unknown')}\n"
        elif resource_type in ["MedicationRequest", "ImmunizationRecommendation", "ServiceRequest"]:
            code = resource.get("medicationCodeableConcept", resource.get("code", {}))
            code_text = code.get("text", code.get("coding", [{}])[0].get("display", "N/A"))
            result += f"   Code: {code_text}\n"
        result += "\n"
    
    return result


def format_request_group_result(rg: dict) -> str:
    """Format RequestGroup result."""
    result = "✅ **RequestGroup Generated**\n\n"
    result += f"**ID:** {rg.get('id', 'N/A')}\n"
    result += f"**Status:** {rg.get('status', 'unknown')}\n"
    result += f"**Intent:** {rg.get('intent', 'unknown')}\n"
    result += format_request_group_summary(rg)
    return result


def format_request_group_summary(rg: dict) -> str:
    """Format RequestGroup actions summary."""
    result = ""
    actions = rg.get("action", [])
    if actions:
        result += f"   **Actions ({len(actions)}):**\n"
        for action in actions:
            title = action.get("title", action.get("description", "Untitled"))
            result += f"      • {title}\n"
            
            resource = action.get("resource", {})
            if resource:
                result += f"        Resource: {resource.get('reference', 'N/A')}\n"
    return result


@mcp.tool()
async def get_plan_definition_data_requirements(plan_definition_id: str = "") -> str:
    """Get data requirements for a PlanDefinition to understand what patient data is needed."""
    logger.info(f"Getting data requirements for PlanDefinition: {plan_definition_id}")
    
    if not plan_definition_id.strip():
        return "❌ Error: plan_definition_id is required"
    
    try:
        async with get_fhir_client() as client:
            response = await client.get(f"/PlanDefinition/{plan_definition_id.strip()}/$data-requirements")
            response.raise_for_status()
            library = response.json()
            
            result = "📊 **Data Requirements for PlanDefinition**\n\n"
            
            data_reqs = library.get("dataRequirement", [])
            if data_reqs:
                result += f"**Required Data Elements ({len(data_reqs)}):**\n\n"
                for req in data_reqs:
                    req_type = req.get("type", "Unknown")
                    result += f"• **{req_type}**\n"
                    
                    # Profile
                    profiles = req.get("profile", [])
                    if profiles:
                        result += f"  Profiles: {', '.join(profiles)}\n"
                    
                    # Code filters
                    code_filters = req.get("codeFilter", [])
                    for cf in code_filters:
                        path = cf.get("path", "N/A")
                        valueset = cf.get("valueSet", "N/A")
                        result += f"  Code Filter: {path} from {valueset}\n"
                    
                    # Date filters
                    date_filters = req.get("dateFilter", [])
                    for df in date_filters:
                        path = df.get("path", "N/A")
                        result += f"  Date Filter: {path}\n"
                    
                    result += "\n"
            else:
                result += "No specific data requirements defined.\n"
            
            return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return "❌ The $data-requirements operation may not be supported by this FHIR server."
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"Error getting data requirements: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def search_patients(name: str = "", identifier: str = "", birthdate: str = "") -> str:
    """Search for patients on the FHIR server with optional name, identifier, or birthdate filters."""
    logger.info(f"Searching patients: name={name}, identifier={identifier}, birthdate={birthdate}")
    
    try:
        async with get_fhir_client() as client:
            params = {"_count": "50"}
            if name.strip():
                params["name"] = name.strip()
            if identifier.strip():
                params["identifier"] = identifier.strip()
            if birthdate.strip():
                params["birthdate"] = birthdate.strip()
            
            response = await client.get("/Patient", params=params)
            response.raise_for_status()
            bundle = response.json()
            
            entries = bundle.get("entry", [])
            total = bundle.get("total", len(entries))
            
            if not entries:
                return "👤 No patients found matching the criteria."
            
            result = f"👤 Found {total} patient(s):\n\n"
            for entry in entries:
                resource = entry.get("resource", {})
                result += format_resource_summary(resource) + "\n\n"
            
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error searching patients: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_patient(patient_id: str = "") -> str:
    """Get detailed information about a specific patient."""
    logger.info(f"Getting patient: {patient_id}")
    
    if not patient_id.strip():
        return "❌ Error: patient_id is required"
    
    try:
        async with get_fhir_client() as client:
            response = await client.get(f"/Patient/{patient_id.strip()}")
            response.raise_for_status()
            patient = response.json()
            
            result = "👤 **Patient Details**\n\n"
            result += f"**ID:** {patient.get('id')}\n"
            
            # Name
            names = patient.get("name", [])
            if names:
                name_obj = names[0]
                given = " ".join(name_obj.get("given", []))
                family = name_obj.get("family", "")
                result += f"**Name:** {given} {family}\n"
            
            # Demographics
            result += f"**Birth Date:** {patient.get('birthDate', 'Unknown')}\n"
            result += f"**Gender:** {patient.get('gender', 'Unknown')}\n"
            
            # Identifiers
            identifiers = patient.get("identifier", [])
            if identifiers:
                result += "**Identifiers:**\n"
                for ident in identifiers:
                    system = ident.get("system", "Unknown")
                    value = ident.get("value", "N/A")
                    result += f"  • {system}: {value}\n"
            
            # Address
            addresses = patient.get("address", [])
            if addresses:
                addr = addresses[0]
                addr_lines = addr.get("line", [])
                city = addr.get("city", "")
                state = addr.get("state", "")
                postal = addr.get("postalCode", "")
                result += f"**Address:** {', '.join(addr_lines)}, {city}, {state} {postal}\n"
            
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error getting patient: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_patient_immunizations(patient_id: str = "") -> str:
    """Get immunization history for a patient."""
    logger.info(f"Getting immunizations for patient: {patient_id}")
    
    if not patient_id.strip():
        return "❌ Error: patient_id is required"
    
    try:
        async with get_fhir_client() as client:
            params = {"patient": f"Patient/{patient_id.strip()}", "_count": "100"}
            response = await client.get("/Immunization", params=params)
            response.raise_for_status()
            bundle = response.json()
            
            entries = bundle.get("entry", [])
            
            if not entries:
                return f"💉 No immunizations found for patient {patient_id}"
            
            result = f"💉 **Immunization History for Patient {patient_id}** ({len(entries)} records):\n\n"
            
            for entry in entries:
                imm = entry.get("resource", {})
                vaccine_code = imm.get("vaccineCode", {})
                vaccine_text = vaccine_code.get("text", "Unknown")
                if not vaccine_text or vaccine_text == "Unknown":
                    codings = vaccine_code.get("coding", [])
                    if codings:
                        vaccine_text = codings[0].get("display", codings[0].get("code", "Unknown"))
                
                result += f"• **{vaccine_text}**\n"
                result += f"  ID: {imm.get('id', 'N/A')}\n"
                result += f"  Status: {imm.get('status', 'unknown')}\n"
                result += f"  Date: {imm.get('occurrenceDateTime', 'Unknown')}\n"
                
                dose_number = imm.get("protocolApplied", [{}])[0].get("doseNumberPositiveInt", 
                              imm.get("protocolApplied", [{}])[0].get("doseNumberString", "N/A"))
                result += f"  Dose Number: {dose_number}\n"
                
                lot = imm.get("lotNumber")
                if lot:
                    result += f"  Lot Number: {lot}\n"
                result += "\n"
            
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error getting immunizations: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def create_immunization(patient_id: str = "", vaccine_code: str = "", vaccine_system: str = "", vaccine_display: str = "", occurrence_date: str = "", status: str = "completed", lot_number: str = "", dose_number: str = "") -> str:
    """Create a new Immunization record for a patient."""
    logger.info(f"Creating immunization for patient {patient_id}")
    
    if not patient_id.strip():
        return "❌ Error: patient_id is required"
    if not vaccine_code.strip():
        return "❌ Error: vaccine_code is required"
    
    try:
        immunization = {
            "resourceType": "Immunization",
            "status": status.strip() if status.strip() else "completed",
            "vaccineCode": {
                "coding": [{
                    "system": vaccine_system.strip() if vaccine_system.strip() else "http://hl7.org/fhir/sid/cvx",
                    "code": vaccine_code.strip(),
                    "display": vaccine_display.strip() if vaccine_display.strip() else vaccine_code.strip()
                }],
                "text": vaccine_display.strip() if vaccine_display.strip() else vaccine_code.strip()
            },
            "patient": {
                "reference": f"Patient/{patient_id.strip()}"
            },
            "occurrenceDateTime": occurrence_date.strip() if occurrence_date.strip() else datetime.now(timezone.utc).isoformat(),
            "primarySource": True
        }
        
        if lot_number.strip():
            immunization["lotNumber"] = lot_number.strip()
        
        if dose_number.strip():
            try:
                dose_int = int(dose_number.strip())
                immunization["protocolApplied"] = [{
                    "doseNumberPositiveInt": dose_int
                }]
            except ValueError:
                immunization["protocolApplied"] = [{
                    "doseNumberString": dose_number.strip()
                }]
        
        async with get_fhir_client() as client:
            response = await client.post("/Immunization", json=immunization)
            response.raise_for_status()
            created = response.json()
            
            return f"✅ Immunization created successfully!\n\n{format_resource_summary(created)}\n\nID: {created.get('id')}"
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating immunization: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}\n\nDetails: {e.response.text}"
    except Exception as e:
        logger.error(f"Error creating immunization: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def create_observation(patient_id: str = "", code: str = "", code_system: str = "", code_display: str = "", value_string: str = "", value_quantity: str = "", value_unit: str = "", status: str = "final", effective_date: str = "") -> str:
    """Create a new Observation record for a patient (e.g., for pre-vaccination screening)."""
    logger.info(f"Creating observation for patient {patient_id}")
    
    if not patient_id.strip():
        return "❌ Error: patient_id is required"
    if not code.strip():
        return "❌ Error: code is required"
    
    try:
        observation = {
            "resourceType": "Observation",
            "status": status.strip() if status.strip() else "final",
            "code": {
                "coding": [{
                    "system": code_system.strip() if code_system.strip() else "http://loinc.org",
                    "code": code.strip(),
                    "display": code_display.strip() if code_display.strip() else code.strip()
                }],
                "text": code_display.strip() if code_display.strip() else code.strip()
            },
            "subject": {
                "reference": f"Patient/{patient_id.strip()}"
            },
            "effectiveDateTime": effective_date.strip() if effective_date.strip() else datetime.now(timezone.utc).isoformat()
        }
        
        if value_string.strip():
            observation["valueString"] = value_string.strip()
        elif value_quantity.strip():
            observation["valueQuantity"] = {
                "value": float(value_quantity.strip()),
                "unit": value_unit.strip() if value_unit.strip() else "",
                "system": "http://unitsofmeasure.org"
            }
        
        async with get_fhir_client() as client:
            response = await client.post("/Observation", json=observation)
            response.raise_for_status()
            created = response.json()
            
            return f"✅ Observation created successfully!\n\n{format_resource_summary(created)}\n\nID: {created.get('id')}"
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating observation: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}\n\nDetails: {e.response.text}"
    except Exception as e:
        logger.error(f"Error creating observation: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def search_valueset(name: str = "", url: str = "") -> str:
    """Search for ValueSets on the FHIR server."""
    logger.info(f"Searching ValueSets: name={name}, url={url}")
    
    try:
        async with get_fhir_client() as client:
            params = {"_count": "50"}
            if name.strip():
                params["name:contains"] = name.strip()
            if url.strip():
                params["url"] = url.strip()
            
            response = await client.get("/ValueSet", params=params)
            response.raise_for_status()
            bundle = response.json()
            
            entries = bundle.get("entry", [])
            
            if not entries:
                return "📚 No ValueSets found matching the criteria."
            
            result = f"📚 Found {len(entries)} ValueSet(s):\n\n"
            for entry in entries:
                vs = entry.get("resource", {})
                result += f"• **{vs.get('title', vs.get('name', 'Untitled'))}**\n"
                result += f"  ID: {vs.get('id', 'N/A')}\n"
                result += f"  URL: {vs.get('url', 'N/A')}\n"
                result += f"  Status: {vs.get('status', 'unknown')}\n"
                result += f"  Description: {vs.get('description', 'No description')[:100]}...\n\n"
            
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error searching ValueSets: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def expand_valueset(valueset_id: str = "", valueset_url: str = "", filter_text: str = "") -> str:
    """Expand a ValueSet to get its list of codes using the $expand operation."""
    logger.info(f"Expanding ValueSet: id={valueset_id}, url={valueset_url}")
    
    if not valueset_id.strip() and not valueset_url.strip():
        return "❌ Error: Either valueset_id or valueset_url is required"
    
    try:
        async with get_fhir_client() as client:
            if valueset_id.strip():
                url = f"/ValueSet/{valueset_id.strip()}/$expand"
                params = {}
            else:
                url = "/ValueSet/$expand"
                params = {"url": valueset_url.strip()}
            
            if filter_text.strip():
                params["filter"] = filter_text.strip()
            
            response = await client.get(url, params=params)
            response.raise_for_status()
            vs = response.json()
            
            result = f"📚 **ValueSet Expansion: {vs.get('name', 'Unnamed')}**\n\n"
            
            expansion = vs.get("expansion", {})
            contains = expansion.get("contains", [])
            
            result += f"**Total codes:** {expansion.get('total', len(contains))}\n\n"
            
            if contains:
                result += "**Codes:**\n"
                for code_entry in contains[:50]:  # Limit to first 50
                    system = code_entry.get("system", "Unknown")
                    code = code_entry.get("code", "N/A")
                    display = code_entry.get("display", "N/A")
                    result += f"• `{code}` - {display}\n"
                    result += f"  System: {system}\n"
                
                if len(contains) > 50:
                    result += f"\n... and {len(contains) - 50} more codes\n"
            else:
                result += "No codes in expansion.\n"
            
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}\n\nDetails: {e.response.text}"
    except Exception as e:
        logger.error(f"Error expanding ValueSet: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def search_codesystem(name: str = "", url: str = "") -> str:
    """Search for CodeSystems on the FHIR server."""
    logger.info(f"Searching CodeSystems: name={name}, url={url}")
    
    try:
        async with get_fhir_client() as client:
            params = {"_count": "50"}
            if name.strip():
                params["name:contains"] = name.strip()
            if url.strip():
                params["url"] = url.strip()
            
            response = await client.get("/CodeSystem", params=params)
            response.raise_for_status()
            bundle = response.json()
            
            entries = bundle.get("entry", [])
            
            if not entries:
                return "📖 No CodeSystems found matching the criteria."
            
            result = f"📖 Found {len(entries)} CodeSystem(s):\n\n"
            for entry in entries:
                cs = entry.get("resource", {})
                result += f"• **{cs.get('title', cs.get('name', 'Untitled'))}**\n"
                result += f"  ID: {cs.get('id', 'N/A')}\n"
                result += f"  URL: {cs.get('url', 'N/A')}\n"
                result += f"  Status: {cs.get('status', 'unknown')}\n"
                result += f"  Content: {cs.get('content', 'unknown')}\n"
                result += f"  Count: {cs.get('count', 'N/A')} concepts\n\n"
            
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error searching CodeSystems: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def lookup_code(system: str = "", code: str = "") -> str:
    """Look up details about a specific code using the CodeSystem $lookup operation."""
    logger.info(f"Looking up code: system={system}, code={code}")
    
    if not system.strip():
        return "❌ Error: system (CodeSystem URL) is required"
    if not code.strip():
        return "❌ Error: code is required"
    
    try:
        async with get_fhir_client() as client:
            params = {
                "system": system.strip(),
                "code": code.strip()
            }
            
            response = await client.get("/CodeSystem/$lookup", params=params)
            response.raise_for_status()
            params_result = response.json()
            
            result = f"🔍 **Code Lookup Result**\n\n"
            result += f"**System:** {system}\n"
            result += f"**Code:** {code}\n\n"
            
            for param in params_result.get("parameter", []):
                name = param.get("name", "Unknown")
                value = param.get("valueString", param.get("valueCode", param.get("valueBoolean", param.get("valueCoding", "N/A"))))
                
                if name == "display":
                    result += f"**Display:** {value}\n"
                elif name == "definition":
                    result += f"**Definition:** {value}\n"
                elif name == "designation":
                    parts = param.get("part", [])
                    for part in parts:
                        if part.get("name") == "value":
                            result += f"**Designation:** {part.get('valueString', 'N/A')}\n"
                elif name == "property":
                    parts = param.get("part", [])
                    prop_code = None
                    prop_value = None
                    for part in parts:
                        if part.get("name") == "code":
                            prop_code = part.get("valueCode", "N/A")
                        elif part.get("name") == "value":
                            prop_value = part.get("valueString", part.get("valueCode", part.get("valueBoolean", "N/A")))
                    if prop_code:
                        result += f"**Property {prop_code}:** {prop_value}\n"
            
            return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"❌ Code not found: {code} in system {system}"
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error looking up code: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def create_patient(family_name: str = "", given_name: str = "", birth_date: str = "", gender: str = "", identifier_value: str = "", identifier_system: str = "") -> str:
    """Create a new Patient resource on the FHIR server."""
    logger.info(f"Creating patient: {given_name} {family_name}")
    
    if not family_name.strip():
        return "❌ Error: family_name is required"
    
    try:
        patient = {
            "resourceType": "Patient",
            "name": [{
                "use": "official",
                "family": family_name.strip(),
                "given": [given_name.strip()] if given_name.strip() else []
            }]
        }
        
        if birth_date.strip():
            patient["birthDate"] = birth_date.strip()
        
        if gender.strip():
            patient["gender"] = gender.strip().lower()
        
        if identifier_value.strip():
            patient["identifier"] = [{
                "system": identifier_system.strip() if identifier_system.strip() else "http://example.org/fhir/identifier",
                "value": identifier_value.strip()
            }]
        
        async with get_fhir_client() as client:
            response = await client.post("/Patient", json=patient)
            response.raise_for_status()
            created = response.json()
            
            return f"✅ Patient created successfully!\n\n{format_resource_summary(created)}\n\nID: {created.get('id')}"
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error creating patient: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}\n\nDetails: {e.response.text}"
    except Exception as e:
        logger.error(f"Error creating patient: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_fhir_resource(resource_type: str = "", resource_id: str = "") -> str:
    """Get any FHIR resource by type and ID."""
    logger.info(f"Getting {resource_type}/{resource_id}")
    
    if not resource_type.strip():
        return "❌ Error: resource_type is required"
    if not resource_id.strip():
        return "❌ Error: resource_id is required"
    
    try:
        async with get_fhir_client() as client:
            response = await client.get(f"/{resource_type.strip()}/{resource_id.strip()}")
            response.raise_for_status()
            resource = response.json()
            
            result = f"📄 **{resource.get('resourceType', 'Unknown')} Details**\n\n"
            result += f"```json\n{json.dumps(resource, indent=2)}\n```"
            return result
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return f"❌ Resource not found: {resource_type}/{resource_id}"
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error getting resource: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def search_fhir_resources(resource_type: str = "", search_params: str = "") -> str:
    """Search for FHIR resources with custom search parameters (format: key=value&key2=value2)."""
    logger.info(f"Searching {resource_type} with params: {search_params}")
    
    if not resource_type.strip():
        return "❌ Error: resource_type is required"
    
    try:
        params = {}
        if search_params.strip():
            for param in search_params.strip().split("&"):
                if "=" in param:
                    key, value = param.split("=", 1)
                    params[key] = value
        
        params["_count"] = params.get("_count", "50")
        
        async with get_fhir_client() as client:
            response = await client.get(f"/{resource_type.strip()}", params=params)
            response.raise_for_status()
            bundle = response.json()
            
            entries = bundle.get("entry", [])
            total = bundle.get("total", len(entries))
            
            if not entries:
                return f"📄 No {resource_type} resources found."
            
            result = f"📄 Found {total} {resource_type} resource(s):\n\n"
            result += format_bundle_entries(bundle)
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error searching resources: {e}")
        return f"❌ Error: {str(e)}"


@mcp.tool()
async def get_server_capability() -> str:
    """Get the FHIR server's capability statement to see supported resources and operations."""
    logger.info("Getting server capability statement")
    
    try:
        async with get_fhir_client() as client:
            response = await client.get("/metadata")
            response.raise_for_status()
            cap = response.json()
            
            result = f"🏥 **FHIR Server Capability Statement**\n\n"
            result += f"**Server:** {FHIR_BASE_URL}\n"
            result += f"**FHIR Version:** {cap.get('fhirVersion', 'Unknown')}\n"
            result += f"**Software:** {cap.get('software', {}).get('name', 'Unknown')} v{cap.get('software', {}).get('version', 'N/A')}\n"
            result += f"**Status:** {cap.get('status', 'Unknown')}\n\n"
            
            rest = cap.get("rest", [])
            if rest:
                server_rest = rest[0]
                resources = server_rest.get("resource", [])
                
                result += f"**Supported Resources ({len(resources)}):**\n"
                
                # Group resources by key types
                key_resources = ["PlanDefinition", "ActivityDefinition", "Patient", "Immunization", 
                               "Observation", "CarePlan", "ValueSet", "CodeSystem", "Library"]
                
                for res in resources:
                    res_type = res.get("type", "Unknown")
                    if res_type in key_resources:
                        interactions = [i.get("code") for i in res.get("interaction", [])]
                        operations = [o.get("name") for o in res.get("operation", [])]
                        
                        result += f"\n• **{res_type}**\n"
                        result += f"  Interactions: {', '.join(interactions)}\n"
                        if operations:
                            result += f"  Operations: {', '.join(operations)}\n"
                
                result += f"\n... and {len(resources) - len(key_resources)} more resource types\n"
            
            return result
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error: {e}")
        return f"❌ FHIR Server Error: {e.response.status_code}"
    except Exception as e:
        logger.error(f"Error getting capability: {e}")
        return f"❌ Error: {str(e)}"


# === SERVER STARTUP ===
if __name__ == "__main__":
    logger.info(f"Starting FHIR Immunization MCP server...")
    logger.info(f"FHIR Base URL: {FHIR_BASE_URL}")
    
    try:
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        sys.exit(1)