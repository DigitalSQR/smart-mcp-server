package com.fhir.immunization.mcp

import ca.uhn.fhir.context.FhirContext
import ca.uhn.fhir.parser.IParser
import io.modelcontextprotocol.kotlin.sdk.*
import io.modelcontextprotocol.kotlin.sdk.server.Server
import io.modelcontextprotocol.kotlin.sdk.server.ServerOptions
import io.modelcontextprotocol.kotlin.sdk.server.StdioServerTransport
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.*
import org.apache.commons.compress.archivers.tar.TarArchiveInputStream
import org.hl7.fhir.r4.model.*
import java.io.*
import java.net.URL
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.*
import java.util.logging.Logger
import java.util.zip.GZIPInputStream

/**
 * FHIR Immunization MCP Server using HAPI FHIR Structures.
 * This server provides local FHIR resource storage and WHO SMART Immunization workflow support.
 * Pre-loads the WHO SMART Immunizations Implementation Guide on startup.
 */

private val logger = Logger.getLogger("FhirImmunizationServer")
private val fhirContext: FhirContext = FhirContext.forR4()
private val jsonParser: IParser = fhirContext.newJsonParser().setPrettyPrint(true)

// WHO SMART Immunizations IG package URL
private const val WHO_SMART_IG_URL = "https://worldhealthorganization.github.io/smart-immunizations/package.tgz"

// In-memory FHIR resource store (simulating Android FHIR Engine)
private val resourceStore = FhirResourceStore()

class FhirResourceStore {
    private val resources = mutableMapOf<String, MutableMap<String, Resource>>()
    private var loadedResourceCount = 0
    
    fun <T : Resource> create(resource: T): String {
        val resourceType = resource.fhirType()
        val id = resource.idElement?.idPart ?: UUID.randomUUID().toString()
        resource.id = id
        
        resources.getOrPut(resourceType) { mutableMapOf() }[id] = resource
        loadedResourceCount++
        return id
    }
    
    inline fun <reified T : Resource> get(id: String): T? {
        val resourceType = T::class.java.simpleName
        @Suppress("UNCHECKED_CAST")
        return resources[resourceType]?.get(id) as? T
    }
    
    fun get(resourceType: String, id: String): Resource? {
        return resources[resourceType]?.get(id)
    }
    
    inline fun <reified T : Resource> search(predicate: (T) -> Boolean = { true }): List<T> {
        val resourceType = T::class.java.simpleName
        @Suppress("UNCHECKED_CAST")
        return resources[resourceType]?.values
            ?.filterIsInstance<T>()
            ?.filter(predicate)
            ?: emptyList()
    }
    
    fun searchByType(resourceType: String): List<Resource> {
        return resources[resourceType]?.values?.toList() ?: emptyList()
    }
    
    fun <T : Resource> update(resource: T): Boolean {
        val resourceType = resource.fhirType()
        val id = resource.idElement?.idPart ?: return false
        
        if (resources[resourceType]?.containsKey(id) == true) {
            resources[resourceType]!![id] = resource
            return true
        }
        return false
    }
    
    inline fun <reified T : Resource> delete(id: String): Boolean {
        val resourceType = T::class.java.simpleName
        return resources[resourceType]?.remove(id) != null
    }
    
    fun getResourceTypeCounts(): Map<String, Int> {
        return resources.mapValues { it.value.size }
    }
    
    fun getTotalResourceCount(): Int = loadedResourceCount
}

// Helper functions
fun Resource.toJsonString(): String = jsonParser.encodeResourceToString(this)

fun formatResourceSummary(resource: Resource): String {
    return when (resource) {
        is PlanDefinition -> {
            val title = resource.title ?: resource.name ?: "Untitled"
            val status = resource.status?.toCode() ?: "unknown"
            val description = resource.description?.take(200) ?: "No description"
            "📋 $title (ID: ${resource.idElement?.idPart})\n   Status: $status\n   Description: $description..."
        }
        is Patient -> {
            val name = resource.nameFirstRep?.let { 
                "${it.givenAsSingleString ?: ""} ${it.family ?: ""}".trim() 
            } ?: "Unknown"
            val birthDate = resource.birthDateElement?.valueAsString ?: "Unknown"
            "👤 $name (ID: ${resource.idElement?.idPart})\n   Birth Date: $birthDate"
        }
        is Immunization -> {
            val vaccine = resource.vaccineCode?.text 
                ?: resource.vaccineCode?.codingFirstRep?.display 
                ?: "Unknown vaccine"
            val status = resource.status?.toCode() ?: "unknown"
            val date = resource.occurrenceDateTimeType?.valueAsString ?: "Unknown date"
            val protocol = resource.protocolAppliedFirstRep
            val doseNum = protocol?.doseNumberPositiveIntType?.value 
                ?: protocol?.doseNumberStringType?.value 
                ?: "N/A"
            val series = protocol?.series ?: "N/A"
            "💉 $vaccine (ID: ${resource.idElement?.idPart})\n   Status: $status, Date: $date\n   Dose: $doseNum, Series: $series"
        }
        is Observation -> {
            val code = resource.code?.text 
                ?: resource.code?.codingFirstRep?.display 
                ?: "Unknown observation"
            val status = resource.status?.toCode() ?: "unknown"
            val value = resource.valueStringType?.value 
                ?: resource.valueQuantity?.value?.toString() 
                ?: "N/A"
            "🔬 $code (ID: ${resource.idElement?.idPart})\n   Status: $status, Value: $value"
        }
        is CarePlan -> {
            val status = resource.status?.toCode() ?: "unknown"
            val intent = resource.intent?.toCode() ?: "unknown"
            val activities = resource.activity?.size ?: 0
            "📝 CarePlan (ID: ${resource.idElement?.idPart})\n   Status: $status, Intent: $intent\n   Activities: $activities"
        }
        is ActivityDefinition -> {
            val title = resource.title ?: resource.name ?: "Untitled"
            val status = resource.status?.toCode() ?: "unknown"
            "⚙️ ActivityDefinition: $title (ID: ${resource.idElement?.idPart})\n   Status: $status"
        }
        is Library -> {
            val title = resource.title ?: resource.name ?: "Untitled"
            val type = resource.type?.codingFirstRep?.code ?: "unknown"
            "📚 Library: $title (ID: ${resource.idElement?.idPart})\n   Type: $type"
        }
        else -> "📄 ${resource.fhirType()} (ID: ${resource.idElement?.idPart})"
    }
}

