/// Finance views for cost tracking and per-subject pricing controls.

import SwiftUI
import SwiftData

/// FinancePricesView view and UI state container.
struct FinancePricesView: View {
    @Environment(\.modelContext) private var context
    @Query(sort: \Career.name) private var careers: [Career]
    @Query private var subjects: [Subject]

    @State private var selectedCareerID: PersistentIdentifier?
    @State private var pricePerCreditInput: Double = 0.0
    
    private var currencyCode: String {
        Locale.current.currency?.identifier ?? "EUR"
    }

    private var selectedCareer: Career? {
        let id = selectedCareerID ?? careers.first?.persistentModelID
        guard let id else { return nil }
        return careers.first(where: { $0.persistentModelID == id }) ?? careers.first
    }

    private var subjectsForSelectedCareer: [Subject] {
        guard let careerID = selectedCareer?.persistentModelID else { return [] }
        return subjects.filter { $0.career?.persistentModelID == careerID }
    }

    private var totalCostCareer: Double {
        subjectsForSelectedCareer.reduce(0.0) { $0 + $1.attemptTotalCost }
    }

    private var totalECTSCareer: Int {
        subjectsForSelectedCareer.reduce(0) { $0 + $1.credits }
    }

    private var completedECTS: Int {
        subjectsForSelectedCareer.reduce(0) { partial, subject in
            if subject.enrollmentStatus == .convalidated || subject.academicStatus == .passed {
                return partial + subject.credits
            }
            return partial
        }
    }

    private var averagePricePerCredit: Double {
        let ects = Double(totalECTSCareer)
        guard ects > 0 else { return 0.0 }
        return totalCostCareer / ects
    }

    var body: some View {
        List {
            Section(String(localized: "ui.career.name")) {
                Picker(String(localized: "ui.career.name"), selection: Binding(
                    get: { selectedCareer?.persistentModelID },
                    set: { selectedCareerID = $0 }
                )) {
                    ForEach(careers) { career in
                        Text(career.name).tag(Optional(career.persistentModelID))
                    }
                }
                .pickerStyle(.menu)
            }

            Section(String(localized: "ui.common.summary")) {
                row(String(localized: "ui.finance.summary.total"), value: totalCostCareer, icon: "eurosign.circle")
                row(String(localized: "ui.finance.summary.average"), value: averagePricePerCredit, icon: "chart.bar")
                HStack {
                    Label(String(localized: "ui.career.ects.completed"), systemImage: "graduationcap.fill")
                    Spacer()
                    Text("\(completedECTS)/\(selectedCareer?.ectsGoal ?? 0)")
                        .foregroundColor(.secondary)
                }
            }

            Section(
                header: Text(String(localized: "ui.common.edit")),
                footer: Text(String(localized: "ui.common.description"))
            ) {
                LabeledContent(String(localized: "ui.finance.pricePerCredit")) {
                    TextField("0.00", value: $pricePerCreditInput, format: .currency(code: currencyCode))
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                }

                Button(String(localized: "ui.common.apply")) {
                    applyPricePerCreditToMissing()
                }
                .disabled(pricePerCreditInput <= 0 || selectedCareer == nil)
            }

            Section(String(localized: "ui.subject.list")) {
                if subjectsForSelectedCareer.isEmpty {
                    ContentUnavailableView(
                        String(localized: "ui.common.none"),
                        systemImage: "text.book.closed",
                        description: Text(String(localized: "ui.common.description"))
                    )
                } else {
                    ForEach(subjectsForSelectedCareer.sorted(by: { $0.name < $1.name }), id: \.persistentModelID) { subject in
                        NavigationLink {
                            FinanceSubjectDetailView(subject: subject)
                        } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(subject.name)
                                    .font(.headline)

                                Text("\(String(localized: "ui.subject.credits")): \(subject.credits)")
                                    .font(.caption)
                                    .foregroundColor(.secondary)

                                Text(String(localized: "ui.finance.total")) + Text(": ") + Text(subject.attemptTotalCost, format: .currency(code: currencyCode))
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                        }
                    }
                }
            }
        }
        .navigationTitle(String(localized: "ui.finance.title"))
        .navigationBarTitleDisplayMode(.inline)
    }

