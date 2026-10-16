/// Career and semester maintenance with lightweight trash restore actions.

import SwiftUI
import SwiftData

/// CareerSettingsView view and UI state container.
struct CareerSettingsView: View {
    private struct DeletedSubjectSnapshot: Codable {
        let name: String
        let credits: Int
        let careerNombre: String
        let semesterInicio: Date
        let eliminadoEn: Date
    }

    private struct DeletedCareerSnapshot: Codable {
        let name: String
        let ectsGoal: Int
        let eliminadoEn: Date
    }

    @Environment(\.modelContext) private var context
    @Environment(\.dismiss) private var dismiss

    @Query(sort: \Career.name) private var careers: [Career]
    @Query(sort: \Semester.startDate) private var semesters: [Semester]
    @Query private var subjects: [Subject]

    @Binding var selectedCareerID: PersistentIdentifier?
    @Binding var selectedSemesterID: PersistentIdentifier?

    @AppStorage("planner_trash_subjects_json") private var plannerTrashSubjectsJSON = "[]"
    @AppStorage("planner_trash_careers_json") private var plannerTrashCareersJSON = "[]"

    @State private var isCareerEditorPresented = false
    @State private var editingCareerID: PersistentIdentifier?
    @State private var draftCareerName = ""
    @State private var draftCareerECTS = 240

    @State private var isSemesterEditorPresented = false
    @State private var semesterToEdit: Semester?

    @State private var isDeleteCareerPresented = false
    @State private var careerToDelete: Career?

    @State private var isDeleteSemesterPresented = false
    @State private var semesterToDelete: Semester?

    private var careerSel: Career? {
        let id = selectedCareerID ?? careers.first?.persistentModelID
        guard let id else { return nil }
        return careers.first(where: { $0.persistentModelID == id }) ?? careers.first
    }

    private var semesterSel: Semester? {
        let id = selectedSemesterID ?? semesters.first?.persistentModelID
        guard let id else { return nil }
        return semesters.first(where: { $0.persistentModelID == id }) ?? semesters.first
    }

    private var subjectsForSelectedCareer: [Subject] {
        guard let careerID = careerSel?.persistentModelID else { return [] }
        return subjects.filter { $0.career?.persistentModelID == careerID }
    }

    private var lastDeletedSubject: DeletedSubjectSnapshot? {
        let current = (try? JSONDecoder().decode([DeletedSubjectSnapshot].self, from: Data(plannerTrashSubjectsJSON.utf8))) ?? []
        return current.last
    }

    private var lastDeletedCareer: DeletedCareerSnapshot? {
        let current = (try? JSONDecoder().decode([DeletedCareerSnapshot].self, from: Data(plannerTrashCareersJSON.utf8))) ?? []
        return current.last
    }

