//
//  AddSubjectView.swift
//  Campus Pilot
//
//  Created by Andrea Osma Rafael on 19/3/26.
//


/// Form to create or edit subjects, evaluation blocks, and objectives.

import SwiftUI
import SwiftData

/// AddSubjectView view and UI state container.
struct AddSubjectView: View {
    @Environment(\.modelContext) private var context
    @Environment(\.dismiss) private var dismiss
    var subjectToEdit: Subject? = nil
    var defaultCareerID: PersistentIdentifier? = nil
    var defaultSemesterID: PersistentIdentifier? = nil

    @Query(sort: \Career.name) private var careers: [Career]
    @Query(sort: \Semester.startDate) private var semesters: [Semester]
    @Query(sort: \SubjectBase.name) private var bases: [SubjectBase]
    
    // --- FORM STATE ---
    @State private var name = ""
    @State private var credits = 6
    @State private var subjectCode = ""
    @State private var selectedCareerID: PersistentIdentifier?
    @State private var selectedSemesterID: PersistentIdentifier?
    @State private var enrollmentStatusRaw: String = EnrollmentStatus.enrolled.rawValue
    @State private var convalidatedGradeInput = ""
    @State private var pricePerCreditInput: Double = 0.0
    
    @State private var tempGroups: [TempGroup] = []
    @State private var tempObjectives: [TempObjective] = []
    @State private var isSaveErrorPresented = false
    @State private var saveErrorMessage = ""
    @State private var didLoadInitialData = false
    @State private var isEvaluationExpanded = true
    @State private var isObjectivesExpanded = true
    
    // Helper to flatten all activities across groups (useful for linking objectives)
    var allActivities: [TempActivity] {
        tempGroups.flatMap { $0.activities }
    }

