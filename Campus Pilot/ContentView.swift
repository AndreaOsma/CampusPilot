/// Dashboard and onboarding flow for the main app modules.

import SwiftUI
import SwiftData
import Foundation

/// ContentView view and UI state container.
struct ContentView: View {
    // Persistent feature flags (backed by UserDefaults)
    @AppStorage("enable_finance") private var enableFinance = false
    @AppStorage("enable_scholarship") private var enableScholarship = false
    @Environment(\.modelContext) private var context
    @Query(sort: \Career.name) private var careers: [Career]
    @Query(sort: \Semester.startDate) private var semesters: [Semester]
    @Query(sort: \SubjectBase.name) private var bases: [SubjectBase]
    @Query private var subjects: [Subject]
    @State private var didBootstrap = false
    @State private var activeCareerID: PersistentIdentifier?
    @AppStorage("did_complete_onboarding") private var didCompleteOnboarding = false
    @State private var isOnboardingPresented = false
    @State private var onboardingCareerName = String(localized: "ui.career.title")
    @State private var onboardingECTS = 240
    @State private var onboardingSemesterStart = Date()

    // Keep only the metrics used by the current dashboard to avoid extra work on each render.
    // NOTE: Avoid shadowing `@Query` properties (Swift will treat it as a redeclaration).

    private var activeCareer: Career? {
        let id = activeCareerID ?? careers.first?.persistentModelID
        guard let id else { return nil }
        return careers.first(where: { $0.persistentModelID == id }) ?? careers.first
    }

    private var activeCareerSubjects: [Subject] {
        guard let careerID = activeCareer?.persistentModelID else { return [] }
        return subjects.filter { $0.career?.persistentModelID == careerID }
    }

    private var activeCareerAverageGradeExcludingConvalidated: Double {
        guard let careerID = activeCareer?.persistentModelID else { return 0.0 }
        let relevant = subjects.filter { subject in
            subject.career?.persistentModelID == careerID &&
            subject.enrollmentStatus != .convalidated &&
            subject.gradedActivitiesCount > 0
        }
        let totalCredits = relevant.reduce(0.0) { $0 + Double($1.credits) }
        guard totalCredits > 0 else { return 0.0 }
        let weightedTotal = relevant.reduce(0.0) { partial, item in
            partial + (item.weightedFinalGrade * Double(item.credits))
        }
        return weightedTotal / totalCredits
    }

    private var activeProgress: Double {
        let objective = Double(activeCareer?.ectsGoal ?? 0)
        guard objective > 0 else { return 0.0 }
        return min(1.0, Double(activeCompletedECTS) / objective)
    }

    private var activeSubjectsAtRisk: Int {
        activeCareerSubjects.filter { $0.evaluationProgress > 0 && $0.weightedFinalGrade < 5.0 }.count
    }

    private var activeCompletedECTS: Int {
        guard let careerID = activeCareer?.persistentModelID else { return 0 }
        return subjects
            .filter { $0.career?.persistentModelID == careerID }
            .reduce(0) { partial, subject in
                if subject.enrollmentStatus == .convalidated || subject.academicStatus == .passed {
                    return partial + subject.credits
                }
                return partial
            }
    }
    
