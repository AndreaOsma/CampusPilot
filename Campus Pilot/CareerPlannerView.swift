/// Career planner workspace with calendar, exports, and productivity tools.

import SwiftUI
import SwiftData
import UserNotifications
import UniformTypeIdentifiers
import Combine
#if canImport(UIKit)
import UIKit
#endif

/// CareerPlannerView view and UI state container.
struct CareerPlannerView: View {
    private enum QuickStatusFilter: String, CaseIterable, Identifiable {
        case all = "All"
        case enrolled = "Enrolled"
        case convalidated = "Convalidated"
        case pending = "Pending"
        case completed = "Completed"
        var id: String { rawValue }

        var localizedName: String {
            switch self {
            case .all: return String(localized: "ui.common.all")
            case .enrolled: return String(localized: "ui.subject.status.enrolled")
            case .convalidated: return String(localized: "ui.subject.status.convalidated")
            case .pending: return String(localized: "ui.subject.status.pending")
            case .completed: return String(localized: "ui.common.completed")
            }
        }
    }

    @Environment(\.modelContext) private var context
    @Query(sort: \Career.name) private var careers: [Career]
    @Query(sort: \Semester.startDate) private var semesters: [Semester]
    @Query private var subjects: [Subject]

    @State private var selectedCareerID: PersistentIdentifier?
    @State private var selectedSemesterID: PersistentIdentifier?

    @State private var isPlanSheetPresented = false
    @State private var selectedSubject: Subject?
    @State private var isAddSubjectPresented = false
    @State private var isAddCareerPresented = false
    @State private var newCareerName = ""
    @State private var newCareerECTS = 240
    @State private var editingCareerID: PersistentIdentifier?
    @State private var quickStatusFilter: QuickStatusFilter = .all
    @State private var ectsSimulationRatio: Double = 100
    @State private var weeklyLoadAlertThreshold: Double = 12
    @State private var isExamModeEnabled = false
    @AppStorage("planner_trash_subjects_json") private var plannerTrashSubjectsJSON = "[]"
    @AppStorage("planner_trash_careers_json") private var plannerTrashCareersJSON = "[]"
    @State private var isImportPresented = false
    @State private var importMessage = ""
    @State private var isImportMessagePresented = false
    @State private var isPDFExporterPresented = false
    @State private var pdfDocument = PlannerPDFDocument(data: Data())
    @State private var pdfExportFilename = "informe"
    @State private var isAdvancedPanelExpanded = false
    @State private var newWeeklyGoal = ""
    @AppStorage("weekly_goals_raw") private var weeklyGoalsRaw = ""
    @AppStorage("weekly_goal_done_keys") private var weeklyGoalDoneKeysRaw = "[]"
    @AppStorage("study_streak_count") private var studyStreakCount = 0
    @AppStorage("study_last_check_date") private var studyLastCheckDateRaw = ""
    @State private var focusRemainingSeconds = 25 * 60
    @State private var isFocusRunning = false
    @State private var focusCancellable: AnyCancellable?
    @State private var focusSelectedSubjectID: PersistentIdentifier?
    @AppStorage("focus_sessions_raw") private var focusSessionsRaw = "[]"
    @State private var isFinalReviewModeEnabled = false
    @State private var isSemesterClosingModeEnabled = false
    @State private var isAdvancedHabitsExpanded = false
    @State private var isAdvancedLearningExpanded = false
    @State private var isAdvancedAnalysisExpanded = false
    @State private var isQuickPanelExpanded = false
    @State private var isCareerManagementExpanded = false
    @State private var isStudyModesExpanded = false
    @State private var isSemesterEditorPresented = false
    @State private var semesterEditorTarget: Semester?
    @State private var isDeleteSemesterPresented = false
    @State private var semesterToDelete: Semester?

    var body: some View {
        List {
            if careers.isEmpty || semesters.isEmpty {
                ContentUnavailableView(
                    String(localized: "ui.common.preparingYourPlan"),
                    systemImage: "hourglass",
                    description: Text(String(localized: "ui.career.onceYourCareerAndSemestersAreInitializedYouWillBeAbleToPlan"))
                )
            } else {
                Section {
                    filters
                }

                Section {
                    summary
                }

                Section {
                    DisclosureGroup(String(localized: "ui.planner.studyModes"), isExpanded: $isStudyModesExpanded) {
                        Toggle(String(localized: "ui.subject.examMode"), isOn: $isExamModeEnabled)
                        Toggle(String(localized: "ui.common.finalReviewMode"), isOn: $isFinalReviewModeEnabled)
                        Toggle(String(localized: "ui.career.semesterClosingMode"), isOn: $isSemesterClosingModeEnabled)

                        if isExamModeEnabled || isFinalReviewModeEnabled || isSemesterClosingModeEnabled {
                            Divider().padding(.vertical, 6)
                        }

                        if isExamModeEnabled { examsModeSection }
                        if isFinalReviewModeEnabled { finalReviewSection }
                        if isSemesterClosingModeEnabled { semesterClosingSection }
                    }

                    DisclosureGroup(String(localized: "ui.common.quickView"), isExpanded: $isQuickPanelExpanded) {
                        dailyAgendaSection
                    }

                    DisclosureGroup(String(localized: "ui.common.advancedPanel"), isExpanded: $isAdvancedPanelExpanded) {
                        VStack(alignment: .leading, spacing: 12) {
                            DisclosureGroup(String(localized: "ui.common.habitsAndPlanning"), isExpanded: $isAdvancedHabitsExpanded) {
                                VStack(alignment: .leading, spacing: 10) {
                                    inactiveSubjectsSection
                                    weeklyGoalsSection
                                    focusModeSection
                                    stressPredictionSection
                                    trafficLightMilestonesSection
                                }
                            }

                            DisclosureGroup(String(localized: "ui.common.learningAndObjectives"), isExpanded: $isAdvancedLearningExpanded) {
                                VStack(alignment: .leading, spacing: 10) {
                                    learningObjectivesSection
                                    semesterObjectivesSection
                                }
                            }

                            DisclosureGroup(String(localized: "ui.sim.title"), isExpanded: $isAdvancedAnalysisExpanded) {
                                VStack(alignment: .leading, spacing: 10) {
                                    semesterComparisonSection
                                    annualReportSection
                                    riskRadarSection
                                    weeklyWorkloadSection
                                    ectsSimulationSection
                                }
                            }
                        }
                        .padding(.top, 6)
                    }
                }

                Section(String(localized: "ui.subject.list")) {
                    subjectListSection
                }
            }
        }
        .listStyle(.insetGrouped)
        .navigationTitle(String(localized: "ui.career.planner.title"))
        .navigationBarTitleDisplayMode(.inline)
        .toolbarBackground(.visible, for: .navigationBar)
        .toolbarBackground(Color(.systemBackground), for: .navigationBar)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                NavigationLink {
                    PlannerSettingsView(
                        isAddSubjectPresented: $isAddSubjectPresented,
                        isImportPresented: $isImportPresented,
                        isPDFExporterPresented: $isPDFExporterPresented,
                        pdfDocument: $pdfDocument,
                        pdfExportFilename: $pdfExportFilename,
                        selectedCareerID: $selectedCareerID,
                        selectedSemesterID: $selectedSemesterID,
                        exportJSON: exportJSON,
                        exportCSV: exportCSV,
                        progressPDFData: { generateProgressPDFData() },
                        progressPDFFilename: { pdfFilename },
                        monthlyPDFData: { generateMonthlySummaryPDFData() },
                        monthlyPDFFilename: { monthlySummaryPDFFilename }
                    )
                } label: {
                    Image(systemName: "gearshape")
                }
            }
        }
        .sheet(isPresented: $isPlanSheetPresented) {
            if let selectedSubject {
                PlanSubjectSheet(subject: selectedSubject)
            }
        }
        .sheet(isPresented: $isAddSubjectPresented) {
            AddSubjectView(
                subjectToEdit: nil,
                defaultCareerID: selectedCareerID,
                defaultSemesterID: selectedSemesterID
            )
            .environment(\.modelContext, context)
        }
        .sheet(isPresented: $isAddCareerPresented) {
            NavigationStack {
                Form {
                    Section(header: Text(String(localized: "ui.common.name"))) {
                        TextField(String(localized: "ui.career.title"), text: $newCareerName)
                            .textInputAutocapitalization(.words)
                    }
                    Section(header: Text(String(localized: "ui.career.ects.target"))) {
                        Stepper(String(format: String(localized: "ui.format.credits"), newCareerECTS), value: $newCareerECTS, in: 30...600, step: 6)
                    }
                }
                .navigationTitle(editingCareerID == nil ? String(localized: "ui.career.new") : String(localized: "ui.career.edit"))

                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button(String(localized: "ui.common.cancel")) {
                            isAddCareerPresented = false
                            editingCareerID = nil
                        }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button(String(localized: "ui.common.save")) { saveCareer() }
                            .disabled(newCareerName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
            }
        }
        .sheet(isPresented: $isSemesterEditorPresented) {
            SemesterEditorView(semesterToEdit: semesterEditorTarget, selectedSemesterID: $selectedSemesterID)
                .environment(\.modelContext, context)
        }
        .alert(String(localized: "ui.semester.delete"), isPresented: $isDeleteSemesterPresented) {
            Button(String(localized: "ui.common.cancel"), role: .cancel) {
                semesterToDelete = nil
            }
            Button(String(localized: "ui.common.delete"), role: .destructive) {
                if let semesterToDelete {
                    deleteSemester(semesterToDelete)
                }
                semesterToDelete = nil
            }
        } message: {
            Text(String(localized: "ui.alert.deleteConfirm"))
        }
        .onAppear {
            initializeSelectionsIfNeeded()
        }
        .fileImporter(
            isPresented: $isImportPresented,
            allowedContentTypes: [.json],
            allowsMultipleSelection: false
        ) { result in
            handleImport(result)
        }
        .fileExporter(
            isPresented: $isPDFExporterPresented,
            document: pdfDocument,
            contentType: .pdf,
            defaultFilename: pdfExportFilename
        ) { _ in }
        .alert(String(localized: "ui.common.import"), isPresented: $isImportMessagePresented) {
            Button(String(localized: "ui.common.ok"), role: .cancel) {}
        } message: {
            Text(importMessage)
        }
        .onDisappear {
            stopFocusTimer()
        }
    }

