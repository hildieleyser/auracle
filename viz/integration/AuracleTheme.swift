//
//  AuracleTheme.swift
//  Brand tokens that match viz/dashboard.html and the marketing palette.
//
//  Drop this into the iOS target. Replace the hard-coded colors / fonts in
//  NoseFilterApp.swift with these tokens to bring the SwiftUI screens in line
//  with the dashboard and the marketing material.
//
//  Usage:
//      Text("AURACLE")
//          .font(Auracle.Font.wordmark(36))
//          .foregroundColor(Auracle.Color.ink)
//
//      VStack { ... }
//          .background(Auracle.Color.bg0)
//

import SwiftUI

enum Auracle {

    // MARK: - Color tokens (mirror :root vars in dashboard.html)
    enum Color {
        static let bg0    = SwiftUI.Color(red: 239/255, green: 237/255, blue: 232/255)  // page — soft cool cream
        static let bg1    = SwiftUI.Color(red: 245/255, green: 243/255, blue: 238/255)  // lifted card
        static let bg2    = SwiftUI.Color(red: 230/255, green: 227/255, blue: 220/255)  // sunken
        static let line   = SwiftUI.Color(red: 213/255, green: 210/255, blue: 201/255)  // hairline
        static let ink    = SwiftUI.Color(red:  15/255, green:  15/255, blue:  15/255)  // primary near-black
        static let ink1   = SwiftUI.Color(red:  58/255, green:  58/255, blue:  58/255)  // secondary
        static let ink2   = SwiftUI.Color(red: 138/255, green: 135/255, blue: 128/255)  // muted
        static let cream  = SwiftUI.Color.white                                          // highlight
        static let accent = SwiftUI.Color(red:  15/255, green:  15/255, blue:  15/255)  // near-black
        static let warm   = SwiftUI.Color(red: 168/255, green: 109/255, blue:  80/255)  // terracotta
        static let hot    = SwiftUI.Color(red: 156/255, green:  51/255, blue:  68/255)  // brick
        static let cool   = SwiftUI.Color(red:  90/255, green: 106/255, blue: 130/255)  // muted slate
        static let violet = SwiftUI.Color(red: 107/255, green:  91/255, blue: 149/255)  // dusty violet
        static let good   = SwiftUI.Color(red:  90/255, green: 120/255, blue:  72/255)  // sage
        static let warn   = warm
        static let bad    = hot

        // Status helpers
        static func stress(_ level: String) -> SwiftUI.Color {
            switch level.lowercased() {
            case "high":     return hot
            case "moderate": return warm
            default:         return good
            }
        }
        static func aqi(_ score: Int) -> SwiftUI.Color {
            switch score {
            case 8...:  return good
            case 6...7: return accent
            case 4...5: return warn
            default:    return bad
            }
        }
    }

    // MARK: - Typography
    //
    // Add Fraunces (https://fonts.google.com/specimen/Fraunces) and Inter
    // (https://rsms.me/inter/) to the app bundle and register them in
    // Info.plist under UIAppFonts. Falls back to Georgia / system if missing.
    enum Font {
        static let serifName = "Fraunces"
        static let sansName  = "Inter"

        static func wordmark(_ size: CGFloat) -> SwiftUI.Font {
            .custom(serifName, size: size).weight(.regular)
        }
        static func title(_ size: CGFloat = 17) -> SwiftUI.Font {
            .custom(serifName, size: size).weight(.medium)
        }
        static func tagline(_ size: CGFloat = 12) -> SwiftUI.Font {
            .custom(sansName, size: size).italic()
        }
        static func body(_ size: CGFloat = 14) -> SwiftUI.Font {
            .custom(sansName, size: size)
        }
        static func mono(_ size: CGFloat = 12) -> SwiftUI.Font {
            .system(size: size, design: .monospaced)
        }
    }
}

// MARK: - Reusable brand pieces

struct AuracleHeader: View {
    var title: String = "Auracle"
    var tagline: String = "Know the air. Shape your aura."

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(Auracle.Font.wordmark(34))
                .tracking(-0.5)
                .foregroundColor(Auracle.Color.ink)
            Text(tagline)
                .font(Auracle.Font.body(13))
                .foregroundColor(Auracle.Color.ink1)
            Rectangle()
                .fill(Auracle.Color.line)
                .frame(height: 0.5)
                .padding(.top, 10)
        }
        .padding(.horizontal, 22)
        .padding(.vertical, 18)
    }
}

struct AuracleCard<Content: View>: View {
    let title: String
    let content: () -> Content

    init(_ title: String, @ViewBuilder content: @escaping () -> Content) {
        self.title = title
        self.content = content
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(Auracle.Font.title(15))
                .foregroundColor(Auracle.Color.ink)
            Rectangle().fill(Auracle.Color.line).frame(height: 0.6)
            content()
        }
        .padding(14)
        .background(Auracle.Color.bg1)
        .overlay(
            Rectangle().stroke(Auracle.Color.line, lineWidth: 0.6)
        )
    }
}

struct AuracleStatusPill: View {
    let label: String
    let color: SwiftUI.Color

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 7, height: 7)
            Text(label)
                .font(Auracle.Font.tagline(11))
                .foregroundColor(Auracle.Color.ink1)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(Auracle.Color.bg1)
        .overlay(Capsule().stroke(Auracle.Color.line, lineWidth: 0.6))
        .clipShape(Capsule())
    }
}
