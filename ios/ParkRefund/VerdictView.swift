import SwiftUI

struct VerdictView: View {
    let claim: Claim
    let assessment: Assessment
    let onNext: () -> Void

    var body: some View {
        List {
            Section {
                VStack(spacing: 8) {
                    Text("\(assessment.success_probability)%").font(.system(size: 64, weight: .bold))
                        .foregroundStyle(Color.strength(assessment.verdict))
                    Text(assessment.verdict.capitalized + " case").font(.title3.bold())
                    ProgressView(value: Double(assessment.success_probability), total: 100).tint(Color.strength(assessment.verdict))
                    Text(assessment.summary).font(.subheadline).multilineTextAlignment(.center).foregroundStyle(.secondary)
                }.frame(maxWidth: .infinity).padding(.vertical)
                if !assessment.recommend_filing {
                    // The honesty moment: we say no when the rulebook says no.
                    Label("We would not recommend appealing. You can still try — the letter is yours.", systemImage: "hand.raised")
                        .foregroundStyle(.red)
                }
            }
            Section("What helps you") {
                ForEach(assessment.grounds, id: \.self) { g in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack { Text(g.title).bold(); Spacer()
                            Text(g.strength).font(.caption).padding(4).background(Color.strength(g.strength).opacity(0.15)).clipShape(.capsule) }
                        Text(g.category).font(.caption).foregroundStyle(.secondary)
                        Text(g.explanation).font(.footnote)
                    }
                }
            }
            if !assessment.weaknesses.isEmpty {
                Section("What hurts you") { ForEach(assessment.weaknesses, id: \.self) { Text($0).font(.footnote) } }
            }
            Section("Evidence to raise the odds") { ForEach(assessment.evidence_to_collect, id: \.self) { Label($0, systemImage: "camera") .font(.footnote) } }
            Section("Where and when") {
                Text(assessment.route).font(.footnote)
                Text(assessment.deadline_note).font(.footnote).foregroundStyle(.secondary)
            }
            Section {
                PrimaryButton(title: assessment.recommend_filing ? "Draft my appeal" : "Draft it anyway", action: onNext)
            }
        }
        .navigationTitle("Your odds")
    }
}
