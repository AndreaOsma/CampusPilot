//
//  SubjectDetailView.swift
//  Campus Pilot
//
//  Created by Andrea Osma Rafael on 19/3/26.
//


/// Subject detail with grading tools, simulators, and sharing.

import SwiftUI
import SwiftData
import UniformTypeIdentifiers
#if canImport(UIKit)
import UIKit
#endif

/// SubjectDetailView view and UI state container.
struct SubjectDetailView: View {
    private enum SimulationMode: String, CaseIterable, Identifiable {
        case splitEvenly = "splitEvenly"
        case fixFirst = "fixFirst"

        var id: String { rawValue }

        var title: String {
            switch self {
            case .splitEvenly: return String(localized: "ui.sim.mode.split")
            case .fixFirst: return String(localized: "ui.sim.mode.fixFirst")
            }
        }
    }

    @Environment(\.modelContext) private var context
    @Bindable var subject: Subject
    @State private var selectedObjective: LearningObjective?
    @State private var isObjectiveInfoPresented = false
    @State private var selectedActivity: Activity?
    @State private var draftGradeText = ""
    @State private var isGradeEditorPresented = false
    @State private var isCopyToastPresented = false
    @State private var copyToastMessage = ""
    @State private var isCSVExporterPresented = false
    @State private var isGradeErrorPresented = false
    @State private var gradeErrorMessage = ""
    @State private var isSubjectEditorPresented = false
    @State private var simulatedActivityID: PersistentIdentifier?
    @State private var simulatedSecondActivityID: PersistentIdentifier?
    @State private var simulationMode: SimulationMode = .splitEvenly
    @State private var fixedFirstGrade = 5.0
    @State private var targetGrade = 5.0
    @State private var isSaveScenarioPresented = false
    @State private var newScenarioName = ""
    @State private var isScenarioErrorPresented = false
    @State private var scenarioErrorMessage = ""
    @State private var compareScenarioAID: PersistentIdentifier?
    @State private var compareScenarioBID: PersistentIdentifier?
    @State private var isAdvancedSectionsExpanded = false
    @State private var impactSimulationActivityID: PersistentIdentifier?

    private var sortedScenarios: [SimulationScenario] {
        subject.simulationScenarios.sorted { $0.createdAt > $1.createdAt }
    }

    private var simulationResult: (text: String, color: Color) {
        requiredGradeForSelectedActivity()
    }

    private var trendGradeEstimate: Double? {
        let recientes = subject.groups
            .flatMap(\.activities)
            .compactMap(\.grade)
            .suffix(3)

        guard !recientes.isEmpty else { return nil }
        let mediaRecientes = recientes.reduce(0.0, +) / Double(recientes.count)
        let base = subject.gradedActivitiesCount > 0 ? subject.weightedFinalGrade : mediaRecientes
        return (base * 0.7) + (mediaRecientes * 0.3)
    }

    var body: some View {
        List {
            summarySection
            quickSimulatorSection
            gradeImpactSection
            DisclosureGroup(String(localized: "ui.common.metrics"), isExpanded: $isAdvancedSectionsExpanded) {
                savedScenariosSection
                scenarioComparisonSection
                evaluationGroupsSections
                learningObjectivesSection
            }
        }
        .navigationTitle(subject.name)
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                Button {
                    isSubjectEditorPresented = true
                } label: {
                    Label(String(localized: "ui.common.edit"), systemImage: "pencil")
                }
            }

            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    ShareLink(
                        item: subject.exportableSummary,
                        preview: SharePreview(String(localized: "ui.common.summary"))
                    ) {
                        Label(String(localized: "ui.common.summary"), systemImage: "square.and.arrow.up")
                    }

                    Button {
                        copySummary()
                    } label: {
                        Label(String(localized: "ui.common.summary"), systemImage: "doc.on.doc")
                    }

                    ShareLink(
                        item: subject.exportableCSV,
                        preview: SharePreview(String(format: String(localized: "ui.format.subject"), subject.name))
                    ) {
                        Label(String(localized: "ui.common.summary"), systemImage: "tablecells")
                    }

                    Button {
                        copyCSV()
                    } label: {
                        Label(String(localized: "ui.common.summary"), systemImage: "tablecells.badge.ellipsis")
                    }

