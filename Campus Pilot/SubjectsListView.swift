//
//  SubjectsListView.swift
//  Campus Pilot
//
//  Created by Andrea Osma Rafael on 19/3/26.
//


/// Subject listing, filtering, sorting, and navigation to details.

import SwiftUI
import SwiftData

/// List filter (initial state per `NavigationLink`, without relying on UserDefaults).
enum SubjectListFilter: String, CaseIterable, Identifiable {
    case all = "All"
    case inProgress = "In progress"
    case passed = "Passed"
    case failed = "Failed"

    var id: String { rawValue }

    var localizedName: String {
        switch self {
        case .all: return String(localized: "ui.common.all")
        case .inProgress: return String(localized: "ui.subject.status.inProgress")
        case .passed: return String(localized: "ui.subject.status.passed")
        case .failed: return String(localized: "ui.subject.status.failed")
        }
    }
}

/// SubjectsListView view and UI state container.
struct SubjectsListView: View {
    private enum SubjectOrder: String, CaseIterable, Identifiable {
        case nameAZ = "Name (A-Z)"
        case highestGrade = "Estimated grade (highest)"
        case highestProgress = "Progress (highest)"

        var id: String { rawValue }

        var localizedName: String {
            switch self {
            case .nameAZ: return String(localized: "ui.common.name")
            case .highestGrade: return String(localized: "ui.subject.grade.estimated")
            case .highestProgress: return String(localized: "ui.subject.evaluation.progress")
            }
        }
    }

    @Environment(\.modelContext) private var context
    @Query private var subjects: [Subject]
    @State private var isFormPresented = false
    @State private var searchText = ""
    @State private var statusFilter: SubjectListFilter
    @AppStorage("subjects_order") private var orderRaw = SubjectOrder.nameAZ.rawValue

    init(initialFilter: SubjectListFilter = .all) {
        _statusFilter = State(initialValue: initialFilter)
    }

    var body: some View {
        List {
                Section {
                    Picker(String(localized: "ui.common.status"), selection: $statusFilter) {
                        ForEach(SubjectListFilter.allCases) { filter in
                            Text(filter.localizedName).tag(filter)
                        }
                    }
                    .pickerStyle(.segmented)
                    if statusFilter != .all {
                        Text(String(format: String(localized: "ui.format.onlySubjectsInFormat"), statusFilter.localizedName))
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                }

                if filteredSubjects.isEmpty {
                    ContentUnavailableView(
                        tituloEstadoVacio,
                        systemImage: "graduationcap",
                        description: Text(descriptionEstadoVacio)
                    )
                } else {
                    ForEach(filteredSubjects) { subject in
                        NavigationLink(destination: SubjectDetailView(subject: subject)) {
                            VStack(alignment: .leading) {
                                Text(subject.name).font(.headline)
                                Text(String(format: String(localized: "ui.format.credits"), subject.credits))
                                    .font(.subheadline)
                                    .foregroundColor(.secondary)

                                Text(subject.enrollmentStatus == .convalidated ? EnrollmentStatus.convalidated.localizedName : subject.academicStatus.localizedName)
                                    .font(.caption)
                                    .fontWeight(.semibold)
                                    .foregroundColor(subject.enrollmentStatus == .convalidated ? .gray : statusColor(subject.academicStatus))

                                ProgressView(value: subject.evaluationProgress) {
                                    Text(String(localized: "ui.subject.evaluation.progress"))
                                        .font(.caption)
                                } currentValueLabel: {
                                    Text(String(format: String(localized: "ui.format.percent"), subject.evaluationProgress * 100))
                                        .font(.caption)
                                }
                            }
                        }
                    }
                    .onDelete(perform: deleteSubjects)
                }
            }
            .navigationTitle(String(localized: "ui.career.grades"))
            .animation(.default, value: subjects.count)
            .searchable(text: $searchText, prompt: String(localized: "ui.common.search"))
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Menu {
                        Picker(String(localized: "ui.common.sortBy"), selection: selectedOrderBinding) {
                            ForEach(SubjectOrder.allCases) { order in
                                Text(order.localizedName).tag(order)
                            }
                        }
                    } label: {
                        Image(systemName: "arrow.up.arrow.down.circle")
                    }
                }

                ToolbarItem(placement: .navigationBarTrailing) {
                    Button(action: { isFormPresented = true }) {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $isFormPresented) {
                AddSubjectView()
                    .environment(\.modelContext, context)
            }
    }

/// Deletes subjects.
    private func deleteSubjects(at offsets: IndexSet) {
        for index in offsets {
            context.delete(filteredSubjects[index])
        }
        try? context.save()
    }

    private var filteredSubjects: [Subject] {
        let searchFiltered = searchText.isEmpty
            ? subjects
            : subjects.filter { $0.name.localizedCaseInsensitiveContains(searchText) }

        let base: [Subject]
        switch statusFilter {
        case .all:
            base = searchFiltered
        case .inProgress:
            base = searchFiltered.filter { $0.academicStatus == .inProgress }
        case .passed:
            base = searchFiltered.filter { $0.academicStatus == .passed }
        case .failed:
            base = searchFiltered.filter { $0.academicStatus == .failed }
        }

        switch selectedOrder {
        case .nameAZ:
            return base.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
        case .highestGrade:
            return base.sorted { $0.weightedFinalGrade > $1.weightedFinalGrade }
        case .highestProgress:
            return base.sorted { $0.evaluationProgress > $1.evaluationProgress }
        }
    }

    private var tituloEstadoVacio: String {
        if !searchText.isEmpty {
            return String(localized: "ui.common.none")
        }
        if statusFilter == .all {
            return String(localized: "ui.common.none")
        }
        return String(localized: "ui.common.none")
    }

    private var descriptionEstadoVacio: String {
        if !searchText.isEmpty {
            return String(localized: "ui.common.description")
        }
        if statusFilter == .all {
            return String(localized: "ui.common.description")
        }
        return String(localized: "ui.common.description")
    }

/// Handles status color.
    private func statusColor(_ status: AcademicStatus) -> Color {
        switch status {
        case .inProgress: return .orange
        case .passed: return .green
        case .failed: return .red
        }
    }

    private var selectedOrder: SubjectOrder {
        SubjectOrder(rawValue: orderRaw) ?? .nameAZ
    }

    private var selectedOrderBinding: Binding<SubjectOrder> {
        Binding(
            get: { selectedOrder },
            set: { orderRaw = $0.rawValue }
        )
    }
}

// (Legacy wrapper removed after full migration to English.)