    private var trimmedName: String {
        name.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    private var groupsHaveBasicData: Bool {
        !tempGroups.isEmpty && tempGroups.allSatisfy { !$0.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }
    }

    private var globalWeightsAreValid: Bool {
        tempGroups.allSatisfy { (0.0...1.0).contains($0.globalWeight) }
    }

    private var totalGlobalWeight: Double {
        tempGroups.reduce(0.0) { $0 + $1.globalWeight }
    }

    private var globalWeightsAreBalanced: Bool {
        abs(totalGlobalWeight - 1.0) < 0.001
    }

    private var internalWeightsAreValid: Bool {
        tempGroups.allSatisfy { group in
            group.activities.allSatisfy { (0.0...1.0).contains($0.weightWithinGroup) }
        }
    }

    private var internalWeightsAreBalanced: Bool {
        tempGroups.allSatisfy { group in
            guard !group.activities.isEmpty else { return true }
            let total = group.activities.reduce(0.0) { $0 + $1.weightWithinGroup }
            return abs(total - 1.0) < 0.001
        }
    }

    private var criticalRuleErrors: [String] {
        var errors: [String] = []
        for group in tempGroups {
            let groupName = group.name.trimmingCharacters(in: .whitespacesAndNewlines)
            let label = groupName.isEmpty ? String(localized: "ui.subject.block") : "\(String(localized: "ui.subject.block")) '\(groupName)'"

            if group.isMandatory && group.activities.isEmpty {
                errors.append("\(label): \(String(localized: "ui.alert.error"))")
            }
        }
        return errors
    }

    private var ruleWarnings: [String] {
        var warnings: [String] = []
        for group in tempGroups {
            let groupName = group.name.trimmingCharacters(in: .whitespacesAndNewlines)
            let label = groupName.isEmpty ? String(localized: "ui.subject.block") : "\(String(localized: "ui.subject.block")) '\(groupName)'"
            let totalActivities = group.activities.count

            if group.hasMaxFails && totalActivities > 0 && group.maxFails >= totalActivities {
                warnings.append("\(label): \(String(localized: "ui.alert.warning"))")
            }

            if group.hasMinimumGrade && !group.isMandatory {
                warnings.append("\(label): \(String(localized: "ui.alert.warning"))")
            }
        }
        return warnings
    }

    private var isFormValid: Bool {
        if enrollmentStatusRaw == EnrollmentStatus.convalidated.rawValue {
            return !trimmedName.isEmpty
        }
        // Basic name check is always required
        guard !trimmedName.isEmpty else { return false }
        
        // If there are groups, they must have names and valid weights
        if !tempGroups.isEmpty {
            return groupsHaveBasicData
                && globalWeightsAreValid
                && internalWeightsAreValid
                && criticalRuleErrors.isEmpty
        }
        
        return true
    }

    private var canSavePlanningFields: Bool {
        if enrollmentStatusRaw == EnrollmentStatus.convalidated.rawValue {
            let normalized = convalidatedGradeInput.replacingOccurrences(of: ",", with: ".")
            return Double(normalized) != nil
        }
        // Allow saving even without career/semester for better UX, 
        // but we keep the check if the user wants to enforce it.
        // For now, let's just make it always true to not block the user.
        return true
    }

    private var formTitle: String {
        subjectToEdit == nil ? String(localized: "ui.subject.new") : String(localized: "ui.subject.edit")
    }
    
    var body: some View {
        NavigationStack {
            Form {
                // 1. GENERAL DATA
                Section(header: Text(String(localized: "ui.form.general"))) {
                    TextField(String(localized: "ui.subject.name"), text: $name)
                    TextField(String(localized: "ui.subject.code"), text: $subjectCode)
                        .textInputAutocapitalization(.characters)
                    Stepper("\(String(localized: "ui.subject.credits")): \(credits)", value: $credits, in: 3...12, step: 3)

                    Picker(String(localized: "ui.career.title"), selection: $selectedCareerID) {
                        Text(String(localized: "ui.common.none")).tag(nil as PersistentIdentifier?)
                        ForEach(careers) { career in
                            Text(career.name).tag(Optional(career.persistentModelID))
                        }
                    }

                    Picker(String(localized: "ui.semester.title"), selection: $selectedSemesterID) {
                        Text(String(localized: "ui.common.none")).tag(nil as PersistentIdentifier?)
                        ForEach(semesters) { semester in
                            Text(semester.displayTitle).tag(Optional(semester.persistentModelID))
                        }
                    }

                    Picker(String(localized: "ui.common.status"), selection: $enrollmentStatusRaw) {
                        Text(EnrollmentStatus.enrolled.localizedName).tag(EnrollmentStatus.enrolled.rawValue)
                        Text(EnrollmentStatus.convalidated.localizedName).tag(EnrollmentStatus.convalidated.rawValue)
                        Text(EnrollmentStatus.pending.localizedName).tag(EnrollmentStatus.pending.rawValue)
                        Text(EnrollmentStatus.completed.localizedName).tag(EnrollmentStatus.completed.rawValue)
                    }

                    if enrollmentStatusRaw == EnrollmentStatus.convalidated.rawValue {
                        TextField(String(localized: "ui.subject.grade.convalidated"), text: $convalidatedGradeInput)
                            .keyboardType(.decimalPad)
                    }

                    let currencyCode = Locale.current.currency?.identifier ?? "EUR"
                    LabeledContent(String(localized: "ui.finance.pricePerCredit")) {
                        TextField("0.00", value: $pricePerCreditInput, format: .currency(code: currencyCode))
                            .keyboardType(.decimalPad)
                            .multilineTextAlignment(.trailing)
                    }
                }
                
                // 2. EVALUATION GROUPS
                if enrollmentStatusRaw != EnrollmentStatus.convalidated.rawValue {
                    Section(header: Text(String(localized: "ui.form.evaluation"))) {
                        VStack(alignment: .leading, spacing: 16) {
                            if !tempGroups.isEmpty {
                                HStack {
                                    Text(String(localized: "ui.common.total"))
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                    Spacer()
                                    Text(String(format: "%.0f%%", totalGlobalWeight * 100))
                                        .fontWeight(.bold)
                                        .foregroundColor(globalWeightsAreBalanced ? .green : .orange)
                                }
                                .padding(.horizontal, 4)
                            }

                            ForEach($tempGroups) { $group in
                                VStack(spacing: 0) {
                                    // Block Header
                                    HStack {
                                        TextField(String(localized: "ui.form.placeholder.block"), text: $group.name)
                                            .font(.headline)
                                        
                                        Spacer()
                                        
                                        Button(action: {
                                            withAnimation {
                                                group.isExpanded.toggle()
                                                ()
                                            }
                                        }) {
                                            Image(systemName: group.isExpanded ? "chevron.up" : "chevron.down")
                                                .foregroundColor(.accentColor)
                                                .padding(8)
                                        }
                                        
                                        Button(role: .destructive, action: {
                                            if let index = tempGroups.firstIndex(where: { $0.id == group.id }) {
                                                withAnimation {
                                                    tempGroups.remove(at: index)
                                                    ()
                                                }
                                            }
                                        }) {
                                            Image(systemName: "trash")
                                                .foregroundColor(.red)
                                                .padding(8)
                                        }
                                        .buttonStyle(.plain)
                                    }
                                    .padding(.vertical, 8)
                                    .padding(.horizontal, 12)
                                    .background(Color(UIColor.secondarySystemBackground))
                                    .cornerRadius(8, corners: group.isExpanded ? [.topLeft, .topRight] : .allCorners)

                                    if group.isExpanded {
                                        VStack(alignment: .leading, spacing: 12) {
                                            // Weight Slider
                                            VStack(alignment: .leading, spacing: 4) {
                                                HStack {
                                                    Text(String(localized: "ui.common.percentage"))
                                                        .font(.caption)
                                                        .foregroundColor(.secondary)
                                                    Spacer()
                                                    Text(String(format: "%.0f%%", group.globalWeight * 100))
                                                        .font(.caption)
                                                        .fontWeight(.bold)
                                                }
                                                Slider(value: Binding(
                                                    get: { group.globalWeight * 100 },
                                                    set: { group.globalWeight = $0 / 100 }
                                                ), in: 0...100, step: 5)
                                            }

                                            // Options Toggles
                                            HStack(spacing: 20) {
                                                Toggle(isOn: $group.isMandatory) {
                                                    Text(String(localized: "ui.common.required"))
                                                        .font(.caption)
                                                }
                                                .toggleStyle(.button)
                                                
                                                Toggle(isOn: $group.hasMinimumGrade) {
                                                    Text(String(localized: "ui.sim.required"))
                                                        .font(.caption)
                                                }
                                                .toggleStyle(.button)
                                            }
                                            
                                            if group.hasMinimumGrade {
                                                HStack {
                                                    Text(String(localized: "ui.sim.required"))
                                                        .font(.caption)
                                                    Spacer()
                                                    Stepper("\(group.minimumGrade, specifier: "%.1f")", value: $group.minimumGrade, in: 0...10, step: 0.5)
                                                        .labelsHidden()
                                                    Text("\(group.minimumGrade, specifier: "%.1f")")
                                                        .font(.caption).monospacedDigit()
                                                }
                                            }

                                            Divider().padding(.vertical, 4)

                                            // Activities
                                            Text(String(localized: "ui.subject.list"))
                                                .font(.caption).bold().foregroundColor(.secondary)
                                            
                                            ForEach($group.activities) { $activity in
                                                VStack(spacing: 10) {
                                                    HStack {
                                                        TextField(String(localized: "ui.form.placeholder.activity"), text: $activity.name)
                                                            .font(.subheadline)
                                                            .fontWeight(.medium)
                                                        
                                                        Spacer()
                                                        
                                                        Button(role: .destructive, action: {
                                                            if let idx = group.activities.firstIndex(where: { $0.id == activity.id }) {
                                                                group.activities.remove(at: idx)
                                                            }
                                                        }) {
                                                            Image(systemName: "minus.circle.fill")
                                                                .foregroundColor(.red.opacity(0.8))
                                                        }
                                                        .buttonStyle(.plain)
                                                    }
                                                    
                                                    // Activity Weight Slider
                                                    VStack(alignment: .leading, spacing: 2) {
                                                        HStack {
                                                            Text(String(localized: "ui.common.percentage"))
                                                                .font(.caption2)
                                                                .foregroundColor(.secondary)
                                                            Spacer()
                                                            TextField("", value: Binding(
                                                                get: { activity.weightWithinGroup * 100 },
                                                                set: { activity.weightWithinGroup = $0 / 100 }
                                                            ), format: .number)
                                                            .keyboardType(.decimalPad)
                                                            .multilineTextAlignment(.trailing)
                                                            .frame(width: 35)
                                                            .font(.caption2.monospacedDigit().bold())
                                                            
                                                            Text("%")
                                                                .font(.caption2)
                                                                .foregroundColor(.secondary)
                                                        }
                                                        Slider(value: Binding(
                                                            get: { activity.weightWithinGroup * 100 },
                                                            set: { activity.weightWithinGroup = $0 / 100 }
                                                        ), in: 0...100, step: 1)
                                                        .controlSize(.mini)
                                                    }

                                                    HStack {
                                                        Label {
                                                            TextField("h", value: $activity.estimatedHours, format: .number)
                                                                .keyboardType(.decimalPad)
                                                                .frame(width: 40)
                                                                .font(.caption.monospacedDigit())
                                                        } icon: {
                                                            Image(systemName: "clock")
                                                        }
                                                        .font(.caption)
                                                        .foregroundColor(.secondary)

                                                        Spacer()

                                                        Stepper(value: $activity.deliveryWeek, in: 0...20) {
                                                            Text("\(String(localized: "ui.format.week").replacingOccurrences(of: "%d", with: "\(activity.deliveryWeek)"))")
                                                                .font(.caption)
                                                                .foregroundColor(.secondary)
                                                        }
                                                        .fixedSize()
                                                    }
                                                }
                                                .padding(10)
                                                .background(Color(UIColor.tertiarySystemBackground))
                                                .cornerRadius(8)
                                            }

                                            Button(action: {
                                                withAnimation {
                                                    group.activities.append(TempActivity(name: String(localized: "ui.subject.activity"), weightWithinGroup: 0.0))
                                                }
                                            }) {
                                                Label(String(localized: "ui.common.add"), systemImage: "plus.circle")
                                                    .font(.caption)
                                            }
                                        }
                                        .padding(12)
                                        .background(Color(UIColor.secondarySystemBackground).opacity(0.5))
                                        .cornerRadius(8, corners: [.bottomLeft, .bottomRight])
                                    }
                                }
                                .padding(.bottom, 8)
                            }

                            HStack {
                                Button(action: {
                                    withAnimation {
                                        let newGroup = TempGroup(name: "\(String(localized: "ui.subject.block")) \(tempGroups.count + 1)", globalWeight: 0.0)
                                        tempGroups.append(newGroup)
                                    }
                                }) {
                                    Label(String(localized: "ui.common.add"), systemImage: "plus.square.fill")
                                        .fontWeight(.semibold)
                                }
                                .buttonStyle(.borderedProminent)

                                Spacer()
                                
                                if tempGroups.isEmpty {
                                    Button(String(localized: "ui.career.setup")) {
                                        withAnimation {
                                            setupDefaultBlocks()
                                        }
                                    }
                                    .buttonStyle(.bordered)
                                }
                            }
                        }
                        .padding(.vertical, 8)
                    }
                }

                if enrollmentStatusRaw != EnrollmentStatus.convalidated.rawValue && (!criticalRuleErrors.isEmpty || !ruleWarnings.isEmpty) {
                    Section(String(localized: "ui.form.diagnostics")) {
                        ForEach(criticalRuleErrors, id: \.self) { error in
                            Label(error, systemImage: "xmark.octagon.fill")
                                .foregroundColor(.red)
                                .font(.caption)
                        }

                        ForEach(ruleWarnings, id: \.self) { warning in
                            Label(warning, systemImage: "exclamationmark.triangle.fill")
                                .foregroundColor(.orange)
                                .font(.caption)
                        }
                    }
                }
                
                // 3. OBJECTIVES
                if enrollmentStatusRaw != EnrollmentStatus.convalidated.rawValue {
                    Section(header: Text(String(localized: "ui.form.objectives"))) {
                        ForEach($tempObjectives) { $objective in
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    TextField(String(localized: "ui.common.description"), text: $objective.description)
                                    Spacer()
                                    Button(role: .destructive) {
                                        if let index = tempObjectives.firstIndex(where: { $0.id == objective.id }) {
                                            tempObjectives.remove(at: index)
                                        }
                                    } label: {
                                        Image(systemName: "trash").foregroundColor(.red)
                                    }
                                    .buttonStyle(.plain)
                                }
                                
                                if !allActivities.isEmpty {
                                    DisclosureGroup {
                                        ForEach(allActivities) { activity in
                                            Toggle(isOn: Binding(
                                                get: { objective.linkedActivitiesIDs.contains(activity.id) },
                                                set: { isSelected in
                                                    if isSelected {
                                                        objective.linkedActivitiesIDs.insert(activity.id)
                                                    } else {
                                                        objective.linkedActivitiesIDs.remove(activity.id)
                                                    }
                                                }
                                            )) {
                                                Text(activity.name.isEmpty ? String(localized: "ui.common.untitled") : activity.name)
                                                    .font(.caption)
                                            }
                                        }
                                    } label: {
                                        Text(String(localized: "ui.subject.activity"))
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                    }
                                }
                            }
                            .padding(.vertical, 4)
                        }
                        
                        Button(action: {
                            withAnimation {
                                tempObjectives.append(TempObjective(description: ""))
                            }
                        }) {
                            Label(String(localized: "ui.common.add"), systemImage: "plus.circle")
                        }
                    }
                }
            }
            .navigationTitle(formTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button(String(localized: "ui.common.cancel")) { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button(subjectToEdit == nil ? String(localized: "ui.common.save") : String(localized: "ui.common.update")) { saveToSwiftData() }
                        .disabled(!isFormValid || !canSavePlanningFields)
                }
            }
            .alert(String(localized: "ui.alert.couldNotSave"), isPresented: $isSaveErrorPresented) {
                Button(String(localized: "ui.common.close"), role: .cancel) { }
            } message: {
                Text(saveErrorMessage)
            }
            .onAppear {
                loadInitialDataIfNeeded()
            }
        }
    }
    
    private func setupDefaultBlocks() {
        tempGroups.append(
            TempGroup(
                name: String(localized: "ui.common.summary"),
                globalWeight: 0.7,
                activities: [
                    TempActivity(name: "\(String(localized: "ui.subject.activity")) 1", weightWithinGroup: 0.33),
                    TempActivity(name: "\(String(localized: "ui.subject.activity")) 2", weightWithinGroup: 0.33),
                    TempActivity(name: "\(String(localized: "ui.subject.activity")) 3", weightWithinGroup: 0.34)
                ]
            )
        )
        tempGroups.append(
            TempGroup(
                name: String(localized: "ui.subject.status.passed"),
                globalWeight: 0.3,
                isMandatory: true,
                hasMinimumGrade: true,
                minimumGrade: 5.0,
                activities: [TempActivity(name: "Final", weightWithinGroup: 1.0)]
            )
        )
    }
    
    // --- SAVE LOGIC (mapping Temp -> Model) ---
