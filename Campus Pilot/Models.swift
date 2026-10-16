//
//  Models.swift
//  Campus Pilot
//
//  Created by Andrea Osma Rafael on 19/3/26.
//


/// SwiftData domain models and computed business logic used by the app.

import Foundation
import SwiftData

/// AcademicStatus options used by planner features.
enum AcademicStatus: String {
    case inProgress = "In progress"
    case passed = "Passed"
    case failed = "Failed"

    var localizedName: String {
        switch self {
        case .inProgress: return String(localized: "ui.subject.status.inProgress")
        case .passed: return String(localized: "ui.subject.status.passed")
        case .failed: return String(localized: "ui.subject.status.failed")
        }
    }
}

/// EnrollmentStatus options used by planner features.
enum EnrollmentStatus: String {
    case enrolled = "Enrolled"
    case convalidated = "Convalidated"
    case pending = "Pending"
    case completed = "Completed"

    var localizedName: String {
        switch self {
        case .enrolled: return String(localized: "ui.subject.status.enrolled")
        case .convalidated: return String(localized: "ui.subject.status.convalidated")
        case .pending: return String(localized: "ui.subject.status.pending")
        case .completed: return String(localized: "ui.subject.status.completed")
        }
    }
}

/// CostCategory options used by planner features.
enum CostCategory: String {
    case learningResources = "Learning resources"
    case tuition = "Tuition"
    case transport = "Transport"
    case materials = "Materials"
    case other = "Other"

    var localizedName: String {
        switch self {
        case .learningResources: return String(localized: "ui.common.category")
        case .tuition: return String(localized: "ui.finance.price")
        case .transport: return String(localized: "ui.common.other")
        case .materials: return String(localized: "ui.common.category")
        case .other: return String(localized: "ui.common.other")
        }
    }
}

@Model
/// Persistent Career model used in SwiftData.
final class Career {
    var name: String
    var ectsGoal: Int

    @Relationship(deleteRule: .cascade) var subjects: [Subject] = []

    init(name: String, ectsGoal: Int = 240) {
        self.name = name
        self.ectsGoal = ectsGoal
    }
}

@Model
/// Persistent Semester model used in SwiftData.
final class Semester {
    var label: String
    var startDate: Date
    var endDate: Date?

    @Relationship(deleteRule: .cascade) var subjects: [Subject] = []

    init(label: String, startDate: Date) {
        self.label = label
        self.startDate = startDate
        self.endDate = nil
    }

    init(label: String, startDate: Date, endDate: Date) {
        self.label = label
        self.startDate = startDate
        self.endDate = endDate
    }

    /// Default semester length for planning purposes (4 months).
    var estimatedEndDate: Date {
        Calendar.current.date(byAdding: .month, value: 4, to: startDate) ?? startDate
    }

    var endDateOrEstimated: Date {
        endDate ?? estimatedEndDate
    }

    /// Human-friendly label derived from dates (preferred for UI).
    var displayTitle: String {
        label
    }

/// Handles contains.
    func contains(_ date: Date) -> Bool {
        (startDate...endDateOrEstimated).contains(date)
    }

    var totalWeeklyHours: Double {
        subjects.reduce(0.0) { $0 + $1.estimatedWeeklyHours }
    }

    var costTotal: Double {
        subjects.reduce(0.0) { $0 + $1.attemptTotalCost }
    }

    /// Semester grade excluding convalidated subjects.
    /// Includes only subjects with at least one graded activity (so we don't force 0.0).
    var weightedSemesterGrade: Double {
        let relevantSubjects = subjects.filter { subject in
            subject.enrollmentStatus != .convalidated && subject.gradedActivitiesCount > 0
        }
        let creditSum = relevantSubjects.reduce(0.0) { $0 + Double($1.credits) }
        guard creditSum > 0 else { return 0.0 }

        let weightedSum = relevantSubjects.reduce(0.0) { partial, subject in
            partial + (subject.weightedFinalGrade * Double(subject.credits))
        }
        return weightedSum / creditSum
    }
}

@Model
/// Persistent SubjectBase model used in SwiftData.
final class SubjectBase {
    var name: String
    var credits: Int
    