    var body: some View {
        List {
            Section(String(localized: "ui.career.name")) {
                Picker(String(localized: "ui.career.name"), selection: Binding(
                    get: { careerSel?.persistentModelID },
                    set: { selectedCareerID = $0 }
                )) {
                    ForEach(careers) { career in
                        Text(career.name).tag(Optional(career.persistentModelID))
                    }
                }
                .pickerStyle(.menu)

                HStack(spacing: 8) {
                    Button {
                        draftCareerName = ""
                        draftCareerECTS = 240
                        editingCareerID = nil
                        isCareerEditorPresented = true
                    } label: {
                        Label(String(localized: "ui.career.new"), systemImage: "plus")
                    }
                    .buttonStyle(.bordered)

                    Button {
                        guard let careerSel else { return }
                        draftCareerName = careerSel.name
                        draftCareerECTS = careerSel.ectsGoal
                        editingCareerID = careerSel.persistentModelID
                        isCareerEditorPresented = true
                    } label: {
                        Label(String(localized: "ui.common.edit"), systemImage: "pencil")
                    }
                    .buttonStyle(.bordered)
                    .disabled(careerSel == nil)

                    Button(role: .destructive) {
                        careerToDelete = careerSel
                        isDeleteCareerPresented = true
                    } label: {
                        Label(String(localized: "ui.common.delete"), systemImage: "trash")
                    }
                    .buttonStyle(.bordered)
                    .disabled(careerSel == nil || careers.count <= 1)
                }
                .controlSize(.small)
            }

            Section(String(localized: "ui.semester.title")) {
                Picker(String(localized: "ui.semester.title"), selection: Binding(
                    get: { semesterSel?.persistentModelID },
                    set: { selectedSemesterID = $0 }
                )) {
                    ForEach(semesters) { cuatri in
                        Text(cuatri.displayTitle).tag(Optional(cuatri.persistentModelID))
                    }
                }
                .pickerStyle(.menu)

                HStack(spacing: 8) {
                    Button {
                        semesterToEdit = nil
                        isSemesterEditorPresented = true
                    } label: {
                        Label(String(localized: "ui.semester.new"), systemImage: "plus")
                    }
                    .buttonStyle(.bordered)

                    Button {
                        semesterToEdit = semesterSel
                        isSemesterEditorPresented = true
                    } label: {
                        Label(String(localized: "ui.common.edit"), systemImage: "pencil")
                    }
                    .buttonStyle(.bordered)
                    .disabled(semesterSel == nil)

                    Button(role: .destructive) {
                        semesterToDelete = semesterSel
                        isDeleteSemesterPresented = true
                    } label: {
                        Label(String(localized: "ui.common.delete"), systemImage: "trash")
                    }
                    .buttonStyle(.bordered)
                    .disabled(
                        semesterSel == nil ||
                        semesters.count <= 1 ||
                        ((semesterSel?.subjects.count ?? 0) > 0)
                    )
                }
                .controlSize(.small)

                if let semesterSel, !semesterSel.subjects.isEmpty {
                    Text(String(localized: "ui.alert.warning"))
                        .font(.caption)
                        .foregroundColor(.secondary)
                }
            }

            Section(String(localized: "ui.planner.trash")) {
                HStack {
                    Text(String(localized: "ui.subject.title"))
                    Spacer()
                    Text(lastDeletedSubject?.name ?? "—")
                        .foregroundColor(.secondary)
                }

                HStack {
                    Text(String(localized: "ui.career.name"))
                    Spacer()
                    Text(lastDeletedCareer?.name ?? "—")
                        .foregroundColor(.secondary)
                }

                HStack(spacing: 8) {
                    Button {
                        restoreLastDeletedSubject()
                    } label: {
                        Label(String(localized: "ui.subject.restoreSubject"), systemImage: "arrow.uturn.backward.circle")
                    }
                    .buttonStyle(.bordered)
                    .disabled(lastDeletedSubject == nil)

                    Button {
                        restoreLastDeletedCareer()
                    } label: {
                        Label(String(localized: "ui.career.restore"), systemImage: "arrow.uturn.backward")
                    }
                    .buttonStyle(.bordered)
                    .disabled(lastDeletedCareer == nil)
                }
                .controlSize(.small)
            }

            Section(String(localized: "ui.common.summary")) {
                HStack {
                    Text(String(localized: "ui.subject.list"))
                    Spacer()
                    Text("\(subjectsForSelectedCareer.count)")
                        .foregroundColor(.secondary)
                }
            }
        }
        .navigationTitle(String(localized: "ui.career.settings.title"))
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button(String(localized: "ui.common.close")) { dismiss() }
            }
        }
        .sheet(isPresented: $isCareerEditorPresented) {
            NavigationStack {
                Form {
                    Section(String(localized: "ui.common.name")) {
                        TextField(String(localized: "ui.career.title"), text: $draftCareerName)
                            .textInputAutocapitalization(.words)
                    }
                    Section(String(localized: "ui.common.target")) {
                        Stepper("\(String(localized: "ui.subject.credits")): \(draftCareerECTS)", value: $draftCareerECTS, in: 30...600, step: 6)
                    }
                }
                .navigationTitle(editingCareerID == nil ? String(localized: "ui.career.new") : String(localized: "ui.career.edit"))
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button(String(localized: "ui.common.cancel")) {
                            isCareerEditorPresented = false
                            editingCareerID = nil
                        }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        Button(String(localized: "ui.common.save")) { saveCareer() }
                            .disabled(draftCareerName.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                }
            }
        }
        .sheet(isPresented: $isSemesterEditorPresented) {
            SemesterEditorView(semesterToEdit: semesterToEdit, selectedSemesterID: $selectedSemesterID)
                .environment(\.modelContext, context)
        }
        .alert(String(localized: "ui.alert.deleteCareer"), isPresented: $isDeleteCareerPresented) {
            Button(String(localized: "ui.common.cancel"), role: .cancel) { careerToDelete = nil }
            Button(String(localized: "ui.common.delete"), role: .destructive) {
                if let careerToDelete { deleteCareer(careerToDelete) }
                careerToDelete = nil
            }
        } message: {
            Text(String(localized: "ui.alert.theSelectedCareerWillBeDeletedThisActionCannotBeUndone"))
        }
        .alert(String(localized: "ui.common.delete.Semester"), isPresented: $isDeleteSemesterPresented) {
            Button(String(localized: "ui.common.cancel"), role: .cancel) { semesterToDelete = nil }
            Button(String(localized: "ui.common.delete"), role: .destructive) {
                if let semesterToDelete { deleteSemester(semesterToDelete) }
                semesterToDelete = nil
            }
        } message: {
            Text(String(localized: "ui.alert.theSelectedSemesterWillBeDeletedThisActionCannotBeUndone"))
        }
        .onAppear {
            if selectedCareerID == nil { selectedCareerID = careers.first?.persistentModelID }
            if selectedSemesterID == nil { selectedSemesterID = semesters.first?.persistentModelID }
        }
    }