/// Saves to swift data.
    private func saveToSwiftData() {
        let targetSubject: Subject
        let trimmedCode = subjectCode.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        let selectedCareer = selectedCareerID.flatMap { id in careers.first(where: { $0.persistentModelID == id }) }
        let selectedSemester = selectedSemesterID.flatMap { id in semesters.first(where: { $0.persistentModelID == id }) }
        if let existing = subjectToEdit {
            targetSubject = existing
            targetSubject.name = trimmedName
            targetSubject.credits = credits
            for group in targetSubject.groups {
                context.delete(group)
            }
            for objective in targetSubject.objectives {
                context.delete(objective)
            }
            targetSubject.groups.removeAll()
            targetSubject.objectives.removeAll()
        } else {
            let newSubject = Subject(name: trimmedName, credits: credits)
            context.insert(newSubject)
            targetSubject = newSubject

            // Create/link SubjectBase to support repeats and future semesters.
            let keyFallback = "\(trimmedName.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())|\(credits)"
            let existingBase: SubjectBase? = {
                if !trimmedCode.isEmpty {
                    return bases.first(where: { $0.code.trimmingCharacters(in: .whitespacesAndNewlines).uppercased() == trimmedCode })
                }
                return bases.first(where: { "\($0.name.trimmingCharacters(in: .whitespacesAndNewlines).lowercased())|\($0.credits)" == keyFallback })
            }()
            
            if let existingBase {
                targetSubject.base = existingBase
                if !trimmedCode.isEmpty, existingBase.code.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    existingBase.code = trimmedCode
                }
                if targetSubject.pricePerCredit <= 0 {
                    targetSubject.pricePerCredit = existingBase.defaultPricePerCredit
                }
            } else {
                let newBase = SubjectBase(name: trimmedName, credits: credits, code: trimmedCode, defaultPricePerCredit: 0.0)
                context.insert(newBase)
                targetSubject.base = newBase
            }

            // Assign to the current plan (MVP).
            targetSubject.career = selectedCareer
                ?? defaultCareerID.flatMap { id in careers.first(where: { $0.persistentModelID == id }) }
                ?? careers.first

            targetSubject.semester = selectedSemester
                ?? defaultSemesterID.flatMap { id in semesters.first(where: { $0.persistentModelID == id }) }
                ?? (semesters.first(where: { $0.contains(Date()) }) ?? semesters.first)

            targetSubject.enrollmentStatus = EnrollmentStatus(rawValue: enrollmentStatusRaw) ?? .enrolled
            if targetSubject.enrollmentStatus == .convalidated {
                let normalized = convalidatedGradeInput.replacingOccurrences(of: ",", with: ".")
                targetSubject.convalidatedGrade = Double(normalized)
            } else {
                targetSubject.convalidatedGrade = nil
            }
            targetSubject.enrollmentDate = Date()
        }
        
        // Persist base code for edits as well.
        if let base = targetSubject.base, !trimmedCode.isEmpty {
            base.code = trimmedCode
        }

        // Persist planning fields for both create and edit.
        targetSubject.career = selectedCareer ?? targetSubject.career
        targetSubject.semester = selectedSemester ?? targetSubject.semester
        targetSubject.enrollmentStatus = EnrollmentStatus(rawValue: enrollmentStatusRaw) ?? targetSubject.enrollmentStatus
        if targetSubject.enrollmentStatus == .convalidated {
            let normalized = convalidatedGradeInput.replacingOccurrences(of: ",", with: ".")
            targetSubject.convalidatedGrade = Double(normalized)
        } else {
            targetSubject.convalidatedGrade = nil
        }

        targetSubject.pricePerCredit = max(0, pricePerCreditInput)
        
        if targetSubject.enrollmentStatus != .convalidated {
            var realActivitiesByTempID: [UUID: Activity] = [:]
            let totalGlobalWeight = tempGroups.reduce(0.0) { $0 + max(0.0, $1.globalWeight) }
            
            // 1. Create groups and their activities
            for groupTemp in tempGroups {
                let groupName = groupTemp.name.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !groupName.isEmpty else { continue }

                let normalizedGlobalWeight: Double = {
                    let raw = min(max(groupTemp.globalWeight, 0.0), 1.0)
                    guard totalGlobalWeight > 0 else { return raw }
                    return raw / totalGlobalWeight
                }()

                let newGroup = EvaluationGroup(
                    name: groupName,
                    globalWeight: normalizedGlobalWeight,
                    isRequiredToPass: groupTemp.isMandatory
                )
                newGroup.minimumRequiredGrade = groupTemp.hasMinimumGrade ? groupTemp.minimumGrade : nil
                newGroup.maxAllowedFails = groupTemp.hasMaxFails ? groupTemp.maxFails : nil

                context.insert(newGroup)
                targetSubject.groups.append(newGroup)

                let internalWeightSum = groupTemp.activities.reduce(0.0) { $0 + max(0.0, $1.weightWithinGroup) }
                for actTemp in groupTemp.activities {
                    let activityName = actTemp.name.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !activityName.isEmpty else { continue }

                    let normalizedInternalWeight: Double = {
                        let raw = min(max(actTemp.weightWithinGroup, 0.0), 1.0)
                        guard internalWeightSum > 0 else { return raw }
                        return raw / internalWeightSum
                    }()
                    let newActivity = Activity(
                        name: activityName,
                        weightWithinGroup: normalizedInternalWeight
                    )
                    newActivity.grade = actTemp.grade
                    newActivity.estimatedHours = actTemp.estimatedHours
                    newActivity.deliveryWeek = actTemp.deliveryWeek
                    context.insert(newActivity)
                    newGroup.activities.append(newActivity)
                    realActivitiesByTempID[actTemp.id] = newActivity
                }
            }
            
            // 2. Create objectives and link them to activities by mapping IDs
            for objTemp in tempObjectives {
                let trimmedDescription = objTemp.description.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !trimmedDescription.isEmpty else { continue }

                let newObjective = LearningObjective(description: trimmedDescription)
                context.insert(newObjective)
                targetSubject.objectives.append(newObjective)
                
                for linkedID in objTemp.linkedActivitiesIDs {
                    if let realActivity = realActivitiesByTempID[linkedID] {
                        newObjective.linkedActivities.append(realActivity)
                    }
                }
            }
        }
        
        do {
            try context.save()
            dismiss()
        } catch {
            saveErrorMessage = String(localized: "ui.common.checkYourInputAndTryAgain")
            isSaveErrorPresented = true
        }
    }