    /// Editable subject code to match shared curricula across careers.
    /// Keep it stable if you want bases to be re-used.
    var code: String

    /// Default price per credit for future attempts (includes learning resources).
    var defaultPricePerCredit: Double

    @Relationship(deleteRule: .cascade) var subjects: [Subject] = []

    init(name: String, credits: Int, code: String = "", defaultPricePerCredit: Double = 0.0) {
        self.name = name
        self.credits = credits
        self.code = code
        self.defaultPricePerCredit = defaultPricePerCredit
    }
}

@Model
/// Persistent ExtraCost model used in SwiftData.
final class ExtraCost {
    var categoryRaw: String
    /// Human-readable label for the cost item.
    var details: String
    var amount: Double
    var date: Date

    @Relationship var subject: Subject?

    init(category: CostCategory, description: String, amount: Double, date: Date = Date.now) {
        self.categoryRaw = category.rawValue
        self.details = description
        self.amount = amount
        self.date = date
    }

    /// Compatibility shim for existing call sites.
    var description: String {
        get { details }
        set { details = newValue }
    }
    var category: CostCategory {
        CostCategory(rawValue: categoryRaw) ?? .other
    }
}

@Model
/// Persistent SimulationScenario model used in SwiftData.
final class SimulationScenario {
    var name: String
    var createdAt: Date
    var targetGrade: Double
    /// Values: `splitEvenly`, `fixFirst`.
    var modeRaw: String
    var fixedFirstGrade: Double
    var groupName1: String
    var activityName1: String
    /// Empty if there is no second activity
    var groupName2: String
    var activityName2: String

    @Relationship(inverse: \Subject.simulationScenarios)
    var subject: Subject?

    init(
        name: String,
        createdAt: Date = .now,
        targetGrade: Double,
        modeRaw: String,
        fixedFirstGrade: Double,
        groupName1: String,
        activityName1: String,
        groupName2: String = "",
        activityName2: String = ""
    ) {
        self.name = name
        self.createdAt = createdAt
        self.targetGrade = targetGrade
        self.modeRaw = modeRaw
        self.fixedFirstGrade = fixedFirstGrade
        self.groupName1 = groupName1
        self.activityName1 = activityName1
        self.groupName2 = groupName2
        self.activityName2 = activityName2
    }
}

@Model
/// Persistent Subject model used in SwiftData.
final class Subject {
    var name: String
    var credits: Int
    
    @Relationship(deleteRule: .cascade) var groups: [EvaluationGroup] = []
    @Relationship(deleteRule: .cascade) var objectives: [LearningObjective] = []
    @Relationship(deleteRule: .cascade) var simulationScenarios: [SimulationScenario] = []

    // --- Career/semester planning ---
    /// Stored as String for stable persistence.
    var enrollmentStatusRaw: String = EnrollmentStatus.enrolled.rawValue
    var convalidatedGrade: Double? = nil
    var enrollmentDate: Date = Date.now

    var enrollmentStatus: EnrollmentStatus {
        get {
            switch enrollmentStatusRaw {
            case EnrollmentStatus.enrolled.rawValue, "Matriculada": return .enrolled
            case EnrollmentStatus.convalidated.rawValue, "Convalidada": return .convalidated
            case EnrollmentStatus.pending.rawValue, "Pendiente": return .pending
            case EnrollmentStatus.completed.rawValue, "Finalizada": return .completed
            default: return .enrolled
            }
        }
        set { enrollmentStatusRaw = newValue.rawValue }
    }

    /// Workload estimate (MVP): hours per week.
    var estimatedWeeklyHours: Double = 0.0

    /// Price per credit (includes learning resources).
    var pricePerCredit: Double = 0.0

    @Relationship(inverse: \Career.subjects) var career: Career?
    @Relationship(inverse: \Semester.subjects) var semester: Semester?
    @Relationship(inverse: \SubjectBase.subjects) var base: SubjectBase?
    @Relationship(deleteRule: .cascade) var extraCosts: [ExtraCost] = []
    
    init(name: String, credits: Int) {
        self.name = name
        self.credits = credits
    }