fun formatActions(actions: List<PlanDefinition.PlanDefinitionActionComponent>, indent: Int = 0): String {
    val prefix = " ".repeat(indent)
    val result = StringBuilder()
    
    for (action in actions) {
        val title = action.title ?: action.description ?: "Untitled action"
        result.append("$prefix• **$title**\n")
        
        action.description?.let { desc ->
            if (desc != title) {
                result.append("$prefix  Description: ${desc.take(100)}...\n")
            }
        }
        
        for (condition in action.condition) {
            val kind = condition.kind?.toCode() ?: "unknown"
            val expr = condition.expression?.expression ?: "N/A"
            result.append("$prefix  Condition ($kind): $expr\n")
        }
        
        action.definitionCanonicalType?.value?.let { def ->
            result.append("$prefix  Definition: $def\n")
        }
        
        if (action.input.isNotEmpty()) {
            result.append("$prefix  📥 Inputs:\n")
            for (input in action.input) {
                val inputType = input.type ?: "Unknown"
                result.append("$prefix    - $inputType\n")
            }
        }
        
        if (action.action.isNotEmpty()) {
            result.append(formatActions(action.action, indent + 4))
        }
    }
    
    return result.toString()
}

/**
 * CarePlan generation from PlanDefinition (simulating $apply operation).
 */
fun generateCarePlan(planDefinition: PlanDefinition, patient: Patient, encounterId: String? = null): CarePlan {
    val carePlan = CarePlan().apply {
        id = UUID.randomUUID().toString()
        status = CarePlan.CarePlanStatus.DRAFT
        intent = CarePlan.CarePlanIntent.PROPOSAL
        subject = Reference("Patient/${patient.idElement?.idPart}")
        instantiatesCanonical = listOf(CanonicalType(planDefinition.url ?: "PlanDefinition/${planDefinition.idElement?.idPart}"))
        created = Date()
        title = "CarePlan from ${planDefinition.title ?: planDefinition.name}"
        description = planDefinition.description
        
        encounterId?.let { encounter = Reference("Encounter/$it") }
        
        // Convert PlanDefinition actions to CarePlan activities
        for (action in planDefinition.action) {
            val activity = CarePlan.CarePlanActivityComponent().apply {
                detail = CarePlan.CarePlanActivityDetailComponent().apply {
                    status = CarePlan.CarePlanActivityStatus.NOTSTARTED
                    description = action.description ?: action.title
                    
                    action.code?.let { actionCode ->
                        code = CodeableConcept().apply {
                            coding = actionCode.coding
                            text = actionCode.text
                        }
                    }
                    
                    // Set timing if specified
                    action.timingTiming?.let { scheduled = it }
                    action.timingAge?.let { 
                        // Convert Age to a description
                        description = "${description ?: ""} (at age ${it.value} ${it.unit})"
                    }
                }
            }
            addActivity(activity)
            
            // Process nested actions
            for (nestedAction in action.action) {
                val nestedActivity = CarePlan.CarePlanActivityComponent().apply {
                    detail = CarePlan.CarePlanActivityDetailComponent().apply {
                        status = CarePlan.CarePlanActivityStatus.NOTSTARTED
                        description = nestedAction.description ?: nestedAction.title
                        nestedAction.code?.let { code = it }
                    }
                }
                addActivity(nestedActivity)
            }
        }
    }
    
    return carePlan
}

/**
 * Load WHO SMART Immunizations Implementation Guide from package.tgz
 */
fun loadWhoSmartImmunizationsIG() {
    logger.info("Loading WHO SMART Immunizations Implementation Guide...")
    
    try {
        val url = URL(WHO_SMART_IG_URL)
        logger.info("Downloading package from: $WHO_SMART_IG_URL")
        
        url.openStream().use { inputStream ->
            GZIPInputStream(inputStream).use { gzipStream ->
                TarArchiveInputStream(gzipStream).use { tarStream ->
                    var entry = tarStream.nextTarEntry
                    var loadedCount = 0
                    var errorCount = 0
                    
                    while (entry != null) {
                        if (!entry.isDirectory && entry.name.endsWith(".json") && 
                            entry.name.startsWith("package/") && 
                            !entry.name.contains("package.json") &&
                            !entry.name.contains(".index.json")) {
                            
                            try {
                                val content = tarStream.readBytes().toString(Charsets.UTF_8)
                                
                                // Skip non-resource JSON files
                                if (content.contains("\"resourceType\"")) {
                                    val resource = jsonParser.parseResource(content) as Resource
                                    
                                    // Only load certain resource types we care about
                                    val resourceType = resource.fhirType()
                                    if (resourceType in listOf(
                                        "PlanDefinition", "ActivityDefinition", "Library",
                                        "ValueSet", "CodeSystem", "Questionnaire",
                                        "StructureDefinition", "ConceptMap"
                                    )) {
                                        resourceStore.create(resource)
                                        loadedCount++
                                        
                                        if (loadedCount % 100 == 0) {
                                            logger.info("Loaded $loadedCount resources...")
                                        }
                                    }
                                }
                            } catch (e: Exception) {
                                errorCount++
                                // Log only first few errors to avoid spam
                                if (errorCount <= 5) {
                                    logger.warning("Failed to parse ${entry.name}: ${e.message}")
                                }
                            }
                        }
                        entry = tarStream.nextTarEntry
                    }
                    
                    logger.info("WHO SMART IG loading complete: $loadedCount resources loaded, $errorCount errors")
                }
            }
        }
    } catch (e: Exception) {
        logger.severe("Failed to load WHO SMART Immunizations IG: ${e.message}")
        logger.info("Server will continue without pre-loaded IG resources")
    }
    
    // Log summary of loaded resources
    val counts = resourceStore.getResourceTypeCounts()
    logger.info("Resource store summary:")
    for ((type, count) in counts.entries.sortedByDescending { it.value }) {
        logger.info("  $type: $count")
    }
}