/// Handles load initial data if needed.
    private func loadInitialDataIfNeeded() {
        guard !didLoadInitialData else { return }
        guard let subject = subjectToEdit else {
            selectedCareerID = defaultCareerID ?? careers.first?.persistentModelID
            selectedSemesterID = defaultSemesterID ?? (semesters.first(where: { $0.contains(Date()) }) ?? semesters.first)?.persistentModelID
            enrollmentStatusRaw = EnrollmentStatus.enrolled.rawValue
            convalidatedGradeInput = ""
            pricePerCreditInput = 0.0
            didLoadInitialData = true
            return
        }

        name = subject.name
        credits = subject.credits
        subjectCode = subject.base?.code ?? ""
        selectedCareerID = subject.career?.persistentModelID ?? defaultCareerID ?? careers.first?.persistentModelID
        selectedSemesterID = subject.semester?.persistentModelID ?? defaultSemesterID ?? (semesters.first(where: { $0.contains(Date()) }) ?? semesters.first)?.persistentModelID
        enrollmentStatusRaw = subject.enrollmentStatus.rawValue
        if let grade = subject.convalidatedGrade {
            convalidatedGradeInput = String(format: "%.1f", grade)
        } else {
            convalidatedGradeInput = ""
        }
        pricePerCreditInput = subject.pricePerCredit

        var activityToUUIDMap: [ObjectIdentifier: UUID] = [:]
        tempGroups = subject.groups.map { group in
            var activitiesTemp: [TempActivity] = []
            for activity in group.activities {
                let newID = UUID()
                activityToUUIDMap[ObjectIdentifier(activity)] = newID
                activitiesTemp.append(
                    TempActivity(
                        id: newID,
                        name: activity.name,
                        weightWithinGroup: activity.weightWithinGroup,
                        grade: activity.grade,
                        estimatedHours: activity.estimatedHours,
                        deliveryWeek: activity.deliveryWeek
                    )
                )
            }

            return TempGroup(
                name: group.name,
                globalWeight: group.globalWeight,
                isMandatory: group.isRequiredToPass,
                hasMinimumGrade: group.minimumRequiredGrade != nil,
                minimumGrade: group.minimumRequiredGrade ?? 5.0,
                hasMaxFails: group.maxAllowedFails != nil,
                maxFails: group.maxAllowedFails ?? 0,
                activities: activitiesTemp,
                isExpanded: true
            )
        }

        tempObjectives = subject.objectives.map { objective in
            let linkedIDs: Set<UUID> = Set(
                objective.linkedActivities.compactMap { activity in
                    activityToUUIDMap[ObjectIdentifier(activity)]
                }
            )
            return TempObjective(
                description: objective.description,
                linkedActivitiesIDs: linkedIDs
            )
        }

        didLoadInitialData = true
    }
}

