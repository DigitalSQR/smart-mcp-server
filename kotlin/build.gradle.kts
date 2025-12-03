plugins {
    kotlin("jvm") version "1.9.22"
    kotlin("plugin.serialization") version "1.9.22"
    id("com.github.johnrengelman.shadow") version "8.1.1"
    application
}

group = "com.fhir.immunization.mcp"
version = "1.0.0"

repositories {
    mavenCentral()
    google()
}

val hapiFhirVersion = "6.10.5"
val mcpSdkVersion = "0.4.0"
val ktorVersion = "2.3.7"

dependencies {
    // MCP Kotlin SDK
    implementation("io.modelcontextprotocol:kotlin-sdk:$mcpSdkVersion")
    
    // Ktor for HTTP (required by MCP SDK)
    implementation("io.ktor:ktor-client-cio:$ktorVersion")
    
    // HAPI FHIR - same libraries used by Android FHIR SDK
    implementation("ca.uhn.hapi.fhir:hapi-fhir-base:$hapiFhirVersion")
    implementation("ca.uhn.hapi.fhir:hapi-fhir-structures-r4:$hapiFhirVersion")
    implementation("ca.uhn.hapi.fhir:hapi-fhir-validation-resources-r4:$hapiFhirVersion")
    
    // Kotlin coroutines
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.7.3")
    
    // Kotlinx serialization
    implementation("org.jetbrains.kotlinx:kotlinx-serialization-json:1.6.2")
    
    // Apache Commons Compress for tar.gz extraction
    implementation("org.apache.commons:commons-compress:1.26.0")
    
    // Logging
    implementation("org.slf4j:slf4j-simple:2.0.9")
    
    // Testing
    testImplementation(kotlin("test"))
    testImplementation("org.jetbrains.kotlinx:kotlinx-coroutines-test:1.7.3")
}

kotlin {
    jvmToolchain(17)
}

application {
    mainClass.set("com.fhir.immunization.mcp.FhirImmunizationServerKt")
}

tasks.test {
    useJUnitPlatform()
}

tasks.shadowJar {
    archiveBaseName.set("fhir-immunization-mcp-server")
    archiveClassifier.set("")
    archiveVersion.set("")
    manifest {
        attributes["Main-Class"] = "com.fhir.immunization.mcp.FhirImmunizationServerKt"
    }
    mergeServiceFiles()
}

tasks.named("build") {
    dependsOn(tasks.shadowJar)
}