/**
 * Load resources from local data directory
 */
fun loadLocalData(dataDir: File) {
    if (!dataDir.exists()) {
        logger.info("Data directory does not exist: ${dataDir.absolutePath}")
        return
    }
    
    var loadedCount = 0
    dataDir.listFiles { file -> file.extension == "json" }?.forEach { file ->
        try {
            val resource = jsonParser.parseResource(file.readText()) as Resource
            resourceStore.create(resource)
            loadedCount++
            logger.info("Loaded ${resource.fhirType()}/${resource.idElement?.idPart} from ${file.name}")
        } catch (e: Exception) {
            logger.warning("Failed to load ${file.name}: ${e.message}")
        }
    }
    logger.info("Loaded $loadedCount resources from local data directory")
}

fun main() = runBlocking {
    logger.info("Starting FHIR Immunization MCP Server...")
    
    // Load WHO SMART Immunizations IG first
    val skipIgLoad = System.getenv("SKIP_IG_LOAD")?.toBoolean() ?: false
    if (!skipIgLoad) {
        loadWhoSmartImmunizationsIG()
    } else {
        logger.info("Skipping WHO SMART IG load (SKIP_IG_LOAD=true)")
    }
    
    // Load local data if DATA_DIR is specified
    val dataDir = System.getenv("DATA_DIR")
    if (dataDir != null) {
        loadLocalData(File(dataDir))
    }
    
    val server = Server(
        serverInfo = Implementation(
            name = "fhir-immunization-server",
            version = "1.0.0"
        ),
        options = ServerOptions(
            capabilities = ServerCapabilities(
                tools = ServerCapabilities.Tools(listChanged = true)
            )
        )
    )
    
    // Register all tools
    registerTools(server)
    
    // Start with stdio transport
    val transport = StdioServerTransport()
    server.connect(transport)
    
    logger.info("FHIR Immunization MCP Server started successfully")
    logger.info("Total resources in store: ${resourceStore.getTotalResourceCount()}")
}

