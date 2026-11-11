import SwiftUI

// One job per screen, one big button. Photo → verdict → letter. Free and open source: you send the letter yourself.
struct ContentView: View {
    @State private var claim = Claim()
    @State private var path: [Step] = []

    enum Step: Hashable { case verdict(Assessment), letter(Assessment) }

    var body: some View {
        NavigationStack(path: $path) {
            IntakeView(claim: $claim) { assessment in path.append(.verdict(assessment)) }
                .navigationTitle("ParkRefund")
                .navigationDestination(for: Step.self) { step in
                    switch step {
                    case .verdict(let a): VerdictView(claim: claim, assessment: a) { path.append(.letter(a)) }
                    case .letter(let a): LetterView(claim: claim, assessment: a) { path = []; claim = Claim() }
                    }
                }
        }
    }
}

// Shared bits
struct PrimaryButton: View {
    let title: String; var busy = false; let action: () -> Void
    var body: some View {
        Button(action: action) {
            HStack { if busy { ProgressView().tint(.white) }; Text(title).bold() }
                .frame(maxWidth: .infinity).padding().background(.blue).foregroundStyle(.white).clipShape(.rect(cornerRadius: 14))
        }.disabled(busy)
    }
}

extension Color {
    static func strength(_ s: String) -> Color { s == "strong" ? .green : s == "medium" ? .orange : .red }
}

struct ErrorBanner: View {
    let message: String?
    var body: some View {
        if let message { Text(message).font(.footnote).foregroundStyle(.red).padding(.horizontal) }
    }
}