/// Saves career.
    private func saveCareer() {
        let trimmed = draftCareerName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        if let editingCareerID,
           let existing = careers.first(where: { $0.persistentModelID == editingCareerID }) {
            existing.name = trimmed
            existing.ectsGoal = draftCareerECTS
            try? context.save()
            selectedCareerID = existing.persistentModelID
            isCareerEditorPresented = false
            self.editingCareerID = nil
            return
        }

        let career = Career(name: trimmed, ectsGoal: draftCareerECTS)
        context.insert(career)
        try? context.save()
        selectedCareerID = career.persistentModelID
        isCareerEditorPresented = false
        editingCareerID = nil
    }

/// Deletes career.
    private func deleteCareer(_ career: Career) {
        let snapshot = DeletedCareerSnapshot(name: career.name, ectsGoal: career.ectsGoal, eliminadoEn: Date())
        let current = (try? JSONDecoder().decode([DeletedCareerSnapshot].self, from: Data(plannerTrashCareersJSON.utf8))) ?? []
        let filtered = current.filter { Date().timeIntervalSince($0.eliminadoEn) <= 30 * 24 * 60 * 60 }
        let next = (filtered + [snapshot]).suffix(50)
        if let data = try? JSONEncoder().encode(Array(next)), let text = String(data: data, encoding: .utf8) {
            plannerTrashCareersJSON = text
        }

        let wasSelected = selectedCareerID == career.persistentModelID
        context.delete(career)
        try? context.save()
        if wasSelected {
            selectedCareerID = careers.first(where: { $0.persistentModelID != career.persistentModelID })?.persistentModelID
        }
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
        let current = (try? JSONDecoder().decode([DeletedSubjectSnapshot].self, from: Data(plannerTrashSubjectsJSON.utf8))) ?? []
        guard let snapshot = current.last else { return }
        var mutable = current
        _ = mutable.popLast()
        if let data = try? JSONEncoder().encode(mutable), let text = String(data: data, encoding: .utf8) {
            plannerTrashSubjectsJSON = text
        }

        let subject = Subject(name: snapshot.name, credits: snapshot.credits)
        subject.enrollmentStatus = .pending
        subject.career = careerSel ?? careers.first

        if let semester = semesters.first(where: { Calendar.current.isDate($0.startDate, inSameDayAs: snapshot.semesterInicio) }) {
            subject.semester = semester
        } else {
            subject.semester = semesterSel ?? semesters.first
        }

        context.insert(subject)
        try? context.save()
    }

/// Restores last deleted career.
    private func restoreLastDeletedCareer() {
        let current = (try? JSONDecoder().decode([DeletedCareerSnapshot].self, from: Data(plannerTrashCareersJSON.utf8))) ?? []
        guard let snapshot = current.last else { return }
        var mutable = current
        _ = mutable.popLast()
        if let data = try? JSONEncoder().encode(mutable), let text = String(data: data, encoding: .utf8) {
            plannerTrashCareersJSON = text
        }

        let career = Career(name: snapshot.name, ectsGoal: snapshot.ectsGoal)
        context.insert(career)
        try? context.save()
        selectedCareerID = career.persistentModelID
    }
}

