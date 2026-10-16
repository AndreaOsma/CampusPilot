//
//  Campus_PilotApp.swift
//  Campus Pilot
//
//  Created by Andrea Osma Rafael on 19/3/26.
//

/// App entry point that configures SwiftData and global appearance.

import SwiftUI
import SwiftData

@main
/// CampusPilotApp view and UI state container.
struct CampusPilotApp: App {
    private let modelContainer: ModelContainer
    @AppStorage("app_theme") private var appTheme = "system"
    @AppStorage("app_accent") private var appAccent = "blue"

    init() {
        let schema = Schema([
            Subject.self,
            SubjectBase.self,
            EvaluationGroup.self,
            Activity.self,
            LearningObjective.self,
            SimulationScenario.self,
            Career.self,
            Semester.self,
            ExtraCost.self
        ])
        
        do {
            self.modelContainer = try ModelContainer(for: schema)
        } catch {
            // Recovery path: if the on-disk store fails to load/migrate, keep the app usable.
            print("SwiftData load failed. Falling back to in-memory store: \(error)")
            let fallback = ModelConfiguration(isStoredInMemoryOnly: true)
            do {
                self.modelContainer = try ModelContainer(for: schema, configurations: [fallback])
            } catch {
                fatalError("Unable to create SwiftData container even in-memory: \(error)")
            }
        }
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .preferredColorScheme(preferredScheme)
                .tint(accentColor)
        }
        .modelContainer(modelContainer)
    }

    private var preferredScheme: ColorScheme? {
        switch appTheme {
        case "light": return .light
        case "dark": return .dark
        default: return nil
        }
    }

    private var accentColor: Color {
        switch appAccent {
        case "green": return .green
        case "orange": return .orange
        case "pink": return .pink
        case "purple": return .purple
        default: return .blue
        }
    }
}
