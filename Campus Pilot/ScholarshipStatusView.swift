/// MEC scholarship eligibility estimator and configurable thresholds.

import SwiftUI

/// ScholarshipStatusView view and UI state container.
struct ScholarshipStatusView: View {
    // MVP inputs (persisted)
    @AppStorage("mec_academic_year") private var academicYear = ""
    @AppStorage("mec_ects_enrolled") private var ectsEnrolled = 60
    @AppStorage("mec_ects_passed") private var ectsPassed = 0
    @AppStorage("mec_average_grade") private var averageGrade = 0.0

    // MVP "rules" (simple + configurable)
    @AppStorage("mec_min_ects_enrolled") private var minECTSEnrolled = 30
    @AppStorage("mec_min_pass_ratio") private var minPassRatio = 0.65
    @AppStorage("mec_min_average_grade") private var minAverageGrade = 5.0

    private var passRatio: Double {
        let enrolled = Double(max(ectsEnrolled, 0))
        guard enrolled > 0 else { return 0.0 }
        return Double(max(ectsPassed, 0)) / enrolled
    }

    private enum Verdict {
        case eligible
        case atRisk
        case notEligible

        var title: String {
            switch self {
            case .eligible: return String(localized: "ui.mec.eligible")
            case .atRisk: return String(localized: "ui.mec.atRisk")
            case .notEligible: return String(localized: "ui.mec.notEligible")
            }
        }

        var systemImage: String {
            switch self {
            case .eligible: return "checkmark.seal.fill"
            case .atRisk: return "exclamationmark.triangle.fill"
            case .notEligible: return "xmark.octagon.fill"
            }
        }

        var color: Color {
            switch self {
            case .eligible: return .green
            case .atRisk: return .orange
            case .notEligible: return .red
            }
        }
    }

    private var unmetReasons: [String] {
        var reasons: [String] = []
        if ectsEnrolled < minECTSEnrolled {
            reasons.append("\(String(localized: "ui.mec.minECTS")): \(minECTSEnrolled)")
        }
        if passRatio < minPassRatio {
            reasons.append("\(String(localized: "ui.mec.minPass")): \(Int(minPassRatio * 100))%")
        }
        if averageGrade < minAverageGrade {
            reasons.append("\(String(localized: "ui.mec.minGrade")): \(minAverageGrade)")
        }
        return reasons
    }

    private var verdict: Verdict {
        let failed = unmetReasons.count
        if failed == 0 { return .eligible }
        if failed == 1 { return .atRisk }
        return .notEligible
    }

    var body: some View {
        List {
            Section(String(localized: "ui.common.status")) {
                HStack {
                    Label(verdict.title, systemImage: verdict.systemImage)
                        .foregroundColor(verdict.color)
                        .font(.headline)
                    Spacer()
                }

                if unmetReasons.isEmpty {
                    Text(String(localized: "ui.common.done"))
                        .font(.caption)
                        .foregroundColor(.secondary)
                } else {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(String(localized: "ui.common.summary"))
                            .font(.subheadline)
                            .foregroundColor(.secondary)
                        ForEach(unmetReasons, id: \.self) { r in
                            Text(r)
                                .font(.caption)
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }

            Section(String(localized: "ui.common.summary")) {
                TextField(String(localized: "ui.mec.academicYear"), text: $academicYear)
                    .textInputAutocapitalization(.never)

                Stepper("\(String(localized: "ui.subject.credits")): \(ectsEnrolled)", value: $ectsEnrolled, in: 0...120, step: 1)
                Stepper("\(String(localized: "ui.career.ects.completed")): \(ectsPassed)", value: $ectsPassed, in: 0...120, step: 1)

                LabeledContent(String(localized: "ui.common.percentage")) {
                    Text(String(format: "%.0f%%", passRatio * 100))
                        .foregroundColor(.secondary)
                }

                LabeledContent(String(localized: "ui.career.metrics.average")) {
                    TextField("5.0", value: $averageGrade, format: .number)
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                }
            }

            Section(
                header: Text(String(localized: "ui.common.settings")),
                footer: Text(String(localized: "ui.mec.eligibility"))
            ) {
                Stepper("\(String(localized: "ui.mec.minECTS")): \(minECTSEnrolled)", value: $minECTSEnrolled, in: 0...120, step: 1)

                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(String(localized: "ui.mec.minPass"))
                        Spacer()
                        Text(String(format: "%.0f%%", minPassRatio * 100))
                            .foregroundColor(.secondary)
                    }
                    Slider(value: $minPassRatio, in: 0...1, step: 0.01)
                }

                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(String(localized: "ui.mec.minGrade"))
                        Spacer()
                        Text(String(format: "%.1f", minAverageGrade))
                            .foregroundColor(.secondary)
                    }
                    Slider(value: $minAverageGrade, in: 0...10, step: 0.1)
                }
            }

        }
        .navigationTitle(String(localized: "ui.mec.title"))
        .navigationBarTitleDisplayMode(.inline)
    }
}

#Preview {
    NavigationStack { ScholarshipStatusView() }
}

