// AGP 9 has built-in Kotlin: no org.jetbrains.kotlin.android plugin; jvmTarget follows compileOptions.
plugins { id("com.android.application") version "9.4.1" }

android {
    namespace = "ledgercash.payee"
    compileSdk = 35
    defaultConfig {
        applicationId = "ledgercash.payee"
        minSdk = 26
        targetSdk = 35
        versionCode = 1
        versionName = "0.1"
    }
    // Fixed debug key (committed, public, demo only): every CI APK installs over the last one, so the phone payee key
    // in filesDir survives updates. A per-run CI key would force an uninstall, which deletes that key and any USDC on it.
    signingConfigs {
        getByName("debug") {
            storeFile = file("debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }
    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    // The pure protocol/crypto/framing code and its tests live in ../core (also buildable alone: ./gradlew -p core test).
    sourceSets {
        getByName("main").kotlin.directories.add("../core/src/main/kotlin")
        getByName("test").kotlin.directories.add("../core/src/test/kotlin")
    }
}

dependencies {
    implementation("org.bouncycastle:bcprov-jdk18on:1.86")
    testImplementation("junit:junit:4.13.2")
}