/// Saves career.
    private func saveCareer() {
        let trimmed = newCareerName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        if let editingCareerID,
           let existing = careers.first(where: { $0.persistentModelID == editingCareerID }) {
            existing.name = trimmed
            existing.ectsGoal = newCareerECTS
            try? context.save()
            isAddCareerPresented = false
            self.editingCareerID = nil
            return
        }

        let career = Career(name: trimmed, ectsGoal: newCareerECTS)
        context.insert(career)
        try? context.save()

        selectedCareerID = career.persistentModelID
        isAddCareerPresented = false
        editingCareerID = nil
    }

/// Deletes career.
    private func deleteCareer(_ career: Career) {
        pushDeletedCareerSnapshot(
            DeletedCareerSnapshot(
                name: career.name,
                ectsGoal: career.ectsGoal,
                deletedAt: Date()
            )
        )
        let wasSelected = selectedCareerID == career.persistentModelID
        context.delete(career)
        try? context.save()

        if wasSelected {
            selectedCareerID = careers.first(where: { $0.persistentModelID != career.persistentModelID })?.persistentModelID
        }
    }

/// Deletes subject.
    private func deleteSubject(_ subject: Subject) {
        let careerName = subject.career?.name ?? ""
        let semesterStart = subject.semester?.startDate ?? Date()
        pushDeletedSubjectSnapshot(
            DeletedSubjectSnapshot(
                name: subject.name,
                credits: subject.credits,
                careerName: careerName,
                semesterStart: semesterStart,
                deletedAt: Date()
            )
        )
        context.delete(subject)
        try? context.save()
    }

/// Deletes semester.
    private func deleteSemester(_ semester: Semester) {
        let wasSelected = selectedSemesterID == semester.persistentModelID
        context.delete(semester)
        try? context.save()

        if wasSelected {
            selectedSemesterID = semesters.first(where: { $0.persistentModelID != semester.persistentModelID })?.persistentModelID
        }
    }

/// Restores last deleted subject.
    private func restoreLastDeletedSubject() {
        guard let snapshot = popLastSubjectSnapshot() else { return }
        let subject = Subject(name: snapshot.name, credits: snapshot.credits)
        subject.enrollmentStatus = .pending
        if let career = careers.first(where: { $0.name == snapshot.careerName }) {
            subject.career = career
        } else {
            subject.career = careerSel ?? careers.first
        }
        if let semester = semesters.first(where: { Calendar.current.isDate($0.startDate, inSameDayAs: snapshot.semesterStart) }) {
            subject.semester = semester
        } else {
            subject.semester = semesterSel ?? semesters.first
        }
        context.insert(subject)
        try? context.save()
    }

/// Restores last deleted career.
    private func restoreLastDeletedCareer() {
        guard let snapshot = popLastCareerSnapshot() else { return }
        let career = Career(name: snapshot.name, ectsGoal: snapshot.ectsGoal)
        context.insert(career)
        try? context.save()
        selectedCareerID = career.persistentModelID
    }

/// Handles duplicate subject.
    private func duplicateSubject(_ source: Subject) {
        let copy = Subject(name: source.name, credits: source.credits)
        copy.career = source.career
        copy.semester = source.semester
        copy.enrollmentStatus = .pending
        copy.enrollmentDate = Date()
        copy.pricePerCredit = source.pricePerCredit
        copy.base = source.base
        context.insert(copy)

        for group in source.groups {
            let newGroup = EvaluationGroup(
                name: group.name,
                globalWeight: group.globalWeight,
                isRequiredToPass: group.isRequiredToPass
            )
            newGroup.minimumRequiredGrade = group.minimumRequiredGrade
            newGroup.maxAllowedFails = group.maxAllowedFails
            context.insert(newGroup)
            copy.groups.append(newGroup)

            for activity in group.activities {
                let newActivity = Activity(name: activity.name, weightWithinGroup: activity.weightWithinGroup)
                newActivity.estimatedHours = activity.estimatedHours
                newActivity.deliveryWeek = activity.deliveryWeek
                context.insert(newActivity)
                newGroup.activities.append(newActivity)
            }
        }

        for goal in source.objectives {
            let newGoal = LearningObjective(description: goal.description)
            context.insert(newGoal)
            copy.objectives.append(newGoal)
        }

        try? context.save()
    }

    private var exportJSON: String {
        let rows = subjects.map { subject in
            [
                "name": subject.name,
                "credits": String(subject.credits),
                "career": subject.career?.name ?? "",
                "semester": subject.semester?.displayTitle ?? "",
                "status": subject.enrollmentStatus.rawValue
            ]
        }
        if let data = try? JSONSerialization.data(withJSONObject: rows, options: [.prettyPrinted]),
           let text = String(data: data, encoding: .utf8) {
            return text
        }
        return "[]"
    }

    private var exportCSV: String {
        var lines = [String(localized: "ui.mec.nameCreditsCareerSemesterStatus")]
        for subject in subjects {
            let row = [
                "\"\(subject.name.replacingOccurrences(of: "\"", with: "\"\""))\"",
                "\(subject.credits)",
                "\"\((subject.career?.name ?? "").replacingOccurrences(of: "\"", with: "\"\""))\"",
                "\"\((subject.semester?.displayTitle ?? "").replacingOccurrences(of: "\"", with: "\"\""))\"",
                "\"\(subject.enrollmentStatus.localizedName)\""
            ]
            lines.append(row.joined(separator: ","))
        }
        return lines.joined(separator: "\n")
    }

    private var pdfFilename: String {
        let formatter = DateFormatter()
        formatter.locale = .current
        formatter.calendar = .current
        formatter.timeZone = .current
        formatter.dateFormat = "yyyy-MM-dd"
        let dateText = formatter.string(from: Date())
        let career = (careerSel?.name ?? String(localized: "ui.career.title")).replacingOccurrences(of: " ", with: "-")
        return "report-\(career)-\(dateText)"
    }

    private var monthlySummaryPDFFilename: String {
        let formatter = DateFormatter()
        formatter.locale = .current
        formatter.calendar = .current
        formatter.timeZone = .current
        formatter.dateFormat = "yyyy-MM"
        let dateText = formatter.string(from: Date())
        let career = (careerSel?.name ?? String(localized: "ui.career.title")).replacingOccurrences(of: " ", with: "-")
        return "monthly-summary-\(career)-\(dateText)"
    }

/// Builds progress pdfdata.
    private func generateProgressPDFData() -> Data {
        let careerName = careerSel?.name ?? String(localized: "ui.common.none")
        let semesterName = semesterSel?.displayTitle ?? String(localized: "ui.common.none")
        let subjects = subjectsInPlanFiltered.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        let lines: [String] = {
            var result: [String] = []
            result.append(String(localized: "ui.planner.progress.report"))
            result.append("\(String(localized: "ui.career.name")): \(careerName)")
            result.append("\(String(localized: "ui.semester.title")): \(semesterName)")
            result.append("\(String(localized: "ui.subject.list")): \(subjects.count)")
            result.append(String(format: String(localized: "ui.subject.grade.estimated"), calculatedSemesterGrade.0))
            result.append("\(String(localized: "ui.career.ects.completed")): \(completedCareerECTS)")
            result.append("")
            result.append(String(localized: "ui.subject.details"))
            for subject in subjects {
                let status = subject.enrollmentStatus.localizedName
                let gradeText = subject.enrollmentStatus == .convalidated
                    ? convalidatedGradeText(subject)
                    : (subject.gradedActivitiesCount > 0 ? String(format: String(localized: "ui.format.grade2f"), subject.weightedFinalGrade) : String(localized: "ui.common.none"))
                result.append("• \(subject.name) (\(subject.credits) ECTS) - \(status) - \(gradeText)")
            }
            return result
        }()

        #if canImport(UIKit)
        let renderer = UIGraphicsPDFRenderer(bounds: CGRect(x: 0, y: 0, width: 595, height: 842))
        return renderer.pdfData { context in
            context.beginPage()
            let paragraph = NSMutableParagraphStyle()
            paragraph.lineSpacing = 4
            let attributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 12),
                .paragraphStyle: paragraph
            ]
            let text = lines.joined(separator: "\n")
            text.draw(in: CGRect(x: 40, y: 40, width: 515, height: 760), withAttributes: attributes)
        }
        #else
        return Data(lines.joined(separator: "\n").utf8)
        #endif
    }

/// Builds monthly summary pdfdata.
    private func generateMonthlySummaryPDFData() -> Data {
        let calendar = Calendar.current
        let now = Date()
        let thisMonth = calendar.component(.month, from: now)
        let thisYear = calendar.component(.year, from: now)

        let monthlyFocus = focusSessions.filter {
            calendar.component(.month, from: $0.date) == thisMonth &&
            calendar.component(.year, from: $0.date) == thisYear
        }
        let monthlyLoad = estimatedWeeklyHoursByWeek.values.reduce(0.0, +)
        let monthlyGrade = calculatedSemesterGrade.0

        let lines: [String] = [
            String(localized: "ui.planner.monthly.summary"),
            "\(String(localized: "ui.career.name")): \(careerSel?.name ?? String(localized: "ui.common.none"))",
            "\(String(localized: "ui.common.month")): \(thisMonth)/\(thisYear)",
            "",
            "\(String(localized: "ui.subject.grade.estimated")): \(String(format: "%.2f", monthlyGrade))",
            "\(String(localized: "ui.planner.workload")): \(String(format: "%.1f h", monthlyLoad))",
            "\(String(localized: "ui.common.other")): \(monthlyFocus.count)",
            "\(String(localized: "ui.career.ects.completed")): \(completedCareerECTS)"
        ]

        #if canImport(UIKit)
        let renderer = UIGraphicsPDFRenderer(bounds: CGRect(x: 0, y: 0, width: 595, height: 842))
        return renderer.pdfData { context in
            context.beginPage()
            let attributes: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: 12)
            ]
            lines.joined(separator: "\n").draw(in: CGRect(x: 40, y: 40, width: 515, height: 760), withAttributes: attributes)
        }
        #else
        return Data(lines.joined(separator: "\n").utf8)
        #endif
    }