    /// Total cost for this attempt (price per credit * credits + extra costs).
    var attemptTotalCost: Double {
        let effectivePrice = pricePerCredit > 0 ? pricePerCredit : (base?.defaultPricePerCredit ?? 0.0)
        let base = effectivePrice * Double(credits)
        let extras = extraCosts.reduce(0.0) { $0 + $1.amount }
        return base + extras
    }

    var weightedFinalGrade: Double {
        let weightedGroups = groups.filter { $0.globalWeight > 0 }
        guard !weightedGroups.isEmpty else { return 0.0 }

        let weightSum = weightedGroups.reduce(0.0) { $0 + $1.globalWeight }
        let weightedSum = weightedGroups.reduce(0.0) { partial, group in
            partial + (group.groupAverageGrade * group.globalWeight)
        }

        return weightSum > 0 ? (weightedSum / weightSum) : 0.0
    }

    var totalActivities: Int {
        groups.reduce(0) { $0 + $1.activities.count }
    }

    var gradedActivitiesCount: Int {
        groups.reduce(0) { partial, group in
            partial + group.activities.filter { $0.grade != nil }.count
        }
    }

    var evaluationProgress: Double {
        guard totalActivities > 0 else { return 0.0 }
        return Double(gradedActivitiesCount) / Double(totalActivities)
    }

    var academicStatus: AcademicStatus {
        if enrollmentStatus == .convalidated {
            return (convalidatedGrade ?? 0.0) >= 5.0 ? .passed : .failed
        }
        
        if enrollmentStatus == .completed {
            return weightedFinalGrade >= 5.0 ? .passed : .failed
        }

        guard totalActivities > 0 else { return .inProgress }
        guard evaluationProgress >= 1.0 else { return .inProgress }

        let requiredGroups = groups.filter { $0.isRequiredToPass }
        let failsRequiredGroups = requiredGroups.contains { $0.groupAverageGrade < 5.0 }
        if failsRequiredGroups { return .failed }

        let failsMinimumGrade = groups.contains { group in
            guard let minimumGrade = group.minimumRequiredGrade else { return false }
            return group.groupAverageGrade < minimumGrade
        }
        if failsMinimumGrade { return .failed }

        let exceedsFailLimit = groups.contains { group in
            guard let maxAllowedFails = group.maxAllowedFails else { return false }
            let fails = group.activities.filter { activity in
                guard let grade = activity.grade else { return false }
                return grade < 5.0
            }.count
            return fails > maxAllowedFails
        }
        if exceedsFailLimit { return .failed }

        return weightedFinalGrade >= 5.0 ? .passed : .failed
    }

    var academicStatusColorName: String {
        switch academicStatus {
        case .inProgress: return "orange"
        case .passed: return "green"
        case .failed: return "red"
        }
    }

    var exportableSummary: String {
        var lines: [String] = []
        lines.append(String(format: String(localized: "ui.format.subject"), name))
        lines.append(String(format: String(localized: "ui.format.credits"), credits))
        lines.append(String(format: String(localized: "ui.format.grade"), weightedFinalGrade))
        lines.append(String(format: String(localized: "ui.format.status"), academicStatus.localizedName))
        lines.append(String(format: String(localized: "ui.format.progress"), "\(Int(evaluationProgress * 100))%", gradedActivitiesCount, totalActivities))
        lines.append("")
        lines.append(String(localized: "ui.subject.evaluation.blocks"))

        for group in groups {
            lines.append("- \(group.name) (\(String(format: String(localized: "ui.format.percent"), group.globalWeight * 100)))")
            for activity in group.activities {
                let gradeText = activity.grade.map { String(format: String(localized: "ui.format.grade2f"), $0) } ?? String(localized: "ui.subject.status.pending")
                lines.append("  - \(activity.name): \(gradeText) | \(String(localized: "ui.common.percentage")): \(String(format: String(localized: "ui.format.percent"), activity.weightWithinGroup * 100))")
            }
        }

        if !objectives.isEmpty {
            lines.append("")
            lines.append(String(localized: "ui.form.objectives"))
            for objective in objectives {
                let status = objective.isAchieved ? String(localized: "ui.common.achieved") : String(localized: "ui.subject.status.pending")
                lines.append("- \(objective.description) (\(status))")
            }
        }

        return lines.joined(separator: "\n")
    }

