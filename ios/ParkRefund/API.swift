import Foundation

// Talks to api.py. Simulator reaches the Mac at localhost; a device needs the Mac's LAN IP.
enum API {
    static var base = URL(string: UserDefaults.standard.string(forKey: "apiBase") ?? "http://localhost:8000")!

    struct ServerError: LocalizedError { let message: String; var errorDescription: String? { message } }

    private static func send<T: Decodable>(_ path: String, body: Encodable? = nil) async throws -> T {
        var req = URLRequest(url: URL(string: path, relativeTo: base)!)
        if let body {
            req.httpMethod = "POST"
            req.httpBody = try JSONEncoder().encode(AnyEncodable(body))
        }
        let (data, resp) = try await URLSession.shared.data(for: req)
        if let http = resp as? HTTPURLResponse, http.statusCode >= 400 {
            let msg = (try? JSONDecoder().decode([String: String].self, from: data))?["error"]
            throw ServerError(message: msg ?? "Server error \(http.statusCode)")
        }
        return try JSONDecoder().decode(T.self, from: data)
    }

    static func cases() async throws -> [Claim] { try await send("cases") }
    static func assess(_ c: Claim) async throws -> Assessment { try await send("assess", body: c) }
    static func draft(_ c: Claim, _ a: Assessment, lang: String) async throws -> String {
        struct Req: Encodable { let claim: Claim; let assessment: Assessment; let language: String }
        struct Res: Decodable { let letter: String }
        let r: Res = try await send("draft", body: Req(claim: c, assessment: a, language: lang))
        return r.letter
    }
    static func extract(_ image: Data, mediaType: String) async throws -> TicketFields {
        struct Req: Encodable { let image_base64: String; let media_type: String }
        return try await send("extract", body: Req(image_base64: image.base64EncodedString(), media_type: mediaType))
    }
}

private struct AnyEncodable: Encodable {
    let value: Encodable
    init(_ value: Encodable) { self.value = value }
    func encode(to encoder: Encoder) throws { try value.encode(to: encoder) }
}