/// Handles handle import.
    private func handleImport(_ result: Result<[URL], Error>) {
        guard case .success(let urls) = result, let url = urls.first else { return }
        do {
            let data = try Data(contentsOf: url)
            guard let rows = try JSONSerialization.jsonObject(with: data) as? [[String: String]] else {
                importMessage = String(localized: "ui.alert.error")
                isImportMessagePresented = true
                return
            }
            for row in rows {
                guard let name = row["name"], let creditsText = row["credits"], let credits = Int(creditsText) else { continue }
                let subject = Subject(name: name, credits: credits)
                subject.enrollmentStatus = .pending
                subject.career = careerSel ?? careers.first
                subject.semester = semesterSel ?? semesters.first
                context.insert(subject)
            }
            try context.save()
            importMessage = String(localized: "ui.alert.success")
        } catch {
            importMessage = String(localized: "ui.alert.couldNotSave")
        }
        isImportMessagePresented = true
    }

/// Handles schedule weekly reminders.
    private func scheduleWeeklyReminders() {
        guard let semester = semesterSel else { return }
        let center = UNUserNotificationCenter.current()
        center.requestAuthorization(options: [.alert, .sound]) { granted, _ in
            guard granted else { return }
            let activities = subjectsInPlanFiltered.flatMap(\.groups).flatMap(\.activities).filter { $0.deliveryWeek > 0 }
            let calendar = Calendar.current
            for (index, activity) in activities.enumerated() {
                let targetDate = calendar.date(byAdding: .day, value: max(0, (activity.deliveryWeek - 1) * 7), to: semester.startDate) ?? Date()
                var comps = calendar.dateComponents([.year, .month, .day], from: targetDate)
                comps.hour = 9
                comps.minute = 0
                let trigger = UNCalendarNotificationTrigger(dateMatching: comps, repeats: false)
                let content = UNMutableNotificationContent()
                content.title = String(localized: "ui.planner.upcoming")
                content.body = "\(activity.name) · \(String(format: String(localized: "ui.format.week"), activity.deliveryWeek))"
                content.sound = .default
                let req = UNNotificationRequest(identifier: "uoc.activity.\(index).\(activity.name)", content: content, trigger: trigger)
                center.add(req)
            }
        }
    }

/// Handles register daily study check.
    private func registerDailyStudyCheck() {
        let calendar = Calendar.current
        let formatter = ISO8601DateFormatter()
        let today = calendar.startOfDay(for: Date())
        let last = formatter.date(from: studyLastCheckDateRaw).map { calendar.startOfDay(for: $0) }

        if let last, calendar.isDate(last, inSameDayAs: today) {
            return
        } else if let last, let yesterday = calendar.date(byAdding: .day, value: -1, to: today), calendar.isDate(last, inSameDayAs: yesterday) {
            studyStreakCount += 1
        } else {
            studyStreakCount = 1
        }

        studyLastCheckDateRaw = formatter.string(from: today)
    }

/// Handles start focus timer.
    private func startFocusTimer() {
        stopFocusTimer()
        isFocusRunning = true
        focusCancellable = Timer.publish(every: 1, on: .main, in: .common)
            .autoconnect()
            .sink { _ in
                if focusRemainingSeconds > 0 {
                    focusRemainingSeconds -= 1
                } else {
                    completeFocusSession()
                }
            }
    }

/// Handles stop focus timer.
    private func stopFocusTimer() {
        isFocusRunning = false
        focusCancellable?.cancel()
        focusCancellable = nil
    }

/// Handles reset focus timer.
    private func resetFocusTimer() {
        stopFocusTimer()
        focusRemainingSeconds = 25 * 60
    }

/// Handles complete focus session.
    private func completeFocusSession() {
        stopFocusTimer()
        appendFocusSession()
        focusRemainingSeconds = 25 * 60
    }

/// Handles append focus session.
    private func appendFocusSession() {
        let sessions = focusSessions
        let subjectName = subjectsForSelectedCareer.first(where: { $0.persistentModelID == focusSelectedSubjectID })?.name
        let entry = FocusSessionEntry(date: Date(), subjectName: subjectName ?? "General")
        let updated = (sessions + [entry]).suffix(200)
        if let data = try? JSONEncoder().encode(Array(updated)),
           let text = String(data: data, encoding: .utf8) {
            focusSessionsRaw = text
        }
        registerDailyStudyCheck()
    }

/// Initializes selections if needed.
    private func initializeSelectionsIfNeeded() {
        if selectedCareerID == nil, let first = careers.first {
            selectedCareerID = first.persistentModelID
        }
        if selectedSemesterID == nil {
            if let current = semesters.first(where: { $0.contains(Date()) }) {
                selectedSemesterID = current.persistentModelID
            } else {
                selectedSemesterID = semesters.first?.persistentModelID
            }
        }
    }
}

private extension CareerPlannerView {
/// FocusSessionEntry view and UI state container.
    struct FocusSessionEntry: Codable {
        let date: Date
        let subjectName: String
    }

/// DeletedSubjectSnapshot view and UI state container.
    struct DeletedSubjectSnapshot: Codable {
        let name: String
        let credits: Int
        let careerName: String
        let semesterStart: Date
        let deletedAt: Date
    }

/// DeletedCareerSnapshot view and UI state container.
    struct DeletedCareerSnapshot: Codable {
        let name: String
        let ectsGoal: Int
        let deletedAt: Date
    }

    typealias ObjectiveState = (description: String, achieved: Bool)
    typealias ComparisonSemesterRow = (semesterID: PersistentIdentifier, title: String, averageGrade: Double, weeklyLoad: Double, completedECTS: Int)
    typealias MilestoneRow = (week: Int, color: Color, summary: String)
    typealias StressWeekRow = (week: Int, score: Double, level: String, color: Color, summary: String)
    typealias AnnualComparisonRow = (semesterID: PersistentIdentifier, title: String, averageGrade: Double, weeklyLoad: Double, completedECTS: Int)

    var careerSel: Career? {
        guard let id = selectedCareerID else { return careers.first }
        return careers.first(where: { $0.persistentModelID == id }) ?? careers.first
    }

    var semesterSel: Semester? {
        guard let id = selectedSemesterID else { return semesters.first }
        return semesters.first(where: { $0.persistentModelID == id }) ?? semesters.first
    }

    private var subjectsForSelectedCareer: [Subject] {
        guard let careerID = selectedCareerID ?? careers.first?.persistentModelID else { return [] }
        return subjects.filter { $0.career?.persistentModelID == careerID }
    }

    private var subjectCountBySemesterIDForSelectedCareer: [PersistentIdentifier: Int] {
        var map: [PersistentIdentifier: Int] = [:]
        for subject in subjectsForSelectedCareer {
            guard let semesterID = subject.semester?.persistentModelID else { continue }
            map[semesterID, default: 0] += 1
        }
        return map
    }

    private var estimatedActivitiesInPlan: [Activity] {
        subjectsInPlanFiltered
            .filter { $0.enrollmentStatus != .convalidated }
            .flatMap { $0.groups }
            .flatMap { $0.activities }
    }