    var body: some View {
        NavigationStack {
            List {
                Section(String(localized: "ui.common.general")) {
                    Picker(String(localized: "ui.career.name"), selection: Binding(
                    get: { activeCareer?.persistentModelID },
                        set: { activeCareerID = $0 }
                    )) {
                        ForEach(careers) { career in
                            Text(career.name).tag(Optional(career.persistentModelID))
                        }
                    }
                    .pickerStyle(.menu)
                }

                Section(String(localized: "ui.common.summary")) {
                    summaryRow(String(localized: "ui.subject.list"), value: "\(activeCareerSubjects.count)", icon: "text.book.closed")
                    summaryRow(String(localized: "ui.career.ects.completed"), value: "\(activeCompletedECTS)", icon: "graduationcap.fill")
                    summaryRow(String(localized: "ui.career.metrics.average"), value: String(format: "%.2f", activeCareerAverageGradeExcludingConvalidated), icon: "chart.line.uptrend.xyaxis")
                    summaryRow(String(localized: "ui.career.metrics.atRisk"), value: "\(activeSubjectsAtRisk)", icon: "exclamationmark.triangle")

                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Label(String(localized: "ui.subject.evaluation.progress"), systemImage: "gauge.with.dots.needle.50percent")
                            Spacer()
                            Text("\(Int(activeProgress * 100))%")
                                .foregroundColor(.secondary)
                        }
                        ProgressView(value: activeProgress)
                    }
                }

                Section {
                    NavigationLink(destination: CareerPlannerView()) {
                        Label(String(localized: "ui.career.planner.title"), systemImage: "graduationcap")
                    }
                }
                
                // Dynamic modules: only render when enabled
                if enableFinance || enableScholarship {
                    Section(header: Text(String(localized: "ui.common.other"))) {
                        if enableFinance {
                            NavigationLink(destination: FinancePricesView()) {
                                Label(String(localized: "ui.finance.title"), systemImage: "eurosign.circle")
                            }
                        }
                        
                        if enableScholarship {
                            NavigationLink(destination: ScholarshipStatusView()) {
                                Label(String(localized: "ui.mec.title"), systemImage: "banknote")
                            }
                        }
                    }
                }
            }
            .navigationTitle(String(localized: "ui.career.planner.title"))
            .toolbar {
                // Settings entry point
                ToolbarItem(placement: .navigationBarTrailing) {
                    NavigationLink(destination: SettingsView()) {
                        Image(systemName: "gearshape")
                            .foregroundColor(.primary)
                    }
                }
            }
            .onAppear {
                if !didCompleteOnboarding && careers.isEmpty {
                    isOnboardingPresented = true
                } else {
                    bootstrapDefaultsIfNeeded()
                }
            }
            .sheet(isPresented: $isOnboardingPresented) {
                onboardingSheet
            }
        }
    }

    private var onboardingSheet: some View {
        NavigationStack {
            Form {
                Section(String(localized: "ui.career.name")) {
                    TextField(String(localized: "ui.career.name"), text: $onboardingCareerName)
                        .textInputAutocapitalization(.words)
                    Stepper("\(String(localized: "ui.career.ects.goal")): \(onboardingECTS)", value: $onboardingECTS, in: 30...600, step: 6)
                }
                Section(String(localized: "ui.semester.start")) {
                    DatePicker(String(localized: "ui.semester.start"), selection: $onboardingSemesterStart, displayedComponents: .date)
                }
            }
            .navigationTitle(String(localized: "ui.career.setup"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button(String(localized: "ui.common.start")) {
                        saveOnboardingAndBootstrap()
                    }
                    .disabled(onboardingCareerName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }

/// Handles summary row.
    private func summaryRow(_ title: String, value: String, icon: String) -> some View {
        HStack {
            Label(title, systemImage: icon)
            Spacer()
            Text(value)
                .fontWeight(.semibold)
                .foregroundColor(.secondary)
        }
    }

/// Handles bootstrap defaults if needed.
    private func bootstrapDefaultsIfNeeded() {
        guard !didBootstrap else { return }
        didBootstrap = true

        // Default career
        let careerDefault: Career
        if let firstCareer = careers.first {
            careerDefault = firstCareer
        } else {
            let newCareer = Career(name: onboardingCareerName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? String(localized: "ui.career.title") : onboardingCareerName, ectsGoal: onboardingECTS)
            context.insert(newCareer)
            careerDefault = newCareer
        }

        // Default semester + past and future (MVP)
        let calendar = Calendar.current
        let semesterDefault: Semester
        if let current = semesters.first(where: { $0.contains(Date()) }) {
            semesterDefault = current
        } else if let first = semesters.first {
            semesterDefault = first
        } else {
            let baseDate = onboardingSemesterStart
            var createdCurrent: Semester?

            // Includes 3 past and 6 future semesters (MVP).
            // Semester label format: YYYYS1 / YYYY S2
            for i in -3..<6 {
                let startDate = calendar.date(byAdding: .month, value: i * 4, to: baseDate) ?? baseDate
                let year = calendar.component(.year, from: startDate)
                let month = calendar.component(.month, from: startDate)
                let suffix = month <= 5 ? "S1" : "S2"
                let label = "\(year)\(suffix)"

                let endDate = calendar.date(byAdding: .month, value: 4, to: startDate) ?? startDate

                let c = Semester(label: label, startDate: startDate, endDate: endDate)
                context.insert(c)

                if i == 0 { createdCurrent = c }
            }

            semesterDefault = createdCurrent!
        }

        // Migration/normalization: ensure semester labels follow YYYY S1/S2.
        // If the user already created semesters with old labels, we normalize based on `startDate`.
        let semRegex = try? NSRegularExpression(pattern: #"^\d{4}S[12]$"#, options: [])
        for semester in semesters {
            let isValidLabel = semRegex?.firstMatch(in: semester.label, options: [], range: NSRange(location: 0, length: semester.label.utf16.count)) != nil
            guard isValidLabel == false else { continue }

            let year = calendar.component(.year, from: semester.startDate)
            let month = calendar.component(.month, from: semester.startDate)
            let suffix = month <= 5 ? "S1" : "S2"
            semester.label = "\(year)\(suffix)"

            if semester.endDate == nil {
                semester.endDate = calendar.date(byAdding: .month, value: 4, to: semester.startDate) ?? semester.startDate
            }
        }

        // Prepare existing bases (avoid duplicates by name+credits).
/// Handles base key.
        func baseKey(name: String, credits: Int) -> String {
            "\(name.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())|\(credits)"
        }

        var baseByKey: [String: SubjectBase] = [:]
        for base in bases {
            baseByKey[baseKey(name: base.name, credits: base.credits)] = base
        }

        // Assign defaults to existing subjects without a plan, and create/link `SubjectBase` when missing.
        for subject in subjects {
            if subject.base == nil {
                let key = baseKey(name: subject.name, credits: subject.credits)
                if let existingBase = baseByKey[key] {
                    subject.base = existingBase
                } else {
                    let newBase = SubjectBase(name: subject.name, credits: subject.credits, defaultPricePerCredit: subject.pricePerCredit)
                    context.insert(newBase)
                    baseByKey[key] = newBase
                    subject.base = newBase
                }
            }

            if subject.career == nil || subject.semester == nil {
                subject.career = careerDefault
                subject.semester = semesterDefault
                subject.enrollmentStatus = .enrolled
                subject.enrollmentDate = Date()
            }
        }

        try? context.save()
    }

/// Saves onboarding and bootstrap.
    private func saveOnboardingAndBootstrap() {
        didCompleteOnboarding = true
        didBootstrap = false
        bootstrapDefaultsIfNeeded()
        isOnboardingPresented = false
    }
}

// Settings view
/// SettingsView view and UI state container.
struct SettingsView: View {
    @AppStorage("enable_finance") private var enableFinance = false
    @AppStorage("enable_scholarship") private var enableScholarship = false
    @AppStorage("app_theme") private var appTheme = "system"
    @AppStorage("app_accent") private var appAccent = "blue"
    @AppStorage("sync_backend_url") private var syncBackendURL = "http://127.0.0.1:8787"
    @AppStorage("sync_workspace_id") private var syncWorkspaceID = "default"
    @AppStorage("sync_auto_enabled") private var syncAutoEnabled = true
    @AppStorage("sync_queue_json") private var syncQueueJSON = "[]"
    @Environment(\.modelContext) private var context
    @Query(sort: \Subject.name) private var subjects: [Subject]
    @Query(sort: \Career.name) private var careers: [Career]
    @Query(sort: \Semester.startDate) private var semesters: [Semester]
    @State private var syncMessage = ""
    @State private var isSyncing = false
    
    var body: some View {
        Form {
            Section(
                header: Text(String(localized: "ui.common.appearance")),
                footer: Text(String(localized: "ui.common.description"))
            ) {
                Toggle(String(localized: "ui.finance.title"), isOn: $enableFinance)
                Toggle(String(localized: "ui.mec.eligibility"), isOn: $enableScholarship)
            }

            Section(
                header: Text(String(localized: "ui.common.appearance")),
                footer: Text(String(localized: "ui.common.description"))
            ) {
                Picker(String(localized: "ui.common.theme"), selection: $appTheme) {
                    Text(String(localized: "ui.common.system")).tag("system")
                    Text(String(localized: "ui.common.light")).tag("light")
                    Text(String(localized: "ui.common.dark")).tag("dark")
                }
                .pickerStyle(.menu)

                Picker(String(localized: "ui.common.accent"), selection: $appAccent) {
                    Text(String(localized: "ui.common.blue")).tag("blue")
                    Text(String(localized: "ui.common.green")).tag("green")
                    Text(String(localized: "ui.common.orange")).tag("orange")
                    Text(String(localized: "ui.common.pink")).tag("pink")
                    Text(String(localized: "ui.common.purple")).tag("purple")
                }
                .pickerStyle(.menu)
            }

            Section(header: Text("Sync backend"), footer: Text("SwiftData sigue siendo local/offline. Sync es opcional.")) {
                TextField("Backend URL", text: $syncBackendURL)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                TextField("Workspace ID", text: $syncWorkspaceID)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Toggle("Auto sync al abrir settings", isOn: $syncAutoEnabled)
                HStack {
                    Button("Push") {
                        Task { await pushSharedSnapshot() }
                    }
                    .buttonStyle(.borderedProminent)
                    Button("Pull") {
                        Task { await pullSharedSnapshot() }
                    }
                    .buttonStyle(.bordered)
                }
                Button("Reintentar cola pendiente") {
                    Task { await flushPendingQueue() }
                }
                .buttonStyle(.bordered)
                .disabled(isSyncing || pendingQueueItems.isEmpty)
                Text("Pendientes en cola: \(pendingQueueItems.count)")
                    .font(.caption2)
                    .foregroundColor(.secondary)
                if !syncMessage.isEmpty {
                    Text(syncMessage)
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .navigationTitle(String(localized: "ui.common.settings"))
        .navigationBarTitleDisplayMode(.inline)
        .task {
            if syncAutoEnabled {
                await flushPendingQueue()
            }
        }
    }

    private func pushPayload() -> SharedSnapshot {
        let snapshots = subjects.map { subject in
            SharedSubjectSnapshot(
                name: subject.name,
                ects: subject.credits,
                semester: subject.semester?.label ?? "S1",
                grade: subject.weightedFinalGrade
            )
        }
        return SharedSnapshot(updatedAt: ISO8601DateFormatter().string(from: Date()), subjects: snapshots)
    }

    private func endpointURL() -> URL? {
        let trimmed = syncBackendURL.trimmingCharacters(in: .whitespacesAndNewlines)
        let workspace = syncWorkspaceID.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty, !workspace.isEmpty else { return nil }
        return URL(string: "\(trimmed)/api/sync/\(workspace.addingPercentEncoding(withAllowedCharacters: .urlPathAllowed) ?? workspace)")
    }

    private func pushSharedSnapshot() async {
        guard let url = endpointURL() else {
            syncMessage = "Config de backend invalida."
            return
        }
        isSyncing = true
        defer { isSyncing = false }
        do {
            let payload = pushPayload()
            let body = try JSONEncoder().encode(payload)
            var request = URLRequest(url: url)
            request.httpMethod = "PUT"
            request.httpBody = body
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            let (_, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                enqueuePending(payload)
                syncMessage = "Push fallido."
                return
            }
            syncMessage = "Push correcto."
        } catch {
            enqueuePending(pushPayload())
            syncMessage = "Push error: \(error.localizedDescription)"
        }
    }

    private func pullSharedSnapshot() async {
        guard let url = endpointURL() else {
            syncMessage = "Config de backend invalida."
            return
        }
        do {
            let (data, response) = try await URLSession.shared.data(from: url)
            guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                syncMessage = "Pull fallido."
                return
            }
            let remote = try JSONDecoder().decode(SharedSnapshot.self, from: data)
            let career = careers.first ?? {
                let created = Career(name: "General", ectsGoal: 240)
                context.insert(created)
                return created
            }()
            for item in remote.subjects {
                if subjects.contains(where: { $0.name.caseInsensitiveCompare(item.name) == .orderedSame }) {
                    continue
                }
                let semester = resolveSemester(label: item.semester)
                let subject = Subject(name: item.name, credits: item.ects)
                subject.career = career
                subject.semester = semester
                if let grade = item.grade {
                    let block = EvaluationGroup(name: "Imported", globalWeight: 1.0)
                    let activity = Activity(name: "Imported grade", weightWithinGroup: 1.0)
                    activity.grade = grade
                    block.activities = [activity]
                    subject.groups = [block]
                    subject.enrollmentStatus = .completed
                }
                context.insert(subject)
            }
            try context.save()
            syncMessage = "Pull correcto. Datos nuevos integrados."
        } catch {
            syncMessage = "Pull error: \(error.localizedDescription)"
        }
    }

    private var pendingQueueItems: [SharedSnapshot] {
        (try? JSONDecoder().decode([SharedSnapshot].self, from: Data(syncQueueJSON.utf8))) ?? []
    }

    private func enqueuePending(_ payload: SharedSnapshot) {
        var items = pendingQueueItems
        items.append(payload)
        items = Array(items.suffix(50))
        if let data = try? JSONEncoder().encode(items), let text = String(data: data, encoding: .utf8) {
            syncQueueJSON = text
        }
    }

    private func flushPendingQueue() async {
        guard let url = endpointURL() else { return }
        guard !pendingQueueItems.isEmpty else { return }
        isSyncing = true
        defer { isSyncing = false }

        var remaining: [SharedSnapshot] = []
        for item in pendingQueueItems {
            do {
                let body = try JSONEncoder().encode(item)
                var request = URLRequest(url: url)
                request.httpMethod = "PUT"
                request.httpBody = body
                request.setValue("application/json", forHTTPHeaderField: "Content-Type")
                let (_, response) = try await URLSession.shared.data(for: request)
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode) else {
                    remaining.append(item)
                    continue
                }
            } catch {
                remaining.append(item)
            }
        }

        if let data = try? JSONEncoder().encode(remaining), let text = String(data: data, encoding: .utf8) {
            syncQueueJSON = text
        }
        syncMessage = remaining.isEmpty ? "Cola sincronizada." : "Quedan \(remaining.count) items pendientes."
    }

    private func resolveSemester(label: String) -> Semester {
        if let existing = semesters.first(where: { $0.label.caseInsensitiveCompare(label) == .orderedSame }) {
            return existing
        }
        let created = Semester(label: label, startDate: Date())
        context.insert(created)
        return created
    }
}

private struct SharedSubjectSnapshot: Codable {
    let name: String
    let ects: Int
    let semester: String
    let grade: Double?
}

private struct SharedSnapshot: Codable {
    let updatedAt: String
    let subjects: [SharedSubjectSnapshot]
}

#Preview {
    ContentView()
}
