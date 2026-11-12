plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "io.github.lshrexgen.smskakao"
    compileSdk = 35

    defaultConfig {
        applicationId = "io.github.lshrexgen.smskakao"
        minSdk = 31
        targetSdk = 35
        versionCode = 4
        versionName = "0.2.0"
    }

    buildTypes {
        release {
            // Personal side-load build: shrink with R8 and sign with the debug key so it
            // installs without a release keystore.
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    buildFeatures {
        viewBinding = true
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("com.google.android.material:material:1.12.0")
}
