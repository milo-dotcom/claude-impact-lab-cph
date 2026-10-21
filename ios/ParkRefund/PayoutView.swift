import SwiftUI

struct PayoutView: View {
    let claim: Claim
    let assessment: Assessment
    let onDone: () -> Void
    @State private var payout: Payout?

    var body: some View {
        VStack(spacing: 20) {
            Image(systemName: "checkmark.seal.fill").font(.system(size: 56)).foregroundStyle(.green)
            Text("Sent for review").font(.title.bold())
            Text("A case handler checks it and files the appeal. You hear from us when the operator answers.")
                .multilineTextAlignment(.center).foregroundStyle(.secondary).padding(.horizontal)
            if let p = payout {
                VStack(spacing: 6) {
                    row("Fine refunded", p.refund)
                    row("Our fee (30%, only if you win)", -p.fee)
                    Divider()
                    row("You get back", p.you_get).bold()
                }.padding().background(.quaternary.opacity(0.4)).clipShape(.rect(cornerRadius: 14)).padding(.horizontal)
            }
            Spacer()
            PrimaryButton(title: "New ticket", action: onDone).padding(.horizontal)
        }
        .padding(.top, 40)
        .navigationTitle("What you get")
        .task { payout = try? await API.payout(claim.amount_dkk ?? 0) }
    }

    private func row(_ label: String, _ dkk: Int) -> some View {
        HStack { Text(label); Spacer(); Text("\(dkk) DKK") }
    }
}
