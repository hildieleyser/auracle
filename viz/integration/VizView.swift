//
//  VizView.swift
//  Auracle / NoseFilter app
//
//  SwiftUI wrapper around WKWebView that mounts viz/dashboard.html as an
//  in-app visualization tab. Drop this file into the NoseFilterApp Xcode
//  project alongside NoseFilterApp.swift.
//
//  Two modes:
//    .bundled  — load dashboard.html from the app bundle (production)
//    .hosted   — load it from a dev HTTP server on your laptop (hackathon)
//
//  Bundled setup:
//    1. Drag viz/dashboard.html into the Xcode project (copy if needed).
//    2. Make sure it is part of the app target's "Copy Bundle Resources".
//
//  Hosted setup (faster iteration):
//    cd viz && python3 -m http.server 8000
//    Update HOST_IP below to your laptop's LAN IP.
//
//  The bridge server itself is server/ovlm_bridge_server.py at the repo root.

import SwiftUI
import WebKit

private let HOST_IP   = "192.168.1.10"
private let WS_PORT   = 8765
private let HTTP_PORT = 8000

enum VizSource {
    case bundled
    case hosted

    var url: URL? {
        switch self {
        case .bundled:
            return Bundle.main.url(forResource: "dashboard", withExtension: "html")
        case .hosted:
            let s = "http://\(HOST_IP):\(HTTP_PORT)/dashboard.html?ws=ws://\(HOST_IP):\(WS_PORT)"
            return URL(string: s)
        }
    }
}

struct VizView: View {
    var source: VizSource = .hosted

    var body: some View {
        ZStack {
            // Auracle warm-sand background while WKWebView loads
            Color(red: 239/255, green: 237/255, blue: 232/255).ignoresSafeArea()
            if let url = source.url {
                VizWebView(url: url)
                    .ignoresSafeArea(edges: [.bottom, .horizontal])
            } else {
                VStack(spacing: 8) {
                    Text("dashboard.html not found")
                        .foregroundColor(Color(red: 156/255, green: 51/255, blue: 68/255))
                    Text("Add viz/dashboard.html to the app bundle, or switch to .hosted")
                        .font(.caption)
                        .foregroundColor(Color(red: 138/255, green: 135/255, blue: 128/255))
                }
            }
        }
    }
}

struct VizWebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let cfg = WKWebViewConfiguration()
        cfg.allowsInlineMediaPlayback = true
        cfg.mediaTypesRequiringUserActionForPlayback = []
        // future: register a script handler so the dashboard can post messages
        // back into the SwiftUI app (e.g. high-stress alerts) via
        //    window.webkit.messageHandlers.viz.postMessage({...})
        let userContent = WKUserContentController()
        userContent.add(context.coordinator, name: "viz")
        cfg.userContentController = userContent

        let wv = WKWebView(frame: .zero, configuration: cfg)
        wv.isOpaque = false
        wv.backgroundColor = UIColor(red: 239/255, green: 237/255, blue: 232/255, alpha: 1)
        wv.scrollView.backgroundColor = .clear
        wv.scrollView.bounces = false
        if url.isFileURL {
            wv.loadFileURL(url, allowingReadAccessTo: url.deletingLastPathComponent())
        } else {
            wv.load(URLRequest(url: url))
        }
        return wv
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {}

    func makeCoordinator() -> Coordinator { Coordinator() }

    final class Coordinator: NSObject, WKScriptMessageHandler {
        func userContentController(_ uc: WKUserContentController,
                                    didReceive message: WKScriptMessage) {
            guard message.name == "viz" else { return }
            // Hook for future bidirectional events (e.g. stress alerts)
            print("[viz]", message.body)
        }
    }
}

// MARK: - How to wire this into ContentView's TabView
//
// Inside NoseFilterApp.swift's ContentView, wrap the existing body in a
// TabView and add a Visualize tab:
//
//     TabView {
//         existingScrollView
//             .tabItem { Label("Live", systemImage: "waveform") }
//         VizView(source: .hosted)
//             .tabItem { Label("Visualize", systemImage: "chart.xyaxis.line") }
//     }

#Preview {
    VizView(source: .hosted)
}
