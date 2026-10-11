// Standalone JVM build of the pure logic so it can be tested without the Android SDK: ../gradlew -p core test
// The app compiles these same sources (app/build.gradle.kts adds them as source dirs).
plugins { kotlin("jvm") version "2.4.21" }
repositories { mavenCentral() }
dependencies {
    implementation("org.bouncycastle:bcprov-jdk18on:1.86")
    testImplementation("junit:junit:4.13.2")
}
tasks.test { testLogging { events("passed", "failed"); exceptionFormat = org.gradle.api.tasks.testing.logging.TestExceptionFormat.FULL } }