/// Handles effective price per credit.
    private func effectivePricePerCredit(_ subject: Subject) -> Double {
        if subject.pricePerCredit > 0 { return subject.pricePerCredit }
        return subject.base?.defaultPricePerCredit ?? 0.0
    }

/// Applies price per credit to missing.
    private func applyPricePerCreditToMissing() {
        guard let _ = selectedCareer else { return }
        for subject in subjectsForSelectedCareer {
            if subject.pricePerCredit <= 0 {
                subject.pricePerCredit = pricePerCreditInput
            }
        }
        try? context.save()
    }

/// Handles row.
    private func row(_ title: String, value: Double, icon: String) -> some View {
        HStack {
            Label(title, systemImage: icon)
            Spacer()
            Text(value, format: .currency(code: currencyCode))
                .fontWeight(.semibold)
                .foregroundColor(.secondary)
        }
    }
}

/// FinanceSubjectDetailView view and UI state container.
struct FinanceSubjectDetailView: View {
    @Environment(\.modelContext) private var context
    @Bindable var subject: Subject

    @State private var extraCostCategory: CostCategory = .learningResources
    @State private var extraCostDescription = ""
    @State private var extraCostAmount: Double = 0.0
    
    private var currencyCode: String {
        Locale.current.currency?.identifier ?? "EUR"
    }

    var body: some View {
        Form {
            Section(String(localized: "ui.common.price")) {
                LabeledContent(String(localized: "ui.finance.pricePerCredit")) {
                    TextField("0.00", value: $subject.pricePerCredit, format: .currency(code: currencyCode))
                        .keyboardType(.decimalPad)
                        .multilineTextAlignment(.trailing)
                }
                Text(String(localized: "ui.common.description"))
                    .font(.caption)
                    .foregroundColor(.secondary)

                HStack {
                    Text(String(localized: "ui.common.total"))
                    Spacer()
                    Text(subject.attemptTotalCost, format: .currency(code: currencyCode))
                        .fontWeight(.semibold)
                        .foregroundColor(.secondary)
                }
            }

            Section(String(localized: "ui.finance.extraCosts")) {
                if subject.extraCosts.isEmpty {
                    Text(String(localized: "ui.common.none"))
                        .font(.caption)
                        .foregroundColor(.secondary)
                } else {
                    ForEach(subject.extraCosts, id: \.persistentModelID) { extraCost in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(extraCost.description)
                                Text(extraCost.category.localizedName)
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                            }
                            Spacer()
                            Text(extraCost.amount, format: .currency(code: currencyCode))
                                .foregroundColor(.secondary)
                        }
                    }
                    .onDelete(perform: deleteExtraCosts)
                }
            }

            Section(String(localized: "ui.common.add")) {
                Picker(String(localized: "ui.common.category"), selection: $extraCostCategory) {
                    Text(CostCategory.learningResources.localizedName).tag(CostCategory.learningResources)
                    Text(CostCategory.tuition.localizedName).tag(CostCategory.tuition)
                    Text(CostCategory.materials.localizedName).tag(CostCategory.materials)
                    Text(CostCategory.other.localizedName).tag(CostCategory.other)
                }
                TextField(String(localized: "ui.common.description"), text: $extraCostDescription)
                TextField(String(localized: "ui.common.amount"), value: $extraCostAmount, format: .currency(code: currencyCode))
                    .keyboardType(.decimalPad)

                Button(String(localized: "ui.common.add")) {
                    addExtraCost()
                }
                .disabled(extraCostAmount <= 0 || extraCostDescription.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .navigationTitle(subject.name)
        .navigationBarTitleDisplayMode(.inline)
        .onDisappear {
            try? context.save()
        }
    }

/// Handles add extra cost.
    private func addExtraCost() {
        let desc = extraCostDescription.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !desc.isEmpty else { return }
        let extraCost = ExtraCost(category: extraCostCategory, description: desc, amount: extraCostAmount)
        extraCost.subject = subject
        subject.extraCosts.append(extraCost)
        context.insert(extraCost)
        try? context.save()

        extraCostDescription = ""
        extraCostAmount = 0
        extraCostCategory = .learningResources
    }

/// Deletes extra costs.
    private func deleteExtraCosts(at offsets: IndexSet) {
        for index in offsets {
            let item = subject.extraCosts[index]
            context.delete(item)
        }
        subject.extraCosts.remove(atOffsets: offsets)
        try? context.save()
    }
}

