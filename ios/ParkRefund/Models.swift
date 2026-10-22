import Foundation

// Mirrors the claims.py contract in CONCEPT.md. Field names match the JSON 1:1.
struct Claim: Codable, Hashable {
    var label: String? = nil
    var issuer_type: String = "private"      // "public" | "private"
    var issuer_name: String = ""
    var ticket_number: String = ""
    var plate: String = ""
    var date: String = ""                    // YYYY-MM-DD
    var time: String = ""                    // HH:MM
    var location: String = ""
    var amount_dkk: Int? = nil
    var reason_on_ticket: String = ""
    var driver_story: String = ""
    var evidence: [String] = []
}

struct Ground: Codable, Hashable {
    var title: String
    var category: String
    var strength: String                     // strong | medium | weak
    var explanation: String
}

struct Assessment: Codable, Hashable {
    var success_probability: Int
    var verdict: String                      // strong | medium | weak
    var summary: String
    var grounds: [Ground]
    var weaknesses: [String]
    var evidence_to_collect: [String]
    var route: String
    var deadline_note: String
    var recommend_filing: Bool
}

// Fields from /extract are all optional: the model leaves unreadable ones out.
struct TicketFields: Codable {
    var issuer_type, issuer_name, ticket_number, plate, date, time, location, reason_on_ticket: String?
    var amount_dkk: Int?
}

let evidenceOptions = [
    "Photos of the signage", "Photo of where the car was parked", "Payment receipt (app or machine)",
    "Permit / guest card", "Witness statement", "Roadside assistance / hospital note", "The ticket",
]