    var exportableCSV: String {
        var rows: [String] = []
        // type,subject,credits,block,global_weight,activity,internal_weight,grade,objective,objective_status
        rows.append([
            String(localized: "ui.common.type"),
            String(localized: "ui.subject.title"),
            String(localized: "ui.subject.credits"),
            String(localized: "ui.subject.block"),
            String(localized: "ui.common.percentage"),
            String(localized: "ui.subject.activity"),
            String(localized: "ui.common.percentage"),
            String(localized: "ui.common.metrics"),
            String(localized: "ui.form.objectives"),
            String(localized: "ui.common.status")
        ].joined(separator: ","))

        for group in groups {
            for activity in group.activities {
                let gradeText = activity.grade.map { String(format: "%.2f", $0) } ?? ""
                rows.append([
                    "activity",
                    csvSafe(name),
                    "\(credits)",
                    csvSafe(group.name),
                    String(format: "%.4f", group.globalWeight),
                    csvSafe(activity.name),
                    String(format: "%.4f", activity.weightWithinGroup),
                    gradeText,
                    "",
                    ""
                ].joined(separator: ","))
            }
        }

        for objective in objectives {
            rows.append([
                "objective",
                csvSafe(name),
                "\(credits)",
                "",
                "",
                "",
                "",
                "",
                csvSafe(objective.description),
                objective.isAchieved ? "achieved" : "pending"
            ].joined(separator: ","))
        }

        return rows.joined(separator: "\n")
    }

/// Handles csv safe.
    private func csvSafe(_ value: String) -> String {
        let escaped = value.replacingOccurrences(of: "\"", with: "\"\"")
        return "\"\(escaped)\""
    }
}

@Model
/// Persistent EvaluationGroup model used in SwiftData.
final class EvaluationGroup {
    var name: String
    var globalWeight: Double
    var isRequiredToPass: Bool
    var minimumRequiredGrade: Double?
    var maxAllowedFails: Int?
    
    @Relationship(deleteRule: .cascade) var activities: [Activity] = []
    
    init(name: String, globalWeight: Double, isRequiredToPass: Bool = false) {
        self.name = name
        self.globalWeight = globalWeight
        self.isRequiredToPass = isRequiredToPass
    }
    
    var groupAverageGrade: Double {
        let completed = activities.filter { $0.grade != nil }
        guard !completed.isEmpty else { return 0.0 }
        
        let weightSum = completed.reduce(0) { $0 + $1.weightWithinGroup }
        let gradeSum = completed.reduce(0) { $0 + ($1.grade! * $1.weightWithinGroup) }
        
        return weightSum > 0 ? (gradeSum / weightSum) : 0.0
    }
}

@Model
/// Persistent Activity model used in SwiftData.
final class Activity {
    var name: String
    var weightWithinGroup: Double
    var grade: Double?

    /// Planned workload (MVP): hours for the week it is done.
    /// `deliveryWeek = 0` means "no week set".
    var estimatedHours: Double = 0.0
    var deliveryWeek: Int = 0
    
    @Relationship(inverse: \LearningObjective.linkedActivities)
    var evaluatedObjectives: [LearningObjective] = []
    
    init(name: String, weightWithinGroup: Double) {
        self.name = name
        self.weightWithinGroup = weightWithinGroup
    }
    
    var isPassed: Bool {
        return (grade ?? 0.0) >= 5.0
    }
}

@Model
/// Persistent LearningObjective model used in SwiftData.
final class LearningObjective {
    /// Objective text shown in the UI.
    var text: String
    var linkedActivities: [Activity] = []
    
    init(description: String) {
        self.text = description
    }

    /// Compatibility shim for existing call sites.
    var description: String {
        get { text }
        set { text = newValue }
    }
    
    var isAchieved: Bool {
        guard !linkedActivities.isEmpty else { return false }
        return linkedActivities.contains(where: { $0.isPassed })
    }
}