                    Button {
                        isCSVExporterPresented = true
                    } label: {
                        Label(String(localized: "ui.common.save"), systemImage: "externaldrive.badge.plus")
                    }
                } label: {
                    Image(systemName: "square.and.arrow.up.on.square")
                }
            }
        }
        .alert(String(localized: "ui.form.objectives"), isPresented: $isObjectiveInfoPresented, presenting: selectedObjective) { _ in
            Button(String(localized: "ui.common.close"), role: .cancel) { }
        } message: { objective in
            let pecNames = objective.linkedActivities.map { $0.name }.joined(separator: ", ")
            Text(pecNames.isEmpty ? String(localized: "ui.common.none") : pecNames)
        }
        .alert(String(localized: "ui.common.edit"), isPresented: $isGradeEditorPresented) {
            TextField(String(localized: "ui.common.metrics"), text: $draftGradeText)
                .keyboardType(.decimalPad)
            Button(String(localized: "ui.common.save")) {
                saveGrade()
            }
            Button(String(localized: "ui.subject.edit"), role: .destructive) {
                selectedActivity?.grade = nil
                do {
                    try context.save()
                } catch {
                    gradeErrorMessage = String(localized: "ui.alert.error")
                    isGradeErrorPresented = true
                }
            }
            Button(String(localized: "ui.common.cancel"), role: .cancel) { }
        } message: {
            Text(String(localized: "ui.common.description"))
        }
        .alert(String(localized: "ui.alert.success"), isPresented: $isCopyToastPresented) {
            Button(String(localized: "ui.common.ok"), role: .cancel) { }
        } message: {
            Text(copyToastMessage)
        }
        .alert(String(localized: "ui.alert.error"), isPresented: $isGradeErrorPresented) {
            Button(String(localized: "ui.common.close"), role: .cancel) { }
        } message: {
            Text(gradeErrorMessage)
        }
        .fileExporter(
            isPresented: $isCSVExporterPresented,
            document: CSVDocument(text: subject.exportableCSV),
            contentType: .commaSeparatedText,
            defaultFilename: csvFilename
        ) { _ in }
        .sheet(isPresented: $isSubjectEditorPresented) {
            AddSubjectView(subjectToEdit: subject)
        }
        .alert(String(localized: "ui.sim.save"), isPresented: $isSaveScenarioPresented) {
            TextField(String(localized: "ui.common.name"), text: $newScenarioName)
            Button(String(localized: "ui.common.cancel"), role: .cancel) { }
            Button(String(localized: "ui.common.save")) {
                saveCurrentScenario()
            }
        } message: {
            Text(String(localized: "ui.subject.grade.thisSavesTheTargetGradeActivitiesAndSimulatorMode"))
        }
        .alert(String(localized: "ui.sim.scenarios"), isPresented: $isScenarioErrorPresented) {
            Button(String(localized: "ui.common.close"), role: .cancel) { }
        } message: {
            Text(scenarioErrorMessage)
        }
    }

    @ViewBuilder
    private var summarySection: some View {
        Section(header: Text(String(localized: "ui.common.summary"))) {
            HStack {
                Label(String(localized: "ui.subject.credits"), systemImage: "book")
                Spacer()
                Text("\(subject.credits)")
                    .foregroundColor(.secondary)
            }

            HStack {
                Label(String(localized: "ui.subject.grade.estimated"), systemImage: "chart.bar.fill")
                Spacer()
                Text(String(format: String(localized: "ui.format.grade2f"), subject.weightedFinalGrade))
                    .fontWeight(.semibold)
                    .foregroundColor(subject.weightedFinalGrade >= 5 ? .green : .red)
            }

            HStack {
                Label(String(localized: "ui.common.status"), systemImage: "checkmark.seal")
                Spacer()
                Text(subject.enrollmentStatus == .convalidated ? EnrollmentStatus.convalidated.localizedName : subject.academicStatus.localizedName)
                    .fontWeight(.semibold)
                    .foregroundColor(subject.enrollmentStatus == .convalidated ? .gray : colorStatus(subject.academicStatus))
            }

            if let trend = trendGradeEstimate {
                HStack {
                    Label(String(localized: "ui.common.metrics"), systemImage: "waveform.path.ecg")
                    Spacer()
                    Text(String(format: String(localized: "ui.format.grade2f"), trend))
                        .fontWeight(.semibold)
                        .foregroundColor(trend >= 5 ? .green : .orange)
                }
                Text(String(localized: "ui.common.description"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }
    }

    @ViewBuilder
    private var quickSimulatorSection: some View {
        Section(header: Text(String(localized: "ui.sim.quick"))) {
            if pendingActivities.isEmpty {
                Label(String(localized: "ui.common.none"), systemImage: "checkmark.circle")
                    .foregroundColor(.secondary)
            } else {
                activeSimulatorContent
            }
        }
    }

    @ViewBuilder
    private var gradeImpactSection: some View {
        let graded = gradedActivitiesWithValue
        Section(header: Text(String(localized: "ui.sim.impact"))) {
            if graded.isEmpty {
                Text(String(localized: "ui.common.none"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                Picker(String(localized: "ui.subject.activity"), selection: Binding(
                    get: { impactSimulationActivityID ?? graded.first?.persistentModelID },
                    set: { impactSimulationActivityID = $0 }
                )) {
                    ForEach(graded, id: \.persistentModelID) { activity in
                        Text(activityNameWithGroup(activity)).tag(Optional(activity.persistentModelID))
                    }
                }

                HStack {
                    impactChip(delta: 0.5)
                    impactChip(delta: 1.0)
                    impactChip(delta: 1.5)
                }
            }
        }
    }

    @ViewBuilder
    private var activeSimulatorContent: some View {
        Picker(String(localized: "ui.subject.activity"), selection: simulatedActivityBinding) {
            ForEach(pendingActivities, id: \.persistentModelID) { activity in
                Text(activityNameWithGroup(activity)).tag(Optional(activity.persistentModelID))
            }
        }

        if pendingActivities.count > 1 {
            simulatorSecondActivityAndMode
        }

        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(String(localized: "ui.sim.target"))
                Spacer()
                Text(String(format: String(localized: "ui.format.grade2f"), targetGrade))
                    .fontWeight(.semibold)
            }
            Slider(value: $targetGrade, in: 5.0...10.0, step: 0.1)
        }

        if selectedSecondSimulatedActivity != nil && simulationMode == .fixFirst {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(String(localized: "ui.common.metrics"))
                    Spacer()
                    Text(String(format: String(localized: "ui.format.grade2f"), fixedFirstGrade))
                        .fontWeight(.semibold)
                }
                Slider(value: $fixedFirstGrade, in: 0.0...10.0, step: 0.1)
            }
        }

        HStack {
            Text(String(localized: "ui.sim.required"))
            Spacer()
            Text(simulationResult.text)
                .fontWeight(.semibold)
                .foregroundColor(simulationResult.color)
        }
        .font(.subheadline)

        if let act1 = selectedSimulatedActivity {
            let hoursAct1 = act1.estimatedHours
            let hoursAct2 = selectedSecondSimulatedActivity?.estimatedHours ?? 0.0
            let totalHours = hoursAct1 + hoursAct2
            if totalHours > 0.0 {
                Text(String(format: String(localized: "ui.format.hours"), totalHours))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }
        }

        Button {
            newScenarioName = ""
            isSaveScenarioPresented = true
        } label: {
            Label(String(localized: "ui.sim.save"), systemImage: "bookmark")
        }
        .disabled(!canSaveCurrentScenario)
    }

    @ViewBuilder
    private var simulatorSecondActivityAndMode: some View {
        Picker(String(localized: "ui.common.other"), selection: selectedSecondSimulatedActivityBinding) {
            Text(String(localized: "ui.common.none")).tag(Optional<PersistentIdentifier>.none)
            ForEach(pendingActivities, id: \.persistentModelID) { activity in
                let label = activityNameWithGroup(activity)
                if activity.persistentModelID == selectedSimulatedActivity?.persistentModelID {
                    Text(label).tag(Optional(activity.persistentModelID))
                } else {
                    Text(label).tag(Optional(activity.persistentModelID))
                }
            }
        }

        if selectedSecondSimulatedActivity != nil {
            Picker(String(localized: "ui.sim.mode.title"), selection: $simulationMode) {
                ForEach(SimulationMode.allCases) { mode in
                    Text(mode.title).tag(mode)
                }
            }
            .pickerStyle(.segmented)
        }
    }

    @ViewBuilder
    private var savedScenariosSection: some View {
        if !sortedScenarios.isEmpty {
            Section(header: Text(String(localized: "ui.sim.scenarios"))) {
                ForEach(sortedScenarios, id: \.persistentModelID) { scenario in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(scenario.name)
                            .font(.headline)
                        Text(scenarioSummary(scenario))
                            .font(.caption)
                            .foregroundColor(.secondary)
                        HStack {
                            Button(String(localized: "ui.common.apply")) {
                                applyScenario(scenario)
                            }
                            .buttonStyle(.borderedProminent)
                            .controlSize(.small)
                            Spacer()
                            Button(role: .destructive) {
                                deleteScenario(scenario)
                            } label: {
                                Image(systemName: "trash")
                            }
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }

    @ViewBuilder
    private var scenarioComparisonSection: some View {
        if sortedScenarios.count >= 2 {
            Section(header: Text(String(localized: "ui.sim.compare"))) {
                Picker(String(localized: "ui.common.other"), selection: Binding(
                    get: { compareScenarioAID ?? sortedScenarios.first?.persistentModelID },
                    set: { compareScenarioAID = $0 }
                )) {
                    ForEach(sortedScenarios, id: \.persistentModelID) { scenario in
                        Text(scenario.name).tag(Optional(scenario.persistentModelID))
                    }
                }

                Picker(String(localized: "ui.common.other"), selection: Binding(
                    get: { compareScenarioBID ?? sortedScenarios.dropFirst().first?.persistentModelID ?? sortedScenarios.first?.persistentModelID },
                    set: { compareScenarioBID = $0 }
                )) {
                    ForEach(sortedScenarios, id: \.persistentModelID) { scenario in
                        Text(scenario.name).tag(Optional(scenario.persistentModelID))
                    }
                }

                if let a = selectedScenarioA, let b = selectedScenarioB {
                    HStack(alignment: .top, spacing: 12) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(String(format: String(localized: "ui.format.subject"), a.name))
                                .font(.subheadline)
                                .fontWeight(.semibold)
                            Text(scenarioSummary(a))
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                        VStack(alignment: .leading, spacing: 4) {
                            Text(String(format: String(localized: "ui.format.subject"), b.name))
                                .font(.subheadline)
                                .fontWeight(.semibold)
                            Text(scenarioSummary(b))
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }

                    Text(scenarioDiffText(a: a, b: b))
                        .font(.caption)
                        .foregroundColor(.secondary)

                    Text(String(format: String(localized: "ui.format.subject"), recommendedScenarioName(a: a, b: b)))
                        .font(.caption)
                        .foregroundColor(.primary)
                }
            }
        }
    }

    @ViewBuilder
    private var evaluationGroupsSections: some View {
        ForEach(subject.groups) { group in
            Section(
                header: Text(String(format: String(localized: "ui.format.groupGlobalWeightHeaderFormat"), group.name, Int(group.globalWeight * 100))),
                footer: Text(groupRulesSummary(for: group))
            ) {
                ForEach(group.activities) { activity in
                    HStack {
                        Text(activity.name)
                        Spacer()
                        Text("\(Int(activity.weightWithinGroup * 100))%")
                            .foregroundColor(.secondary)
                            .font(.caption)

                        if let grade = activity.grade {
                            Text(String(format: "%.2f", grade))
                                .bold()
                                .foregroundColor(grade >= 5.0 ? .green : .red)
                        } else {
                            Text(String(localized: "ui.subject.status.pending"))
                                .foregroundColor(.secondary)
                        }
                    }
                    .contentShape(Rectangle())
                    .onTapGesture {
                        openGradeEditor(activity)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var learningObjectivesSection: some View {
        Section(header: Text(String(localized: "ui.form.objectives"))) {
            ForEach(subject.objectives) { objective in
                VStack(alignment: .leading, spacing: 6) {
                    HStack(alignment: .top, spacing: 8) {
                        Image(systemName: objective.isAchieved ? "checkmark.circle.fill" : "circle")
                            .foregroundColor(objective.isAchieved ? .green : .gray)

                        Text(objective.description)
                            .strikethrough(objective.isAchieved, color: .gray)
                            .foregroundColor(objective.isAchieved ? .gray : .primary)
                            .font(.subheadline)
                            .fontWeight(objective.isAchieved ? .semibold : .regular)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }

                    if objective.linkedActivities.isEmpty {
                        Text(String(localized: "ui.common.none.LinkedActivities.a4c7"))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    } else {
                        ForEach(objective.linkedActivities, id: \.persistentModelID) { activity in
                            HStack(spacing: 8) {
                                Image(systemName: activity.grade != nil ? (activity.isPassed ? "checkmark.circle.fill" : "circle.fill") : "circle")
                                    .foregroundColor(
                                        activity.grade != nil ? (activity.isPassed ? .green : .orange) : .secondary
                                    )

                                Text(activity.name)
                                    .font(.caption2)
                                    .foregroundColor(.primary)

                                Spacer()

                                if let grade = activity.grade {
                                    Text(String(format: "%.2f", grade))
                                        .font(.caption2)
                                        .foregroundColor(grade >= 5.0 ? .green : .orange)
                                } else {
                                    Text(String(localized: "ui.subject.status.pending"))
                                        .font(.caption2)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                    }
                }
                .contentShape(Rectangle())
                .onTapGesture {
                    selectedObjective = objective
                    isObjectiveInfoPresented = true
                }
            }
        }
    }

    // Visual helper to show whether the group has restrictive rules
/// Handles group rules summary.
    private func groupRulesSummary(for group: EvaluationGroup) -> String {
        var rules: [String] = []
        if group.isRequiredToPass { rules.append(String(localized: "ui.common.requiredToPass")) }
        if let minimum = group.minimumRequiredGrade {
            rules.append(String(format: String(localized: "ui.format.minimumGradeFormat"), minimum))
        }
        if let maxFails = group.maxAllowedFails {
            rules.append(String(format: String(localized: "ui.format.maxFailsFormat"), maxFails))
        }
        return rules.isEmpty ? String(localized: "ui.common.none.RestrictiveRules") : rules.joined(separator: " | ")
    }

/// Handles open grade editor.
    private func openGradeEditor(_ activity: Activity) {
        selectedActivity = activity
        if let grade = activity.grade {
            draftGradeText = String(format: "%.2f", grade)
        } else {
            draftGradeText = ""
        }
        isGradeEditorPresented = true
    }

/// Saves grade.
    private func saveGrade() {
        guard let activity = selectedActivity else { return }
        let normalizedText = draftGradeText.replacingOccurrences(of: ",", with: ".")
        guard let value = Double(normalizedText) else {
            gradeErrorMessage = String(localized: "ui.common.enterAValidNumericValueBetween0And10")
            isGradeErrorPresented = true
            return
        }
        activity.grade = min(max(value, 0.0), 10.0)
        do {
            try context.save()
        } catch {
            gradeErrorMessage = String(localized: "ui.alert.couldNotPersistTheChangeTryAgain")
            isGradeErrorPresented = true
        }
    }

/// Handles copy summary.
    private func copySummary() {
        #if canImport(UIKit)
        UIPasteboard.general.string = subject.exportableSummary
        copyToastMessage = String(localized: "ui.subject.theSubjectSummaryHasBeenCopiedToTheClipboard")
        isCopyToastPresented = true
        #endif
    }

/// Handles copy csv.
    private func copyCSV() {
        #if canImport(UIKit)
        UIPasteboard.general.string = subject.exportableCSV
        copyToastMessage = String(localized: "ui.subject.theSubjectCSVHasBeenCopiedToTheClipboard")
        isCopyToastPresented = true
        #endif
    }

    private var csvFilename: String {
        let base = subject.name
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "/", with: "-")
            .replacingOccurrences(of: ":", with: "-")
        let nameBase = base.isEmpty ? "subject" : base
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd"
        let dateText = formatter.string(from: Date())
        return "\(nameBase)-\(dateText)"
    }

/// Handles color status.
    private func colorStatus(_ status: AcademicStatus) -> Color {
        switch status {
        case .inProgress: return .orange
        case .passed: return .green
        case .failed: return .red
        }
    }

    private var canSaveCurrentScenario: Bool {
        guard selectedSimulatedActivity != nil else { return false }
        if selectedSecondSimulatedActivity != nil {
            return selectedSimulatedActivity?.persistentModelID != selectedSecondSimulatedActivity?.persistentModelID
        }
        return true
    }

/// Handles group name.
    private func groupName(for activity: Activity) -> String? {
        for group in subject.groups where group.activities.contains(where: { $0.persistentModelID == activity.persistentModelID }) {
            return group.name
        }
        return nil
    }

/// Handles pending activity.
    private func pendingActivity(groupName: String, activityName: String) -> Activity? {
        for group in subject.groups where group.name == groupName {
            if let activity = group.activities.first(where: { $0.name == activityName && $0.grade == nil }) {
                return activity
            }
        }
        return nil
    }

/// Handles scenario summary.
    private func scenarioSummary(_ scenario: SimulationScenario) -> String {
        let mode = SimulationMode(rawValue: scenario.modeRaw) ?? .splitEvenly
        var parts: [String] = [
            "\(String(localized: "ui.sim.target")): \(String(format: String(localized: "ui.format.grade2f"), scenario.targetGrade))",
            "\(scenario.groupName1) · \(scenario.activityName1)"
        ]
        if !scenario.groupName2.isEmpty, !scenario.activityName2.isEmpty {
            parts.append("+ \(scenario.groupName2) · \(scenario.activityName2)")
            parts.append(mode.title)
            if mode == .fixFirst {
                parts.append("\(String(localized: "ui.common.metrics")): \(String(format: String(localized: "ui.format.grade2f"), scenario.fixedFirstGrade))")
            }
        }
        return parts.joined(separator: " · ")
    }

/// Saves current scenario.
    private func saveCurrentScenario() {
        let cleanName = newScenarioName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleanName.isEmpty else {
            scenarioErrorMessage = String(localized: "ui.common.enterANameForTheScenario")
            isScenarioErrorPresented = true
            return
        }
        guard let act1 = selectedSimulatedActivity, let g1 = groupName(for: act1) else {
            scenarioErrorMessage = String(localized: "ui.alert.couldNotIdentifyTheFirstActivity")
            isScenarioErrorPresented = true
            return
        }
        var g2 = ""
        var secondActivityName = ""
        if let act2 = selectedSecondSimulatedActivity, act2.persistentModelID != act1.persistentModelID, let gg = groupName(for: act2) {
            g2 = gg
            secondActivityName = act2.name
        }
        let scenario = SimulationScenario(
            name: cleanName,
            targetGrade: targetGrade,
            modeRaw: simulationMode.rawValue,
            fixedFirstGrade: fixedFirstGrade,
            groupName1: g1,
            activityName1: act1.name,
            groupName2: g2,
            activityName2: secondActivityName
        )
        context.insert(scenario)
        scenario.subject = subject
        do {
            try context.save()
        } catch {
            scenarioErrorMessage = String(localized: "ui.alert.couldNotSaveTheScenario")
            isScenarioErrorPresented = true
        }
    }

/// Applies scenario.
    private func applyScenario(_ scenario: SimulationScenario) {
        guard let act1 = pendingActivity(groupName: scenario.groupName1, activityName: scenario.activityName1) else {
            scenarioErrorMessage = String(localized: "ui.alert.couldNotFindTheFirstPendingActivityCheckBlockAndActivityNames")
            isScenarioErrorPresented = true
            return
        }
        simulatedActivityID = act1.persistentModelID
        targetGrade = scenario.targetGrade
        simulationMode = SimulationMode(rawValue: scenario.modeRaw) ?? .splitEvenly
        fixedFirstGrade = scenario.fixedFirstGrade

        if scenario.groupName2.isEmpty || scenario.activityName2.isEmpty {
            simulatedSecondActivityID = nil
        } else if let act2 = pendingActivity(groupName: scenario.groupName2, activityName: scenario.activityName2) {
            if act2.persistentModelID == act1.persistentModelID {
                simulatedSecondActivityID = nil
            } else {
                simulatedSecondActivityID = act2.persistentModelID
            }
        } else {
            simulatedSecondActivityID = nil
            scenarioErrorMessage = String(localized: "ui.subject.appliedThe1stActivityThe2ndIsNotPendingOrDoesNotMatch")
            isScenarioErrorPresented = true
        }
    }

/// Deletes scenario.
    private func deleteScenario(_ scenario: SimulationScenario) {
        context.delete(scenario)
        try? context.save()
    }

    private var pendingActivities: [Activity] {
        subject.groups.flatMap(\.activities).filter { $0.grade == nil }
    }

    private var selectedSimulatedActivity: Activity? {
        guard let id = simulatedActivityID else { return pendingActivities.first }
        return pendingActivities.first(where: { $0.persistentModelID == id })
    }

    private var simulatedActivityBinding: Binding<PersistentIdentifier?> {
        Binding(
            get: { selectedSimulatedActivity?.persistentModelID },
            set: { simulatedActivityID = $0 }
        )
    }

    private var selectedSecondSimulatedActivity: Activity? {
        guard let id = simulatedSecondActivityID else { return nil }
        return pendingActivities.first(where: { $0.persistentModelID == id })
    }

    private var selectedSecondSimulatedActivityBinding: Binding<PersistentIdentifier?> {
        Binding(
            get: { selectedSecondSimulatedActivity?.persistentModelID },
            set: { simulatedSecondActivityID = $0 }
        )
    }

    private var gradedActivitiesWithValue: [Activity] {
        subject.groups.flatMap(\.activities).filter { $0.grade != nil }
    }

    private var selectedImpactActivity: Activity? {
        let id = impactSimulationActivityID ?? gradedActivitiesWithValue.first?.persistentModelID
        return gradedActivitiesWithValue.first(where: { $0.persistentModelID == id })
    }

    @ViewBuilder
/// Handles impact chip.
    private func impactChip(delta: Double) -> some View {
        let projected = projectedFinalGradeIfBoost(delta: delta)
        VStack(spacing: 2) {
            Text(delta, format: .number.sign(strategy: .always(includingZero: false)).precision(.fractionLength(1)))
                .font(.caption2)
                .foregroundColor(.secondary)
            Text(projected.map { String(format: "%.2f", $0) } ?? "--")
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundColor((projected ?? 0) >= 5 ? .green : .orange)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Color.secondary.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

/// Handles projected final grade if boost.
    private func projectedFinalGradeIfBoost(delta: Double) -> Double? {
        guard let target = selectedImpactActivity, let original = target.grade else { return nil }
        var weightedSum = 0.0
        var weightTotal = 0.0
        for group in subject.groups {
            let completed = group.activities.filter { $0.grade != nil }
            let groupWeightSum = completed.reduce(0.0) { $0 + $1.weightWithinGroup }
            guard groupWeightSum > 0 else { continue }
            let groupWeighted = completed.reduce(0.0) { partial, activity in
                let grade = (activity.persistentModelID == target.persistentModelID) ? min(10.0, original + delta) : (activity.grade ?? 0)
                return partial + (grade * activity.weightWithinGroup)
            } / groupWeightSum
            weightedSum += groupWeighted * group.globalWeight
            weightTotal += group.globalWeight
        }
        guard weightTotal > 0 else { return nil }
        return weightedSum / weightTotal
    }

    private var selectedScenarioA: SimulationScenario? {
        let id = compareScenarioAID ?? sortedScenarios.first?.persistentModelID
        return sortedScenarios.first(where: { $0.persistentModelID == id })
    }

    private var selectedScenarioB: SimulationScenario? {
        let fallback = sortedScenarios.dropFirst().first?.persistentModelID ?? sortedScenarios.first?.persistentModelID
        let id = compareScenarioBID ?? fallback
        return sortedScenarios.first(where: { $0.persistentModelID == id })
    }

/// Handles scenario diff text.
    private func scenarioDiffText(a: SimulationScenario, b: SimulationScenario) -> String {
        var changes: [String] = []
        if abs(a.targetGrade - b.targetGrade) > 0.0001 {
            changes.append("\(String(localized: "ui.sim.target")): \(String(format: "%.1f", a.targetGrade)) vs \(String(format: "%.1f", b.targetGrade))")
        }
        if a.modeRaw != b.modeRaw {
            changes.append(String(localized: "ui.common.differentMode"))
        }
        if a.activityName1 != b.activityName1 || a.groupName1 != b.groupName1 {
            changes.append(String(localized: "ui.subject.different1stActivity"))
        }
        if a.activityName2 != b.activityName2 || a.groupName2 != b.groupName2 {
            changes.append(String(localized: "ui.subject.different2ndActivity"))
        }
        if changes.isEmpty { return String(localized: "ui.common.none.RelevantDifferences") }
        return changes.joined(separator: " · ")
    }

/// Handles recommended scenario name.
    private func recommendedScenarioName(a: SimulationScenario, b: SimulationScenario) -> String {
        let scoreA = scenarioRecommendationScore(a)
        let scoreB = scenarioRecommendationScore(b)
        if abs(scoreA - scoreB) < 0.01 { return String(localized: "ui.common.bothAreEquivalentRightNow") }
        return scoreA > scoreB ? a.name : b.name
    }

/// Handles scenario recommendation score.
    private func scenarioRecommendationScore(_ scenario: SimulationScenario) -> Double {
        var score = scenario.targetGrade
        if scenario.modeRaw == SimulationMode.fixFirst.rawValue {
            score -= 0.3
            if scenario.fixedFirstGrade < 5 { score -= 0.7 }
        }
        if !scenario.activityName2.isEmpty { score += 0.2 }
        return score
    }

/// Handles activity name with group.
    private func activityNameWithGroup(_ activity: Activity) -> String {
        for group in subject.groups where group.activities.contains(where: { $0.persistentModelID == activity.persistentModelID }) {
            return "\(group.name) · \(activity.name)"
        }
        return activity.name
    }

/// Handles absolute activity weight.
    private func absoluteActivityWeight(_ activity: Activity) -> Double {
        for group in subject.groups where group.activities.contains(where: { $0.persistentModelID == activity.persistentModelID }) {
            return group.globalWeight * activity.weightWithinGroup
        }
        return 0.0
    }

/// Handles required grade for selected activity.
    private func requiredGradeForSelectedActivity() -> (text: String, color: Color) {
        guard let targetActivity = selectedSimulatedActivity else {
            return ("-", .secondary)
        }

        let allActivities = subject.groups.flatMap(\.activities)
        let totalWeight = allActivities.reduce(0.0) { $0 + absoluteActivityWeight($1) }
        guard totalWeight > 0 else { return (String(localized: "ui.common.none.Weights"), .secondary) }

        let secondActivity = selectedSecondSimulatedActivity
        if let secondActivity, secondActivity.persistentModelID == targetActivity.persistentModelID {
            return (String(localized: "ui.common.selectDifferentActivities"), .orange)
        }

        if let secondActivity, simulationMode == .fixFirst {
            let activityWeightA = absoluteActivityWeight(targetActivity)
            let activityWeightB = absoluteActivityWeight(secondActivity)
            guard activityWeightB > 0 else { return (String(localized: "ui.common.2ndHasNoImpact"), .secondary) }

            let targetIDs: Set<PersistentIdentifier> = [targetActivity.persistentModelID, secondActivity.persistentModelID]
            let knownContribution = allActivities.reduce(0.0) { partial, activity in
                if targetIDs.contains(activity.persistentModelID) { return partial }
                guard let grade = activity.grade else { return partial }
                return partial + (absoluteActivityWeight(activity) * grade)
            }

            let fixedContributionA = fixedFirstGrade * activityWeightA
            let requiredB = ((targetGrade * totalWeight) - knownContribution - fixedContributionA) / activityWeightB

            if requiredB <= 0 {
                return (String(format: String(localized: "ui.format.with1fOn1stAlreadyAchievedFormat"), fixedFirstGrade), .green)
            } else if requiredB > 10 {
                return (String(format: String(localized: "ui.format.with1fOn1stUnreachableOn2ndFormat"), fixedFirstGrade), .red)
            } else {
                return (String(format: String(localized: "ui.format.2ndNeeds2fFormat"), requiredB), .orange)
            }
        }

        let targetIDs: Set<PersistentIdentifier> = {
            if let secondActivity {
                return [targetActivity.persistentModelID, secondActivity.persistentModelID]
            }
            return [targetActivity.persistentModelID]
        }()

        let knownContribution = allActivities.reduce(0.0) { partial, activity in
            if targetIDs.contains(activity.persistentModelID) { return partial }
            guard let grade = activity.grade else { return partial }
            return partial + (absoluteActivityWeight(activity) * grade)
        }

        let targetWeight = targetIDs.reduce(0.0) { partial, id in
            guard let activity = allActivities.first(where: { $0.persistentModelID == id }) else { return partial }
            return partial + absoluteActivityWeight(activity)
        }
        guard targetWeight > 0 else { return (String(localized: "ui.common.none.Impact"), .secondary) }

        let required = ((targetGrade * totalWeight) - knownContribution) / targetWeight

        if required <= 0 {
            return secondActivity == nil ? (String(localized: "ui.common.alreadyAchieved"), .green) : (String(localized: "ui.common.alreadyAchievedAcrossBoth"), .green)
        } else if required > 10 {
            return (String(localized: "ui.sim.unreachable"), .red)
        } else {
            if secondActivity == nil {
                return (String(format: "%.2f", required), .orange)
            }
            return (String(format: String(localized: "ui.format.2fOnBothFormat"), required), .orange)
        }
    }
}

private struct CSVDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.commaSeparatedText] }
    var text: String

    init(text: String) {
        self.text = text
    }

    init(configuration: ReadConfiguration) throws {
        if let data = configuration.file.regularFileContents,
           let value = String(data: data, encoding: .utf8) {
            text = value
        } else {
            text = ""
        }
    }

/// Handles file wrapper.
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        let data = Data(text.utf8)
        return .init(regularFileWithContents: data)
    }
}
