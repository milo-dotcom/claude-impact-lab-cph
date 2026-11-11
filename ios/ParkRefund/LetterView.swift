import SwiftUI

struct LetterView: View {
    let claim: Claim
    let assessment: Assessment
    let onDone: () -> Void

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
            Text("Read it, sign it, send it yourself. Free and open source — no fee, no cut of your refund.")
                .font(.footnote).foregroundStyle(.secondary).multilineTextAlignment(.center).padding(.horizontal)
            HStack {
                ShareLink(item: letter) { Label("Share", systemImage: "square.and.arrow.up") }.disabled(letter.isEmpty)
                PrimaryButton(title: "Done", action: onDone)
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
}
