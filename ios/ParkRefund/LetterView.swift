import SwiftUI

struct LetterView: View {
    let claim: Claim
    let assessment: Assessment
    let onNext: () -> Void

    @State private var language = "da"
    @State private var letter = ""
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        VStack(spacing: 12) {
            Picker("Language", selection: $language) { Text("Dansk").tag("da"); Text("English").tag("en") }
                .pickerStyle(.segmented).padding(.horizontal)
            if busy { ProgressView("Drafting…").frame(maxHeight: .infinity) }
            else {
                ScrollView { Text(letter).font(.system(.footnote, design: .monospaced)).textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading).padding() }
            }
            ErrorBanner(message: error)
            HStack {
                ShareLink(item: letter) { Label("Share", systemImage: "square.and.arrow.up") }.disabled(letter.isEmpty)
                PrimaryButton(title: "Send to ParkRefund", busy: busy, action: submit).disabled(letter.isEmpty)
            }.padding(.horizontal)
        }
        .navigationTitle("Your appeal")
        .task(id: language) { await draft() }
    }

    private func draft() async {
        busy = true; defer { busy = false }
        do { letter = try await API.draft(claim, assessment, lang: language); error = nil }
        catch { self.error = error.localizedDescription }
    }

    // Puts the case in the ops queue (api.py /admin). Model drafts; a human files.
    private func submit() {
        Task {
            busy = true; defer { busy = false }
            do { try await API.submit(claim, assessment); onNext() }
            catch { self.error = error.localizedDescription }
        }
    }
}