// --- TEMPORARY MODELS (UI state handling) ---
/// TempGroup view and UI state container.
struct TempGroup: Identifiable {
    var id = UUID()
    var name: String
    var globalWeight: Double
    var isMandatory: Bool = false
    var hasMinimumGrade: Bool = false
    var minimumGrade: Double = 5.0
    var hasMaxFails: Bool = false
    var maxFails: Int = 0
    var activities: [TempActivity] = []
    var isExpanded: Bool = true // Controls whether the DisclosureGroup is expanded
}

/// TempActivity view and UI state container.
struct TempActivity: Identifiable {
    var id = UUID()
    var name: String
    var weightWithinGroup: Double
    var grade: Double? = nil
    var estimatedHours: Double = 0.0
    var deliveryWeek: Int = 0
}

/// TempObjective view and UI state container.
struct TempObjective: Identifiable {
    var id = UUID()
    var description: String
    var linkedActivitiesIDs: Set<UUID> = []
}

// --- VIEW EXTENSIONS ---
extension View {
    func cornerRadius(_ radius: CGFloat, corners: UIRectCorner) -> some View {
        clipShape(RoundedCorner(radius: radius, corners: corners))
    }
}

struct RoundedCorner: Shape {
    var radius: CGFloat = .infinity
    var corners: UIRectCorner = .allCorners

    func path(in rect: CGRect) -> Path {
        let path = UIBezierPath(roundedRect: rect, byRoundingCorners: corners, cornerRadii: CGSize(width: radius, height: radius))
        return Path(path.cgPath)
    }
}