fun registerTools(server: Server) {
    
    // ==================== PlanDefinition Tools ====================
    
    server.addTool(
        name = "list_plan_definitions",
        description = "List available PlanDefinitions from WHO SMART Immunizations IG with optional status and title filters"
    ) { request ->
        val args = request.arguments
        val status = args["status"]?.jsonPrimitive?.contentOrNull ?: ""
        val title = args["title"]?.jsonPrimitive?.contentOrNull ?: ""
        val limit = args["limit"]?.jsonPrimitive?.intOrNull ?: 50
        
        val planDefs = resourceStore.search<PlanDefinition> { pd ->
            (status.isBlank() || pd.status?.toCode() == status) &&
            (title.isBlank() || pd.title?.contains(title, ignoreCase = true) == true ||
                pd.name?.contains(title, ignoreCase = true) == true ||
                pd.idElement?.idPart?.contains(title, ignoreCase = true) == true)
        }.take(limit)
        
        if (planDefs.isEmpty()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("📋 No PlanDefinitions found matching the criteria."))
            )
        }
        
        val total = resourceStore.search<PlanDefinition>().size
        val result = StringBuilder("📋 Found ${planDefs.size} PlanDefinition(s) (showing up to $limit of $total total):\n\n")
        for (pd in planDefs) {
            result.append("• **${pd.title ?: pd.name ?: "Untitled"}**\n")
            result.append("  ID: ${pd.idElement?.idPart}\n")
            result.append("  URL: ${pd.url ?: "N/A"}\n")
            result.append("  Status: ${pd.status?.toCode() ?: "unknown"}\n")
            val desc = pd.description?.take(100) ?: "No description"
            result.append("  Description: $desc...\n\n")
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    server.addTool(
        name = "get_plan_definition",
        description = "Get detailed information about a specific PlanDefinition including actions and requirements"
    ) { request ->
        val planDefinitionId = request.arguments["plan_definition_id"]?.jsonPrimitive?.contentOrNull
        
        if (planDefinitionId.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: plan_definition_id is required"))
            )
        }
        
        val pd = resourceStore.get<PlanDefinition>(planDefinitionId)
            ?: return@addTool CallToolResult(
                content = listOf(TextContent("❌ PlanDefinition not found: $planDefinitionId"))
            )
        
        val result = StringBuilder("📋 **PlanDefinition: ${pd.title ?: pd.name ?: "Untitled"}**\n\n")
        result.append("**ID:** ${pd.idElement?.idPart}\n")
        result.append("**URL:** ${pd.url ?: "N/A"}\n")
        result.append("**Version:** ${pd.version ?: "N/A"}\n")
        result.append("**Status:** ${pd.status?.toCode() ?: "unknown"}\n")
        result.append("**Type:** ${pd.type?.codingFirstRep?.display ?: pd.type?.codingFirstRep?.code ?: "N/A"}\n")
        result.append("**Description:** ${pd.description ?: "No description"}\n\n")
        
        if (pd.library.isNotEmpty()) {
            result.append("**📚 Libraries:**\n")
            for (lib in pd.library) {
                result.append("  • ${lib.value}\n")
            }
            result.append("\n")
        }
        
        if (pd.goal.isNotEmpty()) {
            result.append("**🎯 Goals:**\n")
            for (goal in pd.goal) {
                val desc = goal.description?.text ?: "No description"
                result.append("  • $desc\n")
            }
            result.append("\n")
        }
        
        if (pd.action.isNotEmpty()) {
            result.append("**⚡ Actions (${pd.action.size}):**\n")
            result.append(formatActions(pd.action, indent = 2))
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    server.addTool(
        name = "apply_plan_definition",
        description = "Apply a PlanDefinition to a patient to generate a CarePlan (simulates FHIR \$apply operation)"
    ) { request ->
        val args = request.arguments
        val planDefinitionId = args["plan_definition_id"]?.jsonPrimitive?.contentOrNull
        val subject = args["subject"]?.jsonPrimitive?.contentOrNull
        val encounterId = args["encounter"]?.jsonPrimitive?.contentOrNull
        
        if (planDefinitionId.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: plan_definition_id is required"))
            )
        }
        
        if (subject.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: subject (Patient reference like 'Patient/123') is required"))
            )
        }
        
        val pd = resourceStore.get<PlanDefinition>(planDefinitionId)
            ?: return@addTool CallToolResult(
                content = listOf(TextContent("❌ PlanDefinition not found: $planDefinitionId"))
            )
        
        val patientId = subject.removePrefix("Patient/")
        val patient = resourceStore.get<Patient>(patientId)
            ?: return@addTool CallToolResult(
                content = listOf(TextContent("❌ Patient not found: $patientId"))
            )
        
        val carePlan = generateCarePlan(pd, patient, encounterId)
        resourceStore.create(carePlan)
        
        val result = StringBuilder("✅ **CarePlan Generated Successfully**\n\n")
        result.append("**ID:** ${carePlan.idElement?.idPart}\n")
        result.append("**Status:** ${carePlan.status?.toCode()}\n")
        result.append("**Intent:** ${carePlan.intent?.toCode()}\n")
        result.append("**Subject:** ${carePlan.subject?.reference}\n")
        result.append("**Title:** ${carePlan.title}\n")
        result.append("**Created:** ${carePlan.created}\n")
        result.append("**Based On:** ${carePlan.instantiatesCanonical?.firstOrNull()?.value}\n\n")
        
        if (carePlan.activity.isNotEmpty()) {
            result.append("**📋 Activities (${carePlan.activity.size}):**\n")
            for ((i, activity) in carePlan.activity.withIndex()) {
                val detail = activity.detail
                result.append("\n  **${i + 1}. ${detail?.description ?: "Activity"}**\n")
                result.append("     Status: ${detail?.status?.toCode() ?: "unknown"}\n")
                detail?.code?.text?.let { result.append("     Code: $it\n") }
            }
        }
        
        result.append("\n**📄 Full CarePlan JSON:**\n```json\n${carePlan.toJsonString()}\n```")
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    // ==================== Patient Tools ====================
    
    server.addTool(
        name = "search_patients",
        description = "Search for patients with optional name, identifier, or birthdate filters"
    ) { request ->
        val args = request.arguments
        val name = args["name"]?.jsonPrimitive?.contentOrNull ?: ""
        val identifier = args["identifier"]?.jsonPrimitive?.contentOrNull ?: ""
        val birthdate = args["birthdate"]?.jsonPrimitive?.contentOrNull ?: ""
        
        val patients = resourceStore.search<Patient> { patient ->
            val nameMatch = name.isBlank() || patient.name.any { n ->
                n.givenAsSingleString?.contains(name, ignoreCase = true) == true ||
                n.family?.contains(name, ignoreCase = true) == true
            }
            val identMatch = identifier.isBlank() || patient.identifier.any { id ->
                id.value == identifier
            }
            val birthMatch = birthdate.isBlank() || patient.birthDateElement?.valueAsString == birthdate
            
            nameMatch && identMatch && birthMatch
        }
        
        if (patients.isEmpty()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("👤 No patients found matching the criteria."))
            )
        }
        
        val result = StringBuilder("👤 Found ${patients.size} patient(s):\n\n")
        for (patient in patients) {
            result.append(formatResourceSummary(patient))
            result.append("\n\n")
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    server.addTool(
        name = "get_patient",
        description = "Get detailed information about a specific patient"
    ) { request ->
        val patientId = request.arguments["patient_id"]?.jsonPrimitive?.contentOrNull
        
        if (patientId.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: patient_id is required"))
            )
        }
        
        val patient = resourceStore.get<Patient>(patientId)
            ?: return@addTool CallToolResult(
                content = listOf(TextContent("❌ Patient not found: $patientId"))
            )
        
        val result = StringBuilder("👤 **Patient Details**\n\n")
        result.append("**ID:** ${patient.idElement?.idPart}\n")
        
        patient.nameFirstRep?.let { name ->
            val given = name.givenAsSingleString ?: ""
            val family = name.family ?: ""
            result.append("**Name:** $given $family\n")
        }
        
        result.append("**Birth Date:** ${patient.birthDateElement?.valueAsString ?: "Unknown"}\n")
        result.append("**Gender:** ${patient.gender?.toCode() ?: "Unknown"}\n")
        
        if (patient.identifier.isNotEmpty()) {
            result.append("**Identifiers:**\n")
            for (ident in patient.identifier) {
                result.append("  • ${ident.system ?: "Unknown"}: ${ident.value}\n")
            }
        }
        
        patient.addressFirstRep?.let { addr ->
            val lines = addr.line.joinToString(", ") { it.value }
            result.append("**Address:** $lines, ${addr.city ?: ""}, ${addr.state ?: ""} ${addr.postalCode ?: ""}\n")
        }
        
        // Show immunization history
        val immunizations = resourceStore.search<Immunization> { imm ->
            imm.patient?.reference?.endsWith(patientId) == true
        }
        if (immunizations.isNotEmpty()) {
            result.append("\n**💉 Immunization History (${immunizations.size}):**\n")
            for (imm in immunizations.take(10)) {
                val vaccine = imm.vaccineCode?.text ?: imm.vaccineCode?.codingFirstRep?.display ?: "Unknown"
                val date = imm.occurrenceDateTimeType?.valueAsString ?: "Unknown"
                result.append("  • $vaccine - $date\n")
            }
            if (immunizations.size > 10) {
                result.append("  ... and ${immunizations.size - 10} more\n")
            }
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    server.addTool(
        name = "create_patient",
        description = "Create a new Patient resource"
    ) { request ->
        val args = request.arguments
        val familyName = args["family_name"]?.jsonPrimitive?.contentOrNull
        val givenName = args["given_name"]?.jsonPrimitive?.contentOrNull ?: ""
        val birthDate = args["birth_date"]?.jsonPrimitive?.contentOrNull ?: ""
        val gender = args["gender"]?.jsonPrimitive?.contentOrNull ?: ""
        val identifierValue = args["identifier_value"]?.jsonPrimitive?.contentOrNull ?: ""
        val identifierSystem = args["identifier_system"]?.jsonPrimitive?.contentOrNull ?: ""
        
        if (familyName.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: family_name is required"))
            )
        }
        
        val patient = Patient().apply {
            addName(HumanName().apply {
                this.family = familyName
                if (givenName.isNotBlank()) addGiven(givenName)
                use = HumanName.NameUse.OFFICIAL
            })
            
            if (birthDate.isNotBlank()) {
                this.birthDateElement = DateType(birthDate)
            }
            
            if (gender.isNotBlank()) {
                this.gender = Enumerations.AdministrativeGender.fromCode(gender.lowercase())
            }
            
            if (identifierValue.isNotBlank()) {
                addIdentifier(Identifier().apply {
                    system = identifierSystem.ifBlank { "http://example.org/fhir/identifier" }
                    value = identifierValue
                })
            }
        }
        
        val id = resourceStore.create(patient)
        
        CallToolResult(
            content = listOf(TextContent("✅ Patient created successfully!\n\n${formatResourceSummary(patient)}\n\nID: $id"))
        )
    }
    
    // ==================== Immunization Tools ====================
    
    server.addTool(
        name = "get_patient_immunizations",
        description = "Get immunization history for a patient including dose and series information"
    ) { request ->
        val patientId = request.arguments["patient_id"]?.jsonPrimitive?.contentOrNull
        
        if (patientId.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: patient_id is required"))
            )
        }
        
        val immunizations = resourceStore.search<Immunization> { imm ->
            imm.patient?.reference?.endsWith(patientId) == true
        }
        
        if (immunizations.isEmpty()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("💉 No immunizations found for patient $patientId"))
            )
        }
        
        val result = StringBuilder("💉 **Immunization History for Patient $patientId** (${immunizations.size} records):\n\n")
        
        for (imm in immunizations) {
            val vaccineText = imm.vaccineCode?.text 
                ?: imm.vaccineCode?.codingFirstRep?.display 
                ?: imm.vaccineCode?.codingFirstRep?.code 
                ?: "Unknown"
            
            result.append("• **$vaccineText**\n")
            result.append("  ID: ${imm.idElement?.idPart}\n")
            result.append("  Status: ${imm.status?.toCode() ?: "unknown"}\n")
            result.append("  Date: ${imm.occurrenceDateTimeType?.valueAsString ?: "Unknown"}\n")
            
            imm.protocolAppliedFirstRep?.let { protocol ->
                val doseNumber = protocol.doseNumberPositiveIntType?.value 
                    ?: protocol.doseNumberStringType?.value 
                    ?: "N/A"
                result.append("  Dose Number: $doseNumber\n")
                
                protocol.series?.let { series ->
                    result.append("  Series: $series\n")
                }
                
                val seriesDoses = protocol.seriesDosesPositiveIntType?.value
                    ?: protocol.seriesDosesStringType?.value
                if (seriesDoses != null) {
                    result.append("  Series Doses: $seriesDoses\n")
                }
                
                if (protocol.targetDisease.isNotEmpty()) {
                    val diseases = protocol.targetDisease.mapNotNull { 
                        it.codingFirstRep?.display ?: it.codingFirstRep?.code 
                    }.joinToString(", ")
                    result.append("  Target Disease: $diseases\n")
                }
            }
            
            imm.lotNumber?.let { result.append("  Lot Number: $it\n") }
            result.append("\n")
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    server.addTool(
        name = "create_immunization",
        description = "Create a new Immunization record with full protocol support including series name and series doses"
    ) { request ->
        val args = request.arguments
        val patientId = args["patient_id"]?.jsonPrimitive?.contentOrNull
        val vaccineCode = args["vaccine_code"]?.jsonPrimitive?.contentOrNull
        val vaccineSystem = args["vaccine_system"]?.jsonPrimitive?.contentOrNull ?: "http://hl7.org/fhir/sid/cvx"
        val vaccineDisplay = args["vaccine_display"]?.jsonPrimitive?.contentOrNull ?: ""
        val occurrenceDate = args["occurrence_date"]?.jsonPrimitive?.contentOrNull ?: ""
        val status = args["status"]?.jsonPrimitive?.contentOrNull ?: "completed"
        val lotNumber = args["lot_number"]?.jsonPrimitive?.contentOrNull ?: ""
        val doseNumber = args["dose_number"]?.jsonPrimitive?.contentOrNull ?: ""
        val series = args["series"]?.jsonPrimitive?.contentOrNull ?: ""
        val seriesDoses = args["series_doses"]?.jsonPrimitive?.contentOrNull ?: ""
        val targetDisease = args["target_disease"]?.jsonPrimitive?.contentOrNull ?: ""
        val targetDiseaseSystem = args["target_disease_system"]?.jsonPrimitive?.contentOrNull ?: "http://snomed.info/sct"
        
        if (patientId.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: patient_id is required"))
            )
        }
        if (vaccineCode.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: vaccine_code is required"))
            )
        }
        
        val immunization = Immunization().apply {
            this.status = Immunization.ImmunizationStatus.fromCode(status)
            this.vaccineCode = CodeableConcept().apply {
                addCoding(Coding().apply {
                    this.system = vaccineSystem
                    this.code = vaccineCode
                    this.display = vaccineDisplay.ifBlank { vaccineCode }
                })
                text = vaccineDisplay.ifBlank { vaccineCode }
            }
            this.patient = Reference("Patient/$patientId")
            this.occurrenceDateTimeType = DateTimeType(
                occurrenceDate.ifBlank { 
                    LocalDateTime.now().format(DateTimeFormatter.ISO_DATE_TIME) 
                }
            )
            this.primarySource = true
            
            if (lotNumber.isNotBlank()) {
                this.lotNumber = lotNumber
            }
            
            // Create protocol applied with all fields
            if (doseNumber.isNotBlank() || series.isNotBlank() || seriesDoses.isNotBlank() || targetDisease.isNotBlank()) {
                addProtocolApplied(Immunization.ImmunizationProtocolAppliedComponent().apply {
                    // Dose number
                    if (doseNumber.isNotBlank()) {
                        try {
                            this.doseNumberPositiveIntType = PositiveIntType(doseNumber.toInt())
                        } catch (e: NumberFormatException) {
                            this.doseNumberStringType = StringType(doseNumber)
                        }
                    }
                    
                    // Series name
                    if (series.isNotBlank()) {
                        this.series = series
                    }
                    
                    // Series doses (total number of doses in series)
                    if (seriesDoses.isNotBlank()) {
                        try {
                            this.seriesDosesPositiveIntType = PositiveIntType(seriesDoses.toInt())
                        } catch (e: NumberFormatException) {
                            this.seriesDosesStringType = StringType(seriesDoses)
                        }
                    }
                    
                    // Target disease
                    if (targetDisease.isNotBlank()) {
                        addTargetDisease(CodeableConcept().apply {
                            addCoding(Coding().apply {
                                this.system = targetDiseaseSystem
                                this.code = targetDisease
                            })
                        })
                    }
                })
            }
        }
        
        val id = resourceStore.create(immunization)
        
        val result = StringBuilder("✅ Immunization created successfully!\n\n")
        result.append(formatResourceSummary(immunization))
        result.append("\n\nID: $id")
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    // ==================== Observation Tools ====================
    
    server.addTool(
        name = "create_observation",
        description = "Create a new Observation record for pre-vaccination screening or clinical findings"
    ) { request ->
        val args = request.arguments
        val patientId = args["patient_id"]?.jsonPrimitive?.contentOrNull
        val code = args["code"]?.jsonPrimitive?.contentOrNull
        val codeSystem = args["code_system"]?.jsonPrimitive?.contentOrNull ?: "http://loinc.org"
        val codeDisplay = args["code_display"]?.jsonPrimitive?.contentOrNull ?: ""
        val valueString = args["value_string"]?.jsonPrimitive?.contentOrNull ?: ""
        val valueQuantity = args["value_quantity"]?.jsonPrimitive?.contentOrNull ?: ""
        val valueUnit = args["value_unit"]?.jsonPrimitive?.contentOrNull ?: ""
        val valueBoolean = args["value_boolean"]?.jsonPrimitive?.contentOrNull ?: ""
        val status = args["status"]?.jsonPrimitive?.contentOrNull ?: "final"
        val effectiveDate = args["effective_date"]?.jsonPrimitive?.contentOrNull ?: ""
        
        if (patientId.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: patient_id is required"))
            )
        }
        if (code.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: code is required"))
            )
        }
        
        val observation = Observation().apply {
            this.status = Observation.ObservationStatus.fromCode(status)
            this.code = CodeableConcept().apply {
                addCoding(Coding().apply {
                    this.system = codeSystem
                    this.code = code
                    this.display = codeDisplay.ifBlank { code }
                })
                text = codeDisplay.ifBlank { code }
            }
            this.subject = Reference("Patient/$patientId")
            this.effectiveDateTimeType = DateTimeType(
                effectiveDate.ifBlank { 
                    LocalDateTime.now().format(DateTimeFormatter.ISO_DATE_TIME) 
                }
            )
            
            when {
                valueString.isNotBlank() -> this.value = StringType(valueString)
                valueQuantity.isNotBlank() -> this.value = Quantity().apply {
                    this.value = valueQuantity.toBigDecimalOrNull()
                    this.unit = valueUnit
                    this.system = "http://unitsofmeasure.org"
                }
                valueBoolean.isNotBlank() -> this.value = BooleanType(valueBoolean.toBoolean())
            }
        }
        
        val id = resourceStore.create(observation)
        
        CallToolResult(
            content = listOf(TextContent("✅ Observation created successfully!\n\n${formatResourceSummary(observation)}\n\nID: $id"))
        )
    }
    
    // ==================== Terminology Tools ====================
    
    server.addTool(
        name = "search_valueset",
        description = "Search for ValueSets including those from WHO SMART Immunizations IG"
    ) { request ->
        val args = request.arguments
        val name = args["name"]?.jsonPrimitive?.contentOrNull ?: ""
        val url = args["url"]?.jsonPrimitive?.contentOrNull ?: ""
        val limit = args["limit"]?.jsonPrimitive?.intOrNull ?: 50
        
        val valueSets = resourceStore.search<ValueSet> { vs ->
            (name.isBlank() || vs.name?.contains(name, ignoreCase = true) == true ||
                vs.title?.contains(name, ignoreCase = true) == true ||
                vs.idElement?.idPart?.contains(name, ignoreCase = true) == true) &&
            (url.isBlank() || vs.url == url)
        }.take(limit)
        
        if (valueSets.isEmpty()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("📚 No ValueSets found matching the criteria."))
            )
        }
        
        val total = resourceStore.search<ValueSet>().size
        val result = StringBuilder("📚 Found ${valueSets.size} ValueSet(s) (showing up to $limit of $total total):\n\n")
        for (vs in valueSets) {
            result.append("• **${vs.title ?: vs.name ?: "Untitled"}**\n")
            result.append("  ID: ${vs.idElement?.idPart}\n")
            result.append("  URL: ${vs.url ?: "N/A"}\n")
            result.append("  Status: ${vs.status?.toCode() ?: "unknown"}\n\n")
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    server.addTool(
        name = "expand_valueset",
        description = "Expand a ValueSet to get its list of codes"
    ) { request ->
        val args = request.arguments
        val valuesetId = args["valueset_id"]?.jsonPrimitive?.contentOrNull ?: ""
        val valuesetUrl = args["valueset_url"]?.jsonPrimitive?.contentOrNull ?: ""
        
        if (valuesetId.isBlank() && valuesetUrl.isBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: Either valueset_id or valueset_url is required"))
            )
        }
        
        val vs = if (valuesetId.isNotBlank()) {
            resourceStore.get<ValueSet>(valuesetId)
        } else {
            resourceStore.search<ValueSet> { it.url == valuesetUrl }.firstOrNull()
        } ?: return@addTool CallToolResult(
            content = listOf(TextContent("❌ ValueSet not found"))
        )
        
        val result = StringBuilder("📚 **ValueSet: ${vs.title ?: vs.name ?: "Unnamed"}**\n\n")
        result.append("**URL:** ${vs.url ?: "N/A"}\n")
        result.append("**Description:** ${vs.description ?: "No description"}\n\n")
        
        // Return compose codes if no expansion available
        val includes = vs.compose?.include ?: emptyList()
        if (includes.isNotEmpty()) {
            result.append("**Included Codes:**\n")
            for (include in includes) {
                result.append("\nSystem: ${include.system ?: "Unknown"}\n")
                for (concept in include.concept.take(30)) {
                    result.append("• `${concept.code}` - ${concept.display ?: "N/A"}\n")
                }
                if (include.concept.size > 30) {
                    result.append("... and ${include.concept.size - 30} more\n")
                }
            }
        }
        
        // Also check expansion if available
        vs.expansion?.contains?.let { contains ->
            if (contains.isNotEmpty()) {
                result.append("\n**Expanded Codes (${contains.size}):**\n")
                for (entry in contains.take(30)) {
                    result.append("• `${entry.code}` - ${entry.display ?: "N/A"}\n")
                    result.append("  System: ${entry.system}\n")
                }
                if (contains.size > 30) {
                    result.append("\n... and ${contains.size - 30} more codes\n")
                }
            }
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    server.addTool(
        name = "search_codesystem",
        description = "Search for CodeSystems including those from WHO SMART Immunizations IG"
    ) { request ->
        val args = request.arguments
        val name = args["name"]?.jsonPrimitive?.contentOrNull ?: ""
        val url = args["url"]?.jsonPrimitive?.contentOrNull ?: ""
        val limit = args["limit"]?.jsonPrimitive?.intOrNull ?: 50
        
        val codeSystems = resourceStore.search<CodeSystem> { cs ->
            (name.isBlank() || cs.name?.contains(name, ignoreCase = true) == true ||
                cs.title?.contains(name, ignoreCase = true) == true ||
                cs.idElement?.idPart?.contains(name, ignoreCase = true) == true) &&
            (url.isBlank() || cs.url == url)
        }.take(limit)
        
        if (codeSystems.isEmpty()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("📖 No CodeSystems found matching the criteria."))
            )
        }
        
        val total = resourceStore.search<CodeSystem>().size
        val result = StringBuilder("📖 Found ${codeSystems.size} CodeSystem(s) (showing up to $limit of $total total):\n\n")
        for (cs in codeSystems) {
            result.append("• **${cs.title ?: cs.name ?: "Untitled"}**\n")
            result.append("  ID: ${cs.idElement?.idPart}\n")
            result.append("  URL: ${cs.url ?: "N/A"}\n")
            result.append("  Status: ${cs.status?.toCode() ?: "unknown"}\n")
            result.append("  Content: ${cs.content?.toCode() ?: "unknown"}\n")
            result.append("  Count: ${cs.count ?: cs.concept?.size ?: "N/A"} concepts\n\n")
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    server.addTool(
        name = "lookup_code",
        description = "Look up details about a specific code in a CodeSystem"
    ) { request ->
        val args = request.arguments
        val system = args["system"]?.jsonPrimitive?.contentOrNull
        val code = args["code"]?.jsonPrimitive?.contentOrNull
        
        if (system.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: system (CodeSystem URL) is required"))
            )
        }
        if (code.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: code is required"))
            )
        }
        
        val cs = resourceStore.search<CodeSystem> { it.url == system }.firstOrNull()
            ?: return@addTool CallToolResult(
                content = listOf(TextContent("❌ CodeSystem not found: $system"))
            )
        
        fun findConcept(concepts: List<CodeSystem.ConceptDefinitionComponent>?, targetCode: String): CodeSystem.ConceptDefinitionComponent? {
            for (concept in concepts ?: emptyList()) {
                if (concept.code == targetCode) return concept
                findConcept(concept.concept, targetCode)?.let { return it }
            }
            return null
        }
        
        val concept = findConcept(cs.concept, code)
            ?: return@addTool CallToolResult(
                content = listOf(TextContent("❌ Code not found: $code in system $system"))
            )
        
        val result = StringBuilder("🔍 **Code Lookup Result**\n\n")
        result.append("**System:** $system\n")
        result.append("**Code:** $code\n")
        result.append("**Display:** ${concept.display ?: "N/A"}\n")
        result.append("**Definition:** ${concept.definition ?: "N/A"}\n")
        
        if (concept.designation.isNotEmpty()) {
            result.append("**Designations:**\n")
            for (des in concept.designation) {
                result.append("  • ${des.language ?: "?"}: ${des.value}\n")
            }
        }
        
        if (concept.property.isNotEmpty()) {
            result.append("**Properties:**\n")
            for (prop in concept.property) {
                val value = prop.valueCodeType?.value 
                    ?: prop.valueStringType?.value 
                    ?: prop.valueBooleanType?.value?.toString()
                    ?: "N/A"
                result.append("  • ${prop.code}: $value\n")
            }
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    // ==================== ActivityDefinition Tools ====================
    
    server.addTool(
        name = "list_activity_definitions",
        description = "List available ActivityDefinitions from WHO SMART Immunizations IG"
    ) { request ->
        val args = request.arguments
        val title = args["title"]?.jsonPrimitive?.contentOrNull ?: ""
        val limit = args["limit"]?.jsonPrimitive?.intOrNull ?: 50
        
        val actDefs = resourceStore.search<ActivityDefinition> { ad ->
            title.isBlank() || ad.title?.contains(title, ignoreCase = true) == true ||
                ad.name?.contains(title, ignoreCase = true) == true ||
                ad.idElement?.idPart?.contains(title, ignoreCase = true) == true
        }.take(limit)
        
        if (actDefs.isEmpty()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("⚙️ No ActivityDefinitions found matching the criteria."))
            )
        }
        
        val total = resourceStore.search<ActivityDefinition>().size
        val result = StringBuilder("⚙️ Found ${actDefs.size} ActivityDefinition(s) (showing up to $limit of $total total):\n\n")
        for (ad in actDefs) {
            result.append("• **${ad.title ?: ad.name ?: "Untitled"}**\n")
            result.append("  ID: ${ad.idElement?.idPart}\n")
            result.append("  URL: ${ad.url ?: "N/A"}\n")
            result.append("  Status: ${ad.status?.toCode() ?: "unknown"}\n")
            result.append("  Kind: ${ad.kind?.toCode() ?: "N/A"}\n\n")
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    // ==================== Generic FHIR Tools ====================
    
    server.addTool(
        name = "get_fhir_resource",
        description = "Get any FHIR resource by type and ID"
    ) { request ->
        val resourceType = request.arguments["resource_type"]?.jsonPrimitive?.contentOrNull
        val resourceId = request.arguments["resource_id"]?.jsonPrimitive?.contentOrNull
        
        if (resourceType.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: resource_type is required"))
            )
        }
        if (resourceId.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: resource_id is required"))
            )
        }
        
        val resource = resourceStore.get(resourceType, resourceId)
            ?: return@addTool CallToolResult(
                content = listOf(TextContent("❌ Resource not found: $resourceType/$resourceId"))
            )
        
        val result = "📄 **$resourceType Details**\n\n```json\n${resource.toJsonString()}\n```"
        
        CallToolResult(content = listOf(TextContent(result)))
    }
    
    server.addTool(
        name = "search_fhir_resources",
        description = "Search for FHIR resources by type"
    ) { request ->
        val resourceType = request.arguments["resource_type"]?.jsonPrimitive?.contentOrNull
        val limit = request.arguments["limit"]?.jsonPrimitive?.intOrNull ?: 50
        
        if (resourceType.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: resource_type is required"))
            )
        }
        
        val resources = resourceStore.searchByType(resourceType).take(limit)
        
        if (resources.isEmpty()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("📄 No $resourceType resources found."))
            )
        }
        
        val total = resourceStore.searchByType(resourceType).size
        val result = StringBuilder("📄 Found ${resources.size} $resourceType resource(s) (showing up to $limit of $total total):\n\n")
        for (resource in resources) {
            result.append(formatResourceSummary(resource))
            result.append("\n\n")
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
    
    server.addTool(
        name = "load_fhir_resource",
        description = "Load a FHIR resource from JSON into the local store"
    ) { request ->
        val json = request.arguments["json"]?.jsonPrimitive?.contentOrNull
        
        if (json.isNullOrBlank()) {
            return@addTool CallToolResult(
                content = listOf(TextContent("❌ Error: json is required"))
            )
        }
        
        try {
            val resource = jsonParser.parseResource(json) as Resource
            val id = resourceStore.create(resource)
            
            CallToolResult(
                content = listOf(TextContent("✅ ${resource.fhirType()} loaded successfully!\n\nID: $id"))
            )
        } catch (e: Exception) {
            CallToolResult(
                content = listOf(TextContent("❌ Error parsing FHIR resource: ${e.message}"))
            )
        }
    }
    
    server.addTool(
        name = "get_store_summary",
        description = "Get a summary of all resources in the local FHIR store including WHO SMART IG resources"
    ) { _ ->
        val result = StringBuilder("🏥 **FHIR Store Summary**\n\n")
        result.append("**Total Resources:** ${resourceStore.getTotalResourceCount()}\n\n")
        
        val counts = resourceStore.getResourceTypeCounts()
        
        result.append("**Resources by Type:**\n")
        for ((type, count) in counts.entries.sortedByDescending { it.value }) {
            result.append("• **$type:** $count\n")
        }
        
        // Show some key PlanDefinition categories
        val planDefs = resourceStore.search<PlanDefinition>()
        if (planDefs.isNotEmpty()) {
            result.append("\n**PlanDefinition Categories:**\n")
            val dtCount = planDefs.count { it.idElement?.idPart?.contains("DT") == true }
            val scheduleCount = planDefs.count { it.idElement?.idPart?.contains("18S") == true }
            result.append("• Decision Tables (DT): $dtCount\n")
            result.append("• Schedules (18S): $scheduleCount\n")
        }
        
        CallToolResult(content = listOf(TextContent(result.toString())))
    }
}
