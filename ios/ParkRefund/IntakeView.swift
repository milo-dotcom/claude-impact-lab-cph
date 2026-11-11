import SwiftUI
import PhotosUI
import UIKit

struct IntakeView: View {
    @Binding var claim: Claim
    let onAssessed: (Assessment) -> Void

    @State private var photo: PhotosPickerItem?
    @State private var samples: [Claim] = []
    @State private var busy = false
    @State private var error: String?
    @State private var apiBase = API.base.absoluteString

    var body: some View {
        Form {
            Section {
                Text("Free and open source. Upload the ticket, tell us what happened, get an honest verdict and a letter you send yourself.")
                    .font(.subheadline).foregroundStyle(.secondary)
                PhotosPicker(selection: $photo, matching: .images) {
                    Label(busy ? "Reading ticket…" : "Photograph / pick the ticket", systemImage: "camera.viewfinder")
                }
                if !samples.isEmpty {
                    Menu("…or pick a sample case") {
                        ForEach(samples, id: \.self) { s in Button(s.label ?? s.ticket_number) { claim = s } }
                    }
                }
            }
            Section("Ticket") {
                Picker("Issuer", selection: $claim.issuer_type) { Text("Private operator").tag("private"); Text("Kommune").tag("public") }
                TextField("Issuer name", text: $claim.issuer_name)
                TextField("Ticket number", text: $claim.ticket_number)
                TextField("Plate", text: $claim.plate)
                HStack { TextField("Date YYYY-MM-DD", text: $claim.date); TextField("Time HH:MM", text: $claim.time) }
                TextField("Location", text: $claim.location)
                TextField("Amount DKK", value: $claim.amount_dkk, format: .number)
                TextField("Reason on ticket", text: $claim.reason_on_ticket)
            }
            Section("What happened?") {
                TextEditor(text: $claim.driver_story).frame(minHeight: 110)
            }
            Section("Evidence you have") {
                ForEach(evidenceOptions, id: \.self) { e in
                    Toggle(e, isOn: Binding(get: { claim.evidence.contains(e) },
                                            set: { on in if on { claim.evidence.append(e) } else { claim.evidence.removeAll { $0 == e } } }))
                }
            }
            Section {
                PrimaryButton(title: "Check my odds", busy: busy, action: assess)
                    .disabled(claim.driver_story.trimmingCharacters(in: .whitespaces).isEmpty)
                ErrorBanner(message: error)
            }
            Section("Server") {
                TextField("API base URL", text: $apiBase)
                    .textInputAutocapitalization(.never).autocorrectionDisabled()
                    .onSubmit { if let u = URL(string: apiBase) { API.base = u; UserDefaults.standard.set(apiBase, forKey: "apiBase") } }
            }
        }
        .task { samples = (try? await API.cases()) ?? [] }
        .onChange(of: photo) { _, item in Task { await readTicket(item) } }
    }

    private func readTicket(_ item: PhotosPickerItem?) async {
        guard let item, let data = try? await item.loadTransferable(type: Data.self) else { return }
        busy = true; defer { busy = false }
        do {
            // iPhone photos are HEIC, which the API rejects: re-encode as the JPEG we claim to send.
            guard let jpeg = UIImage(data: data)?.jpegData(compressionQuality: 0.7) else {
                error = "Could not read this photo."; return
            }
            let f = try await API.extract(jpeg, mediaType: "image/jpeg")
            // Only overwrite what the model actually read.
            if let v = f.issuer_type { claim.issuer_type = v }
            if let v = f.issuer_name { claim.issuer_name = v }
            if let v = f.ticket_number { claim.ticket_number = v }
            if let v = f.plate { claim.plate = v }
            if let v = f.date { claim.date = v }
            if let v = f.time { claim.time = v }
            if let v = f.location { claim.location = v }
            if let v = f.amount_dkk { claim.amount_dkk = v }
            if let v = f.reason_on_ticket { claim.reason_on_ticket = v }
            error = nil
        } catch { self.error = error.localizedDescription }
    }

    private func assess() {
        Task {
            busy = true; defer { busy = false }
            do { onAssessed(try await API.assess(claim)); error = nil }
            catch { self.error = error.localizedDescription }
        }
    }
}