    private var careerLearningObjectives: [String] {
        let objectives = subjectsForSelectedCareer
            .flatMap(\.objectives)
            .filter(\.isAchieved)
            .map { $0.description.trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
        return Array(Set(objectives)).sorted()
    }

    private var semesterObjectives: [ObjectiveState] {
        var map: [String: Bool] = [:]
        for goal in subjectsInPlanFiltered.flatMap(\.objectives) {
            let key = goal.description.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !key.isEmpty else { continue }
            map[key] = (map[key] ?? false) || goal.isAchieved
        }
        return map
            .map { (description: $0.key, achieved: $0.value) }
            .sorted { $0.description.localizedCaseInsensitiveCompare($1.description) == .orderedAscending }
    }

    private var completedCareerECTS: Int {
        subjectsForSelectedCareer.reduce(0) { partial, subject in
            if subject.enrollmentStatus == .convalidated || subject.academicStatus == .passed {
                return partial + subject.credits
            }
            return partial
        }
    }

    private var estimatedWeeklyHoursByWeek: [Int: Double] {
        var map: [Int: Double] = [:]
        for activity in estimatedActivitiesInPlan {
            guard activity.deliveryWeek > 0, activity.estimatedHours > 0 else { continue }
            map[activity.deliveryWeek, default: 0.0] += activity.estimatedHours
        }
        return map
    }

    private var averageEstimatedWeeklyHoursInPlan: Double {
        let total = estimatedWeeklyHoursByWeek.values.reduce(0.0, +)
        if total > 0 {
            // MVP: average over a 15-week semester.
            return total / 15.0
        }
        // Fallback to the manual per-subject estimate (kept from the current MVP).
        return subjectsInPlanFiltered.reduce(0.0) { $0 + $1.estimatedWeeklyHours }
    }

    private var isWeeklyOverload: Bool {
        averageEstimatedWeeklyHoursInPlan > weeklyLoadAlertThreshold
    }

    private var overloadMoveSuggestion: (fromWeek: Int, toWeek: Int)? {
        let buckets = estimatedWeeklyHoursByWeek
        guard !buckets.isEmpty else { return nil }
        guard let from = buckets.max(by: { $0.value < $1.value })?.key,
              let to = buckets.min(by: { $0.value < $1.value })?.key,
              from != to else { return nil }
        return (fromWeek: from, toWeek: to)
    }

    private var weeklyGoals: [String] {
        weeklyGoalsRaw
            .split(separator: "\n")
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
    }

    private var focusSessions: [FocusSessionEntry] {
        guard let data = focusSessionsRaw.data(using: .utf8),
              let decoded = try? JSONDecoder().decode([FocusSessionEntry].self, from: data) else { return [] }
        return decoded
    }

    private var todayFocusSessionsCount: Int {
        let calendar = Calendar.current
        return focusSessions.filter { calendar.isDateInToday($0.date) }.count
    }

    private var focusTimeText: String {
        let min = focusRemainingSeconds / 60
        let sec = focusRemainingSeconds % 60
        return String(format: "%02d:%02d", min, sec)
    }

    private var currentWeekKey: String {
        let comps = Calendar.current.dateComponents([.yearForWeekOfYear, .weekOfYear], from: Date())
        return "\(comps.yearForWeekOfYear ?? 0)-\(comps.weekOfYear ?? 0)"
    }

    private var doneGoalKeys: Set<String> {
        guard let data = weeklyGoalDoneKeysRaw.data(using: .utf8),
              let array = try? JSONDecoder().decode([String].self, from: data) else { return [] }
        return Set(array)
    }

/// Handles goal done key.
    private func goalDoneKey(for goal: String) -> String {
        "\(currentWeekKey)|\(goal)"
    }

/// Returns whether goal done.
    private func isGoalDone(_ goal: String) -> Bool {
        doneGoalKeys.contains(goalDoneKey(for: goal))
    }

/// Handles set goal done.
    private func setGoalDone(_ goal: String, _ done: Bool) {
        var keys = doneGoalKeys
        let key = goalDoneKey(for: goal)
        if done {
            keys.insert(key)
        } else {
            keys.remove(key)
        }
        if let data = try? JSONEncoder().encode(Array(keys).sorted()),
           let text = String(data: data, encoding: .utf8) {
            weeklyGoalDoneKeysRaw = text
        }
    }

/// Handles add weekly goal.
    private func addWeeklyGoal() {
        let trimmed = newWeeklyGoal.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        let goals = weeklyGoals
        guard !goals.contains(trimmed) else {
            newWeeklyGoal = ""
            return
        }
        weeklyGoalsRaw = (goals + [trimmed]).joined(separator: "\n")
        newWeeklyGoal = ""
    }

/// Handles remove weekly goal.
    private func removeWeeklyGoal(_ goal: String) {
        let updated = weeklyGoals.filter { $0 != goal }
        weeklyGoalsRaw = updated.joined(separator: "\n")
        var keys = doneGoalKeys
        keys.remove(goalDoneKey(for: goal))
        if let data = try? JSONEncoder().encode(Array(keys).sorted()),
           let text = String(data: data, encoding: .utf8) {
            weeklyGoalDoneKeysRaw = text
        }
    }

    private var currentSemesterWeek: Int {
        guard let start = semesterSel?.startDate else { return 1 }
        let days = Calendar.current.dateComponents([.day], from: start, to: Date()).day ?? 0
        return max(1, (days / 7) + 1)
    }

    private var comparisonRowsBySemester: [ComparisonSemesterRow] {
        let grouped = Dictionary(grouping: subjectsForSelectedCareer) { $0.semester?.persistentModelID }
        let sortedSemesters = semesters.sorted { $0.startDate < $1.startDate }
        return sortedSemesters.compactMap { semester in
            guard let subjects = grouped[Optional(semester.persistentModelID)], !subjects.isEmpty else { return nil }

            let relevant = subjects.filter { $0.enrollmentStatus != .convalidated && $0.gradedActivitiesCount > 0 }
            let credits = relevant.reduce(0.0) { $0 + Double($1.credits) }
            let weighted = relevant.reduce(0.0) { $0 + ($1.weightedFinalGrade * Double($1.credits)) }
            let averageGrade = credits > 0 ? (weighted / credits) : 0.0

            let activities = subjects
                .filter { $0.enrollmentStatus != .convalidated }
                .flatMap(\.groups)
                .flatMap(\.activities)
                .filter { $0.estimatedHours > 0 }
            let totalHours = activities.reduce(0.0) { $0 + $1.estimatedHours }
            let weeklyLoad = totalHours > 0
                ? totalHours / 15.0
                : subjects.reduce(0.0) { $0 + $1.estimatedWeeklyHours }

            let completedECTS = subjects.reduce(0) { partial, subject in
                if subject.enrollmentStatus == .convalidated || subject.academicStatus == .passed {
                    return partial + subject.credits
                }
                return partial
            }

            return (
                semesterID: semester.persistentModelID,
                title: semester.displayTitle,
                averageGrade: averageGrade,
                weeklyLoad: weeklyLoad,
                completedECTS: completedECTS
            )
        }
    }

    private var annualComparisonRows: [AnnualComparisonRow] {
        let calendar = Calendar.current
        let yearAgo = calendar.date(byAdding: .year, value: -1, to: Date()) ?? Date.distantPast
        let relevantSemesters = semesters
            .filter { $0.startDate >= yearAgo && $0.startDate <= Date() }
            .sorted { $0.startDate < $1.startDate }

        var rows: [AnnualComparisonRow] = []
        for semester in relevantSemesters {
            let semesterSubjects = subjectsForSelectedCareer.filter { $0.semester?.persistentModelID == semester.persistentModelID }
            guard !semesterSubjects.isEmpty else { continue }

            let relevant = semesterSubjects.filter { $0.enrollmentStatus != .convalidated && $0.gradedActivitiesCount > 0 }
            let credits = relevant.reduce(0.0) { $0 + Double($1.credits) }
            let weighted = relevant.reduce(0.0) { $0 + ($1.weightedFinalGrade * Double($1.credits)) }
            let averageGrade = credits > 0 ? (weighted / credits) : 0.0

            let totalHoursActivities = semesterSubjects
                .filter { $0.enrollmentStatus != .convalidated }
                .flatMap(\.groups)
                .flatMap(\.activities)
                .filter { $0.estimatedHours > 0 }
                .reduce(0.0) { $0 + $1.estimatedHours }

            let weeklyLoad: Double = {
                if totalHoursActivities > 0 {
                    return totalHoursActivities / 15.0
                }
                return semesterSubjects.reduce(0.0) { $0 + $1.estimatedWeeklyHours }
            }()

            let completedECTS = semesterSubjects.reduce(0) { partial, subject in
                if subject.enrollmentStatus == .convalidated || subject.academicStatus == .passed {
                    return partial + subject.credits
                }
                return partial
            }

            rows.append(
                AnnualComparisonRow(
                    semesterID: semester.persistentModelID,
                    title: semester.displayTitle,
                    averageGrade: averageGrade,
                    weeklyLoad: weeklyLoad,
                    completedECTS: completedECTS
                )
            )
        }
        return rows
    }

    private var milestoneRows: [MilestoneRow] {
        let buckets = estimatedWeeklyHoursByWeek
        let weeks = buckets.keys.sorted()
        return weeks.map { week in
            let hours = buckets[week] ?? 0
            let color: Color
            if hours >= 12 {
                color = .red
            } else if hours >= 6 {
                color = .orange
            } else {
                color = .green
            }
            let activityCount = estimatedActivitiesInPlan.filter { $0.deliveryWeek == week }.count
            let summary = "\(activityCount) \(String(localized: "ui.subject.activity"))(es) · \(String(format: String(localized: "ui.format.hours"), hours))"
            return (week: week, color: color, summary: summary)
        }
    }

    private var stressPredictionRows: [StressWeekRow] {
        let buckets = estimatedWeeklyHoursByWeek
        let weeks = buckets.keys.sorted()
        guard !weeks.isEmpty else { return [] }
        return weeks.map { week in
            let hours = buckets[week] ?? 0
            let activities = estimatedActivitiesInPlan.filter { $0.deliveryWeek == week }.count
            let focusPenalty = weekFocusSessionsCount(week) == 0 ? 2.0 : 0.0
            let score = hours + (Double(activities) * 1.5) + focusPenalty
            let level: String
            let color: Color
            if score >= 12 {
                level = String(localized: "ui.common.high")
                color = .red
            } else if score >= 7 {
                level = String(localized: "ui.common.medium")
                color = .orange
            } else {
                level = String(localized: "ui.common.low")
                color = .green
            }
            let summary = "\(activities) \(String(localized: "ui.subject.activity"))(ies) · \(String(format: String(localized: "ui.format.hours"), hours)) · focus \(weekFocusSessionsCount(week))"
            return (week: week, score: score, level: level, color: color, summary: summary)
        }
        .sorted { $0.score > $1.score }
        .prefix(3)
        .map { $0 }
    }

/// Handles week focus sessions count.
    private func weekFocusSessionsCount(_ week: Int) -> Int {
        guard let semester = semesterSel else { return 0 }
        let start = Calendar.current.date(byAdding: .day, value: max(0, (week - 1) * 7), to: semester.startDate) ?? semester.startDate
        let end = Calendar.current.date(byAdding: .day, value: 6, to: start) ?? start
        return focusSessions.filter { $0.date >= start && $0.date <= end }.count
    }

    private var riskSubjectsForExamMode: [Subject] {
        subjectsInPlanFiltered.filter { $0.evaluationProgress > 0 && $0.weightedFinalGrade < 5.0 }
    }

    private var upcomingActivitiesForExamMode: [Activity] {
        estimatedActivitiesInPlan
            .filter { $0.deliveryWeek > 0 && $0.deliveryWeek >= currentSemesterWeek && $0.deliveryWeek <= (currentSemesterWeek + 2) }
            .sorted { $0.deliveryWeek < $1.deliveryWeek }
    }

    private var dailyAgendaPriorities: [String] {
        var items: [String] = []
        if let firstUpcoming = upcomingActivitiesForExamMode.first {
            items.append("\(String(localized: "ui.planner.upcoming")): \(firstUpcoming.name) (\(String(format: String(localized: "ui.format.week"), firstUpcoming.deliveryWeek)))")
        }
        if let risk = riskSubjectsForExamMode.first {
            items.append("\(String(localized: "ui.career.metrics.atRisk")): \(risk.name)")
        }
        if let pendingGoal = weeklyGoals.first(where: { !isGoalDone($0) }) {
            items.append("\(String(localized: "ui.planner.weeklyGoals")): \(pendingGoal)")
        }
        if items.isEmpty {
            items = [
                String(localized: "ui.career.planner.title"),
                String(localized: "ui.subject.status.pending"),
                String(localized: "ui.planner.agenda")
            ]
        }
        return Array(items.prefix(3))
    }

    private var inactiveSubjects: [Subject] {
        let cutoff = Calendar.current.date(byAdding: .day, value: -21, to: Date()) ?? Date()
        return subjectsForSelectedCareer.filter { subject in
            guard subject.enrollmentStatus == .enrolled || subject.enrollmentStatus == .pending else { return false }
            let hasNoGrades = subject.gradedActivitiesCount == 0
            let hasNoPlannedActivities = subject.groups.flatMap(\.activities).allSatisfy { $0.deliveryWeek == 0 }
            let oldEnrollment = subject.enrollmentDate < cutoff
            return oldEnrollment && (hasNoGrades || hasNoPlannedActivities)
        }
    }

    private var pendingECTSForCareer: Int {
        guard let target = careerSel?.ectsGoal, target > 0 else { return 0 }
        return max(0, target - completedCareerECTS)
    }

    private var finalReviewPriorities: [(subject: Subject, impactScore: Double)] {
        subjectsForSelectedCareer
            .filter { $0.enrollmentStatus != .convalidated }
            .map { subject in
                let creditWeight = Double(subject.credits)
                let gradeRisk = max(0.0, 5.0 - subject.weightedFinalGrade)
                let pendingWork = 1.0 - subject.evaluationProgress
                let score = (creditWeight * 0.6) + (gradeRisk * 1.8) + (pendingWork * 2.0)
                return (subject: subject, impactScore: score)
            }
            .sorted { $0.impactScore > $1.impactScore }
            .prefix(5)
            .map { $0 }
    }

    private var riskRadarRows: [(subject: Subject, score: Double)] {
        subjectsInPlanFiltered
            .map { subject in
                let gradeRisk = max(0.0, 5.0 - subject.weightedFinalGrade) * 2.2
                let progressRisk = (1.0 - subject.evaluationProgress) * 3.0
                let upcomingCount = subject.groups
                    .flatMap(\.activities)
                    .filter { $0.deliveryWeek > 0 && $0.deliveryWeek <= (currentSemesterWeek + 2) && $0.deliveryWeek >= currentSemesterWeek }
                    .count
                let deliveryRisk = Double(upcomingCount) * 1.4
                let total = gradeRisk + progressRisk + deliveryRisk
                return (subject: subject, score: total)
            }
            .sorted { $0.score > $1.score }
    }

    private var closingChecklist: [String] {
        var items: [String] = []
        let pendingGrades = subjectsInPlanFiltered.filter { $0.gradedActivitiesCount < $0.groups.reduce(0) { $0 + $1.activities.count } }.count
        let unconqueredGoals = subjectsInPlanFiltered
            .flatMap(\.objectives)
            .filter { !$0.isAchieved }
            .count
        let totalCost = subjectsInPlanFiltered.reduce(0.0) { $0 + $1.attemptTotalCost }

        items.append("\(String(localized: "ui.subject.status.pending")): \(pendingGrades)")
        items.append("\(String(localized: "ui.form.objectives")): \(unconqueredGoals)")
        items.append("\(String(localized: "ui.finance.total")): \(String(format: "%.2f", totalCost))")
        if pendingGrades == 0 { items.append(String(localized: "ui.common.done")) }
        if unconqueredGoals == 0 { items.append(String(localized: "ui.common.achieved")) }
        return items
    }

    var examsModeSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.subject.status.inProgress"))
                .font(.headline)
            if upcomingActivitiesForExamMode.isEmpty && riskSubjectsForExamMode.isEmpty {
                Text(String(localized: "ui.common.none"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                if !upcomingActivitiesForExamMode.isEmpty {
                    Text(String(localized: "ui.planner.upcoming"))
                        .font(.subheadline)
                    ForEach(upcomingActivitiesForExamMode, id: \.persistentModelID) { activity in
                        Text("\(String(format: String(localized: "ui.format.week"), activity.deliveryWeek)): \(activity.name)")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
                if !riskSubjectsForExamMode.isEmpty {
                    Text(String(localized: "ui.career.metrics.atRisk"))
                        .font(.subheadline)
                    ForEach(riskSubjectsForExamMode, id: \.persistentModelID) { subject in
                        Text(subject.name)
                            .font(.caption)
                            .foregroundColor(.red)
                    }
                }
            }
        }
    }

    var dailyAgendaSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.planner.agenda"))
                .font(.headline)
            ForEach(Array(dailyAgendaPriorities.enumerated()), id: \.offset) { idx, text in
                HStack(alignment: .top, spacing: 6) {
                    Text("\(idx + 1).")
                        .font(.caption)
                        .foregroundColor(.secondary)
                    Text(text)
                        .font(.caption)
                }
            }
        }
    }

    var finalReviewSection: some View {
        let rows = finalReviewPriorities
        return VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.common.summary"))
                .font(.headline)
            if rows.isEmpty {
                Text(String(localized: "ui.common.none"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(rows, id: \.subject.persistentModelID) { row in
                    HStack {
                        Text(row.subject.name)
                            .font(.caption)
                        Spacer()
                        Text(String(format: "impact %.1f", row.impactScore))
                            .font(.caption2)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
    }

    var riskRadarSection: some View {
        let rows = Array(riskRadarRows.prefix(5))
        return VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.career.metrics.atRisk"))
                .font(.headline)
            if rows.isEmpty {
                Text(String(localized: "ui.common.none"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(rows, id: \.subject.persistentModelID) { row in
                    HStack {
                        Text(row.subject.name)
                            .font(.caption)
                        Spacer()
                        Text(String(format: "%.1f", row.score))
                            .font(.caption2)
                            .foregroundColor(row.score >= 8 ? .red : (row.score >= 4 ? .orange : .green))
                    }
                }
            }
        }
    }

    var semesterClosingSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.career.semesterClosing"))
                .font(.headline)
            ForEach(closingChecklist, id: \.self) { item in
                Text(String(format: String(localized: "ui.format.bulletItem"), item))
                    .font(.caption)
            }
        }
    }

    var inactiveSubjectsSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.subject.subjectReactivation"))
                .font(.headline)
            if inactiveSubjects.isEmpty {
                Text(String(localized: "ui.common.none.RecentlyUnattendedSubjects"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(inactiveSubjects, id: \.persistentModelID) { subject in
                    Text(String(format: String(localized: "ui.format.inactiveSubjectHintFormat"), subject.name))
                        .font(.caption)
                        .foregroundColor(.orange)
                }
            }
        }
    }

    var weeklyGoalsSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(String(localized: "ui.planner.weeklyObjectivesAndStreak"))
                .font(.headline)

            HStack {
                Text(String(localized: "ui.planner.studyStreak"))
                Spacer()
                Text(String(format: String(localized: "ui.format.dayCountFormat"), studyStreakCount))
                    .fontWeight(.semibold)
            }

            Button(String(localized: "ui.planner.markTodaySStudy")) {
                registerDailyStudyCheck()
            }
            .buttonStyle(.bordered)

            HStack {
                TextField(String(localized: "ui.planner.newWeeklyGoal"), text: $newWeeklyGoal)
                Button(String(localized: "ui.common.add")) {
                    addWeeklyGoal()
                }
                .disabled(newWeeklyGoal.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }

            if weeklyGoals.isEmpty {
                Text(String(localized: "ui.planner.youHaveNotDefinedWeeklyGoalsYet"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(weeklyGoals, id: \.self) { goal in
                    HStack {
                        Toggle(isOn: Binding(
                            get: { isGoalDone(goal) },
                            set: { setGoalDone(goal, $0) }
                        )) {
                            Text(goal)
                        }
                        Button(role: .destructive) {
                            removeWeeklyGoal(goal)
                        } label: {
                            Image(systemName: "trash")
                        }
                        .buttonStyle(.borderless)
                    }
                }
            }
        }
    }

    var focusModeSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(String(localized: "ui.common.focusMode25Min"))
                .font(.headline)

            Picker(String(localized: "ui.subject.title"), selection: Binding(
                get: { focusSelectedSubjectID },
                set: { focusSelectedSubjectID = $0 }
            )) {
                Text(String(localized: "ui.common.general")).tag(Optional<PersistentIdentifier>.none)

                ForEach(subjectsForSelectedCareer, id: \.persistentModelID) { subject in
                    Text(subject.name).tag(Optional(subject.persistentModelID))
                }
            }
            .pickerStyle(.menu)

            HStack {
                Text(focusTimeText)
                    .font(.title3)
                    .fontWeight(.semibold)
                Spacer()
                Button(isFocusRunning ? String(localized: "ui.common.pause") : String(localized: "ui.common.start")) {
                    if isFocusRunning {
                        stopFocusTimer()
                    } else {
                        startFocusTimer()
                    }
                }
                .buttonStyle(.borderedProminent)
                Button(String(localized: "ui.common.reset")) {
                    resetFocusTimer()
                }
                .buttonStyle(.bordered)
            }

            Text(String(format: String(localized: "ui.format.sessionsTodayFormat"), todayFocusSessionsCount))
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    var stressPredictionSection: some View {
        let rows = stressPredictionRows
        return VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.common.stressWeekPrediction"))
                .font(.headline)
            if rows.isEmpty {
                Text(String(localized: "ui.common.none.tEnoughWorkloadInformationToEstimateStress"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(rows, id: \.week) { row in
                    HStack(alignment: .top, spacing: 8) {
                        Circle()
                            .fill(row.color)
                            .frame(width: 10, height: 10)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(String(format: String(localized: "ui.format.weekLevelFormat"), row.week, row.level))
                                .font(.caption)
                                .fontWeight(.semibold)
                            Text(row.summary)
                                .font(.caption2)
                                .foregroundColor(.secondary)
                        }
                        Spacer()
                        Text(String(format: "%.1f", row.score))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
    }

    private var lastDeletedSubject: DeletedSubjectSnapshot? {
        guard let data = plannerTrashSubjectsJSON.data(using: .utf8),
              let snapshots = try? JSONDecoder().decode([DeletedSubjectSnapshot].self, from: data) else { return nil }
        let maxAge: TimeInterval = 30 * 24 * 60 * 60
        let valid = snapshots.filter { Date().timeIntervalSince($0.deletedAt) <= maxAge }
        return valid.last
    }

    private var lastDeletedCareer: DeletedCareerSnapshot? {
        guard let data = plannerTrashCareersJSON.data(using: .utf8),
              let snapshots = try? JSONDecoder().decode([DeletedCareerSnapshot].self, from: data) else { return nil }
        let maxAge: TimeInterval = 30 * 24 * 60 * 60
        let valid = snapshots.filter { Date().timeIntervalSince($0.deletedAt) <= maxAge }
        return valid.last
    }

/// Handles push deleted subject snapshot.
    private func pushDeletedSubjectSnapshot(_ snapshot: DeletedSubjectSnapshot) {
        let current = (try? JSONDecoder().decode([DeletedSubjectSnapshot].self, from: Data(plannerTrashSubjectsJSON.utf8))) ?? []
        let filtered = current.filter { Date().timeIntervalSince($0.deletedAt) <= 30 * 24 * 60 * 60 }
        let next = (filtered + [snapshot]).suffix(50)
        if let data = try? JSONEncoder().encode(Array(next)), let text = String(data: data, encoding: .utf8) {
            plannerTrashSubjectsJSON = text
        }
    }

/// Handles push deleted career snapshot.
    private func pushDeletedCareerSnapshot(_ snapshot: DeletedCareerSnapshot) {
        let current = (try? JSONDecoder().decode([DeletedCareerSnapshot].self, from: Data(plannerTrashCareersJSON.utf8))) ?? []
        let filtered = current.filter { Date().timeIntervalSince($0.deletedAt) <= 30 * 24 * 60 * 60 }
        let next = (filtered + [snapshot]).suffix(50)
        if let data = try? JSONEncoder().encode(Array(next)), let text = String(data: data, encoding: .utf8) {
            plannerTrashCareersJSON = text
        }
    }

/// Handles pop last subject snapshot.
    private func popLastSubjectSnapshot() -> DeletedSubjectSnapshot? {
        let current = (try? JSONDecoder().decode([DeletedSubjectSnapshot].self, from: Data(plannerTrashSubjectsJSON.utf8))) ?? []
        guard !current.isEmpty else { return nil }
        var mutable = current
        let popped = mutable.removeLast()
        if let data = try? JSONEncoder().encode(mutable), let text = String(data: data, encoding: .utf8) {
            plannerTrashSubjectsJSON = text
        }
        return popped
    }

/// Handles pop last career snapshot.
    private func popLastCareerSnapshot() -> DeletedCareerSnapshot? {
        let current = (try? JSONDecoder().decode([DeletedCareerSnapshot].self, from: Data(plannerTrashCareersJSON.utf8))) ?? []
        guard !current.isEmpty else { return nil }
        var mutable = current
        let popped = mutable.removeLast()
        if let data = try? JSONEncoder().encode(mutable), let text = String(data: data, encoding: .utf8) {
            plannerTrashCareersJSON = text
        }
        return popped
    }

    var weeklyWorkloadSection: some View {
        let buckets = estimatedWeeklyHoursByWeek
        if buckets.isEmpty {
            return AnyView(EmptyView())
        }

        let weeks = buckets.keys.sorted()
        let total = buckets.values.reduce(0.0, +)

        return AnyView(
            VStack(alignment: .leading, spacing: 8) {
                Text(String(localized: "ui.planner.workload"))
                    .font(.headline)

                Text(String(format: String(localized: "ui.format.totalPlannedHoursFormat"), total))
                    .font(.subheadline)
                    .foregroundColor(.secondary)

                Button(String(localized: "ui.common.scheduleLocalReminders")) {
                    scheduleWeeklyReminders()
                }
                .buttonStyle(.bordered)

                ForEach(weeks, id: \.self) { week in
                    let hours = buckets[week] ?? 0.0
                    if hours > 0 {
                        HStack {
                            Text(String(format: String(localized: "ui.format.weekNumberFormat"), week))
                                .foregroundColor(.secondary)
                            Spacer()
                            Text(String(format: "%.1f h", hours))
                                .fontWeight(.semibold)
                        }
                    }
                }
            }
        )
    }

    var filters: some View {
        VStack(alignment: .leading, spacing: 8) {
            Picker(String(localized: "ui.common.quickFilter"), selection: $quickStatusFilter) {
                ForEach(QuickStatusFilter.allCases) { filter in
                    Text(filter.localizedName).tag(filter)
                }
            }
            .pickerStyle(.segmented)

            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Text(String(localized: "ui.alert.weeklyWorkloadAlertThreshold"))
                    Spacer()
                    Text(String(format: "%.1f h", weeklyLoadAlertThreshold))
                        .fontWeight(.semibold)
                }
                Slider(value: $weeklyLoadAlertThreshold, in: 4...30, step: 0.5)
            }

            Picker(String(localized: "ui.career.name"), selection: Binding(
                get: { selectedCareerID ?? careers.first?.persistentModelID },
                set: { selectedCareerID = $0 }
            )) {
                ForEach(careers) { career in
                    Text(career.name).tag(Optional(career.persistentModelID))
                }
            }

            .pickerStyle(.menu)

            Picker(String(localized: "ui.semester.title"), selection: Binding(
                get: { selectedSemesterID ?? semesters.first?.persistentModelID },
                set: { selectedSemesterID = $0 }
            )) {
                ForEach(semesters) { semester in
                    Text(semester.displayTitle).tag(Optional(semester.persistentModelID))
                }
            }
            .pickerStyle(.menu)
        }
    }

    var summary: some View {
        let delPlan = subjectsInPlanFiltered
        let (grade, relevantSubjects) = calculatedSemesterGrade
        let careerPlan = subjectsForSelectedCareer
        let ectsTarget = careerSel?.ectsGoal ?? 0

        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(String(localized: "ui.subject.list"))
                    .foregroundColor(.secondary)
                Spacer()
                Text("\(delPlan.count)")
                    .fontWeight(.semibold)
            }

            HStack {
                Text(String(localized: "ui.subject.grade.semesterGradeExclConvalidated"))
                    .foregroundColor(.secondary)
                Spacer()
                Text(String(format: "%.2f", grade))
                    .fontWeight(.semibold)
                    .foregroundColor(grade >= 5 ? .green : .orange)
            }

            HStack {
                Text(String(localized: "ui.common.hoursWeek"))
                    .foregroundColor(.secondary)
                Spacer()
                Text(String(format: "%.1f", averageEstimatedWeeklyHoursInPlan))
                    .fontWeight(.semibold)
                    .foregroundColor(isWeeklyOverload ? .red : .primary)
            }

            HStack {
                Text(String(localized: "ui.finance.semesterCost"))
                    .foregroundColor(.secondary)
                Spacer()
                Text(String(format: "%.2f", delPlan.reduce(0.0) { $0 + $1.attemptTotalCost }))
                    .fontWeight(.semibold)
            }

            HStack {
                Text(String(localized: "ui.finance.summary.total"))
                    .foregroundColor(.secondary)
                Spacer()
                Text(String(format: "%.2f", careerPlan.reduce(0.0) { $0 + $1.attemptTotalCost }))
                    .fontWeight(.semibold)
            }

            if ectsTarget > 0 {
                HStack {
                    Text(String(localized: "ui.career.ects.completed"))
                        .foregroundColor(.secondary)
                    Spacer()
                    Text("\(completedCareerECTS)/\(ectsTarget)")
                        .fontWeight(.semibold)
                }
            }

            if !relevantSubjects.isEmpty {
                Text(String(format: String(localized: "ui.format.includesSubjectsWithAssessmentFormat"), relevantSubjects.count))
                    .font(.caption)
                    .foregroundColor(.secondary)
            }

            if isWeeklyOverload {
                Label(
                    String(format: String(localized: "ui.format.alertEstimatedWorkload1fHWeekExceedsTheThreshold1fH"), averageEstimatedWeeklyHoursInPlan, weeklyLoadAlertThreshold),
                    systemImage: "exclamationmark.triangle.fill"
                )
                .font(.caption)
                .foregroundColor(.red)

                if let suggestion = overloadMoveSuggestion {
                    Text(String(format: String(localized: "ui.format.moveDeliverySuggestionFormat"), suggestion.fromWeek, suggestion.toWeek))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    var learningObjectivesSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.form.objectives"))
                .font(.headline)

            if careerLearningObjectives.isEmpty {
                Text(String(localized: "ui.common.none.ObjectivesAchievedInThisCareerYet"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(careerLearningObjectives, id: \.self) { goal in
                    Label(goal, systemImage: "checkmark.seal")
                        .font(.caption)
                }
            }
        }
    }

    var semesterObjectivesSection: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.career.objectivesBySemester"))
                .font(.headline)

            if semesterObjectives.isEmpty {
                Text(String(localized: "ui.common.none.ObjectivesDefinedForThisSemester"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(semesterObjectives, id: \.description) { item in
                    Label(item.description, systemImage: item.achieved ? "checkmark.circle.fill" : "circle")
                        .font(.caption)
                        .foregroundColor(item.achieved ? .green : .secondary)
                }
            }
        }
    }

    var subjectListSection: some View {
        let subjectsInPlan = subjectsInPlanFiltered.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }

        return Group {
            if subjectsInPlan.isEmpty {
                ContentUnavailableView(
                    String(localized: "ui.common.none"),
                    systemImage: "text.book.closed",
                    description: Text(String(localized: "ui.common.add.ASubjectUsingTheButton"))
                )
            } else {
                ForEach(subjectsInPlan, id: \.persistentModelID) { subject in
                    NavigationLink(destination: SubjectDetailView(subject: subject)) {
                        HStack(alignment: .top, spacing: 12) {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(subject.name)
                                    .font(.headline)

                                Text(String(format: String(localized: "ui.format.attemptNumberFormat"), attemptNumber(subject)))
                                    .font(.caption)
                                    .foregroundColor(.secondary)

                                HStack(spacing: 8) {
                                    Text(subjectStatusDisplayText(subject))
                                        .font(.caption)
                                        .fontWeight(.semibold)
                                        .foregroundColor(subjectStatusColor(subject))

                                    if subject.enrollmentStatus == .convalidated {
                                        Text(convalidatedGradeText(subject))
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    } else if subject.gradedActivitiesCount > 0 {
                                        Text(String(format: String(localized: "ui.format.grade2f"), subject.weightedFinalGrade))
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    } else {
                                        Text(String(localized: "ui.subject.status.pending"))
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }

                            Spacer()
                        }
                    }
                    .contextMenu {
                        Button {
                            selectedSubject = subject
                            isPlanSheetPresented = true
                        } label: {
                            Label(String(localized: "ui.common.plan"), systemImage: "calendar")
                        }
                        Button {
                            duplicateSubject(subject)
                        } label: {
                            Label(String(localized: "ui.common.duplicateAttempt"), systemImage: "doc.on.doc")
                        }
                        Button(role: .destructive) {
                            deleteSubject(subject)
                        } label: {
                            Label(String(localized: "ui.common.delete"), systemImage: "trash")
                        }
                    }
                }
            }
        }
    }

    var subjectsInPlanFiltered: [Subject] {
        guard let semesterID = selectedSemesterID ?? semesters.first?.persistentModelID else { return [] }
        let base = subjectsForSelectedCareer.filter { $0.semester?.persistentModelID == semesterID }
        switch quickStatusFilter {
        case .all:
            return base
        case .enrolled:
            return base.filter { $0.enrollmentStatus == .enrolled }
        case .convalidated:
            return base.filter { $0.enrollmentStatus == .convalidated }
        case .pending:
            return base.filter { $0.enrollmentStatus == .pending }
        case .completed:
            return base.filter { $0.enrollmentStatus != .convalidated && $0.academicStatus != .inProgress }
        }
    }

    var ectsSimulationSection: some View {
        let pendingCredits = subjectsInPlanFiltered
            .filter { $0.enrollmentStatus == .pending || $0.enrollmentStatus == .enrolled }
            .reduce(0) { $0 + $1.credits }
        let projectedGain = Int((Double(pendingCredits) * ectsSimulationRatio / 100.0).rounded())
        let projectedTotal = completedCareerECTS + projectedGain

        return VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.common.ectsSimulation"))
                .font(.headline)
            HStack {
                Text(String(localized: "ui.subject.expectedPassRate"))
                Spacer()
                Text("\(Int(ectsSimulationRatio))%")
            }
            Slider(value: $ectsSimulationRatio, in: 0...100, step: 5)
            Text(String(format: String(localized: "ui.format.projectedECTSFormat"), projectedTotal))
                .font(.caption)
                .foregroundColor(.secondary)
        }
    }

    var semesterComparisonSection: some View {
        let rows = comparisonRowsBySemester
        return VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.career.semesterComparison"))
                .font(.headline)

            if rows.isEmpty {
                Text(String(localized: "ui.common.none.tEnoughDataToCompareSemesters"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(rows, id: \.semesterID) { row in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(row.title)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                        HStack {
                            Text(String(localized: "ui.subject.grade.estimated"))
                            Spacer()
                            Text(String(format: "%.2f", row.averageGrade))
                                .foregroundColor(row.averageGrade >= 5 ? .green : .orange)
                        }
                        .font(.caption)
                        HStack {
                            Text(String(localized: "ui.common.loadHWeek"))
                            Spacer()
                            Text(String(format: "%.1f", row.weeklyLoad))
                        }
                        .font(.caption)
                        HStack {
                            Text(String(localized: "ui.career.ects.completed"))
                            Spacer()
                            Text("\(row.completedECTS)")
                        }
                        .font(.caption)
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }

    var annualReportSection: some View {
        let rows = annualComparisonRows
        return VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.planner.annualReport"))
                .font(.headline)

            if rows.count < 2 {
                Text(String(localized: "ui.career.atLeast2SemestersLastYearWithDataAreNeededToShowTrend"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else if let first = rows.first, let last = rows.last {
                let deltaNota = last.averageGrade - first.averageGrade
                let deltaColor: Color = deltaNota >= 0 ? .green : .orange

                HStack {
                    Text(String(localized: "ui.subject.grade.tendenciaGrade"))
                    Spacer()
                    Text(deltaNota, format: .number.sign(strategy: .always(includingZero: false)).precision(.fractionLength(2)))
                        .fontWeight(.semibold)
                        .foregroundColor(deltaColor)
                }
                .font(.caption)

                ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                    let prev = index > 0 ? rows[index - 1] : nil
                    let delta = prev != nil ? row.averageGrade - prev!.averageGrade : 0.0

                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            Text(row.title)
                                .font(.subheadline)
                                .fontWeight(.semibold)
                            Spacer()
                            Text(String(format: "%.2f", row.averageGrade))
                                .foregroundColor(row.averageGrade >= 5 ? .green : .orange)
                        }
                        .font(.caption)

                        HStack {
                                Text(String(localized: "ui.common.loadHWeek"))
                            Spacer()
                            Text(String(format: "%.1f", row.weeklyLoad))
                        }
                        .font(.caption2)

                        HStack {
                            Text(String(localized: "ui.career.ects.completed"))
                            Spacer()
                            Text("\(row.completedECTS)")
                        }
                        .font(.caption2)

                        if let prev {
                            HStack {
                                Text(String(localized: "ui.subject.gradeVsPrevious"))
                                Spacer()
                                Text(delta, format: .number.sign(strategy: .always(includingZero: false)).precision(.fractionLength(2)))
                                    .foregroundColor(delta >= 0 ? .green : .orange)
                            }
                            .font(.caption2)
                        }
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }

    var trafficLightMilestonesSection: some View {
        let milestones = milestoneRows
        return VStack(alignment: .leading, spacing: 6) {
            Text(String(localized: "ui.planner.semesterMilestones"))
                .font(.headline)

            if milestones.isEmpty {
                Text(String(localized: "ui.common.none.MilestonesPlannedForThisSemester"))
                    .font(.caption)
                    .foregroundColor(.secondary)
            } else {
                ForEach(milestones, id: \.week) { row in
                    HStack {
                        Circle()
                            .fill(row.color)
                            .frame(width: 10, height: 10)
                        Text(String(format: String(localized: "ui.format.weekNumberFormat"), row.week))
                            .font(.caption)
                        Spacer()
                        Text(row.summary)
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }
            }
        }
    }

    private var calculatedSemesterGrade: (Double, [Subject]) {
        let relevant = subjectsInPlanFiltered.filter { $0.enrollmentStatus != .convalidated && $0.gradedActivitiesCount > 0 }
        let totalCredits = relevant.reduce(0.0) { $0 + Double($1.credits) }
        guard totalCredits > 0 else { return (0.0, []) }

        let weightedSum = relevant.reduce(0.0) { partial, subject in
            partial + (subject.weightedFinalGrade * Double(subject.credits))
        }
        return (weightedSum / totalCredits, relevant)
    }

/// Handles enrollment status color.
    private func enrollmentStatusColor(_ status: EnrollmentStatus) -> Color {
        switch status {
        case .enrolled: return .orange
        case .convalidated: return .gray
        case .pending: return .blue
        case .completed: return .green
        }
    }

/// Handles subject status display text.
    private func subjectStatusDisplayText(_ subject: Subject) -> String {
        if subject.enrollmentStatus == .convalidated {
            return subject.enrollmentStatus.localizedName
        }
        if subject.academicStatus != .inProgress {
            return String(localized: "ui.common.completed")
        }
        return subject.enrollmentStatus.localizedName
    }

/// Handles subject status color.
    private func subjectStatusColor(_ subject: Subject) -> Color {
        if subject.enrollmentStatus == .convalidated {
            return .gray
        }
        switch subject.academicStatus {
        case .inProgress:
            return enrollmentStatusColor(subject.enrollmentStatus)
        case .passed:
            return .green
        case .failed:
            return .red
        }
    }

/// Handles convalidated grade text.
    private func convalidatedGradeText(_ subject: Subject) -> String {
        guard let grade = subject.convalidatedGrade else { return String(localized: "ui.subject.status.convalidated") }
        return String(format: "\(String(localized: "ui.subject.status.convalidated")) \(String(localized: "ui.format.grade2f"))", grade)
    }

/// Handles attempt number.
    private func attemptNumber(_ subject: Subject) -> Int {
        guard selectedCareerID != nil else { return 1 }
        let allAttempts = subjectsForSelectedCareer
            .filter { $0.name == subject.name && $0.credits == subject.credits }
            .sorted { $0.enrollmentDate < $1.enrollmentDate }
        guard let index = allAttempts.firstIndex(where: { $0.persistentModelID == subject.persistentModelID }) else { return 1 }
        return index + 1
    }
}

/// PlannerPDFDocument view and UI state container.
struct PlannerPDFDocument: FileDocument {
    static var readableContentTypes: [UTType] { [.pdf] }

    var data: Data

    init(data: Data) {
        self.data = data
    }

    init(configuration: ReadConfiguration) throws {
        self.data = configuration.file.regularFileContents ?? Data()
    }

/// Handles file wrapper.
    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: data)
    }
}

/// SemesterEditorView view and UI state container.
struct SemesterEditorView: View {
/// SemesterType options used by planner features.
    enum SemesterType: String, CaseIterable, Identifiable {
        case s1 = "S1"
        case s2 = "S2"
        var id: String { rawValue }
    }

    @Environment(\.modelContext) private var context
    @Environment(\.dismiss) private var dismiss

    let semesterToEdit: Semester?
    @Binding var selectedSemesterID: PersistentIdentifier?

    @State private var startDate = Date()
    @State private var endDate: Date = Calendar.current.date(byAdding: .month, value: 4, to: Date()) ?? Date()
    @State private var semesterType: SemesterType = .s1

    private var computedLabel: String {
        let year = Calendar.current.component(.year, from: startDate)
        return "\(year)\(semesterType.rawValue)"
    }

    var body: some View {
        NavigationStack {
            Form {
                Section(String(localized: "ui.common.label")) {
                    Text(computedLabel)
                        .font(.headline)
                }

                Section(String(localized: "ui.common.rangoDeFechas")) {
                    DatePicker(String(localized: "ui.common.startDate"), selection: $startDate, displayedComponents: .date)
                    DatePicker(
                        String(localized: "ui.common.endDate"),
                        selection: $endDate,
                        in: startDate...(Calendar.current.date(byAdding: .year, value: 20, to: startDate) ?? .distantFuture),
                        displayedComponents: .date
                    )
                }

                Section(String(localized: "ui.semester.title")) {
                    Picker(String(localized: "ui.common.type"), selection: $semesterType) {
                        ForEach(SemesterType.allCases) { t in
                            Text(t.rawValue).tag(t)
                        }
                    }
                    .pickerStyle(.segmented)
                }
            }
            .navigationTitle(semesterToEdit == nil ? String(localized: "ui.career.newSemester") : String(localized: "ui.common.edit.Semester"))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(String(localized: "ui.common.cancel")) { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(String(localized: "ui.common.save")) { save() }
                        .disabled(endDate < startDate)
                }
            }
            .onAppear {
                guard let target = semesterToEdit else { return }
                startDate = target.startDate
                endDate = target.endDate ?? target.estimatedEndDate
                semesterType = target.label.contains("S2") ? .s2 : .s1
            }
        }
    }

/// Handles save.
    private func save() {
        let label = computedLabel
        if let target = semesterToEdit {
            target.label = label
            target.startDate = startDate
            target.endDate = endDate
            selectedSemesterID = target.persistentModelID
            try? context.save()
            dismiss()
        } else {
            let semester = Semester(label: label, startDate: startDate, endDate: endDate)
            context.insert(semester)
            selectedSemesterID = semester.persistentModelID
            try? context.save()
            dismiss()
        }
    }
}

/// PlanSubjectSheet view and UI state container.
struct PlanSubjectSheet: View {
    @Environment(\.modelContext) private var context
    @Environment(\.dismiss) private var dismiss
    @Bindable var subject: Subject

    @Query(sort: \Semester.startDate) private var semesters: [Semester]
    @Query(sort: \Career.name) private var careers: [Career]

    @State private var selectedSemesterID: PersistentIdentifier?
    @State private var selectedCareerID: PersistentIdentifier?
    @State private var enrollmentStatusRaw: String = EnrollmentStatus.enrolled.rawValue
    @State private var convalidatedGradeInput = ""
    @State private var weeklyHoursInput: Double = 0.0
    @State private var pricePerCreditInput: Double = 0.0

    @State private var extraCostCategory: CostCategory = .learningResources
    @State private var extraCostDescription = ""
    @State private var extraCostAmount: Double = 0.0

    var body: some View {
        NavigationStack {
            Form {
                Section(header: Text(String(localized: "ui.career.semesterAndStatus"))) {
                    Picker(String(localized: "ui.career.name"), selection: Binding(
                        get: { selectedCareerID },
                        set: { selectedCareerID = $0 }
                    )) {
                        ForEach(careers) { career in
                            Text(career.name).tag(Optional(career.persistentModelID))
                        }
                    }

                    Picker(String(localized: "ui.semester.title"), selection: Binding(
                        get: { selectedSemesterID },
                        set: { selectedSemesterID = $0 }
                    )) {
                        ForEach(semesters) { semester in
                            Text(semester.label).tag(Optional(semester.persistentModelID))
                        }
                    }

                    Picker(String(localized: "ui.common.status"), selection: $enrollmentStatusRaw) {
                        Text(EnrollmentStatus.enrolled.localizedName).tag(EnrollmentStatus.enrolled.rawValue)
                        Text(EnrollmentStatus.convalidated.localizedName).tag(EnrollmentStatus.convalidated.rawValue)
                        Text(EnrollmentStatus.pending.localizedName).tag(EnrollmentStatus.pending.rawValue)
                    }

                    if enrollmentStatusRaw == EnrollmentStatus.convalidated.rawValue {
                        TextField(String(localized: "ui.subject.grade.convalidatedGrade0To10"), text: $convalidatedGradeInput)
                            .keyboardType(.decimalPad)
                    }
                }

                Section(header: Text(String(localized: "ui.finance.costWorkload"))) {
                    Stepper(String(format: String(localized: "ui.format.hoursPerWeek"), weeklyHoursInput), value: $weeklyHoursInput, in: 0...40, step: 0.5)
                    let currencyCode = Locale.current.currency?.identifier ?? "EUR"
                    LabeledContent(String(localized: "ui.finance.pricePerCredit")) {
                        TextField("0.00", value: $pricePerCreditInput, format: .currency(code: currencyCode))
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                    }
                    Text(String(localized: "ui.finance.thisValueIsUsedToCalculateTheSubjectBaseCost"))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }

                Section(header: Text(String(localized: "ui.finance.otherCostsExtra"))) {
                    if subject.extraCosts.isEmpty {
                        Text(String(localized: "ui.common.none.ExtraCosts"))
                            .foregroundColor(.secondary)
                    } else {
                        ForEach(subject.extraCosts, id: \.persistentModelID) { cost in
                            HStack(alignment: .top) {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(cost.category.localizedName)
                                        .font(.caption)
                                        .fontWeight(.semibold)
                                    Text(cost.description)
                                        .font(.caption)
                                        .foregroundColor(.secondary)
                                    Text(String(format: "%.2f", cost.amount))
                                        .font(.caption)
                                }
                                Spacer()
                                Button {
                                    context.delete(cost)
                                } label: {
                                    Image(systemName: "trash")
                                }
                                .buttonStyle(.borderless)
                            }
                        }
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Picker(String(localized: "ui.common.category"), selection: $extraCostCategory) {
                            ForEach([CostCategory.learningResources, CostCategory.tuition, CostCategory.transport, CostCategory.materials, CostCategory.other], id: \.self) { cat in
                                Text(cat.localizedName).tag(cat)
                            }
                        }
                        TextField(String(localized: "ui.common.description"), text: $extraCostDescription)
                        TextField(String(localized: "ui.common.amount"), value: $extraCostAmount, format: .number)
                            .keyboardType(.decimalPad)

                        Button(String(localized: "ui.common.add.ExtraCost")) {
                            let extraCost = ExtraCost(
                                category: extraCostCategory,
                                description: extraCostDescription.isEmpty ? String(localized: "ui.finance.extraCost") : extraCostDescription,
                                amount: extraCostAmount,
                                date: Date()
                            )
                            extraCost.subject = subject
                            context.insert(extraCost)
                        }
                        .disabled(extraCostAmount <= 0 || extraCostDescription.isEmpty)
                    }
                }
            }
            .navigationTitle(String(localized: "ui.common.plan"))
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(String(localized: "ui.common.cancel")) { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(String(localized: "ui.common.save")) {
                        save()
                    }
                    .disabled(!canSave)
                }
            }
            .onAppear {
                initializeFields()
            }
        }
    }

/// Initializes fields.
    private func initializeFields() {
        selectedSemesterID = subject.semester?.persistentModelID
        selectedCareerID = subject.career?.persistentModelID
        enrollmentStatusRaw = subject.enrollmentStatus.rawValue
        if let grade = subject.convalidatedGrade {
            convalidatedGradeInput = String(format: "%.1f", grade)
        } else {
            convalidatedGradeInput = ""
        }
        weeklyHoursInput = subject.estimatedWeeklyHours
        pricePerCreditInput = subject.pricePerCredit
    }

    private var canSave: Bool {
        if enrollmentStatusRaw == EnrollmentStatus.convalidated.rawValue {
            return Double(convalidatedGradeInput.replacingOccurrences(of: ",", with: ".")) != nil
        }
        return selectedSemesterID != nil
    }

/// Handles save.
    private func save() {
        guard let semesterID = selectedSemesterID,
              let semester = semesters.first(where: { $0.persistentModelID == semesterID }) else { return }

        subject.semester = semester

        if let careerID = selectedCareerID,
           let career = careers.first(where: { $0.persistentModelID == careerID }) {
            subject.career = career
        }

        subject.enrollmentStatus = EnrollmentStatus(rawValue: enrollmentStatusRaw) ?? .enrolled
        subject.estimatedWeeklyHours = weeklyHoursInput
        subject.pricePerCredit = pricePerCreditInput

        if subject.enrollmentStatus == .convalidated {
            let normalized = convalidatedGradeInput.replacingOccurrences(of: ",", with: ".")
            subject.convalidatedGrade = Double(normalized)
            // Convalidated subjects should not keep evaluable workload.
            for group in subject.groups {
                context.delete(group)
            }
            for objective in subject.objectives {
                context.delete(objective)
            }
            subject.groups.removeAll()
            subject.objectives.removeAll()
        } else {
            subject.convalidatedGrade = nil
        }

        try? context.save()
        dismiss()
    }
}

